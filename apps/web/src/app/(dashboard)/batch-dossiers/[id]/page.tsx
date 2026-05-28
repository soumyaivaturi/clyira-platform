"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft, FlaskConical, CheckCircle2, AlertCircle, XCircle,
  Clock, AlertTriangle, FileText, Plus, RefreshCw, ChevronDown,
  ChevronRight, Loader2, Shield, Info,
} from "lucide-react";
import { batchDossiersApi, documentsApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Gate { evidence_complete: boolean; data_integrity_ok: boolean; all_findings_addressed: boolean; gray_findings_resolved: boolean; }
interface Finding {
  id: string; level: string; severity: string; title: string; description: string;
  verification_state?: string; field_criticality?: string; source_page?: number;
  human_verification_required?: boolean; status: string; confidence_score?: number;
  regulatory_citation?: string; suggestion_draft?: string; document_id?: string; document_role?: string;
}
interface DossierDoc {
  id: string; document_id: string; document_title?: string; document_category?: string;
  role: string; notes?: string; assessment?: {
    id: string; clyira_score?: number; score_band?: string;
    findings_critical: number; findings_high: number; findings_medium: number;
    findings_low: number; completed_at?: string;
  };
  findings?: Finding[];
}
interface Dossier {
  id: string; lot_number: string; product_name: string; dosage_form?: string;
  record_family: string; product_type: string; is_sterile: boolean; batch_purpose: string;
  manufacturing_date?: string; target_release_date?: string; target_markets: string[];
  status: string; readiness_status?: string; readiness_score?: number; readiness_band?: string;
  disposition_decision?: string; disposition_rationale?: string; disposition_divergence?: boolean;
  gates: Gate; shadow_mode: boolean; documents: DossierDoc[];
  readiness_detail?: { complete: boolean; missing_required_labels?: string[]; missing_conditional?: Record<string, string>; summary: string; };
}
interface DocOption { id: string; title: string; document_category: string; }

// ── Helpers ───────────────────────────────────────────────────────────────────

const SEVERITY_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-700 border-red-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  low: "bg-blue-100 text-blue-700 border-blue-200",
  info: "bg-gray-100 text-gray-600 border-gray-200",
};

const VSTATE_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  green: { label: "Verified Pass",  color: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  red:   { label: "Verified Fail",  color: "bg-red-50 text-red-700 border-red-200",             dot: "bg-red-500" },
  blue:  { label: "AI-Assisted",    color: "bg-blue-50 text-blue-700 border-blue-200",           dot: "bg-blue-500" },
  gray:  { label: "Unverified",     color: "bg-gray-100 text-gray-600 border-gray-200",          dot: "bg-gray-400" },
};

const READINESS_CONFIG: Record<string, { label: string; bg: string; text: string }> = {
  ready:       { label: "Ready for QA Disposition Review", bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-800" },
  conditional: { label: "Conditional Readiness",           bg: "bg-amber-50 border-amber-200",     text: "text-amber-800" },
  not_ready:   { label: "Not Ready",                       bg: "bg-red-50 border-red-200",         text: "text-red-800" },
  hold:        { label: "Hold for QA Evaluation",          bg: "bg-red-100 border-red-300",        text: "text-red-900" },
};

const ROLE_LABELS: Record<string, string> = {
  primary_bpr: "Primary BPR", deviation: "Deviation", capa: "CAPA",
  qc_result: "QC Results", coa: "COA", environmental_monitoring: "Env. Monitoring",
  equipment_log: "Equipment Log", sterilization_record: "Sterilization",
  filter_integrity: "Filter Integrity", packaging_record: "Packaging",
  labeling_record: "Labeling", other: "Other",
};

function GatePill({ pass, label }: { pass: boolean; label: string }) {
  return (
    <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border ${pass ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"}`}>
      {pass ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {label}
    </div>
  );
}

function ScoreBadge({ score, band }: { score?: number; band?: string }) {
  if (score == null) return <span className="text-xs text-muted-foreground">—</span>;
  const color = score >= 85 ? "text-emerald-700" : score >= 70 ? "text-amber-700" : "text-red-700";
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${color}`}>{score.toFixed(1)}</div>
      {band && <div className="text-[10px] text-muted-foreground">{band}</div>}
    </div>
  );
}

// ── Finding Card ─────────────────────────────────────────────────────────────

function FindingCard({ f }: { f: Finding }) {
  const [expanded, setExpanded] = useState(false);
  const vState = f.verification_state ? VSTATE_CONFIG[f.verification_state] : null;
  const sevColor = SEVERITY_COLOR[f.severity] ?? SEVERITY_COLOR.info;

  return (
    <div className={`border rounded-lg overflow-hidden ${vState ? `border-l-4` : ""}`}
      style={vState ? { borderLeftColor: vState.dot === "bg-emerald-500" ? "#10b981" : vState.dot === "bg-red-500" ? "#ef4444" : vState.dot === "bg-blue-500" ? "#3b82f6" : "#9ca3af" } : {}}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-3 py-2.5 flex items-start gap-2 hover:bg-muted/20 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${sevColor}`}>
              {f.severity.toUpperCase()}
            </span>
            <span className="text-[10px] text-muted-foreground">{f.level}</span>
            {vState && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border flex items-center gap-1 ${vState.color}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${vState.dot}`} />
                {vState.label}
              </span>
            )}
            {f.human_verification_required && (
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">
                Human verification required
              </span>
            )}
          </div>
          <div className="text-sm font-medium mt-0.5 truncate">{f.title}</div>
        </div>
        {expanded ? <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" /> : <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />}
      </button>
      {expanded && (
        <div className="px-3 pb-3 text-sm text-muted-foreground border-t bg-muted/10">
          <p className="mt-2">{f.description}</p>
          {f.regulatory_citation && (
            <p className="mt-1.5 text-xs"><span className="font-medium text-foreground">Regulatory basis:</span> {f.regulatory_citation}</p>
          )}
          {f.suggestion_draft && (
            <div className="mt-2 p-2 bg-background rounded border text-xs">
              <span className="font-medium text-foreground">Suggested action: </span>{f.suggestion_draft}
            </div>
          )}
          {f.source_page && (
            <p className="mt-1.5 text-xs text-muted-foreground">Source: Page {f.source_page}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Document Card ─────────────────────────────────────────────────────────────

function DocCard({ dd }: { dd: DossierDoc }) {
  const [expanded, setExpanded] = useState(false);
  const findings = dd.findings ?? [];
  const byState = {
    red: findings.filter(f => f.verification_state === "red").length,
    blue: findings.filter(f => f.verification_state === "blue").length,
    gray: findings.filter(f => f.verification_state === "gray").length,
    green: findings.filter(f => f.verification_state === "green").length,
  };

  return (
    <div className="border rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-muted/20 transition-colors"
      >
        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium truncate">{dd.document_title ?? dd.document_id}</span>
            <span className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground">
              {ROLE_LABELS[dd.role] ?? dd.role}
            </span>
          </div>
          {dd.assessment && (
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xs text-muted-foreground">Score: {dd.assessment.clyira_score?.toFixed(1) ?? "—"}</span>
              {findings.length > 0 && (
                <div className="flex items-center gap-1.5">
                  {byState.red > 0 && <span className="text-[10px] px-1 py-0.5 bg-red-100 text-red-700 rounded">{byState.red} fail</span>}
                  {byState.blue > 0 && <span className="text-[10px] px-1 py-0.5 bg-blue-100 text-blue-700 rounded">{byState.blue} AI</span>}
                  {byState.gray > 0 && <span className="text-[10px] px-1 py-0.5 bg-gray-100 text-gray-600 rounded">{byState.gray} gray</span>}
                </div>
              )}
            </div>
          )}
          {!dd.assessment && (
            <span className="text-xs text-muted-foreground">No assessment yet</span>
          )}
        </div>
        {expanded ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
      </button>
      {expanded && findings.length > 0 && (
        <div className="px-4 pb-4 space-y-2 border-t">
          <div className="pt-3 text-xs font-semibold text-muted-foreground mb-2">{findings.length} finding{findings.length !== 1 ? "s" : ""}</div>
          {findings.map(f => <FindingCard key={f.id} f={f} />)}
        </div>
      )}
      {expanded && findings.length === 0 && dd.assessment && (
        <div className="px-4 pb-4 pt-3 border-t text-xs text-muted-foreground text-center">No findings — all checks passed</div>
      )}
    </div>
  );
}

// ── Add Document Modal ────────────────────────────────────────────────────────

function AddDocumentModal({ dossierId, onClose, onAdded }: {
  dossierId: string; onClose: () => void; onAdded: () => void;
}) {
  const [docs, setDocs] = useState<DocOption[]>([]);
  const [selectedDoc, setSelectedDoc] = useState("");
  const [role, setRole] = useState("other");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    documentsApi.list().then(r => setDocs(r.data.documents ?? r.data ?? [])).catch(() => {});
  }, []);

  const handleAdd = async () => {
    if (!selectedDoc) { setError("Select a document"); return; }
    setLoading(true);
    try {
      await batchDossiersApi.addDocument(dossierId, { document_id: selectedDoc, role, notes: notes || undefined });
      onAdded();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to add document");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 className="text-base font-semibold mb-4">Add Document to Dossier</h3>
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium block mb-1.5">Document</label>
            <select
              className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={selectedDoc} onChange={e => setSelectedDoc(e.target.value)}
            >
              <option value="">Select a document…</option>
              {docs.map(d => (
                <option key={d.id} value={d.id}>{d.title} ({d.document_category})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5">Role in dossier</label>
            <select
              className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={role} onChange={e => setRole(e.target.value)}
            >
              {Object.entries(ROLE_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5">Notes (optional)</label>
            <input
              className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={notes} onChange={e => setNotes(e.target.value)} placeholder="Context or notes for this document…"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button
            onClick={handleAdd} disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60"
          >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Add Document
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Disposition Panel ─────────────────────────────────────────────────────────

function DispositionPanel({ dossier, onDecision }: { dossier: Dossier; onDecision: () => void }) {
  const [decision, setDecision] = useState("");
  const [rationale, setRationale] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!decision) { setError("Select a disposition decision"); return; }
    if (rationale.trim().length < 20) { setError("Rationale must be at least 20 characters"); return; }
    setLoading(true);
    try {
      await batchDossiersApi.recordDisposition(dossier.id, { decision, rationale });
      onDecision();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to record disposition");
    } finally {
      setLoading(false);
    }
  };

  if (dossier.disposition_decision) {
    const colors: Record<string, string> = {
      release: "text-emerald-700 bg-emerald-50 border-emerald-200",
      conditional_release: "text-teal-700 bg-teal-50 border-teal-200",
      hold: "text-amber-700 bg-amber-50 border-amber-200",
      reject: "text-red-700 bg-red-50 border-red-200",
    };
    return (
      <div className={`p-4 rounded-xl border ${colors[dossier.disposition_decision] ?? ""}`}>
        <div className="flex items-center gap-2 font-semibold capitalize">
          <Shield className="w-4 h-4" />
          Disposition: {dossier.disposition_decision.replace("_", " ")}
        </div>
        {dossier.disposition_rationale && (
          <p className="text-sm mt-1.5">{dossier.disposition_rationale}</p>
        )}
        {dossier.disposition_divergence && (
          <div className="mt-2 text-xs flex items-center gap-1 text-amber-700">
            <AlertTriangle className="w-3.5 h-3.5" />
            Human decision diverges from AI readiness assessment — rationale logged in audit trail
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-card border rounded-xl p-5">
      <h3 className="text-sm font-semibold mb-3">QA Approver — Disposition Decision</h3>
      <p className="text-xs text-muted-foreground mb-3">
        This is a human decision. Clyira reports readiness; you decide disposition.
      </p>
      <div className="space-y-3">
        <select
          className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          value={decision} onChange={e => setDecision(e.target.value)}
        >
          <option value="">Select disposition…</option>
          <option value="release">Release — Batch approved for distribution</option>
          <option value="conditional_release">Conditional Release — Approved with documented conditions</option>
          <option value="hold">Hold — Pending investigation or additional data</option>
          <option value="reject">Reject — Fundamental quality failure</option>
        </select>
        <textarea
          className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
          rows={3} placeholder="Disposition rationale (required, min 20 characters)…"
          value={rationale} onChange={e => setRationale(e.target.value)}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          onClick={handleSubmit} disabled={loading}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 transition-colors"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          Record Disposition Decision
        </button>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DossierPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAddDoc, setShowAddDoc] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "documents" | "findings">("overview");

  const load = useCallback(async () => {
    try {
      const res = await batchDossiersApi.get(id);
      setDossier(res.data);
    } catch {
      router.push("/batch-dossiers");
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => { load(); }, [load]);

  const handleRefreshReadiness = async () => {
    if (!dossier) return;
    setRefreshing(true);
    try {
      await batchDossiersApi.assessReadiness(id);
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
  );
  if (!dossier) return null;

  const allFindings = dossier.documents.flatMap(d => d.findings ?? []);
  const findingsByState = {
    green: allFindings.filter(f => f.verification_state === "green").length,
    red: allFindings.filter(f => f.verification_state === "red").length,
    blue: allFindings.filter(f => f.verification_state === "blue").length,
    gray: allFindings.filter(f => f.verification_state === "gray").length,
  };

  const readinessCfg = dossier.readiness_status ? READINESS_CONFIG[dossier.readiness_status] : null;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {showAddDoc && (
        <AddDocumentModal
          dossierId={id}
          onClose={() => setShowAddDoc(false)}
          onAdded={() => { setShowAddDoc(false); load(); }}
        />
      )}

      {/* Header */}
      <div className="flex items-start gap-3 mb-6">
        <Link href="/batch-dossiers" className="text-muted-foreground hover:text-foreground mt-1">
          <ChevronLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-semibold">{dossier.lot_number}</h1>
            <span className="text-sm text-muted-foreground">—</span>
            <span className="text-sm text-muted-foreground">{dossier.product_name}</span>
            {dossier.is_sterile && (
              <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">Sterile</span>
            )}
            {dossier.shadow_mode && (
              <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">Shadow Mode</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {dossier.record_family.replace(/_/g, " ").toUpperCase()} · {dossier.batch_purpose.replace(/_/g, " ")}
            {dossier.manufacturing_date && ` · ${dossier.manufacturing_date}`}
          </p>
        </div>
        <button
          onClick={handleRefreshReadiness}
          disabled={refreshing}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 border rounded-lg hover:bg-accent transition-colors"
        >
          {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Recompute
        </button>
        <button
          onClick={() => setShowAddDoc(true)}
          className="flex items-center gap-1.5 bg-primary text-primary-foreground px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Document
        </button>
      </div>

      {/* Readiness banner */}
      {readinessCfg && (
        <div className={`border rounded-xl p-4 mb-5 ${readinessCfg.bg}`}>
          <div className={`flex items-center gap-2 font-semibold text-sm ${readinessCfg.text}`}>
            {dossier.readiness_status === "ready" ? <CheckCircle2 className="w-4 h-4" /> :
             dossier.readiness_status === "hold" ? <AlertTriangle className="w-4 h-4" /> :
             <AlertCircle className="w-4 h-4" />}
            {readinessCfg.label}
            {dossier.readiness_score != null && (
              <span className="font-normal text-xs ml-2">Score: {dossier.readiness_score.toFixed(1)}</span>
            )}
          </div>
          {dossier.readiness_detail?.summary && (
            <p className={`text-xs mt-1 ${readinessCfg.text} opacity-80`}>{dossier.readiness_detail.summary}</p>
          )}
        </div>
      )}

      {/* Gate pills */}
      <div className="flex flex-wrap gap-2 mb-5">
        <GatePill pass={dossier.gates.evidence_complete} label="Evidence package" />
        <GatePill pass={dossier.gates.data_integrity_ok} label="Data integrity" />
        <GatePill pass={dossier.gates.all_findings_addressed} label="All findings addressed" />
        <GatePill pass={dossier.gates.gray_findings_resolved} label="Gray findings resolved" />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Main content — 2/3 */}
        <div className="lg:col-span-2 space-y-5">

          {/* Tabs */}
          <div className="flex border-b">
            {(["overview", "documents", "findings"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
                  activeTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab}
                {tab === "findings" && allFindings.length > 0 && (
                  <span className="ml-1.5 text-xs px-1.5 py-0.5 bg-muted rounded-full">{allFindings.length}</span>
                )}
              </button>
            ))}
          </div>

          {/* Overview tab */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              {/* Evidence completeness */}
              {dossier.readiness_detail && (
                <div className="bg-card border rounded-xl p-4">
                  <h3 className="text-sm font-semibold mb-3">Evidence Package</h3>
                  {dossier.readiness_detail.missing_required_labels && dossier.readiness_detail.missing_required_labels.length > 0 ? (
                    <div className="space-y-1">
                      {dossier.readiness_detail.missing_required_labels.map(label => (
                        <div key={label} className="flex items-center gap-2 text-sm text-red-700">
                          <XCircle className="w-4 h-4 flex-shrink-0" /> {label} <span className="text-xs text-red-500">Missing required</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-emerald-700">
                      <CheckCircle2 className="w-4 h-4" /> Required documents present
                    </div>
                  )}
                  {dossier.readiness_detail.missing_conditional && Object.keys(dossier.readiness_detail.missing_conditional).length > 0 && (
                    <div className="mt-2 space-y-1">
                      {Object.entries(dossier.readiness_detail.missing_conditional).map(([role, reason]) => (
                        <div key={role} className="flex items-center gap-2 text-sm text-amber-700">
                          <Info className="w-4 h-4 flex-shrink-0" /> {ROLE_LABELS[role] ?? role} — {reason}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Finding summary by state */}
              {allFindings.length > 0 && (
                <div className="bg-card border rounded-xl p-4">
                  <h3 className="text-sm font-semibold mb-3">Finding Summary</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {([
                      { state: "green", label: "Verified Pass",  color: "text-emerald-700" },
                      { state: "red",   label: "Verified Fail",  color: "text-red-700" },
                      { state: "blue",  label: "AI-Assisted",    color: "text-blue-700" },
                      { state: "gray",  label: "Unverified",     color: "text-gray-600" },
                    ] as const).map(({ state, label, color }) => (
                      <div key={state} className="text-center p-2 bg-muted/30 rounded-lg">
                        <div className={`text-xl font-bold ${color}`}>{findingsByState[state]}</div>
                        <div className="text-[10px] text-muted-foreground">{label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Documents summary */}
              <div className="bg-card border rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold">Documents ({dossier.documents.length})</h3>
                  <button onClick={() => setShowAddDoc(true)} className="text-xs text-primary hover:underline flex items-center gap-1">
                    <Plus className="w-3 h-3" /> Add
                  </button>
                </div>
                {dossier.documents.length === 0 ? (
                  <div className="text-center py-6 text-sm text-muted-foreground">
                    No documents added yet.{" "}
                    <button onClick={() => setShowAddDoc(true)} className="text-primary hover:underline">Add the primary batch record</button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {dossier.documents.map(dd => (
                      <div key={dd.id} className="flex items-center gap-3 text-sm">
                        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className="font-medium truncate">{dd.document_title ?? dd.document_id}</span>
                          <span className="ml-2 text-xs text-muted-foreground">({ROLE_LABELS[dd.role] ?? dd.role})</span>
                        </div>
                        {dd.assessment?.clyira_score != null && (
                          <span className="text-xs text-muted-foreground">{dd.assessment.clyira_score.toFixed(1)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Documents tab */}
          {activeTab === "documents" && (
            <div className="space-y-3">
              {dossier.documents.length === 0 ? (
                <div className="text-center py-12 bg-card border rounded-xl text-sm text-muted-foreground">
                  <FileText className="w-8 h-8 mx-auto mb-2 text-muted-foreground/30" />
                  No documents yet.{" "}
                  <button onClick={() => setShowAddDoc(true)} className="text-primary hover:underline">Add the primary batch record</button>
                </div>
              ) : (
                dossier.documents.map(dd => <DocCard key={dd.id} dd={dd} />)
              )}
            </div>
          )}

          {/* Findings tab */}
          {activeTab === "findings" && (
            <div className="space-y-2">
              {allFindings.length === 0 ? (
                <div className="text-center py-12 bg-card border rounded-xl text-sm text-muted-foreground">
                  No findings yet — add documents and run assessments first.
                </div>
              ) : (
                <>
                  <div className="text-xs text-muted-foreground mb-2">{allFindings.length} total finding{allFindings.length !== 1 ? "s" : ""} across all documents</div>
                  {allFindings
                    .sort((a, b) => {
                      const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
                      return (order[a.severity as keyof typeof order] ?? 5) - (order[b.severity as keyof typeof order] ?? 5);
                    })
                    .map(f => <FindingCard key={f.id} f={f} />)
                  }
                </>
              )}
            </div>
          )}
        </div>

        {/* Sidebar — 1/3 */}
        <div className="space-y-4">
          {/* Score */}
          {dossier.documents.some(d => d.assessment?.clyira_score != null) && (
            <div className="bg-card border rounded-xl p-4 text-center">
              <div className="text-xs text-muted-foreground mb-2">Composite Readiness Score</div>
              <ScoreBadge score={dossier.readiness_score ?? undefined} band={dossier.readiness_band ?? undefined} />
            </div>
          )}

          {/* Disposition */}
          <DispositionPanel dossier={dossier} onDecision={load} />

          {/* Dossier metadata */}
          <div className="bg-card border rounded-xl p-4 text-xs space-y-2 text-muted-foreground">
            <div className="font-semibold text-foreground text-sm mb-1">Classification</div>
            <div className="flex justify-between"><span>Record family</span><span className="capitalize">{dossier.record_family.replace(/_/g, " ")}</span></div>
            <div className="flex justify-between"><span>Product type</span><span className="capitalize">{dossier.product_type.replace(/_/g, " ")}</span></div>
            <div className="flex justify-between"><span>Sterile</span><span>{dossier.is_sterile ? "Yes" : "No"}</span></div>
            <div className="flex justify-between"><span>Context</span><span className="capitalize">{dossier.manufacturing_context.replace(/_/g, " ")}</span></div>
            <div className="flex justify-between"><span>Purpose</span><span className="capitalize">{dossier.batch_purpose.replace(/_/g, " ")}</span></div>
            {dossier.target_markets.length > 0 && (
              <div className="flex justify-between"><span>Markets</span><span>{dossier.target_markets.join(", ")}</span></div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

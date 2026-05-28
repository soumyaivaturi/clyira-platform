"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft, CheckCircle2, AlertCircle, XCircle, AlertTriangle,
  FileText, Plus, RefreshCw, Loader2, Shield, RotateCcw, Download,
  X, MessageSquare, Check, Flag, ChevronDown, ChevronRight,
} from "lucide-react";
import { batchDossiersApi, documentsApi } from "@/lib/api";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Gate {
  evidence_complete: boolean; data_integrity_ok: boolean;
  all_findings_addressed: boolean; gray_findings_resolved: boolean;
}
interface Finding {
  id: string; level: string; severity: string; title: string; description: string;
  verification_state?: string; source_page?: number; status: string;
  confidence_score?: number; regulatory_citation?: string; suggestion_draft?: string;
  document_id?: string; document_role?: string; human_verification_required?: boolean;
}
interface DossierDoc {
  id: string; document_id: string; document_title?: string; document_category?: string;
  role: string; notes?: string;
  assessment?: { id: string; clyira_score?: number; score_band?: string; };
  findings?: Finding[];
}
interface Dossier {
  id: string; lot_number: string; product_name: string; product_code?: string;
  dosage_form?: string; batch_size?: string; manufacturing_site?: string;
  manufacturing_date?: string; target_release_date?: string;
  record_family: string; product_type: string; is_sterile: boolean;
  batch_purpose: string; manufacturing_context?: string; target_markets: string[];
  status: string; readiness_status?: string; readiness_score?: number;
  readiness_band?: string; disposition_decision?: string; disposition_rationale?: string;
  disposition_divergence?: boolean; gates: Gate; shadow_mode: boolean;
  documents: DossierDoc[];
  readiness_detail?: { complete: boolean; missing_required_labels?: string[]; summary: string; };
}
interface DocOption { id: string; title: string; document_category: string; }

type ReviewState = "pending" | "pass" | "fail";

const HEADER_FIELDS: { key: keyof Dossier; label: string; critical: boolean }[] = [
  { key: "lot_number",          label: "Lot / Batch Number",    critical: true },
  { key: "product_name",        label: "Product Name",          critical: true },
  { key: "product_code",        label: "Product Code",          critical: false },
  { key: "dosage_form",         label: "Dosage Form",           critical: false },
  { key: "batch_size",          label: "Batch Size",            critical: true },
  { key: "manufacturing_site",  label: "Manufacturing Site",    critical: true },
  { key: "manufacturing_date",  label: "Manufacturing Date",    critical: true },
  { key: "target_release_date", label: "Target Release Date",   critical: false },
];

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500", high: "bg-orange-500",
  medium: "bg-amber-400", low: "bg-blue-400", info: "bg-gray-400",
};
const SEVERITY_LABEL: Record<string, string> = {
  critical: "text-red-700 bg-red-50 border-red-200",
  high: "text-orange-700 bg-orange-50 border-orange-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low: "text-blue-700 bg-blue-50 border-blue-200",
  info: "text-gray-600 bg-gray-100 border-gray-200",
};
const ROLE_LABELS: Record<string, string> = {
  primary_bpr: "Primary BPR", deviation: "Deviation", capa: "CAPA",
  qc_result: "QC Results", coa: "COA", environmental_monitoring: "Env. Monitoring",
  equipment_log: "Equipment Log", sterilization_record: "Sterilization",
  filter_integrity: "Filter Integrity", packaging_record: "Packaging",
  labeling_record: "Labeling", other: "Other",
};
const READINESS_CFG: Record<string, { label: string; bg: string; text: string; icon: React.ReactNode }> = {
  ready:       { label: "Ready for QA Disposition", bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-700", icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
  conditional: { label: "Conditional Readiness",    bg: "bg-amber-50 border-amber-200",     text: "text-amber-700",   icon: <AlertCircle className="w-3.5 h-3.5" /> },
  not_ready:   { label: "Not Ready",                bg: "bg-red-50 border-red-200",         text: "text-red-700",     icon: <XCircle className="w-3.5 h-3.5" /> },
  hold:        { label: "Hold — QA Evaluation",     bg: "bg-red-100 border-red-300",        text: "text-red-900",     icon: <AlertTriangle className="w-3.5 h-3.5" /> },
};

// ── Review Item — header field ────────────────────────────────────────────────

function FieldReviewItem({
  label, value, critical,
  state, onPass, onFail, comment, onComment,
}: {
  label: string; value: string | null | undefined; critical: boolean;
  state: ReviewState; onPass: () => void; onFail: () => void;
  comment: string; onComment: (v: string) => void;
}) {
  const [showComment, setShowComment] = useState(false);

  const bgColor = state === "pass" ? "bg-emerald-50 border-emerald-200"
    : state === "fail" ? "bg-red-50 border-red-200"
    : "bg-white border-gray-200";
  const stateLabel = state === "pass" ? "Verified Pass"
    : state === "fail" ? "Verified Fail"
    : "Need Review";
  const stateDot = state === "pass" ? "bg-emerald-500"
    : state === "fail" ? "bg-red-500"
    : "bg-amber-400";

  return (
    <div className={`rounded-lg border px-3 py-2.5 ${bgColor} transition-colors`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
            {critical && <span className="text-[9px] px-1 py-0.5 bg-primary/10 text-primary rounded">Required</span>}
          </div>
          <div className="text-sm font-medium text-foreground truncate">
            {value || <span className="text-muted-foreground italic">Not extracted</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <div className="flex items-center gap-1 mr-1">
            <span className={`w-1.5 h-1.5 rounded-full ${stateDot}`} />
            <span className="text-[10px] text-muted-foreground">{stateLabel}</span>
          </div>
          <button
            onClick={onPass}
            title="Verify Pass"
            className={`p-1 rounded transition-colors ${state === "pass" ? "bg-emerald-500 text-white" : "hover:bg-emerald-100 text-muted-foreground hover:text-emerald-700 border border-transparent hover:border-emerald-200"}`}
          >
            <Check className="w-3 h-3" />
          </button>
          <button
            onClick={() => { onFail(); setShowComment(true); }}
            title="Flag Issue"
            className={`p-1 rounded transition-colors ${state === "fail" ? "bg-red-500 text-white" : "hover:bg-red-100 text-muted-foreground hover:text-red-700 border border-transparent hover:border-red-200"}`}
          >
            <Flag className="w-3 h-3" />
          </button>
          <button
            onClick={() => setShowComment(!showComment)}
            title="Add comment"
            className={`p-1 rounded transition-colors ${comment ? "text-blue-600" : "text-muted-foreground hover:text-foreground"} border border-transparent hover:border-gray-200`}
          >
            <MessageSquare className="w-3 h-3" />
          </button>
        </div>
      </div>
      {showComment && (
        <textarea
          className="mt-2 w-full px-2 py-1.5 text-xs border rounded bg-white focus:outline-none focus:ring-1 focus:ring-primary/30 resize-none"
          rows={2}
          placeholder="Add review comment…"
          value={comment}
          onChange={e => onComment(e.target.value)}
        />
      )}
    </div>
  );
}

// ── Review Item — finding ─────────────────────────────────────────────────────

function FindingReviewItem({
  finding, dossierId, onStateChange,
}: {
  finding: Finding; dossierId: string; onStateChange: (id: string, state: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  const vs = finding.verification_state ?? "gray";
  const bgColor = vs === "green" ? "bg-emerald-50 border-emerald-200 border-l-emerald-500"
    : vs === "red" ? "bg-red-50 border-red-200 border-l-red-500"
    : vs === "blue" ? "bg-blue-50 border-blue-200 border-l-blue-500"
    : "bg-white border-gray-200 border-l-amber-400";
  const vsLabel = vs === "green" ? "Verified Pass"
    : vs === "red" ? "Verified Fail"
    : vs === "blue" ? "AI-Assisted"
    : "Need Review";

  const handleVerify = async (newState: string) => {
    setSaving(true);
    try {
      await batchDossiersApi.reviewFinding(dossierId, finding.id, newState);
      onStateChange(finding.id, newState);
    } catch {
      // ignore — UI already optimistic
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`rounded-lg border border-l-4 ${bgColor} transition-colors`}>
      <div className="px-3 py-2">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${SEVERITY_LABEL[finding.severity] ?? SEVERITY_LABEL.info}`}>
                {finding.severity.toUpperCase()}
              </span>
              <span className="text-[10px] text-muted-foreground">{finding.level}</span>
              <span className="text-[10px] text-muted-foreground">· {vsLabel}</span>
              {finding.source_page && (
                <span className="text-[10px] text-muted-foreground">· p.{finding.source_page}</span>
              )}
            </div>
            <div className="text-xs font-medium text-foreground leading-snug">{finding.title}</div>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {saving ? (
              <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
            ) : (
              <>
                <button
                  onClick={() => handleVerify("green")}
                  title="Verify Pass"
                  className={`p-1 rounded transition-colors ${vs === "green" ? "bg-emerald-500 text-white" : "hover:bg-emerald-100 text-muted-foreground hover:text-emerald-700 border border-transparent hover:border-emerald-200"}`}
                >
                  <Check className="w-3 h-3" />
                </button>
                <button
                  onClick={() => handleVerify("red")}
                  title="Verify Fail"
                  className={`p-1 rounded transition-colors ${vs === "red" ? "bg-red-500 text-white" : "hover:bg-red-100 text-muted-foreground hover:text-red-700 border border-transparent hover:border-red-200"}`}
                >
                  <Flag className="w-3 h-3" />
                </button>
              </>
            )}
            <button onClick={() => setExpanded(!expanded)} className="p-1 text-muted-foreground hover:text-foreground rounded">
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
          </div>
        </div>
        {expanded && (
          <div className="mt-2 pt-2 border-t text-[11px] text-muted-foreground space-y-1">
            <p>{finding.description}</p>
            {finding.regulatory_citation && (
              <p><span className="font-medium text-foreground">Regulatory basis:</span> {finding.regulatory_citation}</p>
            )}
            {finding.suggestion_draft && (
              <div className="mt-1 p-2 bg-white rounded border text-[11px]">
                <span className="font-medium text-foreground">Suggested action: </span>{finding.suggestion_draft}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Add Document Modal ────────────────────────────────────────────────────────

function AddDocumentModal({ dossierId, onClose, onAdded }: {
  dossierId: string; onClose: () => void; onAdded: () => void;
}) {
  const [docs, setDocs] = useState<DocOption[]>([]);
  const [selectedDoc, setSelectedDoc] = useState("");
  const [role, setRole] = useState("primary_bpr");
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
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to add document");
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold">Add Document to Dossier</h3>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-accent text-muted-foreground"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium block mb-1.5">Document</label>
            <select className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={selectedDoc} onChange={e => setSelectedDoc(e.target.value)}>
              <option value="">Select a document…</option>
              {docs.map(d => <option key={d.id} value={d.id}>{d.title} ({d.document_category})</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5">Role in dossier</label>
            <select className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={role} onChange={e => setRole(e.target.value)}>
              {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5">Notes (optional)</label>
            <input className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={notes} onChange={e => setNotes(e.target.value)} placeholder="Context or notes…" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button onClick={handleAdd} disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
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
  const [reopenReason, setReopenReason] = useState("");
  const [reopening, setReopening] = useState(false);
  const [showReopen, setShowReopen] = useState(false);

  const handleSubmit = async () => {
    if (!decision) { setError("Select a disposition decision"); return; }
    if (rationale.trim().length < 20) { setError("Rationale must be at least 20 characters"); return; }
    setLoading(true);
    setError("");
    try {
      await batchDossiersApi.recordDisposition(dossier.id, { decision, rationale });
      onDecision();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to record disposition");
    } finally { setLoading(false); }
  };

  const handleReopen = async () => {
    if (reopenReason.trim().length < 100) { setError(`Minimum 100 chars (§22.5) — ${reopenReason.trim().length}/100`); return; }
    setReopening(true);
    try {
      await batchDossiersApi.reopen(dossier.id, reopenReason.trim());
      onDecision();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to reopen");
    } finally { setReopening(false); }
  };

  if (dossier.disposition_decision) {
    const colors: Record<string, string> = {
      release: "bg-emerald-50 border-emerald-200 text-emerald-800",
      conditional_release: "bg-teal-50 border-teal-200 text-teal-800",
      hold: "bg-amber-50 border-amber-200 text-amber-800",
      reject: "bg-red-50 border-red-200 text-red-800",
    };
    return (
      <div className={`rounded-lg border p-3 ${colors[dossier.disposition_decision] ?? ""}`}>
        <div className="flex items-center gap-1.5 font-semibold text-sm capitalize">
          <Shield className="w-3.5 h-3.5" />
          {dossier.disposition_decision.replace("_", " ")}
        </div>
        {dossier.disposition_rationale && <p className="text-xs mt-1 opacity-80">{dossier.disposition_rationale}</p>}
        {dossier.disposition_divergence && (
          <div className="mt-1.5 text-[10px] flex items-center gap-1 text-amber-700">
            <AlertTriangle className="w-3 h-3" /> Human decision diverges from AI readiness — logged
          </div>
        )}
        {!showReopen ? (
          <button onClick={() => setShowReopen(true)} className="mt-2 text-xs flex items-center gap-1 hover:underline">
            <RotateCcw className="w-3 h-3" /> Reopen
          </button>
        ) : (
          <div className="mt-2 space-y-1.5">
            <textarea rows={3} className="w-full px-2 py-1.5 border rounded text-xs bg-white resize-none focus:outline-none"
              placeholder="Reopen reason — min 100 chars (§22.5)…"
              value={reopenReason} onChange={e => setReopenReason(e.target.value)} />
            <div className={`text-[10px] ${reopenReason.trim().length >= 100 ? "text-emerald-600" : "text-muted-foreground"}`}>
              {reopenReason.trim().length}/100
            </div>
            {error && <p className="text-[10px] text-destructive">{error}</p>}
            <div className="flex gap-1.5">
              <button onClick={() => { setShowReopen(false); setError(""); }} className="flex-1 py-1 border rounded text-xs hover:bg-white/60">Cancel</button>
              <button onClick={handleReopen} disabled={reopening || reopenReason.trim().length < 100}
                className="flex-1 flex items-center justify-center gap-1 py-1 bg-amber-600 text-white rounded text-xs disabled:opacity-60">
                {reopening && <Loader2 className="w-3 h-3 animate-spin" />} Reopen
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">This is a human decision. Clyira reports readiness; you decide disposition.</p>
      <select className="w-full px-2.5 py-2 border rounded-lg text-xs bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
        value={decision} onChange={e => setDecision(e.target.value)}>
        <option value="">Select disposition…</option>
        <option value="release">Release — Approved for distribution</option>
        <option value="conditional_release">Conditional Release — With documented conditions</option>
        <option value="hold">Hold — Pending investigation</option>
        <option value="reject">Reject — Quality failure</option>
      </select>
      <textarea rows={2} className="w-full px-2.5 py-2 border rounded-lg text-xs bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
        placeholder="Disposition rationale (min 20 chars)…"
        value={rationale} onChange={e => setRationale(e.target.value)} />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <button onClick={handleSubmit} disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 disabled:opacity-60">
        {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        Record Disposition Decision
      </button>
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

  // PDF viewer state
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const prevBlobRef = useRef<string | null>(null);

  // Field review state (local — persists per session)
  const [fieldReviews, setFieldReviews] = useState<Record<string, ReviewState>>({});
  const [fieldComments, setFieldComments] = useState<Record<string, string>>({});

  // Finding states (synced with backend)
  const [findingStates, setFindingStates] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const res = await batchDossiersApi.get(id);
      const d: Dossier = res.data;
      setDossier(d);
      // Init finding states from server data
      const states: Record<string, string> = {};
      d.documents.forEach(dd => (dd.findings ?? []).forEach(f => {
        states[f.id] = f.verification_state ?? "gray";
      }));
      setFindingStates(prev => ({ ...states, ...prev }));
      // Auto-select first document
      if (d.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(d.documents[0].document_id);
      }
    } catch {
      router.push("/batch-dossiers");
    } finally {
      setLoading(false);
    }
  }, [id, router, selectedDocId]);

  useEffect(() => { load(); }, [load]);

  // Load PDF blob URL when selected document changes
  useEffect(() => {
    if (!selectedDocId) return;
    const dd = dossier?.documents.find(d => d.document_id === selectedDocId);
    if (!dd) return;

    setPdfLoading(true);
    api.get(`/documents/${selectedDocId}/download`, { responseType: "blob" })
      .then(resp => {
        if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current);
        const url = URL.createObjectURL(resp.data);
        prevBlobRef.current = url;
        setPdfBlobUrl(url);
      })
      .catch(() => setPdfBlobUrl(null))
      .finally(() => setPdfLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDocId]);

  // Cleanup blob URL on unmount
  useEffect(() => () => { if (prevBlobRef.current) URL.revokeObjectURL(prevBlobRef.current); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await batchDossiersApi.assessReadiness(id); await load(); }
    finally { setRefreshing(false); }
  };

  const handleFindingStateChange = (findingId: string, state: string) => {
    setFindingStates(prev => ({ ...prev, [findingId]: state }));
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
    </div>
  );
  if (!dossier) return null;

  const selectedDoc = dossier.documents.find(d => d.document_id === selectedDocId);
  const selectedFindings = (selectedDoc?.findings ?? []).map(f => ({
    ...f, verification_state: findingStates[f.id] ?? f.verification_state ?? "gray",
  }));

  const readinessCfg = dossier.readiness_status ? READINESS_CFG[dossier.readiness_status] : null;
  const totalFindings = dossier.documents.flatMap(d => d.findings ?? []).length;
  const reviewedFindings = Object.values(findingStates).filter(s => s === "green" || s === "red").length;
  const allFieldsReviewed = HEADER_FIELDS.filter(f => dossier[f.key]).every(f => fieldReviews[f.key] && fieldReviews[f.key] !== "pending");

  return (
    // Bust out of dashboard main's padding to get full height
    <div className="-mx-5 -my-4 flex flex-col" style={{ height: "calc(100vh - 64px)" }}>
      {showAddDoc && (
        <AddDocumentModal
          dossierId={id}
          onClose={() => setShowAddDoc(false)}
          onAdded={() => { setShowAddDoc(false); load(); }}
        />
      )}

      {/* ── Header bar ── */}
      <div className="flex-shrink-0 border-b bg-background px-6 py-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Link href="/batch-dossiers" className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="w-5 h-5" />
          </Link>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-base font-semibold">{dossier.lot_number}</h1>
              <span className="text-muted-foreground">—</span>
              <span className="text-sm text-muted-foreground truncate">{dossier.product_name}</span>
              {dossier.is_sterile && <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded-full">Sterile</span>}
              {dossier.shadow_mode && <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded-full">Shadow Mode</span>}
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              <p className="text-[11px] text-muted-foreground capitalize">
                {dossier.record_family.replace(/_/g, " ")} · {dossier.batch_purpose.replace(/_/g, " ")}
              </p>
              {totalFindings > 0 && (
                <span className="text-[11px] text-muted-foreground">
                  {reviewedFindings}/{totalFindings} findings reviewed
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleRefresh} disabled={refreshing}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2.5 py-1.5 border rounded-lg hover:bg-accent">
              {refreshing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              Recompute
            </button>
            <button onClick={() => setShowAddDoc(true)}
              className="flex items-center gap-1.5 bg-primary text-primary-foreground px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-primary/90">
              <Plus className="w-3.5 h-3.5" /> Add Document
            </button>
          </div>
        </div>
      </div>

      {/* ── Split pane ── */}
      <div className="flex-1 flex min-h-0 overflow-hidden">

        {/* ── LEFT: PDF Viewer ── */}
        <div className="w-[55%] flex flex-col border-r min-h-0 bg-gray-100">

          {/* Document tab selector */}
          <div className="flex-shrink-0 bg-background border-b px-4 py-2 flex items-center gap-2 overflow-x-auto">
            {dossier.documents.length === 0 ? (
              <span className="text-xs text-muted-foreground">No documents — add the primary batch record</span>
            ) : (
              dossier.documents.map(dd => (
                <button
                  key={dd.document_id}
                  onClick={() => setSelectedDocId(dd.document_id)}
                  className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    selectedDocId === dd.document_id
                      ? "bg-primary text-primary-foreground"
                      : "border hover:bg-accent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <FileText className="w-3 h-3" />
                  <span className="max-w-[140px] truncate">{dd.document_title ?? ROLE_LABELS[dd.role] ?? dd.role}</span>
                  {dd.assessment?.clyira_score != null && (
                    <span className={`text-[10px] px-1 rounded ${
                      dd.assessment.clyira_score >= 85 ? "bg-emerald-100 text-emerald-700"
                      : dd.assessment.clyira_score >= 70 ? "bg-amber-100 text-amber-700"
                      : "bg-red-100 text-red-700"
                    }`}>
                      {dd.assessment.clyira_score.toFixed(0)}
                    </span>
                  )}
                </button>
              ))
            )}
            {dossier.documents.length > 0 && (
              <button onClick={() => setShowAddDoc(true)}
                className="flex-shrink-0 flex items-center gap-1 px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground border border-dashed rounded-lg hover:border-solid">
                <Plus className="w-3 h-3" /> Add
              </button>
            )}
          </div>

          {/* PDF render area */}
          <div className="flex-1 min-h-0 relative">
            {dossier.documents.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8">
                <FileText className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-sm font-medium text-gray-500 mb-1">No document selected</p>
                <p className="text-xs text-gray-400 mb-4">Add the primary batch record to begin review</p>
                <button onClick={() => setShowAddDoc(true)}
                  className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                  <Plus className="w-4 h-4" /> Add Primary Batch Record
                </button>
              </div>
            ) : pdfLoading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">Loading document…</p>
                </div>
              </div>
            ) : pdfBlobUrl ? (
              <iframe
                src={pdfBlobUrl}
                className="w-full h-full border-0"
                title="Batch record document"
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8">
                <AlertCircle className="w-10 h-10 text-amber-400 mb-3" />
                <p className="text-sm font-medium text-gray-600 mb-1">Could not load document</p>
                <p className="text-xs text-gray-400">The file may not have been uploaded or is unavailable</p>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: Review Panel ── */}
        <div className="w-[45%] flex flex-col min-h-0 bg-background">

          {/* Readiness + gates strip */}
          <div className="flex-shrink-0 border-b px-4 py-2.5 space-y-2 bg-muted/20">
            {readinessCfg && (
              <div className={`flex items-center gap-2 text-xs font-medium px-2.5 py-1.5 rounded-lg border ${readinessCfg.bg} ${readinessCfg.text}`}>
                {readinessCfg.icon}
                {readinessCfg.label}
                {dossier.readiness_score != null && (
                  <span className="ml-auto font-normal opacity-80">Score: {dossier.readiness_score.toFixed(1)}</span>
                )}
              </div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {([
                { pass: dossier.gates.evidence_complete,       label: "Evidence" },
                { pass: dossier.gates.data_integrity_ok,       label: "Data integrity" },
                { pass: dossier.gates.all_findings_addressed,  label: "Findings" },
                { pass: dossier.gates.gray_findings_resolved,  label: "Gray resolved" },
              ]).map(({ pass, label }) => (
                <div key={label} className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${pass ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"}`}>
                  {pass ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
                  {label}
                </div>
              ))}
            </div>
          </div>

          {/* Scrollable review content */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">

            {/* ── Section 1: Batch Header Fields ── */}
            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">Batch Header Fields</h3>
                <span className="text-[10px] text-muted-foreground">
                  {Object.values(fieldReviews).filter(s => s !== "pending").length}/{HEADER_FIELDS.filter(f => dossier[f.key]).length} reviewed
                  {allFieldsReviewed && " ✓"}
                </span>
              </div>
              <div className="space-y-1.5">
                {HEADER_FIELDS.map(({ key, label, critical }) => {
                  const value = dossier[key] as string | null | undefined;
                  if (!value && !critical) return null;
                  return (
                    <FieldReviewItem
                      key={key}
                      label={label}
                      value={value}
                      critical={critical}
                      state={fieldReviews[key] ?? "pending"}
                      onPass={() => setFieldReviews(prev => ({ ...prev, [key]: "pass" }))}
                      onFail={() => setFieldReviews(prev => ({ ...prev, [key]: "fail" }))}
                      comment={fieldComments[key] ?? ""}
                      onComment={v => setFieldComments(prev => ({ ...prev, [key]: v }))}
                    />
                  );
                })}
              </div>
            </section>

            {/* ── Section 2: Assessment Findings ── */}
            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Assessment Findings
                  {selectedDoc?.document_title && (
                    <span className="ml-1.5 text-muted-foreground normal-case font-normal">
                      — {selectedDoc.document_title}
                    </span>
                  )}
                </h3>
                {selectedFindings.length > 0 && (
                  <span className="text-[10px] text-muted-foreground">
                    {selectedFindings.filter(f => ["green", "red"].includes(f.verification_state ?? "")).length}/{selectedFindings.length} reviewed
                  </span>
                )}
              </div>

              {!selectedDocId ? (
                <p className="text-xs text-muted-foreground italic">Select a document tab to view findings</p>
              ) : selectedFindings.length === 0 ? (
                selectedDoc?.assessment ? (
                  <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                    <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> No findings — all checks passed
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">No assessment run yet for this document</p>
                )
              ) : (
                <div className="space-y-1.5">
                  {/* Group: fail first */}
                  {["critical", "high", "medium", "low", "info"].flatMap(sev =>
                    selectedFindings
                      .filter(f => f.severity === sev)
                      .map(f => (
                        <FindingReviewItem
                          key={f.id}
                          finding={f}
                          dossierId={id}
                          onStateChange={handleFindingStateChange}
                        />
                      ))
                  )}
                </div>
              )}
            </section>

            {/* ── Missing evidence summary ── */}
            {dossier.readiness_detail?.missing_required_labels && dossier.readiness_detail.missing_required_labels.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider mb-2">Missing Evidence</h3>
                <div className="space-y-1">
                  {dossier.readiness_detail.missing_required_labels.map(label => (
                    <div key={label} className="flex items-center gap-2 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
                      <XCircle className="w-3.5 h-3.5 flex-shrink-0" /> {label} <span className="text-[10px] opacity-70">Missing required</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* ── Fixed footer: Disposition ── */}
          <div className="flex-shrink-0 border-t px-4 py-4 bg-background">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-3.5 h-3.5 text-muted-foreground" />
              <h3 className="text-xs font-semibold uppercase tracking-wider">QA Disposition</h3>
              <a
                href="#"
                onClick={async e => {
                  e.preventDefault();
                  try {
                    const res = await batchDossiersApi.getReport(id);
                    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url; a.download = `dossier-${dossier.lot_number}.json`; a.click();
                    URL.revokeObjectURL(url);
                  } catch { /* ignore */ }
                }}
                className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
              >
                <Download className="w-3 h-3" /> Export report
              </a>
            </div>
            <DispositionPanel dossier={dossier} onDecision={load} />
          </div>
        </div>
      </div>
    </div>
  );
}

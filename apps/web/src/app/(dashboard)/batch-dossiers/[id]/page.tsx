"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft, CheckCircle2, AlertCircle, XCircle,
  AlertTriangle, FileText, Plus, RefreshCw, ChevronDown,
  ChevronRight, Loader2, Shield, Info, RotateCcw,
  Download, Pencil, X, GitCompare,
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
  manufacturing_context?: string; manufacturing_date?: string; target_release_date?: string;
  target_markets: string[];
  status: string; readiness_status?: string; readiness_score?: number; readiness_band?: string;
  disposition_decision?: string; disposition_rationale?: string; disposition_divergence?: boolean;
  gates: Gate; shadow_mode: boolean; documents: DossierDoc[];
  readiness_detail?: { complete: boolean; missing_required_labels?: string[]; missing_conditional?: Record<string, string>; summary: string; };
}
interface DocOption { id: string; title: string; document_category: string; }

interface Conflict {
  field: string;
  severity: string;
  description: string;
  documents_involved: string[];
  values_found?: Record<string, string>;
}

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

function FindingCard({ f, dossierId }: { f: Finding; dossierId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correctionField, setCorrectionField] = useState("");
  const [correctedValue, setCorrectedValue] = useState("");
  const [correctionRationale, setCorrectionRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [correctionError, setCorrectionError] = useState("");

  const vState = f.verification_state ? VSTATE_CONFIG[f.verification_state] : null;
  const sevColor = SEVERITY_COLOR[f.severity] ?? SEVERITY_COLOR.info;

  const handleSubmitCorrection = async () => {
    if (!correctionField.trim()) { setCorrectionError("Field name is required"); return; }
    if (!correctedValue.trim()) { setCorrectionError("Corrected value is required"); return; }
    if (!f.document_id) { setCorrectionError("No document associated with this finding"); return; }
    setSubmitting(true);
    setCorrectionError("");
    try {
      await batchDossiersApi.submitCorrection(dossierId, {
        finding_id: f.id,
        document_id: f.document_id,
        field_name: correctionField.trim(),
        corrected_value: correctedValue.trim(),
        correction_rationale: correctionRationale.trim() || undefined,
        field_criticality: f.field_criticality,
      });
      setSubmitted(true);
      setShowCorrection(false);
    } catch {
      setCorrectionError("Failed to submit correction. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const borderColor = vState
    ? vState.dot === "bg-emerald-500" ? "#10b981"
    : vState.dot === "bg-red-500" ? "#ef4444"
    : vState.dot === "bg-blue-500" ? "#3b82f6"
    : "#9ca3af"
    : undefined;

  return (
    <div
      className={`border rounded-lg overflow-hidden ${vState ? "border-l-4" : ""}`}
      style={borderColor ? { borderLeftColor: borderColor } : {}}
    >
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
            {submitted && (
              <span className="text-[10px] px-1.5 py-0.5 rounded border bg-teal-50 text-teal-700 border-teal-200">
                Correction submitted
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

          {/* Correction toggle */}
          {!submitted && (
            <div className="mt-3 border-t pt-2">
              <button
                type="button"
                onClick={() => setShowCorrection(!showCorrection)}
                className="flex items-center gap-1.5 text-xs text-primary hover:underline"
              >
                <Pencil className="w-3 h-3" />
                {showCorrection ? "Cancel correction" : "Flag a correction"}
              </button>
            </div>
          )}

          {showCorrection && (
            <div className="mt-2 space-y-2 p-3 bg-background rounded-lg border">
              <p className="text-xs font-medium text-foreground">Submit a correction to improve future assessments</p>
              <input
                className="w-full px-2 py-1.5 border rounded text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary/30"
                placeholder="Field name (e.g. lot_number, yield_percentage)"
                value={correctionField}
                onChange={e => setCorrectionField(e.target.value)}
              />
              <textarea
                className="w-full px-2 py-1.5 border rounded text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary/30 resize-none"
                rows={2}
                placeholder="Correct value or correction"
                value={correctedValue}
                onChange={e => setCorrectedValue(e.target.value)}
              />
              <textarea
                className="w-full px-2 py-1.5 border rounded text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary/30 resize-none"
                rows={2}
                placeholder="Rationale (optional)"
                value={correctionRationale}
                onChange={e => setCorrectionRationale(e.target.value)}
              />
              {correctionError && <p className="text-[10px] text-destructive">{correctionError}</p>}
              <button
                onClick={handleSubmitCorrection}
                disabled={submitting}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded text-xs font-medium hover:bg-primary/90 disabled:opacity-60"
              >
                {submitting && <Loader2 className="w-3 h-3 animate-spin" />}
                Submit correction
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Document Card ─────────────────────────────────────────────────────────────

function DocCard({ dd, dossierId }: { dd: DossierDoc; dossierId: string }) {
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
          {findings.map(f => <FindingCard key={f.id} f={f} dossierId={dossierId} />)}
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
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to add document");
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

// ── Reopen Modal ──────────────────────────────────────────────────────────────

function ReopenModal({ dossierId, onClose, onReopened }: {
  dossierId: string; onClose: () => void; onReopened: () => void;
}) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (reason.trim().length < 100) {
      setError(`Reason must be at least 100 characters (§22.5). Currently ${reason.trim().length}/100.`);
      return;
    }
    setLoading(true);
    setError("");
    try {
      await batchDossiersApi.reopen(dossierId, reason.trim());
      onReopened();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to reopen dossier");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold">Reopen Dossier</h3>
            <p className="text-xs text-muted-foreground mt-0.5">A documented reason of at least 100 characters is required (§22.5)</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-accent text-muted-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-3">
          <textarea
            className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
            rows={5}
            placeholder="Document the reason for reopening. Include: what was found incorrect, what new evidence requires review, and who authorised the reopen…"
            value={reason}
            onChange={e => setReason(e.target.value)}
          />
          <div className={`text-xs ${reason.trim().length >= 100 ? "text-emerald-600" : "text-muted-foreground"}`}>
            {reason.trim().length}/100 characters minimum
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={loading || reason.trim().length < 100}
            className="flex-1 flex items-center justify-center gap-2 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-60"
          >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <RotateCcw className="w-3.5 h-3.5" />
            Reopen Dossier
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Report Modal ──────────────────────────────────────────────────────────────

function ReportModal({ report, onClose }: { report: Record<string, unknown>; onClose: () => void }) {
  const dossier = report.dossier as Record<string, unknown> | undefined;
  const readiness = report.readiness as Record<string, unknown> | undefined;
  const disposition = report.disposition as Record<string, unknown> | undefined;
  const docSections = (report.document_sections as unknown[]) ?? [];
  const totals = report.finding_totals as Record<string, number> | undefined;

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dossier-review-${String(dossier?.lot_number ?? "report")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-card">
          <div>
            <h3 className="text-base font-semibold">Batch Dossier Review Report</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Generated {report.generated_at ? new Date(report.generated_at as string).toLocaleString() : "—"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent"
            >
              <Download className="w-3.5 h-3.5" /> Download JSON
            </button>
            <button onClick={onClose} className="p-1.5 rounded hover:bg-accent text-muted-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="px-6 py-4 space-y-5">
          {/* Dossier summary */}
          <section>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Lot Information</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {([
                ["Lot Number", dossier?.lot_number],
                ["Product", dossier?.product_name],
                ["Dosage Form", dossier?.dosage_form],
                ["Batch Size", dossier?.batch_size],
                ["Mfg Site", dossier?.manufacturing_site],
                ["Mfg Date", dossier?.manufacturing_date],
              ] as [string, unknown][]).filter(([, v]) => v).map(([label, value]) => (
                <div key={label} className="flex justify-between bg-muted/30 rounded p-2">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-medium">{String(value)}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Readiness */}
          {readiness != null && (
            <section>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Readiness Assessment</h4>
              <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                <div className="text-2xl font-bold text-primary">{readiness.score != null ? String((readiness.score as number).toFixed(1)) : "—"}</div>
                <div>
                  <div className="text-sm font-medium capitalize">{String(readiness.status ?? "").replace(/_/g, " ")}</div>
                  <div className="text-xs text-muted-foreground">{String(readiness.band ?? "")}</div>
                </div>
              </div>
            </section>
          )}

          {/* Finding totals */}
          {totals != null && (
            <section>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Open Findings</h4>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: "Total Open", val: totals.total_open, color: "text-gray-700" },
                  { label: "Critical", val: totals.critical_open, color: "text-red-700" },
                  { label: "High", val: totals.high_open, color: "text-orange-700" },
                  { label: "Medium", val: totals.medium_open, color: "text-amber-700" },
                ].map(({ label, val, color }) => (
                  <div key={label} className="text-center p-2 bg-muted/30 rounded-lg">
                    <div className={`text-xl font-bold ${color}`}>{val ?? 0}</div>
                    <div className="text-[10px] text-muted-foreground">{label}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Disposition */}
          {disposition?.decision != null && (
            <section>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Disposition</h4>
              <div className="p-3 bg-muted/30 rounded-lg text-sm">
                <div className="font-medium capitalize">{String(disposition.decision).replace(/_/g, " ")}</div>
                {disposition.decided_at != null && (
                  <div className="text-xs text-muted-foreground mt-0.5">{new Date(String(disposition.decided_at)).toLocaleString()}</div>
                )}
              </div>
            </section>
          )}

          {/* Documents */}
          {docSections.length > 0 && (
            <section>
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Documents ({docSections.length})</h4>
              <div className="space-y-2">
                {(docSections as Record<string, unknown>[]).map((ds, i) => {
                  const assessment = ds.assessment as Record<string, unknown> | null;
                  const summary = ds.findings_summary as Record<string, number> | undefined;
                  return (
                    <div key={i} className="flex items-center gap-3 p-2.5 bg-muted/20 rounded-lg text-sm">
                      <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                      <div className="flex-1 min-w-0">
                        <span className="font-medium truncate block">{String(ds.document_title ?? ds.document_id)}</span>
                        <span className="text-xs text-muted-foreground capitalize">{String(ds.role ?? "").replace(/_/g, " ")}</span>
                      </div>
                      {assessment?.clyira_score != null && (
                        <span className="text-xs font-mono text-muted-foreground">{String((assessment.clyira_score as number).toFixed(1))}</span>
                      )}
                      {summary && Object.keys(summary).length > 0 && (
                        <div className="flex gap-1">
                          {summary.critical > 0 && <span className="text-[10px] px-1 bg-red-100 text-red-700 rounded">{summary.critical}C</span>}
                          {summary.high > 0 && <span className="text-[10px] px-1 bg-orange-100 text-orange-700 rounded">{summary.high}H</span>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Disposition Panel ─────────────────────────────────────────────────────────

function DispositionPanel({ dossier, onDecision, onReopen }: {
  dossier: Dossier;
  onDecision: () => void;
  onReopen: () => void;
}) {
  const [decision, setDecision] = useState("");
  const [rationale, setRationale] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showReopenModal, setShowReopenModal] = useState(false);

  const handleSubmit = async () => {
    if (!decision) { setError("Select a disposition decision"); return; }
    if (rationale.trim().length < 20) { setError("Rationale must be at least 20 characters"); return; }
    setLoading(true);
    try {
      await batchDossiersApi.recordDisposition(dossier.id, { decision, rationale });
      onDecision();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to record disposition");
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
      <>
        {showReopenModal && (
          <ReopenModal
            dossierId={dossier.id}
            onClose={() => setShowReopenModal(false)}
            onReopened={() => { setShowReopenModal(false); onReopen(); }}
          />
        )}
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
          <button
            onClick={() => setShowReopenModal(true)}
            className="mt-3 flex items-center gap-1.5 text-xs px-3 py-1.5 border rounded-lg hover:bg-white/50 transition-colors w-full justify-center"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reopen Dossier
          </button>
        </div>
      </>
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
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [conflictsLoading, setConflictsLoading] = useState(false);
  const [conflictsLoaded, setConflictsLoaded] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

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

  // Auto-load conflicts when overview tab is active
  useEffect(() => {
    if (activeTab === "overview" && !conflictsLoaded) {
      setConflictsLoading(true);
      batchDossiersApi.getConflicts(id)
        .then(res => setConflicts(res.data.conflicts ?? []))
        .catch(() => {})
        .finally(() => { setConflictsLoading(false); setConflictsLoaded(true); });
    }
  }, [activeTab, conflictsLoaded, id]);

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

  const handleGenerateReport = async () => {
    setReportLoading(true);
    try {
      const res = await batchDossiersApi.getReport(id);
      setReport(res.data);
      setShowReport(true);
    } catch {
      // silently fail — button will re-enable
    } finally {
      setReportLoading(false);
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
  const criticalConflicts = conflicts.filter(c => c.severity === "critical");

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {showAddDoc && (
        <AddDocumentModal
          dossierId={id}
          onClose={() => setShowAddDoc(false)}
          onAdded={() => { setShowAddDoc(false); load(); }}
        />
      )}
      {showReport && report && (
        <ReportModal report={report} onClose={() => setShowReport(false)} />
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
            {criticalConflicts.length > 0 && (
              <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full flex items-center gap-1">
                <GitCompare className="w-3 h-3" />
                {criticalConflicts.length} conflict{criticalConflicts.length !== 1 ? "s" : ""}
              </span>
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
          onClick={handleGenerateReport}
          disabled={reportLoading}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 border rounded-lg hover:bg-accent transition-colors"
        >
          {reportLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          Report
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

              {/* Cross-document conflicts */}
              <div className="bg-card border rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <GitCompare className="w-4 h-4 text-muted-foreground" />
                  <h3 className="text-sm font-semibold">Cross-Document Conflicts</h3>
                  {conflictsLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground ml-auto" />}
                </div>
                {conflictsLoaded && conflicts.length === 0 && (
                  <div className="flex items-center gap-2 text-sm text-emerald-700">
                    <CheckCircle2 className="w-4 h-4" /> No cross-document conflicts detected
                  </div>
                )}
                {conflictsLoaded && conflicts.length > 0 && (
                  <div className="space-y-2">
                    {conflicts.map((c, i) => (
                      <div
                        key={i}
                        className={`rounded-lg border p-3 text-sm ${
                          c.severity === "critical" ? "border-red-200 bg-red-50"
                          : c.severity === "high" ? "border-orange-200 bg-orange-50"
                          : "border-amber-200 bg-amber-50"
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${SEVERITY_COLOR[c.severity] ?? SEVERITY_COLOR.info}`}>
                            {c.severity.toUpperCase()}
                          </span>
                          <span className="font-medium capitalize">{c.field.replace(/_/g, " ")}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">{c.description}</p>
                        {c.values_found && Object.keys(c.values_found).length > 0 && (
                          <div className="mt-1.5 space-y-0.5">
                            {Object.entries(c.values_found).map(([doc, val]) => (
                              <div key={doc} className="text-xs text-muted-foreground font-mono">
                                {doc}: <span className="text-foreground">{val}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

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
                dossier.documents.map(dd => <DocCard key={dd.id} dd={dd} dossierId={id} />)
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
                    .map(f => <FindingCard key={f.id} f={f} dossierId={id} />)
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
          <DispositionPanel dossier={dossier} onDecision={load} onReopen={load} />

          {/* Dossier metadata */}
          <div className="bg-card border rounded-xl p-4 text-xs space-y-2 text-muted-foreground">
            <div className="font-semibold text-foreground text-sm mb-1">Classification</div>
            <div className="flex justify-between"><span>Record family</span><span className="capitalize">{dossier.record_family.replace(/_/g, " ")}</span></div>
            <div className="flex justify-between"><span>Product type</span><span className="capitalize">{dossier.product_type.replace(/_/g, " ")}</span></div>
            <div className="flex justify-between"><span>Sterile</span><span>{dossier.is_sterile ? "Yes" : "No"}</span></div>
            {dossier.manufacturing_context && <div className="flex justify-between"><span>Context</span><span className="capitalize">{dossier.manufacturing_context.replace(/_/g, " ")}</span></div>}
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

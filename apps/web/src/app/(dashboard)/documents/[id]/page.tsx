"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronRight, FileText, Play, Loader2, AlertTriangle,
  CheckCircle2, ChevronDown, ChevronUp, BookOpen, Zap,
  Upload, Plus, X, FileUp, CheckSquare, Square, ShieldCheck,
  Download, MessageCircle, Send, History, Lock, CheckCheck,
  ThumbsUp, Clock, Flag, PenLine, LayoutList, FileSearch,
  Eye, Settings2, AlertCircle, Minus, Link2, Edit3,
  Package, ClipboardList, FlaskConical, BarChart2,
} from "lucide-react";
import { documentsApi, assessmentsApi, assistantApi, documentHistoryApi, signaturesApi } from "@/lib/api";
import { DocumentReviewPane } from "@/components/shared/document-review-pane";
import { DocumentViewer } from "@/components/shared/document-viewer";
import { SignatureModal } from "@/components/shared/signature-modal";
import { ScoreRing } from "@/components/shared/score-display";
import { SeverityBadge, LevelBadge, DocStatusBadge, FindingStatusBadge } from "@/components/shared/badges";
import { formatDate, formatFileSize, getSeverityConfig, timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Document {
  id: string; title: string; document_number?: string; version?: string;
  document_category?: string; department_owner?: string; dtap_id?: string;
  file_type?: string; file_size_bytes?: number; status: string;
  latest_score?: number | null; latest_assessment_id?: string;
  created_at?: string; references?: any[];
}

interface Finding {
  id: string; level: string; level_name?: string; severity: string;
  category?: string; title: string; description: string; evidence?: string;
  location?: string; regulatory_citation?: string; citation_type?: string;
  agency?: string; enforcement_match: boolean; enforcement_context?: string;
  severity_elevated: boolean; suggestion_draft?: string; next_step_text?: string;
  remediation_priority?: number;
  status: string; response_text?: string; dispute_reason?: string;
  confidence_score?: number; validated: boolean;
}

interface Assessment {
  id: string; document_id: string; status: string; current_level?: string;
  clyira_score?: number; adjusted_score?: number; score_band?: string;
  findings_critical: number; findings_high: number;
  findings_medium: number; findings_low: number; findings_info: number;
  enforcement_matches: number; processing_time_seconds?: number;
  levels_run?: string[]; created_at?: string;
  data_integrity_hold?: boolean; suspended_reason?: string;
  error_detail?: string;
}

interface HistoryEntry {
  id: string; clyira_score?: number; adjusted_score?: number;
  score_band?: string; findings_critical: number; findings_high: number;
  created_at: string; dtap_id?: string;
}

interface Signature {
  id: string; user_full_name: string; user_email: string; user_role: string;
  meaning: string; signed_at: string; is_voided: boolean; void_reason?: string;
  document_version?: string; entry_hash?: string;
}

type Tab = "overview" | "references" | "regulatory" | "findings" | "activity";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];

const LEVEL_PROGRESS_LABELS: Record<string, string> = {
  L1: "Structural Integrity", L2: "Document Control", L3: "Quality Logic",
  L4: "Data Integrity", L5: "Data Intelligence", L6: "Cross-Reference",
  L7: "Lifecycle Compliance", L8: "Regulatory Intelligence", L9: "Enforcement",
  L10: "Longitudinal", L11: "Inspection Readiness",
  validating: "Validating findings", scoring: "Calculating score",
};

// ── DTAP Intelligence Maps ─────────────────────────────────────────────────────

const DTAP_LABEL: Record<string, string> = {
  // DB stores DTAP IDs like "DTAP-003"; also accept lowercase shorthand
  "DTAP-001": "Standard Operating Procedure",
  "DTAP-002": "CAPA",
  "DTAP-003": "Analytical Test Method",
  "DTAP-004": "Deviation Report",
  "DTAP-005": "Lab Investigation Report",
  "DTAP-006": "Validation Protocol",
  "DTAP-007": "Batch Record",
  atm: "Analytical Test Method",
  sop: "Standard Operating Procedure",
  capa: "CAPA",
  deviation: "Deviation Report",
  lir: "Lab Investigation Report",
  validation: "Validation Protocol",
};

const DTAP_CONTEXT: Record<string, string> = {
  "DTAP-001": "Process control / operations",
  "DTAP-002": "Quality event / corrective action",
  "DTAP-003": "QC testing / documentation",
  "DTAP-004": "Deviation management",
  "DTAP-005": "Lab investigation / OOS",
  "DTAP-006": "Process / method validation",
  "DTAP-007": "Batch manufacturing / lot release",
  atm: "QC testing / documentation",
  sop: "Process control / operations",
  capa: "Quality event / corrective action",
  deviation: "Deviation management",
  lir: "Lab investigation / OOS",
  validation: "Process / method validation",
};

const DTAP_REVIEW_ITEMS: Record<string, string[]> = {
  "DTAP-001": ["Procedure steps", "Responsibilities", "References", "Revision history", "Approval chain", "Training requirements"],
  "DTAP-002": ["Root cause analysis", "Corrective actions", "Preventive actions", "Effectiveness check", "Timeline", "Risk assessment"],
  "DTAP-003": ["Acceptance criteria", "Sample handling", "Reagents / materials", "Instrument qualification", "Calculations", "Data integrity", "Reference standards", "System suitability"],
  "DTAP-004": ["Event description", "Impact assessment", "Root cause", "Disposition", "CAPA linkage", "Recurrence prevention"],
  "DTAP-005": ["OOS investigation", "Phase I / Phase II", "Assignable cause", "Disposition", "Method validation"],
  "DTAP-006": ["Protocol design", "Acceptance criteria", "Statistical analysis", "Risk assessment", "Change control"],
  "DTAP-007": ["Batch formula", "Process parameters", "In-process controls", "Yield reconciliation", "QC release"],
  atm: ["Acceptance criteria", "Sample handling", "Reagents / materials", "Instrument qualification", "Calculations", "Data integrity", "Reference standards", "System suitability"],
  sop: ["Procedure steps", "Responsibilities", "References", "Revision history", "Approval chain", "Training requirements"],
  capa: ["Root cause analysis", "Corrective actions", "Preventive actions", "Effectiveness check", "Timeline", "Risk assessment"],
  deviation: ["Event description", "Impact assessment", "Root cause", "Disposition", "CAPA linkage", "Recurrence prevention"],
  lir: ["OOS investigation", "Phase I / Phase II", "Assignable cause", "Disposition", "Method validation"],
  validation: ["Protocol design", "Acceptance criteria", "Statistical analysis", "Risk assessment", "Change control"],
};

// ── Regulatory Framework Data ──────────────────────────────────────────────────

const FRAMEWORK_GROUPS = [
  {
    group: "FDA",
    items: [
      { code: "FDA_21CFR211", label: "21 CFR Part 211", description: "Current GMP — Finished Pharmaceuticals" },
      { code: "FDA_21CFR820", label: "21 CFR Part 820", description: "Quality System Regulation — Medical Devices" },
      { code: "FDA_21CFR11", label: "21 CFR Part 11", description: "Electronic Records and Signatures" },
      { code: "FDA_21CFR4", label: "21 CFR Part 4", description: "Regulation of Combination Products" },
      { code: "FDA_PV2011", label: "FDA Process Validation (2011)", description: "Guidance for Industry — Process Validation" },
      { code: "FDA_ASEPTIC", label: "FDA Aseptic Processing (2004)", description: "Sterile Drug Products by Aseptic Processing" },
      { code: "FDA_483", label: "FDA 483 Observations", description: "Inspectional observations database" },
      { code: "FDA_WL", label: "FDA Warning Letters", description: "Published warning letter citations" },
    ],
  },
  {
    group: "ICH",
    items: [
      { code: "ICH_Q10", label: "ICH Q10", description: "Pharmaceutical Quality System" },
      { code: "ICH_Q9", label: "ICH Q9", description: "Quality Risk Management" },
      { code: "ICH_Q8", label: "ICH Q8(R2)", description: "Pharmaceutical Development" },
      { code: "ICH_Q7", label: "ICH Q7", description: "GMP for Active Pharmaceutical Ingredients" },
      { code: "ICH_Q6", label: "ICH Q6A / Q6B", description: "Specifications for Drug Substances and Products" },
      { code: "ICH_E6R2", label: "ICH E6(R2)", description: "Good Clinical Practice" },
    ],
  },
  {
    group: "EMA / EU",
    items: [
      { code: "EU_GMP_PART1", label: "EU GMP Part I", description: "Basic Requirements for Medicinal Products" },
      { code: "EU_GMP_PART2", label: "EU GMP Part II", description: "Basic Requirements for Active Substances" },
      { code: "EU_ANNEX1", label: "EU GMP Annex 1", description: "Manufacture of Sterile Medicinal Products" },
      { code: "EU_ANNEX11", label: "EU GMP Annex 11", description: "Computerised Systems" },
    ],
  },
  {
    group: "ISO",
    items: [
      { code: "ISO_13485", label: "ISO 13485:2016", description: "Medical Devices Quality Management Systems" },
      { code: "ISO_14971", label: "ISO 14971:2019", description: "Risk Management for Medical Devices" },
      { code: "ISO_9001", label: "ISO 9001:2015", description: "Quality Management Systems — Requirements" },
    ],
  },
];

const ALL_FRAMEWORK_CODES = FRAMEWORK_GROUPS.flatMap((g) => g.items.map((i) => i.code));

// ── Framework Selector Panel ───────────────────────────────────────────────────

function FrameworkSelectorPanel({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (codes: string[]) => void;
}) {
  const toggle = (code: string) =>
    onChange(selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code]);

  const toggleGroup = (codes: string[]) => {
    const allSelected = codes.every((c) => selected.includes(c));
    onChange(
      allSelected
        ? selected.filter((c) => !codes.includes(c))
        : Array.from(new Set([...selected, ...codes]))
    );
  };

  return (
    <div className="bg-card border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-muted-foreground" />
        <h2 className="font-semibold">Regulatory Frameworks</h2>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
          {selected.length} / {ALL_FRAMEWORK_CODES.length} selected
        </span>
      </div>
      <div className="px-5 py-4 space-y-4">
        <p className="text-xs text-muted-foreground">
          Select which regulatory frameworks Clyira should assess this document against. All are selected by default.
        </p>
        {FRAMEWORK_GROUPS.map((group) => {
          const groupCodes = group.items.map((i) => i.code);
          const allGroupSelected = groupCodes.every((c) => selected.includes(c));
          const someGroupSelected = groupCodes.some((c) => selected.includes(c));
          return (
            <div key={group.group}>
              <button
                type="button"
                onClick={() => toggleGroup(groupCodes)}
                className="flex items-center gap-2 mb-2"
              >
                {allGroupSelected ? (
                  <CheckSquare className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                ) : someGroupSelected ? (
                  <div className="w-3.5 h-3.5 border-2 border-primary rounded-sm flex-shrink-0 bg-primary/20" />
                ) : (
                  <Square className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                )}
                <span className="text-xs font-semibold">{group.group}</span>
              </button>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 pl-5">
                {group.items.map((item) => (
                  <label key={item.code} className="flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selected.includes(item.code)}
                      onChange={() => toggle(item.code)}
                      className="mt-0.5 accent-primary flex-shrink-0"
                    />
                    <span className="flex-1 min-w-0">
                      <span className="text-xs font-medium">{item.label}</span>
                      <span className="text-[10px] text-muted-foreground ml-1.5">{item.description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
        <div className="flex gap-2 pt-1 border-t">
          <button type="button" onClick={() => onChange(ALL_FRAMEWORK_CODES)}
            className="text-[10px] text-primary hover:underline font-medium">
            Select all
          </button>
          <span className="text-[10px] text-muted-foreground">·</span>
          <button type="button" onClick={() => onChange([])}
            className="text-[10px] text-muted-foreground hover:underline">
            Clear all
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Finding Card ───────────────────────────────────────────────────────────────

function FindingCard({
  finding, documentId, assessmentId, onStatusChange,
}: {
  finding: Finding; documentId: string; assessmentId: string;
  onStatusChange?: (findingId: string, newStatus: string, adjustedScore?: number) => void;
}) {
  const [expanded, setExpanded] = useState(finding.severity === "critical" || finding.severity === "high");
  const [localStatus, setLocalStatus] = useState(finding.status);
  const [actioning, setActioning] = useState(false);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [showDisputeModal, setShowDisputeModal] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const cfg = getSeverityConfig(finding.severity);

  const doAction = async (newStatus: string, disputeReason_?: string) => {
    setActioning(true);
    try {
      const res = await assessmentsApi.actionFinding(assessmentId, finding.id, newStatus, "", disputeReason_);
      setLocalStatus(newStatus);
      onStatusChange?.(finding.id, newStatus, res.data?.adjusted_score);
    } catch { }
    finally { setActioning(false); }
  };

  const loadDraft = async () => {
    setDraftLoading(true);
    try {
      const res = await assistantApi.draftFix(documentId, finding.id);
      setDraft(res.data.draft_text);
    } catch { setDraft("Draft unavailable — LLM service may be busy. Try again."); }
    finally { setDraftLoading(false); }
  };

  const ACTION_BUTTONS = [
    { status: "acknowledged", label: "Acknowledge", icon: ThumbsUp, show: localStatus === "open" },
    { status: "in_progress", label: "In Progress", icon: Clock, show: localStatus === "acknowledged" },
    { status: "resolved", label: "Resolve", icon: CheckCheck, show: ["open", "acknowledged", "in_progress"].includes(localStatus) },
    { status: "disputed", label: "Dispute", icon: Flag, show: localStatus !== "resolved", isDispute: true },
  ];

  return (
    <>
      {showDisputeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-card border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="font-semibold">Dispute Finding</h3>
            <p className="text-sm text-muted-foreground">{finding.title}</p>
            <textarea value={disputeReason} onChange={e => setDisputeReason(e.target.value)}
              placeholder="Explain why this finding is inaccurate or should not apply..."
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 min-h-[80px]" />
            <div className="flex gap-3">
              <button onClick={() => setShowDisputeModal(false)} className="flex-1 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
              <button onClick={() => { doAction("disputed", disputeReason); setShowDisputeModal(false); }}
                disabled={!disputeReason.trim()}
                className="flex-1 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50">
                Submit Dispute
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={cn("border rounded-lg overflow-hidden", cfg.border)}>
        <button className={cn("w-full flex items-start gap-3 px-4 py-3 text-left", cfg.bg, "hover:opacity-90 transition-opacity")}
          onClick={() => setExpanded(!expanded)}>
          <div className={cn("w-1 self-stretch rounded-full flex-shrink-0", cfg.dot)} style={{ minHeight: 20 }} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <SeverityBadge severity={finding.severity} />
              <LevelBadge level={finding.level} compact />
              {finding.enforcement_match && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-100 text-red-700 border border-red-200">
                  <Zap className="w-2.5 h-2.5" /> Enforcement match
                </span>
              )}
              {finding.severity_elevated && (
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200">↑ Elevated</span>
              )}
              <FindingStatusBadge status={localStatus} className="ml-auto" />
            </div>
            <p className="text-sm font-semibold leading-snug pr-6">{finding.title}</p>
            {!expanded && finding.regulatory_citation && (
              <p className="text-[11px] font-mono text-muted-foreground mt-1 truncate">{finding.regulatory_citation}</p>
            )}
          </div>
          <div className="flex-shrink-0 mt-0.5">
            {expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
          </div>
        </button>

        {expanded && (
          <div className="px-4 py-4 space-y-4 bg-card border-t">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Description</p>
              <p className="text-sm leading-relaxed">{finding.description}</p>
            </div>
            {finding.evidence && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Evidence</p>
                <p className="text-sm text-muted-foreground italic leading-relaxed">"{finding.evidence}"</p>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {finding.location && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Location</p>
                  <p className="text-xs bg-muted rounded px-2 py-1.5">{finding.location}</p>
                </div>
              )}
              {finding.regulatory_citation && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                    Regulatory Citation · <span className="capitalize font-normal">{finding.agency}</span>
                  </p>
                  <p className="text-xs font-mono bg-clyira-50 text-clyira-800 border border-clyira-100 rounded px-2 py-1.5 leading-relaxed">
                    {finding.regulatory_citation}
                  </p>
                </div>
              )}
            </div>
            {finding.enforcement_match && finding.enforcement_context && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <p className="text-xs font-semibold text-red-800 mb-1 flex items-center gap-1">
                  <Zap className="w-3 h-3" /> Enforcement Intelligence
                </p>
                <p className="text-xs text-red-700 leading-relaxed">{finding.enforcement_context}</p>
              </div>
            )}
            {finding.suggestion_draft && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2.5">
                <p className="text-xs font-semibold text-blue-800 mb-1.5 flex items-center gap-1">
                  <BookOpen className="w-3 h-3" /> Suggested Remediation
                </p>
                <p className="text-sm text-blue-900 leading-relaxed whitespace-pre-wrap">{finding.suggestion_draft}</p>
              </div>
            )}
            <div>
              {!draft && (
                <button onClick={loadDraft} disabled={draftLoading}
                  className="flex items-center gap-1.5 text-xs text-primary border border-primary/30 hover:bg-primary/5 rounded-lg px-3 py-1.5 transition-colors">
                  {draftLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <BookOpen className="w-3 h-3" />}
                  {draftLoading ? "Drafting fix…" : "Draft Fix with Author Assistant"}
                </button>
              )}
              {draft && (
                <div className="bg-violet-50 border border-violet-200 rounded-lg px-3 py-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-xs font-semibold text-violet-800 flex items-center gap-1">
                      <BookOpen className="w-3 h-3" /> Author Assistant Draft
                    </p>
                    <button onClick={() => setDraft(null)} className="text-violet-400 hover:text-violet-600">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <p className="text-sm text-violet-900 leading-relaxed whitespace-pre-wrap">{draft}</p>
                </div>
              )}
            </div>
            {localStatus === "disputed" && finding.dispute_reason && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
                <p className="text-xs font-semibold text-orange-800 mb-0.5">Dispute Reason</p>
                <p className="text-xs text-orange-700">{finding.dispute_reason}</p>
              </div>
            )}
            {localStatus !== "resolved" && (
              <div className="flex items-center gap-2 flex-wrap pt-1 border-t">
                <span className="text-xs text-muted-foreground font-medium">Actions:</span>
                {actioning ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
                ) : (
                  ACTION_BUTTONS.filter(b => b.show).map(btn => (
                    <button key={btn.status}
                      onClick={() => btn.isDispute ? setShowDisputeModal(true) : doAction(btn.status)}
                      className={cn(
                        "flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md border transition-colors",
                        btn.status === "resolved" ? "border-green-300 text-green-700 hover:bg-green-50" :
                        btn.status === "disputed" ? "border-orange-300 text-orange-700 hover:bg-orange-50" :
                        "border-border text-muted-foreground hover:bg-accent",
                      )}>
                      <btn.icon className="w-2.5 h-2.5" />
                      {btn.label}
                    </button>
                  ))
                )}
              </div>
            )}
            {localStatus === "resolved" && (
              <div className="flex items-center gap-1.5 text-xs text-green-700 pt-1 border-t">
                <CheckCheck className="w-3.5 h-3.5" /> Finding resolved
              </div>
            )}
            {finding.confidence_score != null && (
              <p className="text-[10px] text-muted-foreground">
                Confidence: {(finding.confidence_score * 100).toFixed(0)}% · {finding.validated ? "Validated" : "Unvalidated"}
                {finding.remediation_priority && ` · Priority ${finding.remediation_priority}`}
              </p>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ── Reference type helpers ─────────────────────────────────────────────────────

const REF_TYPES = [
  { value: "organizational_guideline", label: "Org. Guideline" },
  { value: "internal_standard", label: "Internal Standard" },
  { value: "checklist", label: "Checklist" },
  { value: "template", label: "Template" },
];

const REF_TYPE_STYLES: Record<string, string> = {
  organizational_guideline: "bg-blue-50 text-blue-700 border-blue-200",
  internal_standard: "bg-purple-50 text-purple-700 border-purple-200",
  checklist: "bg-green-50 text-green-700 border-green-200",
  template: "bg-amber-50 text-amber-700 border-amber-200",
};

function RefTypeBadge({ type }: { type: string }) {
  const label = REF_TYPES.find(r => r.value === type)?.label ?? type;
  const style = REF_TYPE_STYLES[type] ?? "bg-muted text-muted-foreground border-border";
  return <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded border", style)}>{label}</span>;
}

// ── Upload Reference Modal ─────────────────────────────────────────────────────

function UploadReferenceModal({
  documentId, onClose, onSuccess,
}: { documentId: string; onClose: () => void; onSuccess: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [refType, setRefType] = useState("organizational_guideline");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name));
      return [...prev, ...Array.from(incoming).filter(f => !existing.has(f.name))];
    });
  };

  const handleSubmit = async () => {
    if (!files.length) return;
    setUploading(true); setError("");
    const fd = new FormData();
    files.forEach(f => fd.append("files", f));
    fd.append("reference_type", refType);
    try {
      await documentsApi.addReferences(documentId, fd);
      onSuccess();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Upload failed. Please try again.");
    } finally { setUploading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-semibold">Upload Validation Reference</h2>
            <p className="text-xs text-muted-foreground mt-0.5">SOPs, checklists, internal standards — used during the next assessment</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
            onClick={() => inputRef.current?.click()}
            className={cn("border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors",
              dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30")}>
            <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.doc,.xlsx,.xls"
              className="hidden" onChange={(e) => addFiles(e.target.files)} />
            <FileUp className="w-7 h-7 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium">Drop files or click to browse</p>
            <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, XLSX · multiple files allowed</p>
          </div>
          {files.length > 0 && (
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm bg-muted/40 rounded-lg px-3 py-1.5">
                  <FileText className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                  <span className="flex-1 truncate text-xs">{f.name}</span>
                  <button onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Reference Type</label>
            <select value={refType} onChange={(e) => setRefType(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
              {REF_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          {error && (
            <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />{error}
            </div>
          )}
        </div>
        <div className="px-6 pb-6 flex gap-3">
          <button onClick={onClose} className="flex-1 py-2.5 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button onClick={handleSubmit} disabled={!files.length || uploading}
            className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Uploading…" : `Upload ${files.length > 0 ? `(${files.length})` : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── QA Assistant Panel ─────────────────────────────────────────────────────────

function QAAssistantPanel({ documentId, assessmentId }: { documentId: string; assessmentId?: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{ text: string; citations: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ask = async () => {
    if (!question.trim()) return;
    setLoading(true); setError(""); setAnswer(null);
    try {
      const res = await assistantApi.ask(documentId, question, assessmentId);
      setAnswer({ text: res.data.answer, citations: res.data.citations || [] });
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "QA service unavailable. Please try again.");
    } finally { setLoading(false); }
  };

  return (
    <div className="bg-card border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b flex items-center gap-2">
        <MessageCircle className="w-4 h-4 text-primary" />
        <h2 className="font-semibold">QA Assistant</h2>
        <span className="text-[10px] bg-primary/10 text-primary font-medium px-1.5 py-0.5 rounded-full">Beta</span>
      </div>
      <div className="p-5 space-y-3">
        <p className="text-xs text-muted-foreground">
          Ask questions about this document — e.g. "Does this SOP address deviation handling?" or "What's missing from the root cause section?"
        </p>
        <div className="flex gap-2">
          <input type="text" value={question} onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !loading && ask()}
            placeholder="Ask a compliance question about this document…"
            className="flex-1 px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30" />
          <button onClick={ask} disabled={loading || !question.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        {error && <p className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded px-3 py-2">{error}</p>}
        {answer && (
          <div className="space-y-2">
            <div className="bg-muted/40 rounded-lg px-4 py-3">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer.text}</p>
            </div>
            {answer.citations.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {answer.citations.map((c, i) => (
                  <span key={i} className="text-[10px] font-mono bg-clyira-50 text-clyira-800 border border-clyira-100 px-1.5 py-0.5 rounded">{c}</span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Assessment History Panel ───────────────────────────────────────────────────

function ScoreSparkline({ scores }: { scores: number[] }) {
  if (scores.length < 2) return null;
  const W = 80, H = 28, PAD = 2;
  const minS = Math.min(...scores, 0);
  const maxS = Math.max(...scores, 100);
  const range = maxS - minS || 1;
  const pts = scores.map((s, i) => {
    const x = PAD + (i / (scores.length - 1)) * (W - PAD * 2);
    const y = PAD + ((maxS - s) / range) * (H - PAD * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const latest = scores[0], oldest = scores[scores.length - 1];
  const color = (latest - oldest) >= 0 ? "#10b981" : "#ef4444";
  return (
    <svg width={W} height={H} className="flex-shrink-0">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={pts.split(" ")[0].split(",")[0]} cy={pts.split(" ")[0].split(",")[1]} r="2.5" fill={color} />
    </svg>
  );
}

function AssessmentHistoryPanel({ documentId }: { documentId: string }) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const load = async () => {
    if (history.length > 0) { setExpanded(!expanded); return; }
    setLoading(true);
    try {
      const res = await documentHistoryApi.getAssessmentHistory(documentId);
      setHistory(res.data.assessments || []);
      setExpanded(true);
    } catch { }
    finally { setLoading(false); }
  };

  const scores = history.map(h => h.adjusted_score ?? h.clyira_score ?? 0);

  return (
    <div className="bg-card border rounded-xl overflow-hidden">
      <button onClick={load}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors text-left">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Assessment History</span>
          {history.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">{history.length} runs</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {scores.length >= 2 && <ScoreSparkline scores={scores} />}
          {loading ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            : <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`} />}
        </div>
      </button>
      {expanded && history.length > 0 && (
        <div className="border-t divide-y">
          {history.map((h, i) => {
            const prevScore = i < history.length - 1 ? (history[i + 1].adjusted_score ?? history[i + 1].clyira_score) : null;
            const currScore = h.adjusted_score ?? h.clyira_score;
            const delta = prevScore != null && currScore != null ? currScore - prevScore : null;
            return (
              <div key={h.id} className="flex items-center gap-4 px-5 py-3">
                <span className="text-xs text-muted-foreground w-4 text-right">{history.length - i}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-muted-foreground">{new Date(h.created_at).toLocaleString()}</p>
                  {h.dtap_id && <p className="text-[10px] text-muted-foreground/70 font-mono">{h.dtap_id}</p>}
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold tabular-nums">{currScore?.toFixed(1) ?? "—"}</p>
                  {h.adjusted_score !== h.clyira_score && h.adjusted_score != null && (
                    <p className="text-[10px] text-amber-600 font-medium">was {h.clyira_score?.toFixed(1)}</p>
                  )}
                  {delta != null && Math.abs(delta) > 0.1 && (
                    <p className={`text-[10px] font-medium ${delta >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                      {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}
                    </p>
                  )}
                  <p className="text-[10px] text-muted-foreground">{h.score_band}</p>
                </div>
                <div className="text-right text-xs text-red-600 font-semibold tabular-nums w-6">
                  {h.findings_critical > 0 ? h.findings_critical : ""}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {expanded && history.length === 0 && (
        <div className="px-5 py-6 text-center text-sm text-muted-foreground border-t">No completed assessments yet.</div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<Document | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [adjustedScore, setAdjustedScore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [showRefUpload, setShowRefUpload] = useState(false);
  const [error, setError] = useState("");
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>(ALL_FRAMEWORK_CODES);
  const [signatures, setSignatures] = useState<Signature[]>([]);
  const [showSignModal, setShowSignModal] = useState(false);
  const [viewMode, setViewMode] = useState<"list" | "review">("list");
  const [documentText, setDocumentText] = useState("");
  const [loadingText, setLoadingText] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [showViewer, setShowViewer] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const loadSignatures = async () => {
    try {
      const res = await signaturesApi.list(id);
      setSignatures(res.data);
    } catch { }
  };

  const switchToReview = async () => {
    setViewMode("review");
    if (documentText) return;
    setLoadingText(true);
    try {
      const res = await documentsApi.getText(id);
      setDocumentText(res.data.text || "");
    } catch { }
    finally { setLoadingText(false); }
  };

  const loadDoc = async () => {
    setLoading(true);
    try {
      const [res] = await Promise.all([documentsApi.get(id), loadSignatures()]);
      setDoc(res.data);
      if (res.data.latest_assessment_id) {
        await loadAssessment(res.data.latest_assessment_id);
      }
    } catch (err: any) {
      const status = err?.response?.status;
      setError(status === 404 ? "Document not found." : "Failed to load document. Please refresh.");
    } finally { setLoading(false); }
  };

  const loadAssessment = async (assessmentId: string) => {
    try {
      const [aRes, fRes] = await Promise.all([
        assessmentsApi.get(assessmentId),
        assessmentsApi.getFindings(assessmentId),
      ]);
      setAssessment(aRes.data);
      setAdjustedScore(aRes.data.adjusted_score ?? null);
      setFindings(fRes.data.findings ?? []);
    } catch { setError("Could not load assessment results."); }
  };

  const handleFindingStatusChange = useCallback((_findingId: string, _newStatus: string, newAdjustedScore?: number) => {
    if (newAdjustedScore != null) setAdjustedScore(newAdjustedScore);
  }, []);

  const exportDocx = async () => {
    if (!assessment || !doc) return;
    setExporting(true);
    try {
      const res = await assessmentsApi.exportDocx(assessment.id);
      const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Clyira_${doc.title?.slice(0, 30) ?? "Report"}_${assessment.id.slice(0, 8)}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { setError("Export failed. Please try again."); }
    finally { setExporting(false); }
  };

  const exportRedlined = async () => {
    if (!assessment || !doc) return;
    setExporting(true);
    try {
      const res = await assessmentsApi.exportRedlined(assessment.id);
      const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Clyira_Redlined_${doc.title?.slice(0, 30) ?? "Document"}_${assessment.id.slice(0, 8)}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { setError("Redlined export failed. Please try again."); }
    finally { setExporting(false); }
  };

  const exportCsv = async () => {
    if (!assessment || !doc) return;
    setExporting(true);
    try {
      const res = await assessmentsApi.exportCsv(assessment.id);
      const blob = new Blob([res.data], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Clyira_Findings_${doc.title?.slice(0, 30) ?? "Report"}_${assessment.id.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { setError("CSV export failed. Please try again."); }
    finally { setExporting(false); }
  };

  const pollAssessment = async (assessmentId: string): Promise<void> => {
    const maxAttempts = 90;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 10000));
      if (!mountedRef.current) return;
      try {
        const res = await assessmentsApi.get(assessmentId);
        if (!mountedRef.current) return;
        setAssessment(res.data);
        if (res.data.status === "completed") {
          await loadAssessment(assessmentId);
          if (!mountedRef.current) return;
          try { const docRes = await documentsApi.get(id); if (mountedRef.current) setDoc(docRes.data); } catch { }
          setAssessing(false);
          return;
        }
        if (res.data.status === "failed") {
          setError("Assessment failed. Please try again.");
          setAssessment(res.data); // preserve error_detail for display
          setAssessing(false);
          return;
        }
      } catch { }
    }
    if (!mountedRef.current) return;
    setError("Assessment is taking longer than expected. Refresh to check status.");
    setAssessing(false);
  };

  const runAssessment = async () => {
    if (!doc) return;
    setAssessing(true); setError("");
    try {
      const res = await assessmentsApi.run(doc.id, true, selectedFrameworks);
      setAssessment(res.data);
      if (res.data.status === "queued" || res.data.status === "running") {
        pollAssessment(res.data.id);
      } else if (res.data.id) {
        await loadAssessment(res.data.id);
        setAssessing(false);
      } else {
        setAssessing(false);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Assessment failed.");
      setAssessing(false);
    }
  };

  useEffect(() => { loadDoc(); }, [id]);

  const filteredFindings = severityFilter === "all"
    ? findings.filter(f => f.severity !== "info")
    : findings.filter(f => f.severity === severityFilter);
  const sortedFindings = [...filteredFindings].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="h-8 bg-muted rounded w-1/3 animate-pulse" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-32 bg-muted rounded-xl animate-pulse" />)}
        </div>
        <div className="h-64 bg-muted rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!doc) return <div className="text-muted-foreground text-sm">{error || "Document not found."}</div>;

  // ── Derived state ────────────────────────────────────────────────────────────
  const isReadyForAssessment = !!(doc.dtap_id && selectedFrameworks.length > 0);
  const hasContentGaps = (doc.references?.length ?? 0) === 0;

  const readinessItems = [
    { label: "Document classified", status: doc.dtap_id ? "complete" : "missing", },
    { label: "Regulatory scope", status: selectedFrameworks.length > 0 ? "complete" : "missing", },
    { label: "Company / classification content", status: (doc.references?.length ?? 0) > 0 ? "complete" : "missing", },
    { label: "Product / classification content", status: doc.document_category ? "secondary" : "not_listed", },
    { label: "Prior quality history", status: "not_listed" as const, },
  ];

  const sopCount = doc.references?.filter((r: any) => r.reference_type === "organizational_guideline").length ?? 0;
  const specCount = doc.references?.filter((r: any) => r.reference_type === "internal_standard").length ?? 0;

  const contentCoverageRows = [
    { type: "SOPs & Work Instructions", icon: FileText, count: sopCount, detail: sopCount > 0 ? `${sopCount} reference${sopCount !== 1 ? "s" : ""} linked` : "No company SOPs linked" },
    { type: "Specifications", icon: ClipboardList, count: specCount, detail: specCount > 0 ? `${specCount} linked` : "No product specifications linked" },
    { type: "Validation Protocols", icon: FlaskConical, count: 0, detail: "No validation protocols linked" },
    { type: "Prior Guidance / LIRs", icon: History, count: 0, detail: "No related quality events linked" },
    { type: "Product / Batch Context", icon: Package, count: 0, detail: "Product or batch context not linked" },
  ];

  const TAB_LABELS: Record<Tab, string> = {
    overview: "Overview",
    references: "References",
    regulatory: "Regulatory Scope",
    findings: "Findings & Evidence Map",
    activity: "Activity",
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="-mx-5 -mt-4 flex flex-col">
      {/* Modals */}
      {showRefUpload && (
        <UploadReferenceModal documentId={id} onClose={() => setShowRefUpload(false)}
          onSuccess={() => { setShowRefUpload(false); loadDoc(); }} />
      )}
      {showSignModal && (
        <SignatureModal documentId={id} documentTitle={doc.title}
          onClose={() => setShowSignModal(false)}
          onSigned={() => { setShowSignModal(false); loadSignatures(); }} />
      )}

      {/* Document viewer modal */}
      {showViewer && (
        <div className="fixed inset-0 z-50 flex flex-col bg-background">
          {/* Viewer header */}
          <div className="h-14 border-b bg-card flex items-center justify-between px-5 shrink-0">
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-muted-foreground" />
              <span className="font-medium text-sm truncate max-w-lg">{doc.title}</span>
              {doc.file_type && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted font-mono uppercase">{doc.file_type}</span>
              )}
            </div>
            <button onClick={() => setShowViewer(false)}
              className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>
          {/* Viewer body */}
          <div className="flex-1 overflow-y-auto bg-muted/30">
            <DocumentViewer
              documentId={id}
              fileType={doc.file_type}
              className="max-w-4xl mx-auto py-6"
            />
          </div>
        </div>
      )}

      {/* ── Document Header ─────────────────────────────────────────────────── */}
      <div className="bg-card border-b">
        <div className="px-6 pt-4 pb-3">
          {/* Breadcrumb */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2.5">
            <Link href="/documents" className="hover:text-foreground transition-colors">Documents</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="text-foreground font-medium">{doc.document_number ?? doc.title.slice(0, 24)}</span>
          </div>

          {/* Title + actions */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-semibold leading-tight mb-2">{doc.title}</h1>

              {/* Metadata chips row */}
              <div className="flex items-center gap-2 flex-wrap">
                {doc.dtap_id && (
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border bg-muted/50 font-medium">
                    <FileText className="w-2.5 h-2.5 text-muted-foreground" />
                    {DTAP_LABEL[doc.dtap_id] ?? doc.dtap_id}
                  </span>
                )}
                {doc.document_category && (
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border bg-muted/50 font-medium">
                    {doc.document_category}
                  </span>
                )}
                {doc.version && (
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border bg-muted/50 font-medium">
                    Version {doc.version}
                  </span>
                )}
                {isReadyForAssessment ? (
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border border-green-200 bg-green-50 text-green-700 font-medium">
                    <CheckCircle2 className="w-2.5 h-2.5" />
                    Ready for Assessment
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border border-amber-200 bg-amber-50 text-amber-700 font-medium">
                    <AlertTriangle className="w-2.5 h-2.5" />
                    Setup Required
                  </span>
                )}
                <span className="text-[11px] text-muted-foreground">
                  Owner: {doc.department_owner ?? "Demo User (Admin)"} · Uploaded {formatDate(doc.created_at)} · {doc.file_type?.toUpperCase() ?? "—"} ({formatFileSize(doc.file_size_bytes)})
                </span>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
                      <button onClick={() => setShowViewer(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-xs font-medium hover:bg-accent transition-colors">
                <Eye className="w-3.5 h-3.5" /> Preview Document
              </button>
              <button onClick={() => setShowRefUpload(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-xs font-medium hover:bg-accent transition-colors">
                <Plus className="w-3.5 h-3.5" /> Add Content
              </button>
              <button onClick={() => setActiveTab("regulatory")}
                className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-xs font-medium hover:bg-accent transition-colors">
                <Settings2 className="w-3.5 h-3.5" /> Assessment Settings
                <ChevronDown className="w-3 h-3" />
              </button>
              <button onClick={runAssessment} disabled={assessing}
                className="flex items-center gap-2 px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-xs font-semibold hover:bg-primary/90 disabled:opacity-60 transition-colors">
                {assessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                {assessing
                  ? assessment?.current_level
                    ? `${assessment.current_level}: ${LEVEL_PROGRESS_LABELS[assessment.current_level] ?? "Processing"}…`
                    : (assessment?.status === "queued" ? "Queued…" : "Assessing…")
                  : assessment ? "Re-assess" : "Run Assessment"}
              </button>
            </div>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="px-6 flex items-center gap-0">
          {(Object.keys(TAB_LABELS) as Tab[]).map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors relative whitespace-nowrap",
                activeTab === tab
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30"
              )}>
              {TAB_LABELS[tab]}
              {tab === "findings" && findings.length > 0 && (() => {
                const issueCount = findings.filter(f => f.severity !== "info").length;
                return (
                  <span className={cn(
                    "ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium",
                    (assessment?.findings_critical ?? 0) > 0 ? "bg-red-100 text-red-700" : "bg-muted text-muted-foreground"
                  )}>
                    {issueCount}
                  </span>
                );
              })()}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab Content ─────────────────────────────────────────────────────── */}
      <div className="p-5 flex-1 bg-muted/30">
        {/* Error + hold banners */}
        {error && (
          <div className="mb-4 bg-destructive/10 border border-destructive/20 text-destructive text-sm rounded-lg px-4 py-3">
            <p className="font-medium">{error}</p>
            {assessment?.error_detail && (
              <details className="mt-2">
                <summary className="text-xs cursor-pointer opacity-70 hover:opacity-100">Show error details</summary>
                <pre className="mt-1.5 text-[10px] font-mono whitespace-pre-wrap break-all opacity-80 max-h-40 overflow-y-auto bg-destructive/5 rounded p-2">
                  {assessment.error_detail}
                </pre>
              </details>
            )}
          </div>
        )}
        {assessment?.data_integrity_hold && (
          <div className="mb-4 flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
            <Lock className="w-3.5 h-3.5 text-red-600 shrink-0" />
            <p className="text-xs font-semibold text-red-800">Data Integrity Hold</p>
            <span className="text-red-300">·</span>
            <p className="text-xs text-red-700 truncate">
              {assessment.suspended_reason || "Critical ALCOA+/Data Integrity finding detected. Score capped at 50 until resolved."}
            </p>
          </div>
        )}

        {/* ── OVERVIEW TAB ──────────────────────────────────────────────────── */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-3 gap-5">
            {/* Left column */}
            <div className="col-span-2 space-y-4">

              {/* Readiness Summary */}
              <div className="bg-card border rounded-xl overflow-hidden">
                <div className="px-5 py-3 border-b">
                  <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Readiness Summary</h3>
                </div>
                <div className="p-4 grid grid-cols-2 gap-4">
                  {/* Status callouts */}
                  <div className="space-y-2.5">
                    {isReadyForAssessment ? (
                      <div className="flex items-start gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
                        <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-semibold text-green-800">Ready for assessment</p>
                          <p className="text-xs text-green-700 mt-0.5 leading-relaxed">
                            Clyira can assess this document using the selected regulatory frameworks.
                          </p>
                          {hasContentGaps && (
                            <button onClick={() => setShowRefUpload(true)}
                              className="text-[11px] text-green-700 font-medium mt-1.5 hover:underline">
                              Add content →
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-semibold text-amber-800">Setup required</p>
                          <p className="text-xs text-amber-700 mt-0.5">Document classification and regulatory scope must be configured.</p>
                        </div>
                      </div>
                    )}
                    {hasContentGaps && (
                      <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                        <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-semibold text-amber-800">Company content is incomplete.</p>
                          <p className="text-[11px] text-amber-700 mt-0.5 leading-relaxed">
                            Adding company-specific references improves accuracy and reduces false positives.
                          </p>
                          <button onClick={() => setShowRefUpload(true)}
                            className="text-[11px] text-amber-700 font-medium mt-1.5 hover:underline">
                            Add content →
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Checklist */}
                  <div className="space-y-2">
                    <div className="grid grid-cols-[1fr_auto] gap-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide px-1 pb-1 border-b">
                      <span>Item</span>
                      <span>Status</span>
                    </div>
                    {readinessItems.map((item) => (
                      <div key={item.label} className="flex items-center justify-between gap-2 px-1">
                        <div className="flex items-center gap-2 min-w-0">
                          {item.status === "complete" ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-green-500 shrink-0" />
                          ) : item.status === "missing" ? (
                            <AlertCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                          ) : (
                            <Minus className="w-3.5 h-3.5 text-muted-foreground/40 shrink-0" />
                          )}
                          <span className="text-xs text-muted-foreground truncate">{item.label}</span>
                        </div>
                        <span className={cn(
                          "text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0",
                          item.status === "complete" ? "bg-green-50 text-green-700" :
                          item.status === "missing" ? "bg-amber-50 text-amber-700" :
                          "text-muted-foreground/60"
                        )}>
                          {item.status === "complete" ? "Complete" :
                           item.status === "missing" ? "Missing" :
                           item.status === "secondary" ? "Sec listed" : "Not listed"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Assessment Scope */}
              <div className="bg-card border rounded-xl overflow-hidden">
                <div className="px-5 py-3 border-b flex items-center justify-between">
                  <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Assessment Scope</h3>
                  <button onClick={() => setActiveTab("regulatory")}
                    className="flex items-center gap-1 text-[11px] text-primary hover:underline font-medium">
                    <Edit3 className="w-2.5 h-2.5" /> Edit scope
                  </button>
                </div>
                <div className="p-4">
                  <div className="grid grid-cols-4 gap-3 mb-4">
                    {[
                      { label: "Review mode", value: "Inspection grade" },
                      { label: "Regulatory perspective", value: "FDA / GMP" },
                      { label: "Frameworks", value: `${selectedFrameworks.length} selected` },
                      { label: "Output", value: "Findings + Evidence Map + Action Plan" },
                    ].map(({ label, value }) => (
                      <div key={label} className="text-center p-3 rounded-lg bg-muted/30 border">
                        <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
                        <p className="text-xs font-semibold leading-tight">{value}</p>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      Selected Frameworks ({selectedFrameworks.length} items)
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedFrameworks.slice(0, 5).map(code => {
                        const item = FRAMEWORK_GROUPS.flatMap(g => g.items).find(i => i.code === code);
                        return (
                          <span key={code} className="text-[10px] px-2 py-0.5 rounded-full border bg-muted/30 font-medium">
                            {item?.label ?? code}
                          </span>
                        );
                      })}
                      {selectedFrameworks.length > 5 && (
                        <button onClick={() => setActiveTab("regulatory")}
                          className="text-[10px] px-2 py-0.5 rounded-full border border-primary/30 bg-primary/5 text-primary font-medium hover:bg-primary/10 transition-colors">
                          +{selectedFrameworks.length - 5} more
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Content Coverage */}
              <div className="bg-card border rounded-xl overflow-hidden">
                <div className="px-5 py-3 border-b">
                  <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Content Coverage</h3>
                </div>
                <div className="divide-y">
                  <div className="grid grid-cols-[2fr_1fr_3fr_60px] gap-3 px-5 py-2 bg-muted/20">
                    {["Content Type", "Status", "Details", "Action"].map(h => (
                      <p key={h} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">{h}</p>
                    ))}
                  </div>
                  {contentCoverageRows.map((row) => (
                    <div key={row.type} className="grid grid-cols-[2fr_1fr_3fr_60px] gap-3 items-center px-5 py-2.5">
                      <div className="flex items-center gap-2">
                        <row.icon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="text-xs font-medium">{row.type}</span>
                      </div>
                      <div>
                        {row.count > 0 ? (
                          <span className="flex items-center gap-1 text-[11px] font-semibold text-amber-700">
                            <span className="w-2.5 h-2.5 rounded-full border-2 border-amber-500 shrink-0" />
                            {row.count} linked
                          </span>
                        ) : (
                          <span className="text-[11px] text-muted-foreground font-medium">Not linked</span>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-tight">{row.detail}</p>
                      <button onClick={() => setShowRefUpload(true)}
                        className="text-[11px] text-primary font-medium hover:underline text-left">
                        {row.count > 0 ? "Add" : "Link"}
                      </button>
                    </div>
                  ))}
                  <div className="px-5 py-2.5">
                    <button onClick={() => setShowRefUpload(true)}
                      className="text-[11px] text-primary font-medium hover:underline">
                      Manage content →
                    </button>
                  </div>
                </div>
              </div>

              {/* Assessment result summary (when available) */}
              {assessment && (
                <div className="bg-card border rounded-xl p-4">
                  <div className="flex items-center gap-4">
                    <ScoreRing score={adjustedScore ?? doc.latest_score} size="sm" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold">
                        {assessment.score_band ?? "—"} · {(adjustedScore ?? assessment.clyira_score)?.toFixed(1)} / 100
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {findings.length} findings · L1–L11 · {timeAgo(assessment.created_at)}
                        {assessment.processing_time_seconds ? ` · ${assessment.processing_time_seconds.toFixed(1)}s` : ""}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                        {[
                          { label: "Crit", count: assessment.findings_critical, sev: "critical" },
                          { label: "High", count: assessment.findings_high, sev: "high" },
                          { label: "Med", count: assessment.findings_medium, sev: "medium" },
                          { label: "Low", count: assessment.findings_low, sev: "low" },
                        ].map(({ label, count, sev }) => {
                          const cfg = getSeverityConfig(sev);
                          return count > 0 ? (
                            <button key={sev}
                              onClick={() => { setActiveTab("findings"); setSeverityFilter(sev); }}
                              className={cn("rounded px-2 py-0.5 hover:opacity-80 transition-opacity", cfg.bg)}>
                              <span className={cn("text-xs font-bold tabular-nums", cfg.color)}>{count}</span>
                              <span className={cn("text-[9px] font-medium ml-1", cfg.color)}>{label}</span>
                            </button>
                          ) : null;
                        })}
                        {(assessment.enforcement_matches ?? 0) > 0 && (
                          <span className="text-[10px] font-medium text-orange-600">
                            {assessment.enforcement_matches} enforcement match{assessment.enforcement_matches !== 1 ? "es" : ""}
                          </span>
                        )}
                      </div>
                    </div>
                    <button onClick={() => setActiveTab("findings")}
                      className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-xs font-medium hover:bg-accent transition-colors shrink-0">
                      View findings <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              )}

              {/* No assessment CTA */}
              {!assessment && !assessing && (
                <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-8 text-center">
                  <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                    <Play className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="font-semibold mb-1">No assessment yet</h3>
                  <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-4">
                    Run the L1–L11 neuro-symbolic engine to identify structural, content, and regulatory compliance gaps.
                  </p>
                  <button onClick={runAssessment}
                    className="px-6 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                    Run Assessment Now
                  </button>
                  <p className="text-xs text-muted-foreground mt-2">
                    Assessing against {selectedFrameworks.length} of {ALL_FRAMEWORK_CODES.length} frameworks
                  </p>
                </div>
              )}
            </div>

            {/* Right column */}
            <div className="space-y-4">
              {/* Document Intelligence */}
              <div className="bg-card border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b">
                  <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Document Intelligence</h3>
                </div>
                <div className="p-4 space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "Document Type", value: doc.dtap_id ? (DTAP_LABEL[doc.dtap_id] ?? doc.dtap_id) : "—" },
                      { label: "Document context", value: doc.dtap_id ? (DTAP_CONTEXT[doc.dtap_id] ?? "—") : "—" },
                      { label: "Self-reference", value: (doc.references?.length ?? 0) > 3 ? "High" : (doc.references?.length ?? 0) > 0 ? "Moderate" : "Low" },
                    ].map(({ label, value }) => (
                      <div key={label} className={label === "Document Type" ? "col-span-2" : ""}>
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{label}</p>
                        <p className="text-xs font-semibold">{value}</p>
                      </div>
                    ))}
                    <div className="col-span-2">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">Confidence</p>
                      {assessment ? (
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-semibold w-8">{Math.min(99, Math.round((assessment.clyira_score ?? 50) * 0.87))}%</p>
                          <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                            <div className="h-full bg-primary rounded-full transition-all"
                              style={{ width: `${Math.min(99, Math.round((assessment.clyira_score ?? 50) * 0.87))}%` }} />
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">—</p>
                      )}
                    </div>
                  </div>

                  {doc.dtap_id && DTAP_REVIEW_ITEMS[doc.dtap_id] && (
                    <div>
                      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1.5">Expected review items</p>
                      <div className="flex flex-wrap gap-1">
                        {DTAP_REVIEW_ITEMS[doc.dtap_id].slice(0, 6).map(item => (
                          <span key={item} className="text-[10px] px-1.5 py-0.5 rounded bg-muted border text-muted-foreground">{item}</span>
                        ))}
                        {DTAP_REVIEW_ITEMS[doc.dtap_id].length > 6 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary font-medium">
                            +{DTAP_REVIEW_ITEMS[doc.dtap_id].length - 6} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Linked Context Kit */}
              <div className="bg-card border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b flex items-center justify-between">
                  <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Linked Context Kit</h3>
                  <button onClick={() => setShowRefUpload(true)} className="text-[10px] text-primary hover:underline font-medium">+ Add</button>
                </div>
                <div className="p-4">
                  {(doc.references?.length ?? 0) === 0 ? (
                    <div className="text-center py-4">
                      <Link2 className="w-7 h-7 text-muted-foreground/25 mx-auto mb-2" />
                      <p className="text-[11px] text-muted-foreground">No linked content items</p>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {doc.references!.slice(0, 4).map((ref: any) => (
                        <div key={ref.id} className="flex items-center gap-2">
                          <FileText className="w-3 h-3 text-muted-foreground shrink-0" />
                          <span className="flex-1 truncate text-[11px] text-muted-foreground">{ref.title}</span>
                          <RefTypeBadge type={ref.reference_type} />
                        </div>
                      ))}
                      {doc.references!.length > 4 && (
                        <button onClick={() => setActiveTab("references")} className="text-[10px] text-primary hover:underline">
                          +{doc.references!.length - 4} more
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Document Details */}
              <div className="bg-card border rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b">
                  <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Document Details</h3>
                </div>
                <div className="p-4 space-y-2.5">
                  {[
                    { label: "File name", value: doc.title },
                    { label: "File type", value: doc.file_type?.toUpperCase() ?? "—" },
                    { label: "Version", value: doc.version ?? "—" },
                    { label: "Uploaded", value: formatDate(doc.created_at) },
                    { label: "Last modified", value: formatDate(doc.created_at) },
                    { label: "Owner", value: doc.department_owner ?? "Demo User (Admin)" },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex items-start justify-between gap-2">
                      <p className="text-[10px] text-muted-foreground shrink-0">{label}</p>
                      <p className="text-[10px] font-medium text-right truncate max-w-[150px]" title={value}>{value}</p>
                    </div>
                  ))}
                  {assessment && (
                    <div className="pt-2 mt-1 border-t">
                      <div className="flex items-start gap-1.5">
                        <ShieldCheck className="w-3 h-3 text-primary mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[10px] text-muted-foreground leading-relaxed">
                            Assessment uses {selectedFrameworks.length} regulatory frameworks
                          </p>
                          <button onClick={() => setActiveTab("regulatory")}
                            className="text-[10px] text-primary hover:underline mt-0.5 block">
                            Adjust in Assessment Settings
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── REFERENCES TAB ────────────────────────────────────────────────── */}
        {activeTab === "references" && (
          <div className="max-w-3xl space-y-4">
            <div className="bg-card border rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b">
                <div>
                  <h2 className="font-semibold flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-muted-foreground" />
                    Custom Validation References
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Upload your SOPs, checklists, or internal standards — Clyira uses these as assessment context
                  </p>
                </div>
                <button onClick={() => setShowRefUpload(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent transition-colors">
                  <Plus className="w-3.5 h-3.5" /> Add Reference
                </button>
              </div>
              {doc.references && doc.references.length > 0 ? (
                <div className="divide-y">
                  {doc.references.map((ref: any) => (
                    <div key={ref.id} className="flex items-center gap-3 px-5 py-3">
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm flex-1 truncate">{ref.title}</span>
                      <RefTypeBadge type={ref.reference_type} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-5 py-10 text-center">
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                    <BookOpen className="w-5 h-5 text-muted-foreground/50" />
                  </div>
                  <p className="text-sm font-medium text-muted-foreground">No references uploaded yet</p>
                  <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
                    Add your organizational guidelines or internal standards to get more accurate, context-aware findings.
                  </p>
                  <button onClick={() => setShowRefUpload(true)}
                    className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-accent transition-colors">
                    <Upload className="w-3.5 h-3.5" /> Upload First Reference
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── REGULATORY SCOPE TAB ─────────────────────────────────────────── */}
        {activeTab === "regulatory" && (
          <div className="max-w-2xl">
            <FrameworkSelectorPanel selected={selectedFrameworks} onChange={setSelectedFrameworks} />
          </div>
        )}

        {/* ── FINDINGS TAB ─────────────────────────────────────────────────── */}
        {activeTab === "findings" && (
          <div className="space-y-4">
            {assessment ? (
              <>
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <h2 className="font-semibold">Assessment Findings</h2>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {findings.filter(f => f.severity !== "info").length} issue{findings.filter(f => f.severity !== "info").length !== 1 ? "s" : ""} · {findings.filter(f => f.severity === "info").length} passed checks · L1–L11
                      {assessment.processing_time_seconds ? ` · ${assessment.processing_time_seconds.toFixed(1)}s` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center rounded-lg border bg-muted/30 p-0.5 gap-0.5">
                      <button onClick={() => setViewMode("list")}
                        className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                          viewMode === "list" ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground")}>
                        <LayoutList className="w-3.5 h-3.5" /> List
                      </button>
                      <button onClick={switchToReview}
                        className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                          viewMode === "review" ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground")}>
                        {loadingText ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSearch className="w-3.5 h-3.5" />}
                        Review
                      </button>
                    </div>
                    {viewMode === "list" && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {["all", "critical", "high", "medium", "low", "info"].map(s => (
                          <button key={s} onClick={() => setSeverityFilter(s)}
                            className={cn("px-3 py-1 rounded-full text-xs font-medium border transition-colors capitalize",
                              severityFilter === s ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent border-border")}>
                            {s === "all"
                              ? `Issues (${findings.filter(f => f.severity !== "info").length})`
                              : s === "info"
                              ? `Passed (${findings.filter(f => f.severity === "info").length})`
                              : `${s.charAt(0).toUpperCase() + s.slice(1)} (${findings.filter(f => f.severity === s).length})`}
                          </button>
                        ))}
                      </div>
                    )}
                    {assessment.status === "completed" && (
                      <div className="flex items-center gap-2">
                        {doc.file_type === "docx" && (
                          <button onClick={exportRedlined} disabled={exporting}
                            title="Download original DOCX with all suggestions inserted as tracked changes"
                            className="flex items-center gap-1.5 px-3 py-1.5 border border-clyira-200 bg-clyira-50 text-clyira-700 rounded-lg text-xs font-medium hover:bg-clyira-100 disabled:opacity-50 transition-colors">
                            {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                            Redlined DOCX
                          </button>
                        )}
                        <button onClick={exportDocx} disabled={exporting}
                          className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent disabled:opacity-50">
                          {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Report
                        </button>
                        <button onClick={exportCsv} disabled={exporting}
                          className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent disabled:opacity-50">
                          {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} CSV
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {viewMode === "review" ? (
                  <div className="bg-card border rounded-xl p-4">
                    <DocumentReviewPane documentText={documentText} fileType={doc.file_type}
                      findings={findings} documentId={id} assessmentId={assessment.id} />
                  </div>
                ) : sortedFindings.length === 0 ? (
                  <div className="bg-green-50 border border-green-200 rounded-xl px-6 py-8 text-center">
                    <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto mb-2" />
                    <p className="font-semibold text-green-800">
                      {severityFilter === "all" ? "No findings — document passed all checks" : `No ${severityFilter} findings`}
                    </p>
                    <p className="text-sm text-green-700 mt-1">
                      {severityFilter === "all" ? "All applicable L1–L11 levels passed." : "Change the filter to see other severity levels."}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {sortedFindings.map(f => (
                      <FindingCard key={f.id} finding={f} documentId={id}
                        assessmentId={assessment.id} onStatusChange={handleFindingStatusChange} />
                    ))}
                  </div>
                )}

                {assessment.status === "completed" && (
                  <QAAssistantPanel documentId={id} assessmentId={assessment.id} />
                )}
              </>
            ) : (
              <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-10 text-center">
                <Play className="w-8 h-8 text-primary mx-auto mb-3" />
                <h3 className="font-semibold mb-1">No findings yet</h3>
                <p className="text-sm text-muted-foreground mb-4">Run an assessment from the Overview tab to generate findings.</p>
                <button onClick={runAssessment} disabled={assessing}
                  className="px-6 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
                  Run Assessment
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── ACTIVITY TAB ─────────────────────────────────────────────────── */}
        {activeTab === "activity" && (
          <div className="max-w-3xl space-y-4">
            <AssessmentHistoryPanel documentId={id} />

            {/* Electronic Signatures */}
            <div className="bg-card border rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b">
                <div className="flex items-center gap-2">
                  <PenLine className="w-4 h-4 text-muted-foreground" />
                  <h2 className="font-semibold text-sm">Electronic Signatures</h2>
                  <span className="text-[10px] text-muted-foreground">21 CFR Part 11 §11.50</span>
                </div>
                <button onClick={() => setShowSignModal(true)}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 border rounded-md hover:bg-accent transition-colors font-medium">
                  <PenLine className="w-3 h-3" /> Sign document
                </button>
              </div>
              {signatures.length === 0 ? (
                <div className="px-5 py-8 text-center">
                  <p className="text-sm text-muted-foreground">No signatures applied yet.</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Electronically sign this document to create a tamper-evident, legally binding record.
                  </p>
                </div>
              ) : (
                <div className="divide-y">
                  {signatures.map((sig) => (
                    <div key={sig.id} className={`px-5 py-4 flex items-start gap-4 ${sig.is_voided ? "opacity-50" : ""}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                        sig.meaning === "approved" ? "bg-green-100" : sig.meaning === "reviewed" ? "bg-blue-100" : "bg-purple-100"}`}>
                        <PenLine className={`w-3.5 h-3.5 ${
                          sig.meaning === "approved" ? "text-green-700" : sig.meaning === "reviewed" ? "text-blue-700" : "text-purple-700"}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-sm font-medium">{sig.user_full_name}</p>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded capitalize ${
                            sig.meaning === "approved" ? "bg-green-100 text-green-700" :
                            sig.meaning === "reviewed" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"}`}>
                            {sig.meaning}
                          </span>
                          {sig.is_voided && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-100 text-red-700">VOIDED</span>}
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">{sig.user_email} · {sig.user_role}</p>
                        {sig.void_reason && <p className="text-xs text-red-600 mt-0.5">Voided: {sig.void_reason}</p>}
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="text-xs text-muted-foreground">{new Date(sig.signed_at).toLocaleString()}</p>
                        {sig.document_version && <p className="text-[10px] font-mono text-muted-foreground/60">v{sig.document_version}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

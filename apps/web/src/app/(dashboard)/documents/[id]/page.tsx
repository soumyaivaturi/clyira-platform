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
} from "lucide-react";
import { documentsApi, assessmentsApi, assistantApi, documentHistoryApi, signaturesApi } from "@/lib/api";
import { DocumentReviewPane } from "@/components/shared/document-review-pane";
import { SignatureModal } from "@/components/shared/signature-modal";
import { ScoreRing, ScoreBadge } from "@/components/shared/score-display";
import { SeverityBadge, LevelBadge, DocStatusBadge, FindingStatusBadge } from "@/components/shared/badges";
import { formatDate, formatFileSize, getSeverityConfig, timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

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

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];

const LEVEL_PROGRESS_LABELS: Record<string, string> = {
  L1: "Structural Integrity", L2: "Document Control", L3: "Quality Logic",
  L4: "Data Integrity", L5: "Data Intelligence", L6: "Cross-Reference",
  L7: "Lifecycle Compliance", L8: "Regulatory Intelligence", L9: "Enforcement",
  L10: "Longitudinal", L11: "Inspection Readiness",
  validating: "Validating findings", scoring: "Calculating score",
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
  const [expanded, setExpanded] = useState(false);

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
    <div className="border rounded-xl overflow-hidden bg-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Regulatory Frameworks</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
            {selected.length} / {ALL_FRAMEWORK_CODES.length} selected
          </span>
        </div>
        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="border-t px-5 py-4 space-y-4">
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
      )}
    </div>
  );
}

// ── Finding Card ───────────────────────────────────────────────────────────────

function FindingCard({
  finding,
  documentId,
  assessmentId,
  onStatusChange,
}: {
  finding: Finding;
  documentId: string;
  assessmentId: string;
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
      const res = await assessmentsApi.actionFinding(
        assessmentId, finding.id, newStatus, "", disputeReason_
      );
      setLocalStatus(newStatus);
      onStatusChange?.(finding.id, newStatus, res.data?.adjusted_score);
    } catch { /* ignore */ }
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
    { status: "resolved", label: "Resolve", icon: CheckCheck, show: ["open","acknowledged","in_progress"].includes(localStatus) },
    { status: "disputed", label: "Dispute", icon: Flag, show: localStatus !== "resolved", isDispute: true },
  ];

  return (
    <>
      {showDisputeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-card border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="font-semibold">Dispute Finding</h3>
            <p className="text-sm text-muted-foreground">{finding.title}</p>
            <textarea
              value={disputeReason}
              onChange={e => setDisputeReason(e.target.value)}
              placeholder="Explain why this finding is inaccurate or should not apply..."
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 min-h-[80px]"
            />
            <div className="flex gap-3">
              <button onClick={() => setShowDisputeModal(false)} className="flex-1 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
              <button
                onClick={() => { doAction("disputed", disputeReason); setShowDisputeModal(false); }}
                disabled={!disputeReason.trim()}
                className="flex-1 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50"
              >
                Submit Dispute
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={cn("border rounded-lg overflow-hidden", cfg.border)}>
        <button
          className={cn("w-full flex items-start gap-3 px-4 py-3 text-left", cfg.bg, "hover:opacity-90 transition-opacity")}
          onClick={() => setExpanded(!expanded)}
        >
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
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200">
                  ↑ Elevated
                </span>
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
            {/* Description */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Description</p>
              <p className="text-sm leading-relaxed">{finding.description}</p>
            </div>

            {/* Evidence */}
            {finding.evidence && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Evidence</p>
                <p className="text-sm text-muted-foreground italic leading-relaxed">"{finding.evidence}"</p>
              </div>
            )}

            {/* Location + Citation */}
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

            {/* Enforcement context */}
            {finding.enforcement_match && finding.enforcement_context && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <p className="text-xs font-semibold text-red-800 mb-1 flex items-center gap-1">
                  <Zap className="w-3 h-3" /> Enforcement Intelligence
                </p>
                <p className="text-xs text-red-700 leading-relaxed">{finding.enforcement_context}</p>
              </div>
            )}

            {/* Remediation */}
            {finding.suggestion_draft && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2.5">
                <p className="text-xs font-semibold text-blue-800 mb-1.5 flex items-center gap-1">
                  <BookOpen className="w-3 h-3" /> Suggested Remediation
                </p>
                <p className="text-sm text-blue-900 leading-relaxed whitespace-pre-wrap">{finding.suggestion_draft}</p>
              </div>
            )}

            {/* Author Assistant — Draft Fix */}
            <div>
              {!draft && (
                <button
                  onClick={loadDraft}
                  disabled={draftLoading}
                  className="flex items-center gap-1.5 text-xs text-primary border border-primary/30 hover:bg-primary/5 rounded-lg px-3 py-1.5 transition-colors"
                >
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

            {/* Dispute reason display */}
            {localStatus === "disputed" && finding.dispute_reason && (
              <div className="bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
                <p className="text-xs font-semibold text-orange-800 mb-0.5">Dispute Reason</p>
                <p className="text-xs text-orange-700">{finding.dispute_reason}</p>
              </div>
            )}

            {/* Action buttons */}
            {localStatus !== "resolved" && (
              <div className="flex items-center gap-2 flex-wrap pt-1 border-t">
                <span className="text-xs text-muted-foreground font-medium">Actions:</span>
                {actioning ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
                ) : (
                  ACTION_BUTTONS.filter(b => b.show).map(btn => (
                    <button
                      key={btn.status}
                      onClick={() => btn.isDispute ? setShowDisputeModal(true) : doAction(btn.status)}
                      className={cn(
                        "flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md border transition-colors",
                        btn.status === "resolved" ? "border-green-300 text-green-700 hover:bg-green-50" :
                        btn.status === "disputed" ? "border-orange-300 text-orange-700 hover:bg-orange-50" :
                        "border-border text-muted-foreground hover:bg-accent",
                      )}
                    >
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

            {/* Confidence */}
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
  { value: "internal_standard",        label: "Internal Standard" },
  { value: "checklist",                label: "Checklist" },
  { value: "template",                 label: "Template" },
];

const REF_TYPE_STYLES: Record<string, string> = {
  organizational_guideline: "bg-blue-50 text-blue-700 border-blue-200",
  internal_standard:        "bg-purple-50 text-purple-700 border-purple-200",
  checklist:                "bg-green-50 text-green-700 border-green-200",
  template:                 "bg-amber-50 text-amber-700 border-amber-200",
};

function RefTypeBadge({ type }: { type: string }) {
  const label = REF_TYPES.find(r => r.value === type)?.label ?? type;
  const style = REF_TYPE_STYLES[type] ?? "bg-muted text-muted-foreground border-border";
  return (
    <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded border", style)}>
      {label}
    </span>
  );
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
      const next = Array.from(incoming).filter(f => !existing.has(f.name));
      return [...prev, ...next];
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    addFiles(e.dataTransfer.files);
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
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-semibold">Upload Validation Reference</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              SOPs, checklists, internal standards — used during the next assessment
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-6 space-y-4">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={cn(
              "border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors",
              dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"
            )}
          >
            <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.doc,.xlsx,.xls"
              className="hidden" onChange={(e) => addFiles(e.target.files)} />
            <FileUp className="w-7 h-7 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium">Drop files or click to browse</p>
            <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, XLSX · multiple files allowed</p>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm bg-muted/40 rounded-lg px-3 py-1.5">
                  <FileText className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                  <span className="flex-1 truncate text-xs">{f.name}</span>
                  <button onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                    className="text-muted-foreground hover:text-foreground">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Reference type */}
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">
              Reference Type
            </label>
            <select value={refType} onChange={(e) => setRefType(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
              {REF_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <p className="text-xs text-muted-foreground mt-1.5">
              {refType === "organizational_guideline" && "Company SOPs, quality manuals, and internal guidance documents"}
              {refType === "internal_standard" && "Internal testing standards, specifications, and method validations"}
              {refType === "checklist" && "Audit checklists, inspection readiness templates, and verification forms"}
              {refType === "template" && "Blank forms, report templates, and document shells"}
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {error}
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
          <input
            type="text"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !loading && ask()}
            placeholder="Ask a compliance question about this document…"
            className="flex-1 px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button
            onClick={ask}
            disabled={loading || !question.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        {error && (
          <p className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded px-3 py-2">{error}</p>
        )}
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
  const latest = scores[0];
  const oldest = scores[scores.length - 1];
  const trend = latest - oldest;
  const color = trend >= 0 ? "#10b981" : "#ef4444";
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
      <button
        onClick={load}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Assessment History</span>
          {history.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
              {history.length} runs
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {scores.length >= 2 && <ScoreSparkline scores={scores} />}
          {loading
            ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            : <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`} />
          }
        </div>
      </button>
      {expanded && history.length > 0 && (
        <div className="border-t divide-y">
          {history.map((h, i) => {
            const prevScore = i < history.length - 1 ? (history[i+1].adjusted_score ?? history[i+1].clyira_score) : null;
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

  const loadSignatures = async () => {
    try {
      const res = await signaturesApi.list(id);
      setSignatures(res.data);
    } catch { /* non-critical */ }
  };

  const switchToReview = async () => {
    setViewMode("review");
    if (documentText) return;
    setLoadingText(true);
    try {
      const res = await documentsApi.getText(id);
      setDocumentText(res.data.text || "");
    } catch { /* non-critical — pane shows "no text" state */ }
    finally { setLoadingText(false); }
  };

  const loadDoc = async () => {
    setLoading(true);
    try {
      const [res] = await Promise.all([
        documentsApi.get(id),
        loadSignatures(),
      ]);
      setDoc(res.data);
      if (res.data.latest_assessment_id) {
        await loadAssessment(res.data.latest_assessment_id);
      }
    } catch (err: any) {
      const status = err?.response?.status;
      setError(status === 404 ? "Document not found." : "Failed to load document. Please refresh.");
    } finally {
      setLoading(false);
    }
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
    } catch {
      setError("Could not load assessment results.");
    }
  };

  const handleFindingStatusChange = useCallback((_findingId: string, _newStatus: string, newAdjustedScore?: number) => {
    if (newAdjustedScore != null) setAdjustedScore(newAdjustedScore);
  }, []);

  const exportDocx = async () => {
    if (!assessment) return;
    setExporting(true);
    try {
      const res = await assessmentsApi.exportDocx(assessment.id);
      const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Clyira_${doc?.title?.slice(0, 30) ?? "Report"}_${assessment.id.slice(0, 8)}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { setError("Export failed. Please try again."); }
    finally { setExporting(false); }
  };

  const pollAssessment = async (assessmentId: string): Promise<void> => {
    const maxAttempts = 90; // 90 × 10s = 15 min ceiling
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 10000));
      try {
        const res = await assessmentsApi.get(assessmentId);
        setAssessment(res.data);
        if (res.data.status === "completed") {
          await loadAssessment(assessmentId);
          // Refresh doc to pick up updated score and status from DB
          try {
            const docRes = await documentsApi.get(id);
            setDoc(docRes.data);
          } catch { /* non-fatal — score ring just won't update */ }
          setAssessing(false);
          return;
        }
        if (res.data.status === "failed") {
          setError("Assessment failed. Please try again.");
          setAssessing(false);
          return;
        }
      } catch { /* continue polling */ }
    }
    setError("Assessment is taking longer than expected. Refresh to check status.");
    setAssessing(false);
  };

  const runAssessment = async () => {
    if (!doc) return;
    setAssessing(true); setError("");
    try {
      const res = await assessmentsApi.run(doc.id, true, selectedFrameworks);
      setAssessment(res.data);
      const status = res.data.status;
      if (status === "queued" || status === "running") {
        // Assessment running in background — poll for completion
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
    ? findings
    : findings.filter(f => f.severity === severityFilter);

  const sortedFindings = [...filteredFindings].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="h-8 bg-muted rounded w-1/3 animate-pulse" />
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="h-32 bg-muted rounded-xl animate-pulse" />)}
        </div>
        <div className="h-64 bg-muted rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!doc) return <div className="text-muted-foreground text-sm">{error || "Document not found."}</div>;

  return (
    <div className="space-y-6">
      {showRefUpload && (
        <UploadReferenceModal
          documentId={id}
          onClose={() => setShowRefUpload(false)}
          onSuccess={() => { setShowRefUpload(false); loadDoc(); }}
        />
      )}
      {showSignModal && doc && (
        <SignatureModal
          documentId={id}
          documentTitle={doc.title}
          onClose={() => setShowSignModal(false)}
          onSigned={() => { setShowSignModal(false); loadSignatures(); }}
        />
      )}

      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/documents" className="hover:text-foreground">Documents</Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="text-foreground font-medium truncate max-w-xs">{doc.title}</span>
      </div>

      {/* Document header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-clyira-50 border border-clyira-100 flex items-center justify-center flex-shrink-0">
            <FileText className="w-6 h-6 text-clyira-600" />
          </div>
          <div>
            <h1 className="text-xl font-semibold leading-tight">{doc.title}</h1>
            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
              {doc.document_number && (
                <span className="text-xs font-mono text-muted-foreground">{doc.document_number} · v{doc.version ?? "1.0"}</span>
              )}
              {doc.document_category && <span className="text-xs font-medium bg-muted px-2 py-0.5 rounded">{doc.document_category}</span>}
              {doc.department_owner && <span className="text-xs text-muted-foreground">{doc.department_owner}</span>}
              {doc.dtap_id && <span className="text-xs font-mono text-muted-foreground/70">{doc.dtap_id}</span>}
              <DocStatusBadge status={doc.status} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {assessment?.status === "completed" && (
            <>
              <button
                onClick={exportDocx}
                disabled={exporting}
                className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm font-medium hover:bg-accent disabled:opacity-50"
              >
                {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                DOCX
              </button>
              <button
                onClick={async () => {
                  if (!assessment) return;
                  setExporting(true);
                  try {
                    const res = await assessmentsApi.exportCsv(assessment.id);
                    const blob = new Blob([res.data], { type: "text/csv" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `Clyira_Findings_${doc?.title?.slice(0, 30) ?? "Report"}_${assessment.id.slice(0, 8)}.csv`;
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch { setError("CSV export failed. Please try again."); }
                  finally { setExporting(false); }
                }}
                disabled={exporting}
                className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm font-medium hover:bg-accent disabled:opacity-50"
              >
                {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                CSV
              </button>
            </>
          )}
          <button
            onClick={() => setShowSignModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm font-medium hover:bg-accent transition-colors"
            title="Electronically sign this document (21 CFR §11.50)"
          >
            <PenLine className="w-4 h-4" />
            Sign
          </button>
        <button onClick={runAssessment} disabled={assessing}
          className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 flex-shrink-0"
          title={`Assess against ${selectedFrameworks.length} frameworks`}>
          {assessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {assessing
            ? assessment?.current_level
              ? `${assessment.current_level}: ${LEVEL_PROGRESS_LABELS[assessment.current_level] ?? "Processing"}…`
              : (assessment?.status === "queued" ? "Queued…" : "Assessing…")
            : assessment ? "Re-assess" : "Run Assessment"}
        </button>
        </div>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* Data Integrity Hold Banner — compact single line */}
      {assessment?.data_integrity_hold && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
          <Lock className="w-3.5 h-3.5 text-red-600 shrink-0" />
          <p className="text-xs font-semibold text-red-800">Data Integrity Hold</p>
          <span className="text-red-300">·</span>
          <p className="text-xs text-red-700 truncate">
            {assessment.suspended_reason || "Critical ALCOA+/Data Integrity finding detected. Score capped at 50 until resolved."}
          </p>
        </div>
      )}

      {/* Score + meta — compact single row */}
      <div className="bg-card border rounded-lg px-4 py-2.5 flex items-center gap-6 flex-wrap">
        {/* Score */}
        <div className="flex items-center gap-3 shrink-0">
          <ScoreRing score={adjustedScore ?? doc.latest_score} size="sm" />
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Score</p>
            {assessment && adjustedScore != null && adjustedScore !== assessment.clyira_score && (
              <p className="text-[10px] text-green-600 font-medium">↑ adj from {assessment.clyira_score?.toFixed(1)}</p>
            )}
            {assessment && (
              <p className="text-[10px] text-muted-foreground">{assessment.levels_run?.length ?? 0} levels · {timeAgo(assessment.created_at)}</p>
            )}
          </div>
        </div>

        <div className="h-8 w-px bg-border shrink-0" />

        {/* Findings summary */}
        {assessment ? (
          <div className="flex items-center gap-1.5">
            {[
              { label: "Crit", count: assessment.findings_critical, sev: "critical" },
              { label: "High", count: assessment.findings_high, sev: "high" },
              { label: "Med", count: assessment.findings_medium, sev: "medium" },
              { label: "Low", count: assessment.findings_low, sev: "low" },
              { label: "Info", count: assessment.findings_info, sev: "info" },
            ].map(({ label, count, sev }) => {
              const cfg = getSeverityConfig(sev);
              return (
                <div key={sev} className={cn("rounded px-2 py-1 text-center min-w-[36px]", count > 0 ? cfg.bg : "bg-muted/30")}>
                  <p className={cn("text-sm font-bold tabular-nums leading-none", count > 0 ? cfg.color : "text-muted-foreground/30")}>{count}</p>
                  <p className={cn("text-[9px] font-medium mt-0.5", count > 0 ? cfg.color : "text-muted-foreground/30")}>{label}</p>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Not yet assessed</p>
        )}

        <div className="h-8 w-px bg-border shrink-0" />

        {/* File info inline */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
          <span><span className="font-medium text-foreground">{doc.file_type?.toUpperCase() ?? "—"}</span> · {formatFileSize(doc.file_size_bytes)}</span>
          <span>Uploaded {formatDate(doc.created_at)}</span>
          <span>{doc.references?.length ?? 0} references</span>
          {assessment?.enforcement_matches ? (
            <span className="font-medium text-orange-600">{assessment.enforcement_matches} enforcement match{assessment.enforcement_matches !== 1 ? "es" : ""}</span>
          ) : null}
        </div>
      </div>

      {/* Findings */}
      {assessment && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="font-semibold">Assessment Findings</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {findings.length} finding{findings.length !== 1 ? "s" : ""} · L1–L11 neuro-symbolic analysis
                {assessment.processing_time_seconds ? ` · ${assessment.processing_time_seconds.toFixed(1)}s` : ""}
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              {/* List / Review toggle */}
              <div className="flex items-center rounded-lg border bg-muted/30 p-0.5 gap-0.5">
                <button
                  onClick={() => setViewMode("list")}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                    viewMode === "list"
                      ? "bg-card shadow-sm text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <LayoutList className="w-3.5 h-3.5" />
                  List
                </button>
                <button
                  onClick={switchToReview}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                    viewMode === "review"
                      ? "bg-card shadow-sm text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {loadingText
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <FileSearch className="w-3.5 h-3.5" />
                  }
                  Review
                </button>
              </div>

              {/* Severity filter — only in list mode */}
              {viewMode === "list" && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  {["all", "critical", "high", "medium", "low"].map(s => (
                    <button key={s} onClick={() => setSeverityFilter(s)}
                      className={cn("px-3 py-1 rounded-full text-xs font-medium border transition-colors capitalize",
                        severityFilter === s ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent border-border")}>
                      {s === "all" ? `All (${findings.length})` : `${s.charAt(0).toUpperCase() + s.slice(1)} (${findings.filter(f => f.severity === s).length})`}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {viewMode === "review" ? (
            <div className="bg-card border rounded-xl p-4">
              <DocumentReviewPane
                documentText={documentText}
                fileType={doc.file_type}
                findings={findings}
                documentId={id}
                assessmentId={assessment.id}
              />
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
                <FindingCard
                  key={f.id}
                  finding={f}
                  documentId={id}
                  assessmentId={assessment.id}
                  onStatusChange={handleFindingStatusChange}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* QA Assistant */}
      {assessment?.status === "completed" && (
        <QAAssistantPanel documentId={id} assessmentId={assessment.id} />
      )}

      {/* Assessment History */}
      <AssessmentHistoryPanel documentId={id} />

      {/* Custom Validation References */}
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
          <button
            onClick={() => setShowRefUpload(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent transition-colors"
          >
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
          <div className="px-5 py-8 text-center">
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
              <BookOpen className="w-5 h-5 text-muted-foreground/50" />
            </div>
            <p className="text-sm font-medium text-muted-foreground">No references uploaded yet</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
              Add your organizational guidelines or internal standards to get more accurate, context-aware findings.
            </p>
            <button
              onClick={() => setShowRefUpload(true)}
              className="mt-4 flex items-center gap-1.5 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-accent transition-colors mx-auto"
            >
              <Upload className="w-3.5 h-3.5" /> Upload First Reference
            </button>
          </div>
        )}
      </div>

      {/* Regulatory Framework Selector (always visible) */}
      <FrameworkSelectorPanel selected={selectedFrameworks} onChange={setSelectedFrameworks} />

      {/* No assessment CTA */}
      {!assessment && !assessing && (
        <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-10 text-center">
          <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
            <Play className="w-6 h-6 text-primary" />
          </div>
          <h3 className="font-semibold mb-1">Ready to assess</h3>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-4">
            Run the L1–L11 neuro-symbolic assessment engine to identify structural, content, and regulatory compliance gaps.
          </p>
          <button onClick={runAssessment}
            className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
            Run Assessment Now
          </button>
          <p className="text-xs text-muted-foreground mt-3">
            Assessing against {selectedFrameworks.length} of {ALL_FRAMEWORK_CODES.length} frameworks
          </p>
        </div>
      )}

      {/* Electronic Signature Manifest */}
      <div className="bg-card border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div className="flex items-center gap-2">
            <PenLine className="w-4 h-4 text-muted-foreground" />
            <h2 className="font-semibold text-sm">Electronic Signatures</h2>
            <span className="text-[10px] text-muted-foreground">21 CFR Part 11 §11.50</span>
          </div>
          <button
            onClick={() => setShowSignModal(true)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 border rounded-md hover:bg-accent transition-colors font-medium"
          >
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
                  sig.meaning === "approved" ? "bg-green-100" :
                  sig.meaning === "reviewed" ? "bg-blue-100" : "bg-purple-100"
                }`}>
                  <PenLine className={`w-3.5 h-3.5 ${
                    sig.meaning === "approved" ? "text-green-700" :
                    sig.meaning === "reviewed" ? "text-blue-700" : "text-purple-700"
                  }`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium">{sig.user_full_name}</p>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded capitalize ${
                      sig.meaning === "approved" ? "bg-green-100 text-green-700" :
                      sig.meaning === "reviewed" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"
                    }`}>
                      {sig.meaning}
                    </span>
                    {sig.is_voided && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-red-100 text-red-700">VOIDED</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{sig.user_email} · {sig.user_role}</p>
                  {sig.void_reason && (
                    <p className="text-xs text-red-600 mt-0.5">Voided: {sig.void_reason}</p>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-xs text-muted-foreground">{new Date(sig.signed_at).toLocaleString()}</p>
                  {sig.document_version && (
                    <p className="text-[10px] font-mono text-muted-foreground/60">v{sig.document_version}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

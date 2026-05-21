"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronRight, FileText, Play, Loader2, AlertTriangle,
  CheckCircle2, ChevronDown, ChevronUp, BookOpen, Zap,
  Upload, Plus, X, FileUp, CheckSquare, Square, ShieldCheck,
} from "lucide-react";
import { documentsApi, assessmentsApi } from "@/lib/api";
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
  status: string; confidence_score?: number; validated: boolean;
}

interface Assessment {
  id: string; document_id: string; status: string; clyira_score?: number;
  score_band?: string; findings_critical: number; findings_high: number;
  findings_medium: number; findings_low: number; findings_info: number;
  enforcement_matches: number; processing_time_seconds?: number;
  levels_run?: string[]; created_at?: string;
}

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];

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

function FindingCard({ finding }: { finding: Finding }) {
  const [expanded, setExpanded] = useState(finding.severity === "critical" || finding.severity === "high");
  const cfg = getSeverityConfig(finding.severity);

  return (
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
            <FindingStatusBadge status={finding.status} className="ml-auto" />
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

          {/* Confidence */}
          {finding.confidence_score != null && (
            <p className="text-[10px] text-muted-foreground">
              Confidence: {(finding.confidence_score * 100).toFixed(0)}% · {finding.validated ? "Validated" : "Unvalidated"}
            </p>
          )}
        </div>
      )}
    </div>
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

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<Document | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [showRefUpload, setShowRefUpload] = useState(false);
  const [error, setError] = useState("");
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>(ALL_FRAMEWORK_CODES);

  const loadDoc = async () => {
    setLoading(true);
    try {
      const res = await documentsApi.get(id);
      setDoc(res.data);
      if (res.data.latest_assessment_id) {
        await loadAssessment(res.data.latest_assessment_id);
      }
    } catch {
      setError("Document not found.");
    } finally {
      setLoading(false);
    }
  };

  const loadAssessment = async (assessmentId: string) => {
    const [aRes, fRes] = await Promise.all([
      assessmentsApi.get(assessmentId),
      assessmentsApi.getFindings(assessmentId),
    ]);
    setAssessment(aRes.data);
    setFindings(fRes.data.findings ?? []);
  };

  const runAssessment = async () => {
    if (!doc) return;
    setAssessing(true); setError("");
    try {
      const res = await assessmentsApi.run(doc.id, true, selectedFrameworks);
      setAssessment(res.data);
      if (res.data.id) await loadAssessment(res.data.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Assessment failed.");
    } finally {
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
        <button onClick={runAssessment} disabled={assessing}
          className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 flex-shrink-0"
          title={`Assess against ${selectedFrameworks.length} frameworks`}>
          {assessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {assessing ? "Assessing…" : assessment ? "Re-assess" : "Run Assessment"}
        </button>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive text-sm rounded-lg px-4 py-3">{error}</div>
      )}

      {/* Score + meta cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card border rounded-xl p-5 flex items-center gap-5">
          <ScoreRing score={doc.latest_score} size="md" />
          <div>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Clyira Score</p>
            {assessment && (
              <>
                <p className="text-xs text-muted-foreground mt-1">
                  {assessment.levels_run?.length ?? 0} levels assessed
                </p>
                <p className="text-xs text-muted-foreground">
                  {timeAgo(assessment.created_at)}
                </p>
              </>
            )}
            {!assessment && <p className="text-xs text-muted-foreground mt-1">Not yet assessed</p>}
          </div>
        </div>

        {assessment ? (
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">Findings Summary</p>
            <div className="grid grid-cols-5 gap-1 text-center">
              {[
                { label: "Crit", count: assessment.findings_critical, sev: "critical" },
                { label: "High", count: assessment.findings_high, sev: "high" },
                { label: "Med", count: assessment.findings_medium, sev: "medium" },
                { label: "Low", count: assessment.findings_low, sev: "low" },
                { label: "Info", count: assessment.findings_info, sev: "info" },
              ].map(({ label, count, sev }) => {
                const cfg = getSeverityConfig(sev);
                return (
                  <div key={sev} className={cn("rounded-lg py-2 px-1", count > 0 ? cfg.bg : "bg-muted/30")}>
                    <p className={cn("text-lg font-bold tabular-nums", count > 0 ? cfg.color : "text-muted-foreground/40")}>{count}</p>
                    <p className={cn("text-[10px] font-medium", count > 0 ? cfg.color : "text-muted-foreground/40")}>{label}</p>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="bg-card border rounded-xl p-5 flex flex-col items-center justify-center text-center">
            <Play className="w-8 h-8 text-muted-foreground/30 mb-2" />
            <p className="text-sm font-medium">No assessment yet</p>
            <p className="text-xs text-muted-foreground mt-0.5">Run the L1–L11 engine to get findings</p>
          </div>
        )}

        <div className="bg-card border rounded-xl p-5">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">File Info</p>
          <div className="space-y-1.5">
            {[
              ["Type", doc.file_type?.toUpperCase() ?? "—"],
              ["Size", formatFileSize(doc.file_size_bytes)],
              ["Uploaded", formatDate(doc.created_at)],
              ["References", `${doc.references?.length ?? 0} attached`],
              ...(assessment?.enforcement_matches ? [["Enforcement", `${assessment.enforcement_matches} match${assessment.enforcement_matches !== 1 ? "es" : ""}`]] : []),
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{k}</span>
                <span className="text-xs font-medium">{v}</span>
              </div>
            ))}
          </div>
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
            <div className="flex items-center gap-1.5 flex-wrap">
              {["all", "critical", "high", "medium", "low"].map(s => (
                <button key={s} onClick={() => setSeverityFilter(s)}
                  className={cn("px-3 py-1 rounded-full text-xs font-medium border transition-colors capitalize",
                    severityFilter === s ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent border-border")}>
                  {s === "all" ? `All (${findings.length})` : `${s.charAt(0).toUpperCase() + s.slice(1)} (${findings.filter(f => f.severity === s).length})`}
                </button>
              ))}
            </div>
          </div>

          {sortedFindings.length === 0 ? (
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
              {sortedFindings.map(f => <FindingCard key={f.id} finding={f} />)}
            </div>
          )}
        </div>
      )}

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
    </div>
  );
}

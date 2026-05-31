"use client";

import { useEffect, useState, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  FileText, Upload, Plus, Search, X, Loader2, FileUp, Sparkles,
  AlertCircle, ChevronRight, CheckSquare, Square, ChevronDown,
  ChevronUp, MoreHorizontal, Settings2, LayoutList, Check,
  Clock, AlertTriangle, CheckCircle2, Play, RotateCcw, RefreshCw,
  Archive, Download, Copy, MessageSquare, Eye, Columns, SlidersHorizontal,
  CalendarDays, User, Tag, Filter,
} from "lucide-react";
import { documentsApi, assessmentsApi } from "@/lib/api";
import { ScoreBadge } from "@/components/shared/score-display";
import { EmptyState, LoadingRows } from "@/components/shared/empty-state";
import { formatDate, formatFileSize, timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

// ── Constants ──────────────────────────────────────────────────────────────────

const FRAMEWORK_GROUPS = [
  { group: "FDA", items: [
    { code: "FDA_21CFR211", label: "21 CFR Part 211", description: "Current GMP — Finished Pharmaceuticals" },
    { code: "FDA_21CFR820", label: "21 CFR Part 820", description: "Quality System Regulation — Medical Devices" },
    { code: "FDA_21CFR11",  label: "21 CFR Part 11",  description: "Electronic Records and Signatures" },
    { code: "FDA_PV2011",   label: "FDA Process Validation (2011)", description: "Guidance for Industry" },
    { code: "FDA_ASEPTIC",  label: "FDA Aseptic Processing (2004)", description: "Sterile Drug Products" },
    { code: "FDA_483",      label: "FDA 483 Observations", description: "Inspectional observations database" },
    { code: "FDA_WL",       label: "FDA Warning Letters", description: "Published warning letter citations" },
  ]},
  { group: "ICH", items: [
    { code: "ICH_Q10", label: "ICH Q10", description: "Pharmaceutical Quality System" },
    { code: "ICH_Q9",  label: "ICH Q9",  description: "Quality Risk Management" },
    { code: "ICH_Q8",  label: "ICH Q8(R2)", description: "Pharmaceutical Development" },
    { code: "ICH_Q7",  label: "ICH Q7",  description: "GMP for Active Pharmaceutical Ingredients" },
    { code: "ICH_E6R2",label: "ICH E6(R2)", description: "Good Clinical Practice" },
  ]},
  { group: "EMA / EU", items: [
    { code: "EU_GMP_PART1", label: "EU GMP Part I",   description: "Basic Requirements for Medicinal Products" },
    { code: "EU_GMP_PART2", label: "EU GMP Part II",  description: "Basic Requirements for Active Substances" },
    { code: "EU_ANNEX1",    label: "EU GMP Annex 1",  description: "Manufacture of Sterile Medicinal Products" },
    { code: "EU_ANNEX11",   label: "EU GMP Annex 11", description: "Computerised Systems" },
  ]},
  { group: "ISO", items: [
    { code: "ISO_13485", label: "ISO 13485:2016", description: "Medical Devices Quality Management Systems" },
    { code: "ISO_14971", label: "ISO 14971:2019", description: "Risk Management for Medical Devices" },
    { code: "ISO_9001",  label: "ISO 9001:2015",  description: "Quality Management Systems" },
  ]},
];
const ALL_FRAMEWORK_CODES = FRAMEWORK_GROUPS.flatMap(g => g.items.map(i => i.code));

const DOC_CATEGORIES = ["SOP", "CAPA", "ATM", "Deviation", "LIR", "Validation", "Protocol", "Report", "Other"];
const DEPARTMENTS = ["Quality Assurance", "Quality Control", "Manufacturing", "Validation", "Regulatory Affairs", "Research & Development", "Clinical & Safety"];

const LIFECYCLE_VALUES = ["Draft", "Authoring", "In Author Review", "In QA Review", "Approved", "Effective", "Obsolete", "Archived"];
const ASSESSMENT_VALUES = ["Not Assessed", "Queued", "Assessing", "Assessed", "Needs Review", "Reassessment Needed", "Assessment Failed"];

// ── Types ──────────────────────────────────────────────────────────────────────

interface Document {
  id: string;
  title: string;
  document_number?: string;
  version?: string;
  document_category?: string;
  department_owner?: string;
  dtap_id?: string;
  file_type?: string;
  file_size_bytes?: number;
  status: string;
  latest_score?: number | null;
  adjusted_score?: number | null;
  latest_assessment_id?: string;
  findings_critical?: number;
  findings_high?: number;
  findings_medium?: number;
  findings_low?: number;
  created_at?: string;
  updated_at?: string;
}

type TabId = "all" | "attention" | "assessments" | "authoring" | "review" | "approved" | "archived";
type SortDir = "asc" | "desc";
type ColKey = "document" | "type" | "lifecycle" | "assessment" | "score" | "owner" | "dueDate" | "version" | "source" | "lastActivity" | "openItems" | "actions";

const COLUMN_DEFS: Record<ColKey, { label: string; width: string; sortable: boolean }> = {
  document:     { label: "Document",      width: "minmax(220px,1fr)", sortable: true  },
  type:         { label: "Type",          width: "90px",              sortable: true  },
  lifecycle:    { label: "Lifecycle",     width: "130px",             sortable: true  },
  assessment:   { label: "Assessment",    width: "140px",             sortable: true  },
  score:        { label: "Score / Findings", width: "120px",          sortable: true  },
  openItems:    { label: "Open Items",    width: "120px",             sortable: false },
  owner:        { label: "Owner",         width: "130px",             sortable: true  },
  dueDate:      { label: "Due Date",      width: "110px",             sortable: true  },
  version:      { label: "Version",       width: "80px",              sortable: false },
  source:       { label: "Source",        width: "110px",             sortable: false },
  lastActivity: { label: "Last Activity", width: "130px",             sortable: true  },
  actions:      { label: "",              width: "40px",              sortable: false },
};

const DEFAULT_COLS: ColKey[] = ["document", "type", "lifecycle", "assessment", "score", "owner", "dueDate", "actions"];
const OPTIONAL_COLS: ColKey[] = ["openItems", "version", "source", "lastActivity"];
const COLS_KEY = "clyira_doc_cols_v2";

// ── Helpers ────────────────────────────────────────────────────────────────────

function getLifecycle(doc: Document): string {
  const s = doc.status?.toLowerCase();
  if (s === "archived") return "Archived";
  if (s === "approved" || s === "effective") return "Effective";
  if (s === "review") return "In QA Review";
  if (s === "draft") return "Draft";
  if (s === "processing" || s === "uploading") return "Authoring";
  if (s === "ready") return doc.latest_score != null ? "Effective" : "Authoring";
  return "Draft";
}

function getLifecycleStyle(lc: string) {
  const map: Record<string, string> = {
    "Draft":           "bg-gray-100 text-gray-600 border-gray-200",
    "Authoring":       "bg-blue-50 text-blue-700 border-blue-200",
    "In Author Review":"bg-amber-50 text-amber-700 border-amber-200",
    "In QA Review":    "bg-orange-50 text-orange-700 border-orange-200",
    "Approved":        "bg-green-50 text-green-700 border-green-200",
    "Effective":       "bg-emerald-50 text-emerald-700 border-emerald-200",
    "Obsolete":        "bg-gray-50 text-gray-400 border-gray-200",
    "Archived":        "bg-gray-50 text-gray-400 border-gray-200",
  };
  return map[lc] ?? "bg-gray-100 text-gray-600 border-gray-200";
}

function getAssessmentStatus(doc: Document): string {
  if (!doc.latest_score && doc.latest_score !== 0) return "Not Assessed";
  if (doc.latest_score < 50) return "Needs Review";
  return "Assessed";
}

function getAssessmentStyle(status: string) {
  const map: Record<string, string> = {
    "Not Assessed":        "bg-gray-100 text-gray-500 border-gray-200",
    "Queued":              "bg-blue-50 text-blue-700 border-blue-200",
    "Assessing":           "bg-violet-50 text-violet-700 border-violet-200",
    "Assessed":            "bg-green-50 text-green-700 border-green-200",
    "Needs Review":        "bg-amber-50 text-amber-700 border-amber-200",
    "Reassessment Needed": "bg-orange-50 text-orange-700 border-orange-200",
    "Assessment Failed":   "bg-red-50 text-red-700 border-red-200",
  };
  return map[status] ?? "bg-gray-100 text-gray-500 border-gray-200";
}

function getSource(doc: Document): string {
  if (doc.file_type) return `Uploaded ${doc.file_type.toUpperCase()}`;
  if (!doc.file_type && doc.status === "draft") return "AI Authored";
  return "Uploaded";
}

function getSourceStyle(source: string) {
  if (source.startsWith("Uploaded")) return "text-blue-600";
  if (source === "AI Authored") return "text-violet-600";
  if (source === "Template") return "text-indigo-600";
  return "text-gray-500";
}

function formatFindings(doc: Document): string | null {
  const c = doc.findings_critical;
  const h = doc.findings_high;
  const m = doc.findings_medium;
  const l = doc.findings_low;
  if (c == null && h == null) return null;
  const parts = [];
  if (c) parts.push(`C${c}`);
  if (h) parts.push(`H${h}`);
  if (m) parts.push(`M${m}`);
  if (l) parts.push(`L${l}`);
  return parts.length ? parts.join(" ") : null;
}

function getDueDateStyle(due?: string): "overdue" | "soon" | "ok" | "none" {
  if (!due) return "none";
  const d = new Date(due);
  const now = new Date();
  const diffDays = (d.getTime() - now.getTime()) / 86400000;
  if (diffDays < 0) return "overdue";
  if (diffDays <= 3) return "soon";
  return "ok";
}

function savedCols(): ColKey[] {
  try {
    const raw = localStorage.getItem(COLS_KEY);
    if (!raw) return DEFAULT_COLS;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) return (parsed as string[]) as ColKey[];
  } catch {}
  return DEFAULT_COLS;
}

// ── UploadModal ────────────────────────────────────────────────────────────────

function UploadModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [department, setDepartment] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [fwExpanded, setFwExpanded] = useState(false);
  const [selectedFw, setSelectedFw] = useState<string[]>(ALL_FRAMEWORK_CODES);
  const inputRef = useRef<HTMLInputElement>(null);

  const toggleFw = (code: string) =>
    setSelectedFw(p => p.includes(code) ? p.filter(c => c !== code) : [...p, code]);
  const toggleGroup = (codes: string[]) => {
    const all = codes.every(c => selectedFw.includes(c));
    setSelectedFw(p => all ? p.filter(c => !codes.includes(c)) : Array.from(new Set([...p, ...codes])));
  };
  const handleFile = (f: File) => { setFile(f); setTitle(f.name.replace(/\.[^.]+$/, "")); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0]; if (f) handleFile(f);
  };
  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true); setError("");
    const fd = new FormData();
    fd.append("file", file); fd.append("title", title || file.name);
    if (category) fd.append("document_category", category);
    if (department) fd.append("department_owner", department);
    fd.append("regulatory_frameworks", JSON.stringify(selectedFw));
    try {
      const res = await documentsApi.upload(fd, setProgress);
      onSuccess(res.data.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Upload failed.");
    } finally { setUploading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0">
          <div><h2 className="font-semibold">Upload Document</h2>
            <p className="text-xs text-muted-foreground mt-0.5">PDF, DOCX, or XLSX · Max 50 MB</p></div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          <div onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
            onDrop={handleDrop} onClick={() => inputRef.current?.click()}
            className={cn("border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
              dragging ? "border-primary bg-primary/5" : file ? "border-green-300 bg-green-50" : "border-border hover:border-primary/50 hover:bg-muted/30")}>
            <input ref={inputRef} type="file" accept=".pdf,.docx,.doc,.xlsx,.xls" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileText className="w-8 h-8 text-green-600" />
                <p className="text-sm font-medium text-green-700">{file.name}</p>
                <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <FileUp className="w-8 h-8 text-muted-foreground" />
                <p className="text-sm font-medium">Drop file here or click to browse</p>
                <p className="text-xs text-muted-foreground">PDF, DOCX, XLSX</p>
              </div>
            )}
          </div>
          {file && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Document Title</label>
                <input value={title} onChange={e => setTitle(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Category</label>
                  <select value={category} onChange={e => setCategory(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                    <option value="">Auto-detect</option>
                    {DOC_CATEGORIES.map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Department</label>
                  <select value={department} onChange={e => setDepartment(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                    <option value="">Select dept.</option>
                    {DEPARTMENTS.map(d => <option key={d}>{d}</option>)}
                  </select>
                </div>
              </div>
              <div className="border rounded-lg overflow-hidden">
                <button type="button" onClick={() => setFwExpanded(v => !v)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Regulatory Frameworks</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                      {selectedFw.length}/{ALL_FRAMEWORK_CODES.length}
                    </span>
                  </div>
                  <ChevronRight className={cn("w-3.5 h-3.5 text-muted-foreground transition-transform", fwExpanded && "rotate-90")} />
                </button>
                {fwExpanded && (
                  <div className="p-4 space-y-4 max-h-64 overflow-y-auto border-t">
                    {FRAMEWORK_GROUPS.map(group => {
                      const codes = group.items.map(i => i.code);
                      const allSel = codes.every(c => selectedFw.includes(c));
                      return (
                        <div key={group.group}>
                          <button type="button" onClick={() => toggleGroup(codes)} className="flex items-center gap-2 mb-2">
                            {allSel ? <CheckSquare className="w-3.5 h-3.5 text-primary flex-shrink-0" /> : <Square className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />}
                            <span className="text-xs font-semibold">{group.group}</span>
                          </button>
                          <div className="grid gap-1 pl-5">
                            {group.items.map(item => (
                              <label key={item.code} className="flex items-start gap-2 cursor-pointer">
                                <input type="checkbox" checked={selectedFw.includes(item.code)} onChange={() => toggleFw(item.code)} className="mt-0.5 accent-primary flex-shrink-0" />
                                <span className="text-xs font-medium">{item.label} <span className="text-muted-foreground font-normal">{item.description}</span></span>
                              </label>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
          {uploading && (
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted-foreground">Uploading…</span>
                <span className="font-medium">{progress}%</span>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}
          {error && <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2"><AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />{error}</div>}
        </div>
        <div className="px-6 pb-6 flex gap-3 flex-shrink-0 border-t pt-4">
          <button onClick={onClose} className="flex-1 py-2.5 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button onClick={handleSubmit} disabled={!file || uploading}
            className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {uploading && <Loader2 className="w-4 h-4 animate-spin" />} Upload & Classify
          </button>
        </div>
      </div>
    </div>
  );
}

// ── CreateDocumentModal ────────────────────────────────────────────────────────

function CreateDocumentModal({ onClose, onSuccess, initialType = "SOP" }: { onClose: () => void; onSuccess: () => void; initialType?: string }) {
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState(initialType);
  const [department, setDepartment] = useState("");
  const [instructions, setInstructions] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!title.trim()) { setError("Title is required"); return; }
    setCreating(true); setError("");
    const fd = new FormData();
    fd.append("document_type", docType); fd.append("title", title);
    if (department) fd.append("department", department);
    if (instructions) fd.append("instructions", instructions);
    try { await documentsApi.create(fd); onSuccess(); }
    catch (err: any) { setError(err?.response?.data?.detail ?? "Creation failed."); }
    finally { setCreating(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-primary" />
            </div>
            <div><h2 className="font-semibold">Create Document</h2>
              <p className="text-xs text-muted-foreground">AI-generated compliant document scaffold</p></div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Document Title *</label>
            <input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. SOP for Aseptic Gowning Procedure"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Document Type</label>
              <select value={docType} onChange={e => setDocType(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                {DOC_CATEGORIES.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Department</label>
              <select value={department} onChange={e => setDepartment(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                <option value="">Select dept.</option>
                {DEPARTMENTS.map(d => <option key={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Instructions <span className="normal-case font-normal text-muted-foreground/60">(optional)</span></label>
            <textarea value={instructions} onChange={e => setInstructions(e.target.value)} rows={3}
              placeholder="e.g. Include ISO 13485 references. Focus on small-scale API synthesis."
              className="w-full px-3 py-2 border rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
            AI drafting requires an Anthropic API key. A structured scaffold will be created and queued for AI drafting.
          </div>
          {error && <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">{error}</div>}
        </div>
        <div className="px-6 pb-6 flex gap-3">
          <button onClick={onClose} className="flex-1 py-2.5 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button onClick={handleSubmit} disabled={creating || !title.trim()}
            className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {creating && <Loader2 className="w-4 h-4 animate-spin" />}
            <Sparkles className="w-3.5 h-3.5" /> Create Document
          </button>
        </div>
      </div>
    </div>
  );
}

// ── ColumnPicker ───────────────────────────────────────────────────────────────

function ColumnPicker({ cols, onChange, onReset }: {
  cols: ColKey[]; onChange: (c: ColKey[]) => void; onReset: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const toggle = (key: ColKey) => {
    if (key === "document" || key === "actions") return;
    const next: ColKey[] = cols.includes(key) ? cols.filter(c => c !== key) : [...cols.filter(c => c !== "actions"), key, "actions"];
    onChange(next);
  };

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(v => !v)}
        className={cn("flex items-center gap-1.5 px-2.5 py-1.5 border rounded-md text-xs font-medium transition-colors",
          open ? "bg-primary/10 border-primary/30 text-primary" : "hover:bg-accent text-muted-foreground")}>
        <Columns className="w-3.5 h-3.5" /> Columns
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-52 bg-card border rounded-xl shadow-lg z-30 overflow-hidden">
          <div className="px-3 py-2 border-b bg-muted/30 flex items-center justify-between">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Visible columns</span>
            <button onClick={() => { onReset(); setOpen(false); }} className="text-[10px] text-primary hover:underline">Reset</button>
          </div>
          <div className="py-1 max-h-64 overflow-y-auto">
            {(Object.keys(COLUMN_DEFS) as ColKey[]).filter(k => k !== "actions").map(key => {
              const locked = key === "document";
              const active = cols.includes(key);
              return (
                <button key={key} onClick={() => toggle(key)} disabled={locked}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-xs hover:bg-accent transition-colors disabled:opacity-40">
                  <div className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0",
                    active ? "bg-primary border-primary" : "border-border")}>
                    {active && <Check className="w-2.5 h-2.5 text-primary-foreground" />}
                  </div>
                  <span className={cn("font-medium", locked && "text-muted-foreground")}>{COLUMN_DEFS[key].label}</span>
                  {locked && <span className="ml-auto text-[9px] text-muted-foreground">locked</span>}
                  {OPTIONAL_COLS.includes(key) && !locked && <span className="ml-auto text-[9px] text-muted-foreground/60">optional</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── RowActionMenu ──────────────────────────────────────────────────────────────

function RowActionMenu({ doc, onAssess, onArchive }: {
  doc: Document; onAssess: () => void; onArchive: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const hasAssessment = doc.latest_score != null;

  const actions = [
    { label: "Open", icon: Eye, action: () => router.push(`/documents/${doc.id}`) },
    { label: hasAssessment ? "Re-run Assessment" : "Run Assessment", icon: hasAssessment ? RefreshCw : Play, action: () => { onAssess(); setOpen(false); } },
    { label: "View Findings", icon: AlertTriangle, action: () => router.push(`/documents/${doc.id}#findings`), disabled: !hasAssessment },
    { label: "Add Comment", icon: MessageSquare, action: () => router.push(`/documents/${doc.id}`) },
    { label: "Open in Review Editor", icon: FileText, action: () => router.push(`/documents/${doc.id}`), comingSoon: true },
    { type: "divider" as const },
    { label: "Download Redlined DOCX", icon: Download, action: () => router.push(`/documents/${doc.id}`), disabled: !hasAssessment || doc.file_type !== "docx" },
    { label: "Download Clean DOCX", icon: Download, action: () => {}, comingSoon: true },
    { label: "View Version History", icon: RotateCcw, action: () => router.push(`/documents/${doc.id}#activity`), comingSoon: true },
    { label: "Duplicate", icon: Copy, action: () => {}, comingSoon: true },
    { type: "divider" as const },
    { label: "Archive", icon: Archive, action: () => { onArchive(); setOpen(false); }, danger: true },
  ];

  return (
    <div className="relative" ref={ref} onClick={e => e.stopPropagation()}>
      <button onClick={() => setOpen(v => !v)}
        className={cn("w-7 h-7 flex items-center justify-center rounded-md transition-colors opacity-0 group-hover:opacity-100",
          open ? "opacity-100 bg-accent" : "hover:bg-accent")}>
        <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-52 bg-card border rounded-xl shadow-xl z-40 overflow-hidden">
          <div className="py-1">
            {actions.map((item, i) => {
              if (item.type === "divider") return <div key={i} className="h-px bg-border my-1" />;
              return (
                <button key={item.label} onClick={() => { if (!item.comingSoon && !item.disabled) { item.action(); setOpen(false); } }}
                  disabled={item.disabled || item.comingSoon}
                  className={cn("w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors",
                    item.danger ? "text-destructive hover:bg-destructive/10" : "hover:bg-accent",
                    (item.disabled || item.comingSoon) && "opacity-40 cursor-default")}>
                  <item.icon className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="flex-1">{item.label}</span>
                  {item.comingSoon && <span className="text-[9px] text-muted-foreground border border-border rounded px-1">soon</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page Content ──────────────────────────────────────────────────────────

function DocumentsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Data
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [toast, setToast] = useState("");

  // UI state
  const [activeTab, setActiveTab] = useState<TabId>("all");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState(searchParams?.get("document_category") ?? "");
  const [deptFilter, setDeptFilter] = useState(searchParams?.get("department_owner") ?? "");
  const [assessFilter, setAssessFilter] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [sortCol, setSortCol] = useState<string>("lastActivity");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [visibleCols, setVisibleCols] = useState<ColKey[]>(DEFAULT_COLS);

  // Modals
  const [showUpload, setShowUpload] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createType, setCreateType] = useState("SOP");
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const [showBulkMenu, setShowBulkMenu] = useState(false);
  const [bulkRunning, setBulkRunning] = useState(false);

  const createMenuRef = useRef<HTMLDivElement>(null);
  const bulkMenuRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load column prefs from localStorage once on mount
  useEffect(() => { setVisibleCols(savedCols()); }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (createMenuRef.current && !createMenuRef.current.contains(e.target as Node)) setShowCreateMenu(false);
      if (bulkMenuRef.current && !bulkMenuRef.current.contains(e.target as Node)) setShowBulkMenu(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  useEffect(() => () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current); }, []);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 4000); };

  const load = useCallback(async () => {
    setLoading(true); setLoadError("");
    try {
      const res = await documentsApi.list({
        ...(typeFilter ? { document_category: typeFilter } : {}),
        ...(deptFilter ? { department_owner: deptFilter } : {}),
      });
      setDocuments(res.data.documents ?? []);
    } catch { setLoadError("Could not load documents. Please refresh."); }
    finally { setLoading(false); }
  }, [typeFilter, deptFilter]);

  useEffect(() => { load(); }, [load]);

  const saveCols = (cols: ColKey[]) => {
    setVisibleCols(cols);
    try { localStorage.setItem(COLS_KEY, JSON.stringify(cols)); } catch {}
  };
  const resetCols = () => saveCols(DEFAULT_COLS);

  // Sorting
  const handleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("asc"); }
  };

  // Tab filtering
  const tabFiltered = documents.filter(doc => {
    const lc = getLifecycle(doc);
    switch (activeTab) {
      case "attention":
        return doc.latest_score == null || (doc.latest_score != null && doc.latest_score < 70);
      case "assessments":
        return doc.latest_score != null;
      case "authoring":
        return ["Authoring", "Draft"].includes(lc) || (doc.status === "processing");
      case "review":
        return ["In Author Review", "In QA Review"].includes(lc);
      case "approved":
        return ["Approved", "Effective"].includes(lc);
      case "archived":
        return lc === "Archived" || doc.status === "archived";
      default:
        return true;
    }
  });

  // Search + assessment filter
  const filtered = tabFiltered.filter(doc => {
    const q = search.toLowerCase();
    const matchesSearch = !q || doc.title.toLowerCase().includes(q)
      || (doc.document_number ?? "").toLowerCase().includes(q)
      || (doc.document_category ?? "").toLowerCase().includes(q)
      || (doc.department_owner ?? "").toLowerCase().includes(q);
    const assessStatus = getAssessmentStatus(doc);
    const matchesAssess = !assessFilter || assessStatus === assessFilter;
    return matchesSearch && matchesAssess;
  });

  // Sorting
  const sorted = [...filtered].sort((a, b) => {
    let va: any = "", vb: any = "";
    switch (sortCol) {
      case "document":     va = a.title; vb = b.title; break;
      case "type":         va = a.document_category ?? ""; vb = b.document_category ?? ""; break;
      case "lifecycle":    va = getLifecycle(a); vb = getLifecycle(b); break;
      case "assessment":   va = getAssessmentStatus(a); vb = getAssessmentStatus(b); break;
      case "score":        va = a.adjusted_score ?? a.latest_score ?? -1; vb = b.adjusted_score ?? b.latest_score ?? -1; break;
      case "owner":        va = a.department_owner ?? ""; vb = b.department_owner ?? ""; break;
      case "lastActivity": va = a.updated_at ?? a.created_at ?? ""; vb = b.updated_at ?? b.created_at ?? ""; break;
      default: va = a.updated_at ?? a.created_at ?? ""; vb = b.updated_at ?? b.created_at ?? "";
    }
    if (va < vb) return sortDir === "asc" ? -1 : 1;
    if (va > vb) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  // Selection
  const allSelected = sorted.length > 0 && sorted.every(d => selectedIds.has(d.id));
  const someSelected = selectedIds.size > 0;
  const toggleAll = () => {
    if (allSelected) setSelectedIds(new Set());
    else setSelectedIds(new Set(sorted.map(d => d.id)));
  };
  const toggleRow = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // Assess selected
  const assessSelected = async (docIds?: string[]) => {
    setBulkRunning(true);
    try {
      const res = await assessmentsApi.bulkRun(docIds ? Array.from(docIds) : undefined);
      const count = res.data.queued ?? 0;
      showToast(count > 0 ? `${count} assessment${count !== 1 ? "s" : ""} queued` : "No un-assessed documents found.");
      setSelectedIds(new Set());
    } catch { showToast("Failed to queue assessments."); }
    finally { setBulkRunning(false); }
  };

  // Grid template from selected columns
  const gridCols = visibleCols.map(k => COLUMN_DEFS[k].width).join(" ");
  const gridStyle = { gridTemplateColumns: `28px ${gridCols}` };

  // Tabs
  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: "all",        label: "All Documents",      count: documents.length },
    { id: "attention",  label: "Needs My Attention", count: documents.filter(d => d.latest_score == null || (d.latest_score != null && d.latest_score < 70)).length || undefined },
    { id: "assessments",label: "Assessments",        count: documents.filter(d => d.latest_score != null).length || undefined },
    { id: "authoring",  label: "Authoring" },
    { id: "review",     label: "Review Queue" },
    { id: "approved",   label: "Approved",           count: documents.filter(d => ["Approved", "Effective"].includes(getLifecycle(d))).length || undefined },
    { id: "archived",   label: "Archived" },
  ];

  // Create Document menu items
  const createItems = [
    { label: "AI Draft", icon: Sparkles, type: "SOP", impl: true, purple: true },
    { type: "divider" },
    { label: "SOP",                        icon: FileText, type: "SOP",        impl: false },
    { label: "CAPA",                       icon: FileText, type: "CAPA",       impl: false },
    { label: "Deviation",                  icon: FileText, type: "Deviation",  impl: false },
    { label: "Lab Investigation",          icon: FileText, type: "LIR",        impl: false },
    { label: "Test Method",                icon: FileText, type: "ATM",        impl: false },
    { label: "Validation Protocol",        icon: FileText, type: "Validation", impl: false },
    { label: "Batch Record Review Memo",   icon: FileText, type: "Report",     impl: false },
    { label: "Inspection Response",        icon: FileText, type: "Other",      impl: false },
    { type: "divider" },
    { label: "From Template",              icon: Copy,     type: "",           impl: false },
    { label: "Import from QMS / EDMS",     icon: Tag,      type: "",           impl: false },
  ];

  const SortIndicator = ({ col }: { col: string }) => (
    sortCol !== col ? null :
    sortDir === "asc" ? <ChevronUp className="w-3 h-3 inline-block ml-0.5" /> : <ChevronDown className="w-3 h-3 inline-block ml-0.5" />
  );

  const activeFilterCount = [typeFilter, deptFilter, assessFilter].filter(Boolean).length;

  return (
    <div className="-mx-5 -mt-4 flex flex-col h-screen overflow-hidden bg-muted/20">
      {/* Modals */}
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSuccess={id => { setShowUpload(false); router.push(`/documents/${id}`); }} />}
      {showCreate && <CreateDocumentModal onClose={() => setShowCreate(false)} onSuccess={() => { setShowCreate(false); load(); }} initialType={createType} />}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-foreground text-background text-sm px-4 py-2.5 rounded-xl shadow-lg flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-400" /> {toast}
        </div>
      )}

      {/* ── Header ───────────────────────────── */}
      <div className="bg-card border-b px-5 py-3 flex items-center justify-between gap-4 flex-shrink-0">
        <div>
          <h1 className="text-base font-semibold tracking-tight">Documents</h1>
          <p className="text-[11px] text-muted-foreground">Controlled document workbench · {documents.length} document{documents.length !== 1 ? "s" : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Bulk Actions */}
          <div className="relative" ref={bulkMenuRef}>
            <button
              onClick={() => someSelected && setShowBulkMenu(v => !v)}
              className={cn("flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors",
                someSelected ? "hover:bg-accent text-foreground" : "opacity-40 cursor-default text-muted-foreground")}>
              {bulkRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LayoutList className="w-3.5 h-3.5" />}
              Bulk Actions
              {someSelected && <span className="bg-primary text-primary-foreground text-[10px] px-1.5 py-0.5 rounded-full font-semibold">{selectedIds.size}</span>}
              <ChevronDown className="w-3 h-3" />
            </button>
            {showBulkMenu && someSelected && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-card border rounded-xl shadow-lg z-30 py-1 overflow-hidden">
                {[
                  { label: "Run Assessment", icon: Play, action: () => { assessSelected(Array.from(selectedIds)); setShowBulkMenu(false); }, impl: true },
                  { label: "Assign Owner",    icon: User,         impl: false },
                  { label: "Assign Reviewer", icon: User,         impl: false },
                  { label: "Change Department",icon: Tag,         impl: false },
                  { label: "Change Due Date", icon: CalendarDays, impl: false },
                  { label: "Export Selected", icon: Download,     impl: false },
                  { type: "divider" },
                  { label: "Archive",         icon: Archive,      impl: false, danger: true },
                ].map((item, i) => {
                  if ((item as any).type === "divider") return <div key={i} className="h-px bg-border my-1" />;
                  const act = item as any;
                  return (
                    <button key={act.label} onClick={() => act.impl ? act.action?.() : showToast(`${act.label} — coming soon`)}
                      className={cn("w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-accent",
                        act.danger && "text-destructive hover:bg-destructive/10")}>
                      <act.icon className="w-3.5 h-3.5 flex-shrink-0" />
                      {act.label}
                      {!act.impl && <span className="ml-auto text-[9px] text-muted-foreground border border-border rounded px-1">soon</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Upload */}
          <button onClick={() => setShowUpload(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent transition-colors">
            <Upload className="w-3.5 h-3.5" /> Upload
          </button>

          {/* Create Document */}
          <div className="relative" ref={createMenuRef}>
            <button onClick={() => setShowCreateMenu(v => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 transition-colors">
              <Plus className="w-3.5 h-3.5" /> Create Document <ChevronDown className="w-3 h-3" />
            </button>
            {showCreateMenu && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-card border rounded-xl shadow-xl z-30 py-1 overflow-hidden">
                {createItems.map((item, i) => {
                  if ((item as any).type === "divider") return <div key={i} className="h-px bg-border my-1" />;
                  const ci = item as any;
                  return (
                    <button key={ci.label} onClick={() => {
                      setShowCreateMenu(false);
                      if (!ci.impl) { showToast(`${ci.label} — coming soon`); return; }
                      setCreateType(ci.type); setShowCreate(true);
                    }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-accent transition-colors">
                      <ci.icon className={cn("w-3.5 h-3.5 flex-shrink-0", ci.purple ? "text-primary" : "text-muted-foreground")} />
                      <span className={ci.purple ? "font-semibold text-primary" : ""}>{ci.label}</span>
                      {!ci.impl && <span className="ml-auto text-[9px] text-muted-foreground border border-border rounded px-1">soon</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────── */}
      <div className="bg-card border-b flex-shrink-0 px-5 flex items-center gap-0 overflow-x-auto">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => { setActiveTab(tab.id); setSelectedIds(new Set()); }}
            className={cn("flex items-center gap-1.5 px-3.5 py-2.5 text-xs font-medium border-b-2 whitespace-nowrap transition-colors",
              activeTab === tab.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30")}>
            {tab.label}
            {tab.count != null && tab.count > 0 && (
              <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full font-semibold",
                tab.id === "attention" && tab.count > 0 ? "bg-amber-100 text-amber-700" :
                activeTab === tab.id ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground")}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Search + Filters ──────────────────── */}
      <div className="bg-card border-b flex-shrink-0 px-5 py-2.5 space-y-2">
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search title, number, type, owner, department…"
              className="w-full pl-8 pr-4 py-1.5 border rounded-lg text-xs bg-background focus:outline-none focus:ring-2 focus:ring-primary/30" />
            {search && <button onClick={() => setSearch("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"><X className="w-3 h-3" /></button>}
          </div>

          {/* Filter toggle */}
          <button onClick={() => setShowFilters(v => !v)}
            className={cn("flex items-center gap-1.5 px-2.5 py-1.5 border rounded-md text-xs font-medium transition-colors",
              showFilters || activeFilterCount > 0 ? "bg-primary/10 border-primary/30 text-primary" : "hover:bg-accent text-muted-foreground")}>
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Filters
            {activeFilterCount > 0 && <span className="bg-primary text-primary-foreground text-[10px] px-1.5 py-0.5 rounded-full font-semibold">{activeFilterCount}</span>}
          </button>

          {/* Column picker */}
          <ColumnPicker cols={visibleCols} onChange={saveCols} onReset={resetCols} />

          {/* Clear all */}
          {(search || activeFilterCount > 0) && (
            <button onClick={() => { setSearch(""); setTypeFilter(""); setDeptFilter(""); setAssessFilter(""); }}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <X className="w-3 h-3" /> Clear
            </button>
          )}
        </div>

        {/* Filter bar */}
        {showFilters && (
          <div className="flex items-center gap-2 flex-wrap">
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
              className="px-2.5 py-1.5 border rounded-md text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary/30">
              <option value="">All Types</option>
              {DOC_CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
            <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)}
              className="px-2.5 py-1.5 border rounded-md text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary/30">
              <option value="">All Departments</option>
              {DEPARTMENTS.map(d => <option key={d}>{d}</option>)}
            </select>
            <select value={assessFilter} onChange={e => setAssessFilter(e.target.value)}
              className="px-2.5 py-1.5 border rounded-md text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary/30">
              <option value="">All Assessment States</option>
              {ASSESSMENT_VALUES.map(v => <option key={v}>{v}</option>)}
            </select>
            <span className="text-[11px] text-muted-foreground italic">Lifecycle, Owner, Due Date, Severity — coming soon</span>
          </div>
        )}

        {/* Active filter chips */}
        {activeFilterCount > 0 && !showFilters && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {typeFilter && <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full font-medium">Type: {typeFilter} <button onClick={() => setTypeFilter("")}><X className="w-2.5 h-2.5" /></button></span>}
            {deptFilter && <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full font-medium">Dept: {deptFilter.split(" ")[0]} <button onClick={() => setDeptFilter("")}><X className="w-2.5 h-2.5" /></button></span>}
            {assessFilter && <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full font-medium">{assessFilter} <button onClick={() => setAssessFilter("")}><X className="w-2.5 h-2.5" /></button></span>}
          </div>
        )}
      </div>

      {/* ── Table ────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {loadError && (
          <div className="mx-5 mt-3 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-lg px-4 py-2">{loadError}</div>
        )}

        <div className="bg-card">
          {/* Table header */}
          <div className="grid items-center gap-0 px-4 py-2 border-b bg-muted/40 sticky top-0 z-10" style={gridStyle}>
            {/* Checkbox */}
            <div className="flex items-center justify-center">
              <button onClick={toggleAll} className="w-4 h-4 rounded border border-border flex items-center justify-center hover:border-primary transition-colors flex-shrink-0">
                {allSelected ? <Check className="w-3 h-3 text-primary" /> : someSelected ? <Minus className="w-3 h-3 text-muted-foreground" /> : null}
              </button>
            </div>
            {visibleCols.map(col => {
              const def = COLUMN_DEFS[col];
              if (col === "actions") return <div key={col} />;
              return (
                <button key={col} onClick={() => def.sortable && handleSort(col)}
                  className={cn("text-left text-[10px] font-semibold text-muted-foreground uppercase tracking-wide select-none truncate",
                    def.sortable ? "hover:text-foreground cursor-pointer" : "cursor-default")}>
                  {def.label}
                  {def.sortable && <SortIndicator col={col} />}
                </button>
              );
            })}
          </div>

          {/* Rows */}
          {loading ? (
            <div className="divide-y">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-4 py-3">
                  <div className="w-4 h-4 bg-muted rounded animate-pulse" />
                  <div className="w-8 h-8 bg-muted rounded-lg animate-pulse" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 bg-muted rounded w-2/3 animate-pulse" />
                    <div className="h-2.5 bg-muted rounded w-1/3 animate-pulse" />
                  </div>
                  <div className="w-16 h-5 bg-muted rounded animate-pulse" />
                  <div className="w-20 h-5 bg-muted rounded animate-pulse" />
                </div>
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
              <FileText className="w-10 h-10 text-muted-foreground/30" />
              <p className="font-medium text-sm text-muted-foreground">
                {search || activeFilterCount > 0 ? "No documents match your filters" : activeTab !== "all" ? `No documents in this view` : "No documents yet"}
              </p>
              <p className="text-xs text-muted-foreground max-w-xs">
                {!search && activeFilterCount === 0 && activeTab === "all" ? "Upload a document or create one with AI to get started." : "Try adjusting your search or filters."}
              </p>
              {!search && activeFilterCount === 0 && activeTab === "all" && (
                <button onClick={() => setShowUpload(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-medium mt-1">
                  <Upload className="w-3.5 h-3.5" /> Upload Document
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y">
              {sorted.map(doc => {
                const isSelected = selectedIds.has(doc.id);
                const lifecycle = getLifecycle(doc);
                const assessStatus = getAssessmentStatus(doc);
                const score = doc.adjusted_score ?? doc.latest_score;
                const findings = formatFindings(doc);
                const source = getSource(doc);
                const lastTs = doc.updated_at ?? doc.created_at;

                return (
                  <div key={doc.id}
                    className={cn("group grid items-center gap-0 px-4 py-0 transition-colors cursor-pointer",
                      isSelected ? "bg-primary/5" : "hover:bg-muted/30")}
                    style={gridStyle}
                    onClick={() => router.push(`/documents/${doc.id}`)}>

                    {/* Checkbox */}
                    <div className="flex items-center justify-center py-3" onClick={e => { e.stopPropagation(); toggleRow(doc.id); }}>
                      <div className={cn("w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors",
                        isSelected ? "bg-primary border-primary" : "border-border group-hover:border-primary/50")}>
                        {isSelected && <Check className="w-3 h-3 text-primary-foreground" />}
                      </div>
                    </div>

                    {visibleCols.map(col => {
                      if (col === "actions") return (
                        <div key="actions" className="flex items-center justify-center py-3">
                          <RowActionMenu
                            doc={doc}
                            onAssess={() => assessSelected([doc.id])}
                            onArchive={() => showToast("Archive — coming soon")}
                          />
                        </div>
                      );

                      switch (col) {
                        case "document": return (
                          <div key="document" className="flex items-center gap-2.5 min-w-0 py-3 pr-3">
                            <div className={cn("w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0",
                              source === "AI Authored" ? "bg-violet-50" : "bg-primary/8")}>
                              {source === "AI Authored"
                                ? <Sparkles className="w-3.5 h-3.5 text-violet-600" />
                                : <FileText className="w-3.5 h-3.5 text-primary/60" />}
                            </div>
                            <div className="min-w-0">
                              <p className="text-xs font-semibold truncate leading-tight">{doc.title}</p>
                              <p className="text-[10px] text-muted-foreground font-mono truncate mt-0.5">
                                {doc.document_number ? `${doc.document_number} · ` : ""}{doc.dtap_id ?? doc.document_category ?? "No DTAP"}
                              </p>
                            </div>
                          </div>
                        );

                        case "type": return (
                          <div key="type" className="py-3 pr-2">
                            {doc.document_category ? (
                              <span className="text-[10px] font-medium px-1.5 py-0.5 bg-primary/8 text-primary/80 rounded border border-primary/15">
                                {doc.document_category}
                              </span>
                            ) : <span className="text-[10px] text-muted-foreground">—</span>}
                          </div>
                        );

                        case "lifecycle": return (
                          <div key="lifecycle" className="py-3 pr-2">
                            <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded border", getLifecycleStyle(lifecycle))}>
                              {lifecycle}
                            </span>
                          </div>
                        );

                        case "assessment": return (
                          <div key="assessment" className="py-3 pr-2">
                            <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded border", getAssessmentStyle(assessStatus))}>
                              {assessStatus === "Assessing" && <span className="inline-block w-1.5 h-1.5 bg-violet-500 rounded-full animate-pulse mr-1" />}
                              {assessStatus}
                            </span>
                          </div>
                        );

                        case "score": return (
                          <div key="score" className="py-3 pr-2">
                            {score != null ? (
                              <div>
                                <div className="flex items-center gap-1.5">
                                  <span className={cn("text-xs font-bold tabular-nums",
                                    score >= 85 ? "text-green-700" : score >= 70 ? "text-amber-700" : score >= 50 ? "text-orange-700" : "text-red-700")}>
                                    {score.toFixed(1)}
                                  </span>
                                </div>
                                {findings && (
                                  <p className="text-[10px] font-mono text-muted-foreground mt-0.5 leading-none">{findings}</p>
                                )}
                              </div>
                            ) : <span className="text-[10px] text-muted-foreground">Not assessed</span>}
                          </div>
                        );

                        case "owner": return (
                          <div key="owner" className="py-3 pr-2">
                            {doc.department_owner ? (
                              <p className="text-[11px] text-foreground/80 truncate">{doc.department_owner}</p>
                            ) : <span className="text-[10px] text-muted-foreground">Unassigned</span>}
                          </div>
                        );

                        case "dueDate": return (
                          <div key="dueDate" className="py-3 pr-2">
                            <span className="text-[10px] text-muted-foreground">No due date</span>
                          </div>
                        );

                        case "version": return (
                          <div key="version" className="py-3 pr-2">
                            <span className="text-[10px] font-mono text-muted-foreground">
                              {doc.version ? `v${doc.version}` : "v1.0"}
                            </span>
                          </div>
                        );

                        case "source": return (
                          <div key="source" className="py-3 pr-2">
                            <span className={cn("text-[10px] font-medium", getSourceStyle(source))}>{source}</span>
                          </div>
                        );

                        case "lastActivity": return (
                          <div key="lastActivity" className="py-3 pr-2">
                            <span className="text-[10px] text-muted-foreground">
                              {lastTs ? timeAgo(lastTs) : "—"}
                            </span>
                          </div>
                        );

                        case "openItems": return (
                          <div key="openItems" className="py-3 pr-2">
                            <span className="text-[10px] text-muted-foreground">—</span>
                          </div>
                        );

                        default: return <div key={col} className="py-3" />;
                      }
                    })}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Footer ───────────────────────────── */}
      {!loading && sorted.length > 0 && (
        <div className="bg-card border-t px-5 py-2 flex items-center justify-between flex-shrink-0">
          <p className="text-[11px] text-muted-foreground">
            {someSelected ? `${selectedIds.size} selected · ` : ""}{sorted.length} of {documents.length} document{documents.length !== 1 ? "s" : ""}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {documents.filter(d => d.latest_score != null).length} assessed · {documents.filter(d => d.latest_score == null).length} pending
          </p>
        </div>
      )}
    </div>
  );
}

// Need Minus icon for indeterminate checkbox state
function Minus({ className }: { className?: string }) {
  return <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}><line x1="5" y1="12" x2="19" y2="12" /></svg>;
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>}>
      <DocumentsPageContent />
    </Suspense>
  );
}

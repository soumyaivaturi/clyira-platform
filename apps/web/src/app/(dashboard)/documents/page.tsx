"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText, Upload, Plus, Search, X, Loader2,
  FileUp, Sparkles, AlertCircle, ChevronRight, CheckSquare, Square, TrendingDown,
  PlayCircle,
} from "lucide-react";
import { documentsApi, assessmentsApi } from "@/lib/api";
import { ScoreBadge } from "@/components/shared/score-display";
import { DocStatusBadge } from "@/components/shared/badges";
import { EmptyState, LoadingRows } from "@/components/shared/empty-state";
import { formatDate, formatFileSize } from "@/lib/utils";

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

const DOC_CATEGORIES = ["SOP", "CAPA", "ATM", "Deviation", "LIR", "Validation", "Protocol", "Report", "Other"];
const DEPARTMENTS = ["Quality Assurance", "Quality Control", "Manufacturing", "Validation", "Regulatory Affairs", "Research & Development", "Clinical & Safety"];

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
  created_at?: string;
}

// ── Upload Modal ───────────────────────────────────────────────────────────────

function UploadModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [department, setDepartment] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Regulatory framework selector — all selected by default
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>(ALL_FRAMEWORK_CODES);
  const [frameworksExpanded, setFrameworksExpanded] = useState(false);

  const toggleFramework = (code: string) =>
    setSelectedFrameworks((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );

  const toggleGroup = (codes: string[]) => {
    const allSelected = codes.every((c) => selectedFrameworks.includes(c));
    setSelectedFrameworks((prev) =>
      allSelected ? prev.filter((c) => !codes.includes(c)) : Array.from(new Set([...prev, ...codes]))
    );
  };

  const handleFile = (f: File) => { setFile(f); setTitle(f.name.replace(/\.[^.]+$/, "")); };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true); setError("");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title || file.name);
    if (category) fd.append("document_category", category);
    if (department) fd.append("department_owner", department);
    fd.append("regulatory_frameworks", JSON.stringify(selectedFrameworks));
    try {
      const res = await documentsApi.upload(fd, setProgress);
      onSuccess(res.data.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0">
          <div>
            <h2 className="font-semibold">Upload Document</h2>
            <p className="text-xs text-muted-foreground mt-0.5">PDF, DOCX, or XLSX · Max 50 MB</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              dragging ? "border-primary bg-primary/5" : file ? "border-green-300 bg-green-50" : "border-border hover:border-primary/50 hover:bg-muted/30"
            }`}
          >
            <input ref={inputRef} type="file" accept=".pdf,.docx,.doc,.xlsx,.xls" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
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
                <p className="text-xs text-muted-foreground">Supported: PDF, DOCX, XLSX</p>
              </div>
            )}
          </div>

          {file && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Document Title</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                    <option value="">Auto-detect</option>
                    {DOC_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Department</label>
                  <select value={department} onChange={(e) => setDepartment(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                    <option value="">Select dept.</option>
                    {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>

              {/* Regulatory Framework Selector */}
              <div className="border rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setFrameworksExpanded((v) => !v)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Regulatory Frameworks
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                      {selectedFrameworks.length} / {ALL_FRAMEWORK_CODES.length} selected
                    </span>
                  </div>
                  <ChevronRight className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${frameworksExpanded ? "rotate-90" : ""}`} />
                </button>

                {frameworksExpanded && (
                  <div className="p-4 space-y-4 max-h-72 overflow-y-auto border-t">
                    <p className="text-xs text-muted-foreground">
                      Clyira will assess this document against the selected frameworks. All are selected by default.
                    </p>
                    {FRAMEWORK_GROUPS.map((group) => {
                      const groupCodes = group.items.map((i) => i.code);
                      const allGroupSelected = groupCodes.every((c) => selectedFrameworks.includes(c));
                      const someGroupSelected = groupCodes.some((c) => selectedFrameworks.includes(c));
                      return (
                        <div key={group.group}>
                          <button
                            type="button"
                            onClick={() => toggleGroup(groupCodes)}
                            className="flex items-center gap-2 mb-2 group"
                          >
                            {allGroupSelected ? (
                              <CheckSquare className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                            ) : someGroupSelected ? (
                              <div className="w-3.5 h-3.5 border-2 border-primary rounded-sm flex-shrink-0 bg-primary/20" />
                            ) : (
                              <Square className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                            )}
                            <span className="text-xs font-semibold text-foreground">{group.group}</span>
                          </button>
                          <div className="grid grid-cols-1 gap-1 pl-5">
                            {group.items.map((item) => {
                              const checked = selectedFrameworks.includes(item.code);
                              return (
                                <label
                                  key={item.code}
                                  className="flex items-start gap-2 cursor-pointer group"
                                >
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleFramework(item.code)}
                                    className="mt-0.5 accent-primary flex-shrink-0"
                                  />
                                  <span className="flex-1 min-w-0">
                                    <span className="text-xs font-medium">{item.label}</span>
                                    <span className="text-[10px] text-muted-foreground ml-1.5">{item.description}</span>
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                    <div className="flex gap-2 pt-1 border-t">
                      <button
                        type="button"
                        onClick={() => setSelectedFrameworks(ALL_FRAMEWORK_CODES)}
                        className="text-[10px] text-primary hover:underline font-medium"
                      >
                        Select all
                      </button>
                      <span className="text-[10px] text-muted-foreground">·</span>
                      <button
                        type="button"
                        onClick={() => setSelectedFrameworks([])}
                        className="text-[10px] text-muted-foreground hover:underline"
                      >
                        Clear all
                      </button>
                    </div>
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

          {error && (
            <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {error}
            </div>
          )}
        </div>

        <div className="px-6 pb-6 flex gap-3 flex-shrink-0 border-t pt-4">
          <button onClick={onClose} className="flex-1 py-2.5 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button onClick={handleSubmit} disabled={!file || uploading}
            className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
            Upload & Classify
          </button>
        </div>
      </div>
    </div>
  );
}

// ── AI Create Modal ────────────────────────────────────────────────────────────

function CreateModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("SOP");
  const [department, setDepartment] = useState("");
  const [instructions, setInstructions] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!title.trim()) { setError("Title is required"); return; }
    setCreating(true); setError("");
    const fd = new FormData();
    fd.append("document_type", docType);
    fd.append("title", title);
    if (department) fd.append("department", department);
    if (instructions) fd.append("instructions", instructions);
    try {
      await documentsApi.create(fd);
      onSuccess();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Creation failed.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">AI Document Creator</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Generate a compliant document scaffold</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-accent"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Document Title *</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. SOP for Aseptic Gowning Procedure"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Document Type</label>
              <select value={docType} onChange={(e) => setDocType(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                {DOC_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">Department</label>
              <select value={department} onChange={(e) => setDepartment(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                <option value="">Select dept.</option>
                {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">
              Instructions <span className="text-muted-foreground/60 normal-case font-normal">(optional — AI will follow these)</span>
            </label>
            <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3}
              placeholder="e.g. Include ISO 13485 references. Focus on small-scale API synthesis. Add media fill section."
              className="w-full px-3 py-2 border rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
            Full AI drafting requires an Anthropic API key. A structured scaffold will be created and queued for AI drafting when the key is configured.
          </div>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">{error}</div>
          )}
        </div>

        <div className="px-6 pb-6 flex gap-3">
          <button onClick={onClose} className="flex-1 py-2.5 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button onClick={handleSubmit} disabled={creating || !title.trim()}
            className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {creating && <Loader2 className="w-4 h-4 animate-spin" />}
            <Sparkles className="w-3.5 h-3.5" />
            Create Document
          </button>
        </div>
      </div>
    </div>
  );
}

interface SearchResult {
  id: string;
  title: string;
  document_number?: string;
  document_category?: string;
  department_owner?: string;
  status: string;
  latest_score?: number | null;
  match_in: string;
  excerpt: string;
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [bulkRunning, setBulkRunning] = useState(false);
  const [bulkMsg, setBulkMsg] = useState("");
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const res = await documentsApi.list({
        ...(categoryFilter ? { document_category: categoryFilter } : {}),
        ...(deptFilter ? { department_owner: deptFilter } : {}),
      });
      setDocuments(res.data.documents ?? []);
    } catch {
      setLoadError("Could not load documents. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, deptFilter]);

  useEffect(() => { load(); }, [load]);

  const handleSearchChange = (value: string) => {
    setSearch(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    if (!value.trim() || value.trim().length < 3) {
      setSearchResults(null);
      return;
    }
    searchTimerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await documentsApi.search(value.trim());
        setSearchResults(res.data.results ?? []);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 400);
  };

  const isSearchMode = search.trim().length >= 3;
  const filtered = isSearchMode
    ? []
    : documents.filter(d =>
        !search ||
        d.title.toLowerCase().includes(search.toLowerCase()) ||
        (d.document_category ?? "").toLowerCase().includes(search.toLowerCase())
      );

  return (
    <div className="space-y-5">
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onSuccess={(id) => { setShowUpload(false); router.push(`/documents/${id}`); }} />}
      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onSuccess={() => { setShowCreate(false); load(); }} />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Upload, assess, and manage your quality document corpus</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              setBulkRunning(true);
              setBulkMsg("");
              try {
                const res = await assessmentsApi.bulkRun();
                const count = res.data.queued ?? 0;
                setBulkMsg(count > 0 ? `${count} assessment${count !== 1 ? "s" : ""} queued` : "No un-assessed documents found.");
              } catch {
                setBulkMsg("Failed to queue bulk assessments.");
              } finally {
                setBulkRunning(false);
                setTimeout(() => setBulkMsg(""), 5000);
              }
            }}
            disabled={bulkRunning}
            title="Assess all un-assessed documents"
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-accent transition-colors disabled:opacity-50">
            {bulkRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
            Assess All
          </button>
          <button onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-accent transition-colors">
            <Upload className="w-4 h-4" /> Upload
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors">
            <Sparkles className="w-4 h-4" /> AI Create
          </button>
        </div>
      </div>

      {loadError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3">
          {loadError}
        </div>
      )}
      {bulkMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-lg px-4 py-3">
          {bulkMsg}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input value={search} onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search titles, numbers, or document content…"
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30" />
          {searching && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 animate-spin text-muted-foreground" />}
        </div>
        {!isSearchMode && (
          <>
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
              <option value="">All types</option>
              {DOC_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
              <option value="">All departments</option>
              {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </>
        )}
        {(categoryFilter || deptFilter || search) && (
          <button onClick={() => { setCategoryFilter(""); setDeptFilter(""); setSearch(""); setSearchResults(null); }}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <X className="w-3 h-3" /> Clear
          </button>
        )}
      </div>

      {/* Full-text Search Results */}
      {isSearchMode && (
        <div className="bg-card border rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b bg-muted/30 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Search Results
            </span>
            {searchResults && (
              <span className="text-xs text-muted-foreground">{searchResults.length} match{searchResults.length !== 1 ? "es" : ""} for "{search}"</span>
            )}
          </div>
          {searching ? (
            <div className="flex items-center gap-2 px-5 py-8 text-sm text-muted-foreground justify-center">
              <Loader2 className="w-4 h-4 animate-spin" />
              Searching document content…
            </div>
          ) : !searchResults || searchResults.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-muted-foreground">
              No documents found for "{search}"
            </div>
          ) : (
            <div className="divide-y">
              {searchResults.map((r) => (
                <Link key={r.id} href={`/documents/${r.id}`}
                  className="flex items-start gap-4 px-5 py-4 hover:bg-muted/30 transition-colors">
                  <div className="w-8 h-8 rounded-lg bg-clyira-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-4 h-4 text-clyira-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p className="text-sm font-medium">{r.title}</p>
                      {r.document_category && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 bg-primary/10 text-primary rounded">
                          {r.document_category}
                        </span>
                      )}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                        r.match_in === "title" ? "bg-amber-50 text-amber-700 border-amber-200" :
                        r.match_in === "number" ? "bg-blue-50 text-blue-700 border-blue-200" :
                        "bg-muted text-muted-foreground border-border"
                      }`}>
                        {r.match_in === "content" ? "in content" : `in ${r.match_in}`}
                      </span>
                    </div>
                    {r.excerpt && r.match_in === "content" && (
                      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{r.excerpt}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1.5">
                      {r.department_owner && <span className="text-[10px] text-muted-foreground">{r.department_owner}</span>}
                      <ScoreBadge score={r.latest_score} />
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-1" />
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Document Table (non-search mode) */}
      {!isSearchMode && (
        <div className="bg-card border rounded-xl overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_100px_160px_80px_110px_80px] gap-4 px-5 py-3 border-b bg-muted/30">
            {["Document", "Type", "Department", "Score", "Status", "Uploaded"].map(h => (
              <span key={h} className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{h}</span>
            ))}
          </div>

          {loading ? (
            <LoadingRows count={5} cols={6} />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={FileText}
              title={search || categoryFilter || deptFilter ? "No documents match your filters" : "No documents yet"}
              description={search || categoryFilter || deptFilter ? "Try adjusting your search or filters." : "Upload a document or use AI Create to get started."}
              action={!search && !categoryFilter && !deptFilter ? (
                <button onClick={() => setShowUpload(true)} className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium">
                  <Upload className="w-4 h-4" /> Upload Document
                </button>
              ) : undefined}
            />
          ) : (
            <div className="divide-y">
              {filtered.map((doc) => (
                <Link key={doc.id} href={`/documents/${doc.id}`}
                  className="grid grid-cols-[1fr_100px_160px_80px_110px_80px] gap-4 px-5 py-3.5 items-center hover:bg-muted/30 transition-colors cursor-pointer">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-clyira-50 flex items-center justify-center flex-shrink-0">
                      <FileText className="w-4 h-4 text-clyira-600" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{doc.title}</p>
                      {doc.document_number && (
                        <p className="text-[10px] font-mono text-muted-foreground">{doc.document_number} · v{doc.version ?? "1.0"}</p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">{doc.document_category ?? "—"}</span>
                  <span className="text-xs text-muted-foreground truncate">{doc.department_owner ?? "Unassigned"}</span>
                  <div className="flex flex-col gap-0.5">
                    <ScoreBadge score={doc.adjusted_score ?? doc.latest_score} />
                    {doc.adjusted_score != null && doc.latest_score != null &&
                     Math.abs(doc.adjusted_score - doc.latest_score) > 0.1 && (
                      <span className="flex items-center gap-0.5 text-[9px] text-amber-600 font-medium">
                        <TrendingDown className="w-2.5 h-2.5" />
                        was {doc.latest_score.toFixed(1)}
                      </span>
                    )}
                  </div>
                  <DocStatusBadge status={doc.status} />
                  <span className="text-xs text-muted-foreground">{formatDate(doc.created_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer count */}
      {!loading && !isSearchMode && filtered.length > 0 && (
        <p className="text-xs text-muted-foreground px-1">
          Showing {filtered.length} of {documents.length} document{documents.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}

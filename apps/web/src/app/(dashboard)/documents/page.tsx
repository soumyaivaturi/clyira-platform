"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText, Upload, Plus, Search, Filter, X, Loader2,
  ChevronDown, FileUp, Sparkles, AlertCircle,
} from "lucide-react";
import { documentsApi } from "@/lib/api";
import { ScoreBadge } from "@/components/shared/score-display";
import { DocStatusBadge } from "@/components/shared/badges";
import { EmptyState, LoadingRows } from "@/components/shared/empty-state";
import { formatDate, formatFileSize } from "@/lib/utils";

const DOC_CATEGORIES = ["SOP", "CAPA", "ATM", "Deviation", "Validation", "Protocol", "Report", "Other"];
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
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-semibold">Upload Document</h2>
            <p className="text-xs text-muted-foreground mt-0.5">PDF, DOCX, or XLSX · Max 50 MB</p>
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

        <div className="px-6 pb-6 flex gap-3">
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

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await documentsApi.list({
        ...(categoryFilter ? { document_category: categoryFilter } : {}),
        ...(deptFilter ? { department_owner: deptFilter } : {}),
      });
      setDocuments(res.data.documents ?? []);
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, deptFilter]);

  useEffect(() => { load(); }, [load]);

  const filtered = documents.filter(d =>
    !search || d.title.toLowerCase().includes(search.toLowerCase()) ||
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

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search documents…"
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
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
        {(categoryFilter || deptFilter || search) && (
          <button onClick={() => { setCategoryFilter(""); setDeptFilter(""); setSearch(""); }}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <X className="w-3 h-3" /> Clear
          </button>
        )}
      </div>

      {/* Document Table */}
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
                <ScoreBadge score={doc.latest_score} />
                <DocStatusBadge status={doc.status} />
                <span className="text-xs text-muted-foreground">{formatDate(doc.created_at)}</span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Footer count */}
      {!loading && filtered.length > 0 && (
        <p className="text-xs text-muted-foreground px-1">
          Showing {filtered.length} of {documents.length} document{documents.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}

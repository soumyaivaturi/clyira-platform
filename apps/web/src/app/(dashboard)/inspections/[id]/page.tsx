"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ChevronLeft, Radio, Plus, Send, RefreshCw, Loader2,
  MessageSquare, FileText, Zap, Clock, CheckCircle2,
  AlertTriangle, XCircle, X, PlayCircle, Square,
  Users, Shield, Package, BarChart3, BookOpen,
  ChevronRight, Calendar, MapPin, User, ArrowRight,
  Flag, Paperclip, MessageCircle, Activity, Star,
  TriangleAlert, BadgeCheck, Timer, TrendingUp, Info,
  Mic, ClipboardList, ChevronDown, ExternalLink, Trash2,
  Edit3, Eye, Lock, Unlock, CheckSquare, Circle,
} from "lucide-react";
import { inspectionsApi } from "@/lib/api";
import { InspStatusBadge } from "@/components/shared/badges";
import { timeAgo } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Inspection {
  id: string;
  title: string;
  agency: string | null;
  inspection_type: string | null;
  status: string;
  current_phase: string | null;
  start_date: string | null;
  end_date: string | null;
  total_requests: number;
  created_at: string;
  requests?: InspRequest[];
}

interface InspRequest {
  id: string;
  request_number: number | null;
  request_text: string;
  criticality: string;
  category: string;
  status: string;
  inspector_name: string | null;
  inspector_department: string | null;
  location: string | null;
  assigned_to_name: string | null;
  assigned_to_title: string | null;
  sla_minutes: number | null;
  due_at: string | null;
  fulfillment_progress: number;
  response_text: string | null;
  ai_talking_points?: string[];
  ai_suggested_documents?: string[];
  ai_risk_assessment?: string | null;
  created_at: string;
}

interface LogEntry {
  id: string;
  entry_type: string;
  content: string;
  tags: string[];
  created_at: string;
}

interface Commitment {
  id: string;
  commitment_text: string;
  committed_to: string | null;
  deadline_at: string | null;
  status: string;
  delivery_note: string | null;
  created_at: string;
}

interface Observation {
  id: string;
  observation_number: number;
  observation_text: string;
  system_area: string | null;
  cfr_citations: string[];
  draft_response: string | null;
  status: string;
  response_deadline: string | null;
  legal_review_required: boolean;
  created_at: string;
}

interface Delivery {
  id: string;
  document_titles: string[];
  delivered_to: string;
  delivery_method: string | null;
  delivered_at: string;
  acknowledgment_received: boolean;
  created_at: string;
}

interface Inspector {
  id: string;
  name: string;
  fda_district: string | null;
  role: string;
  focus_areas: string[];
  email: string | null;
  notes: string | null;
}

interface RequestDocument {
  id: string;
  filename: string;
  file_size_bytes: number | null;
  status: string;
  created_at: string;
}

interface Comment {
  id: string;
  author_name: string | null;
  content: string;
  created_at: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CRITICALITY_COLORS: Record<string, string> = {
  critical: "border-l-red-600 bg-red-50",
  high: "border-l-red-500 bg-red-50",
  medium: "border-l-amber-500 bg-amber-50",
  low: "border-l-blue-500 bg-blue-50",
};

const CRITICALITY_BADGE: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
};

const REQUEST_STATUS_STYLES: Record<string, { label: string; className: string; icon: any }> = {
  open: { label: "Open", className: "text-amber-700 bg-amber-50 border-amber-200", icon: AlertTriangle },
  in_progress: { label: "In Progress", className: "text-blue-700 bg-blue-50 border-blue-200", icon: Clock },
  fulfilled: { label: "Fulfilled", className: "text-emerald-700 bg-emerald-50 border-emerald-200", icon: CheckCircle2 },
  declined: { label: "Declined", className: "text-red-700 bg-red-50 border-red-200", icon: XCircle },
};

const LOG_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  scribe_note: { label: "Scribe", color: "text-primary bg-primary/10" },
  observation: { label: "Observation", color: "text-amber-700 bg-amber-50" },
  deficiency: { label: "Deficiency", color: "text-red-700 bg-red-50" },
  action_item: { label: "Action Item", color: "text-blue-700 bg-blue-50" },
  document_request: { label: "Doc Request", color: "text-purple-700 bg-purple-50" },
  question: { label: "Question", color: "text-indigo-700 bg-indigo-50" },
  commitment: { label: "Commitment", color: "text-emerald-700 bg-emerald-50" },
};

const PHASES = [
  { key: "opening_meeting", label: "Opening Meeting", short: "Opening" },
  { key: "facility_tour", label: "Facility Tour", short: "Tour" },
  { key: "document_review", label: "Document Review", short: "Docs" },
  { key: "systems_review", label: "Systems Review", short: "Systems" },
  { key: "closing_meeting", label: "Closing Meeting", short: "Closing" },
];

const ENTRY_TYPES = [
  { value: "scribe_note", label: "Scribe Note" },
  { value: "observation", label: "Observation" },
  { value: "deficiency", label: "Deficiency" },
  { value: "action_item", label: "Action Item" },
  { value: "document_request", label: "Document Request" },
  { value: "commitment", label: "Commitment" },
  { value: "question", label: "Question" },
];

const AI_AGENTS = [
  { key: "scribe", label: "Scribe AI" },
  { key: "prep_manager", label: "Prep Manager" },
  { key: "sme_coach", label: "SME Coach" },
  { key: "qa_agent", label: "QA Agent" },
  { key: "doc_reviewer", label: "Doc Reviewer" },
];

function typeLabel(t: string | null) {
  const map: Record<string, string> = {
    routine: "Routine GMP", for_cause: "For Cause",
    pre_approval: "Pre-Approval (PAI)", surveillance: "Surveillance", directed: "Directed",
  };
  return map[t ?? ""] ?? t ?? "Inspection";
}

// ── SLA Countdown ─────────────────────────────────────────────────────────────
function SlaCountdown({ dueAt, slaMinutes }: { dueAt: string | null; slaMinutes: number | null }) {
  const [remaining, setRemaining] = useState<string>("");
  const [overdue, setOverdue] = useState(false);
  const [urgent, setUrgent] = useState(false);

  useEffect(() => {
    if (!dueAt) return;
    const tick = () => {
      const diff = new Date(dueAt).getTime() - Date.now();
      if (diff <= 0) {
        setOverdue(true);
        setRemaining("Overdue");
        return;
      }
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setUrgent(m < 10);
      setRemaining(m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m ${s}s`);
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [dueAt]);

  if (!dueAt) return null;
  return (
    <span className={`flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${
      overdue ? "bg-red-100 text-red-700 border-red-200" :
      urgent ? "bg-orange-100 text-orange-700 border-orange-200" :
      "bg-green-100 text-green-700 border-green-200"
    }`}>
      <Timer className="w-3 h-3" />
      {remaining}
    </span>
  );
}

// ── Progress Bar ──────────────────────────────────────────────────────────────
function ProgressBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${pct === 100 ? "bg-emerald-500" : pct >= 50 ? "bg-primary" : "bg-amber-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-semibold text-muted-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}

// ── Phase Navigator ───────────────────────────────────────────────────────────
function PhaseNavigator({
  current,
  status,
  onPhaseChange,
}: {
  current: string | null;
  status: string;
  onPhaseChange: (p: string) => void;
}) {
  if (status !== "active") return null;
  const currentIndex = PHASES.findIndex(p => p.key === current);

  return (
    <div className="bg-card border rounded-xl p-3">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2.5 flex items-center gap-1.5">
        <Activity className="w-3 h-3 text-primary" />
        Inspection Phase
      </p>
      <div className="flex items-center gap-0">
        {PHASES.map((phase, i) => {
          const done = currentIndex > i;
          const active = currentIndex === i;
          return (
            <div key={phase.key} className="flex items-center flex-1">
              <button
                onClick={() => onPhaseChange(phase.key)}
                title={phase.label}
                className={`flex-1 flex flex-col items-center gap-1 py-2 px-1 rounded-lg text-center transition-colors ${
                  active
                    ? "bg-primary/10 text-primary"
                    : done
                    ? "text-emerald-700 hover:bg-emerald-50"
                    : "text-muted-foreground hover:bg-accent"
                }`}
              >
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  active ? "bg-primary text-white" :
                  done ? "bg-emerald-500 text-white" :
                  "bg-muted text-muted-foreground"
                }`}>
                  {done ? <CheckCircle2 className="w-3 h-3" /> : i + 1}
                </div>
                <span className="text-[10px] font-medium leading-tight hidden sm:block">{phase.short}</span>
              </button>
              {i < PHASES.length - 1 && (
                <div className={`h-0.5 flex-shrink-0 w-4 ${done ? "bg-emerald-400" : "bg-border"}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Add Request Modal ─────────────────────────────────────────────────────────
function AddRequestModal({ onClose, onAdd }: { onClose: () => void; onAdd: (d: any) => Promise<void> }) {
  const [form, setForm] = useState({
    request_text: "", criticality: "medium", category: "question",
    inspector_name: "", inspector_department: "", location: "",
  });
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.request_text.trim()) return;
    setSaving(true);
    try { await onAdd(form); onClose(); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-card z-10">
          <h2 className="font-semibold">Log Inspector Request</h2>
          <button onClick={onClose}><X className="w-4 h-4 text-muted-foreground" /></button>
        </div>
        <form onSubmit={submit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Request / Question *
            </label>
            <textarea
              rows={3}
              placeholder="Describe the inspector's request or question exactly as stated…"
              value={form.request_text}
              onChange={e => setForm(f => ({ ...f, request_text: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              Tip: capture the exact wording — it helps the AI generate accurate talking points.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Criticality</label>
              <select value={form.criticality} onChange={e => setForm(f => ({ ...f, criticality: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                <option value="critical">Critical (15 min SLA)</option>
                <option value="high">High (30 min SLA)</option>
                <option value="medium">Medium (60 min SLA)</option>
                <option value="low">Low (120 min SLA)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Category</label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                <option value="question">Question</option>
                <option value="document_request">Document Request</option>
                <option value="observation">Observation</option>
                <option value="commitment">Commitment</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Inspector Name
              </label>
              <input
                value={form.inspector_name}
                onChange={e => setForm(f => ({ ...f, inspector_name: e.target.value }))}
                placeholder="e.g., Dr. Sarah Chen"
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Location / Area
              </label>
              <input
                value={form.location}
                onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
                placeholder="e.g., Prep Room A · Mfg Floor 2"
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-accent">Cancel</button>
            <button type="submit" disabled={saving || !form.request_text.trim()}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-60">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              {saving ? "Saving…" : "Log Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Request Detail Modal ──────────────────────────────────────────────────────
function RequestDetailModal({
  req,
  inspectionId,
  onClose,
  onUpdate,
}: {
  req: InspRequest;
  inspectionId: string;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const [subTab, setSubTab] = useState<"overview" | "documents" | "comments" | "ai" | "trail">("overview");
  const [docs, setDocs] = useState<RequestDocument[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingComments, setLoadingComments] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [sendingComment, setSendingComment] = useState(false);
  const [docFilename, setDocFilename] = useState("");
  const [addingDoc, setAddingDoc] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [aiData, setAiData] = useState<{ talking_points: string[]; suggested_documents: string[]; risk_assessment: string } | null>(
    req.ai_talking_points?.length
      ? { talking_points: req.ai_talking_points, suggested_documents: req.ai_suggested_documents ?? [], risk_assessment: req.ai_risk_assessment ?? "" }
      : null
  );
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [progress, setProgress] = useState(req.fulfillment_progress);

  const loadDocs = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const res = await inspectionsApi.listRequestDocuments(inspectionId, req.id);
      setDocs(res.data.documents ?? []);
    } finally { setLoadingDocs(false); }
  }, [inspectionId, req.id]);

  const loadComments = useCallback(async () => {
    setLoadingComments(true);
    try {
      const res = await inspectionsApi.listComments(inspectionId, req.id);
      setComments(res.data.comments ?? []);
    } finally { setLoadingComments(false); }
  }, [inspectionId, req.id]);

  useEffect(() => {
    if (subTab === "documents") loadDocs();
    if (subTab === "comments") loadComments();
  }, [subTab, loadDocs, loadComments]);

  const handleStatusUpdate = async (status: string) => {
    setUpdatingStatus(true);
    try {
      await inspectionsApi.updateRequest(inspectionId, req.id, { req_status: status, fulfillment_progress: status === "fulfilled" ? 100 : progress });
      onUpdate();
      onClose();
    } finally { setUpdatingStatus(false); }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res = await inspectionsApi.analyzeRequest(inspectionId, req.id);
      setAiData({ talking_points: res.data.ai_talking_points ?? [], suggested_documents: res.data.ai_suggested_documents ?? [], risk_assessment: res.data.ai_risk_assessment ?? "" });
      setSubTab("ai");
    } finally { setAnalyzing(false); }
  };

  const handleAddDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFilename.trim()) return;
    setAddingDoc(true);
    try {
      await inspectionsApi.addRequestDocument(inspectionId, req.id, { filename: docFilename });
      setDocFilename("");
      await loadDocs();
    } finally { setAddingDoc(false); }
  };

  const handleSendComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    setSendingComment(true);
    try {
      await inspectionsApi.addComment(inspectionId, req.id, commentText);
      setCommentText("");
      await loadComments();
    } finally { setSendingComment(false); }
  };

  const statusCfg = REQUEST_STATUS_STYLES[req.status] ?? REQUEST_STATUS_STYLES.open;
  const StatusIcon = statusCfg.icon;
  const reqNum = req.request_number ? `REQ-${String(req.request_number).padStart(3, "0")}` : "REQ";

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border rounded-t-2xl sm:rounded-2xl shadow-2xl w-full max-w-2xl mx-0 sm:mx-4 max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b flex-shrink-0">
          <div className="flex-1 min-w-0 pr-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold text-primary font-mono">{reqNum}</span>
              <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${CRITICALITY_BADGE[req.criticality] ?? ""}`}>
                {req.criticality}
              </span>
              <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusCfg.className}`}>
                <StatusIcon className="w-2.5 h-2.5" />
                {statusCfg.label}
              </span>
              <SlaCountdown dueAt={req.due_at} slaMinutes={req.sla_minutes} />
            </div>
            <p className="text-sm font-medium mt-1.5 leading-snug">{req.request_text}</p>
            <div className="flex flex-wrap gap-3 mt-2 text-[11px] text-muted-foreground">
              {req.inspector_name && (
                <span className="flex items-center gap-1">
                  <User className="w-3 h-3" />{req.inspector_name}
                  {req.inspector_department && ` · ${req.inspector_department}`}
                </span>
              )}
              {req.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3" />{req.location}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />{timeAgo(req.created_at)}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="flex-shrink-0">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Progress */}
        <div className="px-5 py-3 border-b flex-shrink-0">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Fulfillment Progress</span>
            <span className="text-xs font-bold text-muted-foreground">{progress}%</span>
          </div>
          <ProgressBar value={progress} />
          <input
            type="range" min={0} max={100} step={5} value={progress}
            onChange={async e => {
              const v = Number(e.target.value);
              setProgress(v);
              await inspectionsApi.updateRequest(inspectionId, req.id, { fulfillment_progress: v });
            }}
            className="w-full mt-1.5 h-1 accent-primary"
          />
        </div>

        {/* Sub-tabs */}
        <div className="flex border-b flex-shrink-0 px-2">
          {[
            { key: "overview", label: "Overview", icon: Eye },
            { key: "documents", label: "Documents", icon: Paperclip },
            { key: "comments", label: "Discussion", icon: MessageCircle },
            { key: "ai", label: "AI Coach", icon: Zap },
            { key: "trail", label: "History", icon: Activity },
          ].map(t => {
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setSubTab(t.key as any)}
                className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px ${
                  subTab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}>
                <Icon className="w-3 h-3" />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Sub-tab content */}
        <div className="flex-1 overflow-y-auto p-5">
          {subTab === "overview" && (
            <div className="space-y-4">
              {req.response_text && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
                  <p className="text-[10px] font-semibold text-emerald-800 uppercase tracking-wide mb-1">Response Logged</p>
                  <p className="text-sm text-emerald-900">{req.response_text}</p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Category", value: req.category },
                  { label: "Criticality", value: req.criticality },
                  { label: "SLA Budget", value: req.sla_minutes ? `${req.sla_minutes} min` : "—" },
                  { label: "Assigned To", value: req.assigned_to_name ?? "Unassigned" },
                ].map(f => (
                  <div key={f.label} className="bg-muted/40 rounded-lg px-3 py-2.5">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">{f.label}</p>
                    <p className="text-sm font-medium mt-0.5 capitalize">{f.value}</p>
                  </div>
                ))}
              </div>
              <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-xs text-blue-800">
                <p className="font-semibold mb-1 flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> What inspectors look for</p>
                <p>Document requests require the exact document within the SLA window. Questions need a clear, concise answer — avoid volunteering extra information beyond what was asked.</p>
              </div>
            </div>
          )}

          {subTab === "documents" && (
            <div className="space-y-4">
              <form onSubmit={handleAddDoc} className="flex gap-2">
                <input
                  value={docFilename}
                  onChange={e => setDocFilename(e.target.value)}
                  placeholder="Add document name or path…"
                  className="flex-1 border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                <button type="submit" disabled={addingDoc || !docFilename.trim()}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60 flex items-center gap-1.5">
                  {addingDoc ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                  Add
                </button>
              </form>
              {loadingDocs ? (
                <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
              ) : docs.length === 0 ? (
                <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-8 text-center">
                  <Paperclip className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No documents attached yet</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {docs.map(doc => (
                    <div key={doc.id} className="flex items-center justify-between bg-muted/30 border rounded-lg px-3 py-2.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <span className="text-sm truncate">{doc.filename}</span>
                      </div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border flex-shrink-0 ml-2 ${
                        doc.status === "ready" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                        doc.status === "delivered" ? "bg-blue-50 text-blue-700 border-blue-200" :
                        "bg-amber-50 text-amber-700 border-amber-200"
                      }`}>{doc.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {subTab === "comments" && (
            <div className="space-y-4">
              {loadingComments ? (
                <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
              ) : comments.length === 0 ? (
                <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-6 text-center mb-4">
                  <MessageCircle className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No comments yet — start a war-room discussion</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {comments.map(c => (
                    <div key={c.id} className="bg-card border rounded-xl px-4 py-3">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs font-semibold">{c.author_name ?? "Team"}</span>
                        <span className="text-[10px] text-muted-foreground">{timeAgo(c.created_at)}</span>
                      </div>
                      <p className="text-sm leading-relaxed">{c.content}</p>
                    </div>
                  ))}
                </div>
              )}
              <form onSubmit={handleSendComment} className="flex gap-2 sticky bottom-0 bg-card pt-2">
                <input
                  value={commentText}
                  onChange={e => setCommentText(e.target.value)}
                  placeholder="Add war-room note…"
                  className="flex-1 border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                <button type="submit" disabled={sendingComment || !commentText.trim()}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60 flex items-center gap-1.5">
                  {sendingComment ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                </button>
              </form>
            </div>
          )}

          {subTab === "ai" && (
            <div className="space-y-4">
              {!aiData ? (
                <div className="text-center py-8">
                  <Zap className="w-10 h-10 text-primary/30 mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">AI hasn't analyzed this request yet</p>
                  <button onClick={handleAnalyze} disabled={analyzing}
                    className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium mx-auto disabled:opacity-60">
                    {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    {analyzing ? "Analyzing…" : "Run AI Analysis"}
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {aiData.risk_assessment && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                      <p className="text-[10px] font-semibold text-amber-800 uppercase tracking-wide mb-1.5 flex items-center gap-1">
                        <TriangleAlert className="w-3 h-3" /> Risk Assessment
                      </p>
                      <p className="text-sm text-amber-900">{aiData.risk_assessment}</p>
                    </div>
                  )}
                  {aiData.talking_points.length > 0 && (
                    <div className="bg-card border rounded-xl px-4 py-3">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Talking Points</p>
                      <ul className="space-y-2">
                        {aiData.talking_points.map((pt, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <span className="text-primary font-bold mt-0.5 flex-shrink-0">{i + 1}.</span>
                            <span>{pt}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {aiData.suggested_documents.length > 0 && (
                    <div className="bg-card border rounded-xl px-4 py-3">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Suggested Documents</p>
                      <div className="flex flex-wrap gap-2">
                        {aiData.suggested_documents.map((doc, i) => (
                          <span key={i} className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-primary/5 border border-primary/20 rounded-lg font-medium text-primary">
                            <FileText className="w-3 h-3" />{doc}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <button onClick={handleAnalyze} disabled={analyzing}
                    className="flex items-center gap-1.5 text-xs text-primary hover:underline font-medium disabled:opacity-50">
                    {analyzing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    Re-analyze
                  </button>
                </div>
              )}
            </div>
          )}

          {subTab === "trail" && (
            <div className="space-y-2">
              <div className="bg-card border rounded-xl px-4 py-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-bold uppercase text-muted-foreground px-2 py-0.5 rounded bg-muted">Created</span>
                  <span className="text-[10px] text-muted-foreground">{timeAgo(req.created_at)}</span>
                </div>
                <p className="text-sm">Request logged</p>
              </div>
              {aiData && (
                <div className="bg-card border rounded-xl px-4 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-bold uppercase text-primary px-2 py-0.5 rounded bg-primary/10">AI</span>
                  </div>
                  <p className="text-sm">AI analysis completed</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action bar */}
        {req.status !== "fulfilled" && req.status !== "declined" && (
          <div className="border-t px-5 py-3 flex gap-2 flex-wrap flex-shrink-0">
            {req.status === "open" && (
              <button onClick={() => handleStatusUpdate("in_progress")} disabled={updatingStatus}
                className="px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors disabled:opacity-50">
                Mark In Progress
              </button>
            )}
            <button onClick={() => handleStatusUpdate("fulfilled")} disabled={updatingStatus}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 ml-auto">
              {updatingStatus ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
              Mark Fulfilled
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Log Entry Card ────────────────────────────────────────────────────────────
function LogEntryCard({ entry }: { entry: LogEntry }) {
  const cfg = LOG_TYPE_CONFIG[entry.entry_type] ?? { label: entry.entry_type, color: "text-muted-foreground bg-muted" };
  return (
    <div className="bg-card border rounded-xl px-4 py-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded ${cfg.color}`}>{cfg.label}</span>
        <span className="text-[10px] text-muted-foreground">{timeAgo(entry.created_at)}</span>
        {entry.tags?.length > 0 && (
          <div className="flex gap-1 ml-1">
            {entry.tags.map(tag => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground">#{tag}</span>
            ))}
          </div>
        )}
      </div>
      <p className="text-sm leading-relaxed">{entry.content}</p>
    </div>
  );
}

// ── Compact Request Card ──────────────────────────────────────────────────────
function RequestCard({
  req,
  inspectionId,
  onOpen,
}: {
  req: InspRequest;
  inspectionId: string;
  onOpen: (req: InspRequest) => void;
}) {
  const statusCfg = REQUEST_STATUS_STYLES[req.status] ?? REQUEST_STATUS_STYLES.open;
  const StatusIcon = statusCfg.icon;
  const reqNum = req.request_number ? `REQ-${String(req.request_number).padStart(3, "0")}` : "REQ";

  return (
    <div
      className={`border-l-4 rounded-r-xl border rounded-xl overflow-hidden cursor-pointer hover:shadow-sm transition-shadow ${CRITICALITY_COLORS[req.criticality] ?? "bg-card"}`}
      onClick={() => onOpen(req)}
    >
      <div className="px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-bold text-primary font-mono">{reqNum}</span>
              <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${CRITICALITY_BADGE[req.criticality] ?? ""}`}>
                {req.criticality}
              </span>
            </div>
            <p className="text-sm font-medium leading-snug">{req.request_text}</p>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {req.inspector_name && (
                <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <User className="w-2.5 h-2.5" />{req.inspector_name}
                </span>
              )}
              {req.location && (
                <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <MapPin className="w-2.5 h-2.5" />{req.location}
                </span>
              )}
              <span className="text-[10px] text-muted-foreground">{timeAgo(req.created_at)}</span>
              {req.ai_talking_points?.length ? (
                <span className="text-[10px] text-primary font-medium flex items-center gap-0.5">
                  <Zap className="w-2.5 h-2.5" /> AI analyzed
                </span>
              ) : null}
            </div>
            {req.status !== "open" && (
              <div className="mt-2">
                <ProgressBar value={req.fulfillment_progress} />
              </div>
            )}
          </div>
          <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
            <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusCfg.className}`}>
              <StatusIcon className="w-2.5 h-2.5" />
              {statusCfg.label}
            </span>
            <SlaCountdown dueAt={req.due_at} slaMinutes={req.sla_minutes} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function WarRoomPage() {
  const { id } = useParams<{ id: string }>();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"requests" | "people" | "observations" | "commitments" | "binder" | "intel" | "scribe" | "closing">("requests");
  const [showAddRequest, setShowAddRequest] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<InspRequest | null>(null);
  const [scribeText, setScribeText] = useState("");
  const [scribeType, setScribeType] = useState("scribe_note");
  const [sendingScribe, setSendingScribe] = useState(false);
  const [activating, setActivating] = useState(false);
  const [closing, setClosing] = useState(false);
  const [loadError, setLoadError] = useState("");

  // Sub-resource state
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [inspectors, setInspectors] = useState<Inspector[]>([]);
  const [riskAnalysis, setRiskAnalysis] = useState<any>(null);
  const [closingSummary, setClosingSummary] = useState<string>("");
  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [generatingClosing, setGeneratingClosing] = useState(false);

  // Forms
  const [newCommitment, setNewCommitment] = useState({ commitment_text: "", committed_to: "", deadline_at: "" });
  const [savingCommitment, setSavingCommitment] = useState(false);
  const [newObservation, setNewObservation] = useState({ observation_text: "", system_area: "", response_deadline: "" });
  const [savingObservation, setSavingObservation] = useState(false);
  const [newDelivery, setNewDelivery] = useState({ document_titles: "", delivered_to: "", delivery_method: "hand" });
  const [savingDelivery, setSavingDelivery] = useState(false);
  const [newInspector, setNewInspector] = useState({ name: "", fda_district: "", role: "lead", email: "", notes: "" });
  const [savingInspector, setSavingInspector] = useState(false);

  const [draftingObs, setDraftingObs] = useState<string | null>(null);

  const logEndRef = useRef<HTMLDivElement>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [inspRes, logRes] = await Promise.all([inspectionsApi.get(id), inspectionsApi.getLog(id)]);
      setInspection(inspRes.data);
      setLog(logRes.data.entries ?? []);
    } catch {
      setLoadError("Could not load inspection. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadTabData = useCallback(async (t: string) => {
    try {
      if (t === "commitments") {
        const r = await inspectionsApi.listCommitments(id);
        setCommitments(r.data.commitments ?? []);
      } else if (t === "observations") {
        const r = await inspectionsApi.listObservations(id);
        setObservations(r.data.observations ?? []);
      } else if (t === "binder") {
        const r = await inspectionsApi.listDeliveries(id);
        setDeliveries(r.data.deliveries ?? []);
      } else if (t === "people") {
        const r = await inspectionsApi.listInspectors(id);
        setInspectors(r.data.inspectors ?? []);
      }
    } catch { /* tab data missing is non-fatal */ }
  }, [id]);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { loadTabData(tab); }, [tab, loadTabData]);

  const handleAddRequest = async (data: any) => {
    await inspectionsApi.createRequest(id, data);
    const res = await inspectionsApi.get(id);
    setInspection(res.data);
  };

  const handleScribe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scribeText.trim()) return;
    setSendingScribe(true);
    try {
      const res = await inspectionsApi.addScribeEntry(id, { content: scribeText, entry_type: scribeType });
      setLog(l => [...l, res.data]);
      setScribeText("");
    } finally { setSendingScribe(false); }
  };

  const handleActivate = async () => {
    setActivating(true);
    try { await inspectionsApi.activate(id); await loadAll(); }
    finally { setActivating(false); }
  };

  const handleClose = async () => {
    if (!confirm("Close this inspection? This action cannot be undone.")) return;
    setClosing(true);
    try { await inspectionsApi.close(id); await loadAll(); }
    finally { setClosing(false); }
  };

  const handlePhaseChange = async (phase: string) => {
    try { await inspectionsApi.updatePhase(id, phase); setInspection(i => i ? { ...i, current_phase: phase } : i); }
    catch { /* ignore */ }
  };

  const handleSaveCommitment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCommitment.commitment_text.trim()) return;
    setSavingCommitment(true);
    try {
      await inspectionsApi.createCommitment(id, newCommitment);
      setNewCommitment({ commitment_text: "", committed_to: "", deadline_at: "" });
      await loadTabData("commitments");
    } finally { setSavingCommitment(false); }
  };

  const handleSaveObservation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newObservation.observation_text.trim()) return;
    setSavingObservation(true);
    try {
      await inspectionsApi.createObservation(id, newObservation);
      setNewObservation({ observation_text: "", system_area: "", response_deadline: "" });
      await loadTabData("observations");
    } finally { setSavingObservation(false); }
  };

  const handleSaveDelivery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDelivery.delivered_to.trim() || !newDelivery.document_titles.trim()) return;
    setSavingDelivery(true);
    try {
      await inspectionsApi.createDelivery(id, {
        ...newDelivery,
        document_titles: newDelivery.document_titles.split(",").map(s => s.trim()).filter(Boolean),
      });
      setNewDelivery({ document_titles: "", delivered_to: "", delivery_method: "hand" });
      await loadTabData("binder");
    } finally { setSavingDelivery(false); }
  };

  const handleSaveInspector = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newInspector.name.trim()) return;
    setSavingInspector(true);
    try {
      await inspectionsApi.addInspector(id, newInspector);
      setNewInspector({ name: "", fda_district: "", role: "lead", email: "", notes: "" });
      await loadTabData("people");
    } finally { setSavingInspector(false); }
  };

  const handleDraftObsResponse = async (obsId: string) => {
    setDraftingObs(obsId);
    try {
      const r = await inspectionsApi.draftObservationResponse(id, obsId);
      setObservations(obs => obs.map(o => o.id === obsId ? { ...o, draft_response: r.data.draft_response } : o));
    } finally { setDraftingObs(null); }
  };

  const handleRiskAnalysis = async () => {
    setRunningAnalysis(true);
    try {
      const r = await inspectionsApi.runRiskAnalysis(id);
      setRiskAnalysis(r.data);
    } finally { setRunningAnalysis(false); }
  };

  const handleGenerateClosing = async () => {
    setGeneratingClosing(true);
    try {
      const r = await inspectionsApi.generateClosingSummary(id);
      setClosingSummary(r.data.summary ?? "");
    } finally { setGeneratingClosing(false); }
  };

  const openRequests = (inspection?.requests ?? []).filter(r => r.status === "open" || r.status === "in_progress");
  const resolvedRequests = (inspection?.requests ?? []).filter(r => r.status === "fulfilled" || r.status === "declined");

  const TABS = [
    { key: "requests", label: `Requests${openRequests.length ? ` (${openRequests.length})` : ""}`, icon: MessageSquare },
    { key: "people", label: "People", icon: Users },
    { key: "observations", label: "483s", icon: Shield },
    { key: "commitments", label: "Commitments", icon: BadgeCheck },
    { key: "binder", label: "Binder", icon: Package },
    { key: "intel", label: "Intel", icon: BarChart3 },
    { key: "scribe", label: "Scribe", icon: Mic },
    { key: "closing", label: "Closing", icon: BookOpen },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!inspection) {
    return (
      <div className="text-center py-24">
        <p className="text-muted-foreground">{loadError || "Inspection not found."}</p>
        <Link href="/inspections" className="text-sm text-primary hover:underline mt-2 inline-block">← Back to inspections</Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {showAddRequest && (
        <AddRequestModal onClose={() => setShowAddRequest(false)} onAdd={handleAddRequest} />
      )}
      {selectedRequest && (
        <RequestDetailModal
          req={selectedRequest}
          inspectionId={id}
          onClose={() => setSelectedRequest(null)}
          onUpdate={loadAll}
        />
      )}

      {/* Breadcrumb + Header */}
      <div>
        <Link href="/inspections" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-3">
          <ChevronLeft className="w-3.5 h-3.5" />
          All Inspections
        </Link>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 ${
              inspection.status === "active" ? "bg-emerald-100" : "bg-primary/10"
            }`}>
              <Radio className={`w-5 h-5 ${inspection.status === "active" ? "text-emerald-600 animate-pulse" : "text-primary"}`} />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-semibold tracking-tight">{inspection.title}</h1>
                <InspStatusBadge status={inspection.status} />
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                {inspection.agency && `${inspection.agency} · `}
                {typeLabel(inspection.inspection_type)}
                {inspection.start_date && ` · Started ${inspection.start_date}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadAll} disabled={loading}
              className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
            {inspection.status === "planned" && (
              <button onClick={handleActivate} disabled={activating}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-60">
                {activating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />}
                Activate
              </button>
            )}
            {inspection.status === "active" && (
              <button onClick={handleClose} disabled={closing}
                className="flex items-center gap-2 px-4 py-2 bg-muted border rounded-lg text-sm font-medium hover:bg-accent disabled:opacity-60">
                {closing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                Close
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Phase Navigator */}
      <PhaseNavigator current={inspection.current_phase} status={inspection.status} onPhaseChange={handlePhaseChange} />

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Requests", value: inspection.total_requests },
          { label: "Open / In Progress", value: openRequests.length, highlight: openRequests.length > 0 },
          { label: "Log Entries", value: log.length },
          { label: "AI Agents", value: inspection.status === "active" ? 5 : 0, active: inspection.status === "active" },
        ].map(s => (
          <div key={s.label} className="bg-card border rounded-xl px-4 py-3">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{s.label}</p>
            <p className={`text-2xl font-bold tabular-nums mt-1 ${
              (s as any).highlight ? "text-amber-600" : (s as any).active ? "text-emerald-600" : ""
            }`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* AI Agents Status */}
      <div className="bg-card border rounded-xl p-3">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2.5 flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5 text-primary" /> AI Agents
        </p>
        <div className="flex gap-2 flex-wrap">
          {AI_AGENTS.map(agent => (
            <div key={agent.key} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${
              inspection.status === "active"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-muted/50 border-border text-muted-foreground"
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${inspection.status === "active" ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/40"}`} />
              {agent.label}
            </div>
          ))}
        </div>
      </div>

      {/* Main Tabs */}
      <div className="flex border-b gap-0 overflow-x-auto scrollbar-hide">
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.key} onClick={() => setTab(t.key as any)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${
                tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}>
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* ── Requests Tab ──────────────────────────────────────────────────────── */}
      {tab === "requests" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">Track, respond to, and fulfill inspector requests in real time.</p>
            <button onClick={() => setShowAddRequest(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
              <Plus className="w-3.5 h-3.5" />
              Log Request
            </button>
          </div>
          {(inspection.requests ?? []).length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
              <MessageSquare className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">No requests logged yet</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-sm mx-auto">
                When an inspector asks a question or requests a document, log it here to track SLA and get AI-powered talking points.
              </p>
              <button onClick={() => setShowAddRequest(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 mx-auto">
                <Plus className="w-4 h-4" /> Log First Request
              </button>
            </div>
          ) : (
            <div className="space-y-5">
              {openRequests.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-3 h-3 text-amber-500" /> Active ({openRequests.length})
                  </p>
                  <div className="space-y-2">
                    {openRequests.map(req => (
                      <RequestCard key={req.id} req={req} inspectionId={id} onOpen={setSelectedRequest} />
                    ))}
                  </div>
                </div>
              )}
              {resolvedRequests.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Resolved ({resolvedRequests.length})
                  </p>
                  <div className="space-y-2">
                    {resolvedRequests.map(req => (
                      <RequestCard key={req.id} req={req} inspectionId={id} onOpen={setSelectedRequest} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── People Tab ────────────────────────────────────────────────────────── */}
      {tab === "people" && (
        <div className="space-y-5">
          <p className="text-sm text-muted-foreground">Track the inspection team — FDA investigators and your internal response leads.</p>

          {/* Inspector profiles */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-amber-500" /> FDA Investigators
            </p>
            {inspectors.length === 0 ? (
              <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-8 text-center mb-4">
                <Users className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No investigators added yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                {inspectors.map(insp => (
                  <div key={insp.id} className="bg-card border rounded-xl px-4 py-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-sm">{insp.name}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {insp.role} {insp.fda_district && `· ${insp.fda_district}`}
                        </p>
                        {insp.email && <p className="text-xs text-primary mt-0.5">{insp.email}</p>}
                        {insp.focus_areas?.length > 0 && (
                          <div className="flex gap-1 flex-wrap mt-1.5">
                            {insp.focus_areas.map(a => (
                              <span key={a} className="text-[10px] px-1.5 py-0.5 bg-amber-50 border border-amber-200 rounded text-amber-800">{a}</span>
                            ))}
                          </div>
                        )}
                        {insp.notes && <p className="text-xs text-muted-foreground mt-1 italic">{insp.notes}</p>}
                      </div>
                      <button onClick={async () => { await inspectionsApi.deleteInspector(id, insp.id); await loadTabData("people"); }}
                        className="text-muted-foreground hover:text-red-500 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <form onSubmit={handleSaveInspector} className="bg-card border rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Add Investigator</p>
              <div className="grid grid-cols-2 gap-3">
                <input value={newInspector.name} onChange={e => setNewInspector(f => ({ ...f, name: e.target.value }))}
                  placeholder="Full name *" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <input value={newInspector.fda_district} onChange={e => setNewInspector(f => ({ ...f, fda_district: e.target.value }))}
                  placeholder="FDA District / Agency office" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <input value={newInspector.email} onChange={e => setNewInspector(f => ({ ...f, email: e.target.value }))}
                  placeholder="Email (optional)" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <select value={newInspector.role} onChange={e => setNewInspector(f => ({ ...f, role: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                  <option value="lead">Lead Investigator</option>
                  <option value="secondary">Secondary</option>
                  <option value="observer">Observer</option>
                </select>
              </div>
              <input value={newInspector.notes} onChange={e => setNewInspector(f => ({ ...f, notes: e.target.value }))}
                placeholder="Notes (known focus areas, previous inspections…)"
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              <div className="flex justify-end">
                <button type="submit" disabled={savingInspector || !newInspector.name.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                  {savingInspector ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                  Add
                </button>
              </div>
            </form>
          </div>

          {/* Coaching tip */}
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-xs text-blue-800">
            <p className="font-semibold mb-1 flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> First-time audit tip</p>
            <p>Log each investigator's name and district — Clyira can pull their inspection history to show likely focus areas and past warning letters from their district. Knowing who's in the room is a real advantage.</p>
          </div>
        </div>
      )}

      {/* ── 483 Observations Tab ──────────────────────────────────────────────── */}
      {tab === "observations" && (
        <div className="space-y-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">FDA Form 483 observations — draft responses while the inspection is still live.</p>
            </div>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-900">
            <p className="font-semibold mb-1 flex items-center gap-1.5"><TriangleAlert className="w-3.5 h-3.5" /> What is a Form 483?</p>
            <p>A 483 is a list of inspectional observations the FDA investigator issues at the end of an inspection. You have 15 business days to submit a written response. Starting your draft response early — while facts are fresh — significantly improves your response quality.</p>
          </div>

          {observations.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-8 text-center">
              <Shield className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No observations logged yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {observations.map(obs => (
                <div key={obs.id} className="bg-card border rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b bg-amber-50/50">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="text-[10px] font-bold text-amber-800 font-mono">OBS-{String(obs.observation_number).padStart(3, "0")}</span>
                        {obs.system_area && <span className="text-[10px] text-muted-foreground ml-2">· {obs.system_area}</span>}
                      </div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                        obs.status === "submitted" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                        obs.status === "under_review" ? "bg-blue-50 text-blue-700 border-blue-200" :
                        "bg-muted text-muted-foreground border-border"
                      }`}>{obs.status.replace("_", " ")}</span>
                    </div>
                    <p className="text-sm font-medium mt-1.5 leading-snug">{obs.observation_text}</p>
                    {obs.cfr_citations?.length > 0 && (
                      <div className="flex gap-1 flex-wrap mt-2">
                        {obs.cfr_citations.map(c => (
                          <span key={c} className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded border border-amber-200 font-mono">{c}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="px-4 py-3">
                    {obs.draft_response ? (
                      <div>
                        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Draft Response</p>
                        <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">{obs.draft_response}</p>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleDraftObsResponse(obs.id)}
                        disabled={draftingObs === obs.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-primary/5 hover:border-primary/40 hover:text-primary transition-colors disabled:opacity-50">
                        {draftingObs === obs.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                        {draftingObs === obs.id ? "Drafting…" : "AI Draft Response"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleSaveObservation} className="bg-card border rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Log Observation</p>
            <textarea rows={3} value={newObservation.observation_text}
              onChange={e => setNewObservation(f => ({ ...f, observation_text: e.target.value }))}
              placeholder="Paste the observation text exactly as written by the investigator…"
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none" />
            <div className="grid grid-cols-2 gap-3">
              <input value={newObservation.system_area} onChange={e => setNewObservation(f => ({ ...f, system_area: e.target.value }))}
                placeholder="System area (e.g., Lab Controls)"
                className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              <input type="date" value={newObservation.response_deadline} onChange={e => setNewObservation(f => ({ ...f, response_deadline: e.target.value }))}
                className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
            </div>
            <div className="flex justify-end">
              <button type="submit" disabled={savingObservation || !newObservation.observation_text.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                {savingObservation ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                Log Observation
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Commitments Tab ───────────────────────────────────────────────────── */}
      {tab === "commitments" && (
        <div className="space-y-5">
          <p className="text-sm text-muted-foreground">Track every verbal commitment made to inspectors — these must be followed through.</p>
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-xs text-blue-800">
            <p className="font-semibold mb-1 flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> Why this matters</p>
            <p>If your team says "we'll send that by Friday" during the inspection and doesn't follow through, it becomes a post-inspection observation. Log every commitment made — even casual ones — and track them to completion.</p>
          </div>

          {commitments.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-8 text-center">
              <BadgeCheck className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No commitments logged yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {commitments.map(c => (
                <div key={c.id} className={`bg-card border rounded-xl px-4 py-3 ${
                  c.status === "overdue" ? "border-red-200" :
                  c.status === "delivered" ? "border-emerald-200" : ""
                }`}>
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium leading-snug flex-1">{c.commitment_text}</p>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border flex-shrink-0 ${
                      c.status === "delivered" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                      c.status === "overdue" ? "bg-red-50 text-red-700 border-red-200" :
                      "bg-amber-50 text-amber-700 border-amber-200"
                    }`}>{c.status}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
                    {c.committed_to && <span>To: {c.committed_to}</span>}
                    {c.deadline_at && <span>Due: {new Date(c.deadline_at).toLocaleDateString()}</span>}
                  </div>
                  {c.status === "pending" && (
                    <button
                      onClick={async () => {
                        await inspectionsApi.updateCommitment(id, c.id, { status: "delivered" });
                        await loadTabData("commitments");
                      }}
                      className="mt-2 flex items-center gap-1 text-[10px] text-emerald-700 hover:underline font-medium">
                      <CheckCircle2 className="w-3 h-3" /> Mark Delivered
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleSaveCommitment} className="bg-card border rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Log Commitment</p>
            <textarea rows={2} value={newCommitment.commitment_text}
              onChange={e => setNewCommitment(f => ({ ...f, commitment_text: e.target.value }))}
              placeholder="What was committed? Be specific about deliverables and timelines…"
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none" />
            <div className="grid grid-cols-2 gap-3">
              <input value={newCommitment.committed_to} onChange={e => setNewCommitment(f => ({ ...f, committed_to: e.target.value }))}
                placeholder="Committed to (investigator name)"
                className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              <input type="date" value={newCommitment.deadline_at} onChange={e => setNewCommitment(f => ({ ...f, deadline_at: e.target.value }))}
                className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
            </div>
            <div className="flex justify-end">
              <button type="submit" disabled={savingCommitment || !newCommitment.commitment_text.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                {savingCommitment ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                Log Commitment
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Binder / Document Delivery Tab ────────────────────────────────────── */}
      {tab === "binder" && (
        <div className="space-y-5">
          <p className="text-sm text-muted-foreground">Document delivery log — every hand-off to the inspector, timestamped and receipted.</p>
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-xs text-blue-800">
            <p className="font-semibold mb-1 flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> Best practice</p>
            <p>Always get verbal acknowledgment when handing over documents. Log the investigator's name and method. This creates an auditable chain of custody if the FDA claims a document was "not provided."</p>
          </div>

          {deliveries.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-8 text-center">
              <Package className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No deliveries logged yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {deliveries.map(d => (
                <div key={d.id} className="bg-card border rounded-xl px-4 py-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold">{new Date(d.delivered_at).toLocaleString()}</span>
                    {d.acknowledgment_received && (
                      <span className="flex items-center gap-1 text-[10px] text-emerald-700 font-semibold">
                        <CheckCircle2 className="w-3 h-3" /> Acknowledged
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {d.document_titles.map(t => (
                      <span key={t} className="text-xs px-2 py-1 bg-muted border rounded-md font-medium">{t}</span>
                    ))}
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1.5">
                    To: {d.delivered_to} · via {d.delivery_method ?? "hand"}
                  </p>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleSaveDelivery} className="bg-card border rounded-xl p-4 space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Log Delivery</p>
            <input value={newDelivery.document_titles} onChange={e => setNewDelivery(f => ({ ...f, document_titles: e.target.value }))}
              placeholder="Document names (comma-separated)"
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
            <div className="grid grid-cols-2 gap-3">
              <input value={newDelivery.delivered_to} onChange={e => setNewDelivery(f => ({ ...f, delivered_to: e.target.value }))}
                placeholder="Delivered to (investigator)"
                className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              <select value={newDelivery.delivery_method} onChange={e => setNewDelivery(f => ({ ...f, delivery_method: e.target.value }))}
                className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                <option value="hand">Hand delivery</option>
                <option value="email">Email</option>
                <option value="portal">Portal upload</option>
                <option value="usb">USB / media</option>
              </select>
            </div>
            <div className="flex justify-end">
              <button type="submit" disabled={savingDelivery || !newDelivery.delivered_to.trim() || !newDelivery.document_titles.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                {savingDelivery ? <Loader2 className="w-3 h-3 animate-spin" /> : <Package className="w-3 h-3" />}
                Log Delivery
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ── Intel Tab ─────────────────────────────────────────────────────────── */}
      {tab === "intel" && (
        <div className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm text-muted-foreground">AI-powered cross-request pattern analysis — predicts 483 likelihood before the inspection ends.</p>
            </div>
            <button onClick={handleRiskAnalysis} disabled={runningAnalysis}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium flex-shrink-0 disabled:opacity-60">
              {runningAnalysis ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BarChart3 className="w-3.5 h-3.5" />}
              {runningAnalysis ? "Analyzing…" : "Run Risk Analysis"}
            </button>
          </div>

          {!riskAnalysis ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
              <TrendingUp className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">No analysis yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                Run risk analysis to identify patterns across requests that suggest potential 483 observations before the closing meeting.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {riskAnalysis.risk_level && (
                <div className={`rounded-xl px-5 py-4 border ${
                  riskAnalysis.risk_level === "high" ? "bg-red-50 border-red-200" :
                  riskAnalysis.risk_level === "medium" ? "bg-amber-50 border-amber-200" :
                  "bg-emerald-50 border-emerald-200"
                }`}>
                  <p className="text-xs font-semibold uppercase tracking-wide mb-1">Overall Risk Level</p>
                  <p className="text-2xl font-bold capitalize">{riskAnalysis.risk_level}</p>
                </div>
              )}
              {riskAnalysis.patterns?.length > 0 && (
                <div className="bg-card border rounded-xl p-4">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Detected Patterns</p>
                  <ul className="space-y-2">
                    {riskAnalysis.patterns.map((p: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {riskAnalysis.recommendations?.length > 0 && (
                <div className="bg-card border rounded-xl p-4">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Recommendations</p>
                  <ul className="space-y-2">
                    {riskAnalysis.recommendations.map((r: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <ArrowRight className="w-3.5 h-3.5 text-primary mt-0.5 flex-shrink-0" />
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Scribe Tab ────────────────────────────────────────────────────────── */}
      {tab === "scribe" && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Real-time scribe — capture every observation, question, and action item as it happens.
          </p>
          <form onSubmit={handleScribe} className="bg-card border rounded-xl p-5 space-y-4">
            <div className="flex gap-2 flex-wrap">
              {ENTRY_TYPES.map(t => (
                <button key={t.value} type="button" onClick={() => setScribeType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    scribeType === t.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background border-border text-muted-foreground hover:text-foreground"
                  }`}>
                  {t.label}
                </button>
              ))}
            </div>
            <textarea rows={4}
              placeholder={`Enter ${ENTRY_TYPES.find(t => t.value === scribeType)?.label.toLowerCase() ?? "note"}…`}
              value={scribeText}
              onChange={e => setScribeText(e.target.value)}
              className="w-full border rounded-lg px-3 py-2.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none" />
            <div className="flex justify-end">
              <button type="submit" disabled={sendingScribe || !scribeText.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
                {sendingScribe ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                {sendingScribe ? "Saving…" : "Add Entry"}
              </button>
            </div>
          </form>

          {log.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Timeline</p>
              {[...log].reverse().map(entry => <LogEntryCard key={entry.id} entry={entry} />)}
            </div>
          )}
        </div>
      )}

      {/* ── Closing Tab ───────────────────────────────────────────────────────── */}
      {tab === "closing" && (
        <div className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <p className="text-sm text-muted-foreground">Closing meeting preparation — AI-generated summary and post-inspection checklist.</p>
            <button onClick={handleGenerateClosing} disabled={generatingClosing}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium flex-shrink-0 disabled:opacity-60">
              {generatingClosing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
              {generatingClosing ? "Generating…" : "Generate Summary"}
            </button>
          </div>

          {closingSummary ? (
            <div className="bg-card border rounded-xl p-5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5 text-primary" /> AI Closing Summary
              </p>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{closingSummary}</p>
            </div>
          ) : (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
              <BookOpen className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Ready for closing meeting</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                Generate an AI-powered closing summary that synthesizes all requests, commitments, and observations into a meeting-ready briefing.
              </p>
            </div>
          )}

          {/* Post-inspection checklist */}
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <ClipboardList className="w-3.5 h-3.5 text-primary" /> Post-Inspection Checklist
            </p>
            <div className="space-y-2">
              {[
                { text: "All open requests fulfilled or formally declined", done: openRequests.length === 0 },
                { text: "All verbal commitments logged with deadlines", done: commitments.length > 0 },
                { text: "483 observations documented with response drafts", done: observations.length > 0 },
                { text: "Document delivery log complete with receipts", done: deliveries.length > 0 },
                { text: "Inspection log reviewed and complete", done: log.length > 0 },
              ].map(item => (
                <div key={item.text} className="flex items-center gap-2.5">
                  {item.done
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                    : <Circle className="w-4 h-4 text-muted-foreground/40 flex-shrink-0" />
                  }
                  <span className={`text-sm ${item.done ? "text-foreground" : "text-muted-foreground"}`}>{item.text}</span>
                </div>
              ))}
            </div>
          </div>

          {inspection.status === "active" && (
            <div className="flex justify-end">
              <button onClick={handleClose} disabled={closing}
                className="flex items-center gap-2 px-5 py-2.5 bg-muted border rounded-xl text-sm font-medium hover:bg-accent disabled:opacity-60">
                {closing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                Close Inspection
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

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
  Mic, MicOff, ClipboardList, ChevronDown, ExternalLink, Trash2,
  Edit3, Eye, Lock, Unlock, CheckSquare, Circle,
  Hash, AtSign, ArrowUpRight, Flame,
  Bell, Download, GitMerge, Database, BookMarked,
  ShieldCheck, ShieldOff, AlertCircle,
} from "lucide-react";
import { inspectionsApi } from "@/lib/api";
import { InspStatusBadge } from "@/components/shared/badges";
import { timeAgo } from "@/lib/utils";
import { useInspectionWs } from "@/hooks/use-inspection-ws";

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
  verbal_concern: boolean;
  verbal_concern_notes: string | null;
  root_cause_hypothesis: string | null;
  factual_accuracy_confirmed: boolean;
  created_at: string;
}

interface BinderDoc {
  id: string;
  category: string;
  title: string;
  filename: string | null;
  version: string | null;
  document_date: string | null;
  status: string;
  required: boolean;
  notes: string | null;
  linked_request_id: string | null;
  staged_by_name: string | null;
  staged_at: string | null;
  delivered_at: string | null;
  delivered_to: string | null;
  created_at: string;
}

interface InspectionAlert {
  type: string;
  severity: string;
  title: string;
  body: string;
  request_id?: string;
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

interface TeamMember {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  title: string | null;
  company: string | null;
  room: string;
  role: string | null;
  secondary_roles: string[];
  functional_area: string | null;
  topics: string[];
  approved_talking_points: string[];
  do_not_volunteer: string[];
  known_weak_areas: string | null;
  likely_questions: { question: string; recommended_answer: string }[];
  fda_district: string | null;
  focus_areas: string[];
  notes_on_style: string | null;
  availability: string;
  notes: string | null;
  created_at: string;
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

interface SME {
  id: string;
  name: string;
  title: string | null;
  department: string | null;
  email: string | null;
  phone: string | null;
  room: string;
  availability: string;
  topics: string[];
  backup_for: string | null;
  prep_status: string;
  qa_cleared: boolean;
  qa_cleared_at: string | null;
  approved_talking_points: string[];
  do_not_volunteer: string[];
  do_not_speculate: string[];
  escalation_triggers: string[];
  likely_questions: { question: string; recommended_answer: string }[];
  relevant_documents: string[];
  known_weak_areas: string | null;
  call_log: { called_at: string; called_by: string; reason: string; notes: string }[];
  notes: string | null;
  created_at: string;
}

interface EvidencePackage {
  id: string;
  inspection_id: string;
  request_id: string | null;
  title: string;
  description: string | null;
  status: string;
  documents: { id: string; filename: string; version?: string; approval_status: string; flags: Record<string, boolean>; added_by: string }[];
  package_risk: string;
  completeness_status: string;
  owner_name: string | null;
  qa_approver_name: string | null;
  qa_approved_at: string | null;
  qa_notes: string | null;
  qa_checks: Record<string, boolean>;
  released_by_name: string | null;
  released_at: string | null;
  release_notes: string | null;
  legal_review_required: boolean;
  created_at: string;
}

interface CAPA {
  id: string;
  action_type: string;
  title: string;
  description: string | null;
  owner_name: string | null;
  department: string | null;
  due_date: string | null;
  completed_at: string | null;
  status: string;
  criticality: string;
  completion_notes: string | null;
  effectiveness_check_required: boolean;
  lesson_learned: string | null;
  linked_observation_id: string | null;
  linked_request_id: string | null;
  created_at: string;
}

interface InspectionMetrics {
  requests: { total: number; open: number; qa_review: number; approved: number; released: number; fulfilled: number; critical: number; overdue: number; completion_pct: number; avg_response_minutes: number | null };
  commitments: { total: number; open: number; overdue: number };
  findings: { active: number; high_confidence: number };
  packages: { staged: number; released: number };
  smes: { total: number; available: number; qa_cleared: number };
  control_status: string;
  risk_score: number;
  current_phase: string | null;
  day_count: number;
}

interface PotentialFinding {
  id: string;
  title: string;
  inspector_framing: string | null;
  system_area: string | null;
  cfr_citations: string[];
  confidence: string;
  status: string;
  defense_summary: string | null;
  linked_request_ids: string[];
  linked_document_ids: string[];
  qa_reviewed: boolean;
  qa_reviewed_by: string | null;
  qa_reviewed_at: string | null;
  ai_generated: boolean;
  source: string;
  created_at: string;
}

interface ChatMessage {
  id: string;
  sender_id: string;
  sender_name: string;
  content: string;
  room: string;
  message_type: string;
  linked_request_id: string | null;
  linked_commitment_id: string | null;
  converted_to_request_id: string | null;
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
  open: { label: "Logged", className: "text-amber-700 bg-amber-50 border-amber-200", icon: AlertTriangle },
  triage: { label: "Triage", className: "text-orange-700 bg-orange-50 border-orange-200", icon: AlertCircle },
  assigned: { label: "Assigned to Prep", className: "text-blue-700 bg-blue-50 border-blue-200", icon: User },
  in_progress: { label: "With Runner", className: "text-indigo-700 bg-indigo-50 border-indigo-200", icon: Clock },
  evidence_gathering: { label: "With Liaison", className: "text-violet-700 bg-violet-50 border-violet-200", icon: FileText },
  qa_review: { label: "Under Review", className: "text-purple-700 bg-purple-50 border-purple-200", icon: Shield },
  approved: { label: "With Host", className: "text-blue-700 bg-blue-50 border-blue-200", icon: CheckSquare },
  released: { label: "Delivered", className: "text-emerald-700 bg-emerald-50 border-emerald-200", icon: ArrowUpRight },
  fulfilled: { label: "Done", className: "text-emerald-700 bg-emerald-50 border-emerald-200", icon: CheckCircle2 },
  declined: { label: "Declined", className: "text-red-700 bg-red-50 border-red-200", icon: XCircle },
  withdrawn: { label: "Withdrawn", className: "text-gray-600 bg-gray-50 border-gray-200", icon: XCircle },
  closed: { label: "Closed", className: "text-gray-600 bg-gray-50 border-gray-200", icon: CheckCircle2 },
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
  const [qaing, setQaing] = useState(false);
  const [converting, setConverting] = useState<string | null>(null);

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

  const handleQaAction = async (action: string) => {
    setQaing(true);
    try {
      await inspectionsApi.qaActionRequest(inspectionId, req.id, action);
      onUpdate();
      onClose();
    } finally { setQaing(false); }
  };

  const handleConvert = async (to: "commitment" | "finding" | "capa") => {
    setConverting(to);
    try {
      if (to === "commitment") {
        await inspectionsApi.createCommitment(inspectionId, { commitment_text: req.request_text });
      } else if (to === "finding") {
        await inspectionsApi.createPotentialFinding(inspectionId, {
          title: req.request_text.slice(0, 120),
          inspector_framing: req.request_text,
          linked_request_ids: [req.id],
        });
      } else if (to === "capa") {
        await inspectionsApi.createCAPA(inspectionId, {
          title: req.request_text.slice(0, 120),
          linked_request_id: req.id,
        });
      }
      onUpdate();
    } finally { setConverting(null); }
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
        {req.status !== "fulfilled" && req.status !== "declined" && req.status !== "withdrawn" && (
          <div className="border-t px-4 py-3 flex-shrink-0 space-y-2">
            {/* QA Gate workflow row */}
            <div className="flex gap-2 flex-wrap">
              {req.status === "open" && (
                <button onClick={() => handleStatusUpdate("in_progress")} disabled={updatingStatus}
                  className="px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors disabled:opacity-50">
                  Mark In Progress
                </button>
              )}
              {(req.status === "open" || req.status === "in_progress" || req.status === "evidence_gathering") && (
                <button onClick={() => handleQaAction("send_to_qa")} disabled={qaing}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-purple-200 text-purple-700 rounded-lg hover:bg-purple-50 disabled:opacity-50">
                  {qaing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Shield className="w-3 h-3" />}
                  Send to QA
                </button>
              )}
              {req.status === "qa_review" && (
                <>
                  <button onClick={() => handleQaAction("approve")} disabled={qaing}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-emerald-200 text-emerald-700 rounded-lg hover:bg-emerald-50 disabled:opacity-50">
                    {qaing ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                    QA Approve
                  </button>
                  <button onClick={() => handleQaAction("reject")} disabled={qaing}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-red-200 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-50">
                    Return
                  </button>
                </>
              )}
              {req.status === "approved" && (
                <button onClick={() => handleQaAction("release")} disabled={qaing}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50">
                  {qaing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowUpRight className="w-3 h-3" />}
                  Release to Inspector
                </button>
              )}
              <button onClick={() => handleStatusUpdate("fulfilled")} disabled={updatingStatus}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 ml-auto">
                {updatingStatus ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                Fulfilled
              </button>
            </div>
            {/* Convert to row */}
            <div className="flex gap-2 flex-wrap">
              <span className="text-[10px] text-muted-foreground self-center">Convert to:</span>
              {(["commitment", "finding", "capa"] as const).map(target => (
                <button key={target} onClick={() => handleConvert(target)} disabled={converting === target}
                  className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium border rounded-md hover:bg-muted disabled:opacity-50">
                  {converting === target ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : null}
                  {target === "commitment" ? "Commitment" : target === "finding" ? "Finding" : "CAPA"}
                </button>
              ))}
            </div>
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
  const [tab, setTab] = useState<"requests" | "findings" | "team" | "scribe" | "chat" | "prep" | "post">("requests");
  const [showAddRequest, setShowAddRequest] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<InspRequest | null>(null);
  const [scribeText, setScribeText] = useState("");
  const [scribeType, setScribeType] = useState("scribe_note");
  const [sendingScribe, setSendingScribe] = useState(false);

  // Voice scribe
  const [isRecording, setIsRecording] = useState(false);
  const [interimText, setInterimText] = useState("");
  const [voiceSupported, setVoiceSupported] = useState(false);
  const recognitionRef = useRef<any>(null);
  const isRecordingRef = useRef(false);
  const lastFinalRef = useRef("");
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
  const [connectedUsers, setConnectedUsers] = useState(1);
  const [inspectorBriefs, setInspectorBriefs] = useState<Record<string, any>>({});
  const [briefingInspector, setBriefingInspector] = useState<string | null>(null);
  const [expandedBrief, setExpandedBrief] = useState<string | null>(null);
  const [wsToasts, setWsToasts] = useState<{ id: string; message: string; type: string }[]>([]);

  // SME state (kept for backward compat with existing API calls)
  const [smes, setSMEs] = useState<SME[]>([]);
  const [showAddSME, setShowAddSME] = useState(false);
  const [newSME, setNewSME] = useState({ name: "", title: "", department: "", email: "", topics: "" });
  const [savingSME, setSavingSME] = useState(false);
  const [expandedSME, setExpandedSME] = useState<string | null>(null);
  const [coachingSME, setCoachingSME] = useState<string | null>(null);

  // Team members (new unified model)
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [showAddTeamMember, setShowAddTeamMember] = useState(false);
  const [newTeamMember, setNewTeamMember] = useState({ name: "", title: "", email: "", phone: "", room: "prep", role: "", functional_area: "", topics: "", fda_district: "", notes: "" });
  const [savingTeamMember, setSavingTeamMember] = useState(false);
  const [expandedTeamMember, setExpandedTeamMember] = useState<string | null>(null);

  // CAPA state
  const [capas, setCAPAs] = useState<CAPA[]>([]);
  const [showAddCAPA, setShowAddCAPA] = useState(false);
  const [newCAPA, setNewCAPA] = useState({ title: "", description: "", action_type: "capa", owner_name: "", department: "", due_date: "", criticality: "medium" });
  const [savingCAPA, setSavingCAPA] = useState(false);

  // Metrics
  const [metrics, setMetrics] = useState<InspectionMetrics | null>(null);
  const [dailyBrief, setDailyBrief] = useState("");
  const [generatingBrief, setGeneratingBrief] = useState(false);

  // Post-inspection
  const [postSummary, setPostSummary] = useState<any>(null);
  const [postEdit, setPostEdit] = useState({ outcome: "", post_inspection_notes: "", final_483_count: 0 });
  const [savingPost, setSavingPost] = useState(false);

  // Potential findings state
  const [potentialFindings, setPotentialFindings] = useState<PotentialFinding[]>([]);
  const [showAddFinding, setShowAddFinding] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [newFinding, setNewFinding] = useState({ title: "", inspector_framing: "", system_area: "", cfr_citations: "", confidence: "medium", defense_summary: "" });
  const [savingFinding, setSavingFinding] = useState(false);
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);
  const [editingFinding, setEditingFinding] = useState<string | null>(null);
  const [editFindingData, setEditFindingData] = useState<Partial<PotentialFinding>>({});

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatRoom, setChatRoom] = useState("all");
  const [chatInput, setChatInput] = useState("");
  const [chatType, setChatType] = useState("general");
  const [sendingChat, setSendingChat] = useState(false);
  const [convertingMsg, setConvertingMsg] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Binder state
  const [binderDocs, setBinderDocs] = useState<BinderDoc[]>([]);
  const [showAddBinder, setShowAddBinder] = useState(false);
  const [newBinderDoc, setNewBinderDoc] = useState({ title: "", category: "other", filename: "", version: "" });
  const [savingBinder, setSavingBinder] = useState(false);
  const [seedingBinder, setSeedingBinder] = useState(false);

  // Alerts
  const [alerts, setAlerts] = useState<InspectionAlert[]>([]);
  const [showAlerts, setShowAlerts] = useState(false);

  // Safe mode
  const [safeMode, setSafeMode] = useState(false);
  const [togglingMode, setTogglingMode] = useState(false);

  // Lessons learned
  const [lessons, setLessons] = useState<string[]>([]);
  const [newLesson, setNewLesson] = useState("");
  const [savingLesson, setSavingLesson] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);
  // Stable ref so the WS callback can call the latest loadAll without a circular dep
  const loadAllRef = useRef<() => void>(() => {});

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
      if (t === "team") {
        const [teamRes, smeRes, peopleRes] = await Promise.all([
          inspectionsApi.listTeam(id),
          inspectionsApi.listSMEs(id),
          inspectionsApi.listInspectors(id),
        ]);
        setTeamMembers(teamRes.data.members ?? []);
        setSMEs(smeRes.data.smes ?? []);
        setInspectors(peopleRes.data.inspectors ?? []);
      } else if (t === "prep") {
        const [binderRes, deliveriesRes] = await Promise.all([
          inspectionsApi.listBinder(id),
          inspectionsApi.listDeliveries(id),
        ]);
        setBinderDocs(binderRes.data.binder_docs ?? []);
        setDeliveries(deliveriesRes.data.deliveries ?? []);
      } else if (t === "chat") {
        const r = await inspectionsApi.listMessages(id);
        setChatMessages(r.data.messages ?? []);
      } else if (t === "findings") {
        const r = await inspectionsApi.listPotentialFindings(id);
        setPotentialFindings(r.data.findings ?? []);
      } else if (t === "post") {
        const [postRes, lessonsRes, obsRes, capaRes, metricsRes] = await Promise.all([
          inspectionsApi.getPostInspectionSummary(id),
          inspectionsApi.getLessons(id),
          inspectionsApi.listObservations(id),
          inspectionsApi.listCAPAs(id),
          inspectionsApi.getMetrics(id),
        ]);
        setPostSummary(postRes.data);
        setLessons(lessonsRes.data.lessons ?? []);
        setObservations(obsRes.data.observations ?? []);
        setCAPAs(capaRes.data.capas ?? []);
        setMetrics(metricsRes.data);
      }
    } catch { /* tab data missing is non-fatal */ }
  }, [id]);

  // Keep ref current so WS callback always calls the latest version
  loadAllRef.current = loadAll;

  const addToast = useCallback((message: string, type: string = "info") => {
    const tid = Math.random().toString(36).slice(2);
    setWsToasts(t => [...t.slice(-2), { id: tid, message, type }]);
    setTimeout(() => setWsToasts(t => t.filter(x => x.id !== tid)), 4000);
  }, []);

  useInspectionWs(id, useCallback((event) => {
    if (event.type === "presence") {
      setConnectedUsers(event.connected);
    } else if (event.type === "request_update") {
      loadAllRef.current();
    } else if (event.type === "scribe_note") {
      addToast(`${event.author}: ${event.content.slice(0, 60)}${event.content.length > 60 ? "…" : ""}`, "note");
      loadAllRef.current();
    } else if (event.type === "sla_alert") {
      addToast(`SLA breach: ${event.request_text.slice(0, 50)}…`, "alert");
    } else if (event.type === "chat_message") {
      setChatMessages(prev => {
        if (prev.some(m => m.id === event.id)) return prev;
        return [...prev, event as ChatMessage];
      });
    } else if (event.type === "request_created" && event.from_chat) {
      loadAllRef.current();
      addToast("Chat message converted to request", "info");
    } else if (event.type === "potential_finding_added") {
      setPotentialFindings(prev => {
        if (prev.some(f => f.id === (event as any).id)) return prev;
        return [event as unknown as PotentialFinding, ...prev];
      });
    } else if (event.type === "potential_finding_updated") {
      setPotentialFindings(prev => prev.map(f => f.id === (event as any).id ? event as unknown as PotentialFinding : f));
    } else if (event.type === "ai_scan_complete") {
      loadTabData("findings");
      addToast(`AI scan complete — ${(event as any).count} potential finding${(event as any).count !== 1 ? "s" : ""} identified`, "info");
    } else if (event.type === "sme_update") {
      setSMEs(prev => prev.map(s => s.id === event.sme_id
        ? { ...s, availability: event.availability ?? s.availability, qa_cleared: event.qa_cleared ?? s.qa_cleared }
        : s));
    }
  }, [addToast]));

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { loadTabData(tab); }, [tab, loadTabData]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatMessages]);

  // Detect Web Speech API support (client-side only)
  useEffect(() => {
    setVoiceSupported(
      typeof window !== "undefined" &&
      !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
    );
  }, []);

  // Stop recording when leaving the scribe tab
  useEffect(() => {
    if (tab !== "scribe" && isRecordingRef.current) {
      isRecordingRef.current = false;
      recognitionRef.current?.stop();
      setIsRecording(false);
      setInterimText("");
    }
  }, [tab]);

  // Stop recording on unmount
  useEffect(() => {
    return () => {
      isRecordingRef.current = false;
      recognitionRef.current?.stop();
    };
  }, []);

  const handleAddRequest = async (data: any) => {
    await inspectionsApi.createRequest(id, data);
    const res = await inspectionsApi.get(id);
    setInspection(res.data);
  };

  const handleScribe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scribeText.trim()) return;
    // Stop voice if running before saving
    if (isRecordingRef.current) {
      isRecordingRef.current = false;
      recognitionRef.current?.stop();
      setIsRecording(false);
      setInterimText("");
    }
    setSendingScribe(true);
    try {
      const res = await inspectionsApi.addScribeEntry(id, { content: scribeText, entry_type: scribeType });
      setLog(l => [...l, res.data]);
      setScribeText("");
      lastFinalRef.current = "";
    } finally { setSendingScribe(false); }
  };

  const toggleRecording = () => {
    if (isRecordingRef.current) {
      isRecordingRef.current = false;
      recognitionRef.current?.stop();
      setIsRecording(false);
      setInterimText("");
      return;
    }

    const SR: any = typeof window !== "undefined" &&
      ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
    if (!SR) return;

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript: string = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          // Capitalise first char and ensure space separator
          const segment = transcript.trim().replace(/^./, c => c.toUpperCase()) + " ";
          lastFinalRef.current = segment;
          setScribeText(prev => prev + segment);
        } else {
          interim += transcript;
        }
      }
      setInterimText(interim);
    };

    recognition.onerror = (event: any) => {
      // "no-speech" is normal (silence timeout) — restart silently
      if (event.error !== "no-speech") {
        isRecordingRef.current = false;
        setIsRecording(false);
      }
      setInterimText("");
    };

    recognition.onend = () => {
      setInterimText("");
      // Chrome stops after ~60s of silence — restart automatically if still in recording mode
      if (isRecordingRef.current) {
        try { recognition.start(); } catch {}
      }
    };

    recognitionRef.current = recognition;
    isRecordingRef.current = true;
    setIsRecording(true);
    recognition.start();
  };

  const handleRedoLast = () => {
    if (!lastFinalRef.current) return;
    setScribeText(prev => {
      const idx = prev.lastIndexOf(lastFinalRef.current);
      if (idx >= 0) return prev.slice(0, idx) + prev.slice(idx + lastFinalRef.current.length);
      return prev;
    });
    lastFinalRef.current = "";
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    setSendingChat(true);
    try {
      await inspectionsApi.sendMessage(id, {
        content: chatInput.trim(),
        room: chatRoom,
        message_type: chatType,
      });
      setChatInput("");
    } catch { /* ignore — WS will not fire but REST response is ok */ }
    finally { setSendingChat(false); }
  };

  const handleSaveSME = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSME.name.trim()) return;
    setSavingSME(true);
    try {
      const res = await inspectionsApi.createSME(id, {
        ...newSME,
        topics: newSME.topics.split(",").map(s => s.trim()).filter(Boolean),
      });
      setSMEs(prev => [...prev, res.data]);
      setNewSME({ name: "", title: "", department: "", email: "", topics: "" });
      setShowAddSME(false);
    } finally { setSavingSME(false); }
  };

  const handleCoachSME = async (smeId: string) => {
    setCoachingSME(smeId);
    try {
      const res = await inspectionsApi.aiCoachSME(id, smeId);
      setSMEs(prev => prev.map(s => s.id === smeId ? res.data : s));
    } finally { setCoachingSME(null); }
  };

  const handleSaveCAPA = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCAPA.title.trim()) return;
    setSavingCAPA(true);
    try {
      const res = await inspectionsApi.createCAPA(id, newCAPA);
      setCAPAs(prev => [res.data, ...prev]);
      setNewCAPA({ title: "", description: "", action_type: "capa", owner_name: "", department: "", due_date: "", criticality: "medium" });
      setShowAddCAPA(false);
    } finally { setSavingCAPA(false); }
  };

  const handleGenerateBrief = async () => {
    setGeneratingBrief(true);
    try {
      const res = await inspectionsApi.generateDailyBrief(id);
      setDailyBrief(res.data.brief);
    } finally { setGeneratingBrief(false); }
  };

  const handleAiScan = async () => {
    setScanning(true);
    try {
      await inspectionsApi.aiScanFindings(id);
      await loadTabData("findings");
    } finally { setScanning(false); }
  };

  const handleSaveFinding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFinding.title.trim()) return;
    setSavingFinding(true);
    try {
      const res = await inspectionsApi.createPotentialFinding(id, {
        ...newFinding,
        cfr_citations: newFinding.cfr_citations.split(",").map(s => s.trim()).filter(Boolean),
      });
      setPotentialFindings(prev => [res.data, ...prev]);
      setNewFinding({ title: "", inspector_framing: "", system_area: "", cfr_citations: "", confidence: "medium", defense_summary: "" });
      setShowAddFinding(false);
    } finally { setSavingFinding(false); }
  };

  const handleQaFinding = async (fid: string) => {
    const res = await inspectionsApi.qaPotentialFinding(id, fid);
    setPotentialFindings(prev => prev.map(f => f.id === fid ? res.data : f));
  };

  const handleUpdateFinding = async (fid: string) => {
    const payload: Parameters<typeof inspectionsApi.updatePotentialFinding>[2] = {};
    if (editFindingData.title !== undefined) payload.title = editFindingData.title;
    if (editFindingData.inspector_framing != null) payload.inspector_framing = editFindingData.inspector_framing;
    if (editFindingData.defense_summary != null) payload.defense_summary = editFindingData.defense_summary;
    if (editFindingData.system_area != null) payload.system_area = editFindingData.system_area;
    if (editFindingData.confidence !== undefined) payload.confidence = editFindingData.confidence;
    if (editFindingData.cfr_citations !== undefined) payload.cfr_citations = editFindingData.cfr_citations;
    if (editFindingData.linked_request_ids !== undefined) payload.linked_request_ids = editFindingData.linked_request_ids;
    const res = await inspectionsApi.updatePotentialFinding(id, fid, payload);
    setPotentialFindings(prev => prev.map(f => f.id === fid ? res.data : f));
    setEditingFinding(null);
  };

  const handleDeleteFinding = async (fid: string) => {
    if (!confirm("Remove this potential finding?")) return;
    await inspectionsApi.deletePotentialFinding(id, fid);
    setPotentialFindings(prev => prev.filter(f => f.id !== fid));
  };

  const handleConvertToRequest = async (msgId: string) => {
    setConvertingMsg(msgId);
    try {
      await inspectionsApi.convertMessageToRequest(id, msgId);
      setChatMessages(prev => prev.map(m => m.id === msgId ? { ...m, converted_to_request_id: "converted" } : m));
    } catch { /* already converted or error */ }
    finally { setConvertingMsg(null); }
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
      /* commitments tab removed — no reload needed */
    } finally { setSavingCommitment(false); }
  };

  const handleSaveObservation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newObservation.observation_text.trim()) return;
    setSavingObservation(true);
    try {
      await inspectionsApi.createObservation(id, newObservation);
      setNewObservation({ observation_text: "", system_area: "", response_deadline: "" });
      await loadTabData("post");
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
      await loadTabData("prep");
    } finally { setSavingDelivery(false); }
  };

  const handleSaveInspector = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newInspector.name.trim()) return;
    setSavingInspector(true);
    try {
      await inspectionsApi.addInspector(id, newInspector);
      setNewInspector({ name: "", fda_district: "", role: "lead", email: "", notes: "" });
      await loadTabData("team");
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

  const DONE_STATUSES = ["fulfilled", "declined", "withdrawn", "closed", "released"];
  const openRequests = (inspection?.requests ?? []).filter(r => !DONE_STATUSES.includes(r.status));
  const resolvedRequests = (inspection?.requests ?? []).filter(r => DONE_STATUSES.includes(r.status));
  const teamCount = teamMembers.length + smes.length + inspectors.length;

  const TABS = [
    { key: "requests", label: `Requests${openRequests.length ? ` (${openRequests.length})` : ""}`, icon: MessageSquare },
    { key: "findings", label: `Findings${potentialFindings.filter(f => f.status === "tracking").length ? ` (${potentialFindings.filter(f => f.status === "tracking").length})` : ""}`, icon: TriangleAlert },
    { key: "team", label: `Team${teamCount ? ` (${teamCount})` : ""}`, icon: Users },
    { key: "scribe", label: "Scribe", icon: Mic },
    { key: "chat", label: "Chat", icon: Hash },
    { key: "prep", label: "Pre-Inspection Prep", icon: FileText },
    { key: "post", label: "Post-Inspection", icon: ClipboardList },
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
      {/* WebSocket toast notifications */}
      {wsToasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
          {wsToasts.map(t => (
            <div key={t.id} className={`px-4 py-3 rounded-xl border shadow-lg text-sm max-w-xs backdrop-blur-sm ${
              t.type === "alert" ? "bg-red-50 border-red-200 text-red-800" : "bg-card border-border"
            }`}>
              {t.message}
            </div>
          ))}
        </div>
      )}

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
            {inspection.status === "active" && (
              <div className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-xs font-medium text-muted-foreground">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {connectedUsers} live
              </div>
            )}
            {/* Alert Bell */}
            <div className="relative">
              <button
                onClick={async () => {
                  setShowAlerts(f => !f);
                  if (!showAlerts) {
                    try {
                      const r = await inspectionsApi.getAlerts(id);
                      setAlerts(r.data.alerts ?? []);
                    } catch {}
                  }
                }}
                className="relative flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent"
                title="Alerts"
              >
                <Bell className="w-3.5 h-3.5" />
                {alerts.filter(a => a.severity === "critical").length > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-600 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                    {alerts.filter(a => a.severity === "critical").length}
                  </span>
                )}
              </button>
              {showAlerts && (
                <div className="absolute right-0 top-10 z-50 w-80 bg-card border rounded-xl shadow-xl overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2.5 border-b">
                    <span className="text-xs font-semibold">Live Alerts ({alerts.length})</span>
                    <button onClick={() => setShowAlerts(false)}><X className="w-3.5 h-3.5" /></button>
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {alerts.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-6">No active alerts</p>
                    ) : (
                      <div className="divide-y">
                        {alerts.map((a, i) => (
                          <div key={i} className={`px-4 py-3 ${
                            a.severity === "critical" ? "bg-red-50" : a.severity === "warning" ? "bg-amber-50" : "bg-blue-50"
                          }`}>
                            <p className="text-xs font-semibold">{a.title}</p>
                            <p className="text-[11px] text-muted-foreground mt-0.5">{a.body}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            {/* Safe Mode Toggle */}
            <button
              onClick={async () => {
                setTogglingMode(true);
                try {
                  const r = await inspectionsApi.toggleSafeMode(id);
                  setSafeMode(r.data.inspector_safe_mode);
                } finally { setTogglingMode(false); }
              }}
              disabled={togglingMode}
              title={safeMode ? "Inspector-safe mode ON — click to show internal data" : "Show internal-only data — click to enable safe mode"}
              className={`flex items-center gap-1.5 px-3 py-2 border rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                safeMode ? "bg-amber-50 border-amber-300 text-amber-800" : "hover:bg-accent text-muted-foreground"
              }`}
            >
              {safeMode ? <ShieldOff className="w-3.5 h-3.5" /> : <ShieldCheck className="w-3.5 h-3.5" />}
              {safeMode ? "Safe" : "Internal"}
            </button>
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

      {/* ── Potential Findings Tab ────────────────────────────────────────────── */}
      {tab === "findings" && (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="font-semibold flex items-center gap-2">
                <TriangleAlert className="w-4 h-4 text-amber-500" />
                Potential 483 Tracker
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Track patterns the inspector may be building toward. Internal only — never shown to the inspector.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAiScan}
                disabled={scanning}
                className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
                {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-primary" />}
                {scanning ? "Scanning…" : "AI Scan"}
              </button>
              <button
                onClick={() => setShowAddFinding(f => !f)}
                className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                <Plus className="w-3.5 h-3.5" />
                Add Finding
              </button>
            </div>
          </div>

          {/* Add finding form */}
          {showAddFinding && (
            <form onSubmit={handleSaveFinding} className="bg-card border rounded-xl p-5 space-y-3">
              <h3 className="text-sm font-semibold">New Potential Finding</h3>
              <input
                placeholder="Title (e.g. Batch Record Completeness)"
                value={newFinding.title}
                onChange={e => setNewFinding(f => ({ ...f, title: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              />
              <div className="grid grid-cols-2 gap-3">
                <input
                  placeholder="System area (e.g. Batch Records)"
                  value={newFinding.system_area}
                  onChange={e => setNewFinding(f => ({ ...f, system_area: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                />
                <select
                  value={newFinding.confidence}
                  onChange={e => setNewFinding(f => ({ ...f, confidence: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary">
                  <option value="low">Low confidence</option>
                  <option value="medium">Medium confidence</option>
                  <option value="high">High confidence</option>
                  <option value="certain">Certain</option>
                </select>
              </div>
              <textarea
                placeholder="How inspector would write this in a 483 (optional)"
                value={newFinding.inspector_framing}
                onChange={e => setNewFinding(f => ({ ...f, inspector_framing: e.target.value }))}
                rows={2}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
              />
              <textarea
                placeholder="Internal defense notes"
                value={newFinding.defense_summary}
                onChange={e => setNewFinding(f => ({ ...f, defense_summary: e.target.value }))}
                rows={2}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
              />
              <input
                placeholder="CFR citations (comma-separated, e.g. 21 CFR 211.68, 21 CFR 211.100)"
                value={newFinding.cfr_citations}
                onChange={e => setNewFinding(f => ({ ...f, cfr_citations: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              />
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setShowAddFinding(false)}
                  className="px-3 py-2 text-sm border rounded-lg hover:bg-accent">Cancel</button>
                <button type="submit" disabled={savingFinding}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-60">
                  {savingFinding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  {savingFinding ? "Saving…" : "Save Finding"}
                </button>
              </div>
            </form>
          )}

          {/* Finding cards */}
          {potentialFindings.length === 0 ? (
            <div className="bg-card border rounded-xl py-12 text-center">
              <TriangleAlert className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No potential findings tracked yet</p>
              <p className="text-xs text-muted-foreground mt-1">Add manually or run an AI scan to identify patterns from inspector requests</p>
            </div>
          ) : (
            <div className="space-y-3">
              {potentialFindings.map(pf => {
                const confColors: Record<string, string> = {
                  low: "bg-blue-50 border-blue-200 text-blue-700",
                  medium: "bg-amber-50 border-amber-200 text-amber-700",
                  high: "bg-orange-50 border-orange-200 text-orange-700",
                  certain: "bg-red-50 border-red-200 text-red-700",
                };
                const statusColors: Record<string, string> = {
                  tracking: "bg-amber-100 text-amber-800",
                  responded: "bg-blue-100 text-blue-800",
                  resolved: "bg-emerald-100 text-emerald-800",
                  escalated_to_483: "bg-red-100 text-red-800",
                };
                const confColor = confColors[pf.confidence] ?? confColors.medium;
                const isExpanded = expandedFinding === pf.id;
                const isEditing = editingFinding === pf.id;

                return (
                  <div key={pf.id} className={`bg-card border rounded-xl overflow-hidden ${
                    pf.confidence === "certain" ? "border-red-200" : pf.confidence === "high" ? "border-orange-200" : ""
                  }`}>
                    {/* Card header */}
                    <div className="flex items-start gap-3 p-4">
                      <div className={`mt-0.5 px-2 py-0.5 rounded border text-xs font-semibold flex-shrink-0 ${confColor}`}>
                        {pf.confidence.charAt(0).toUpperCase() + pf.confidence.slice(1)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold">{pf.title}</p>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              {pf.system_area && (
                                <span className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground">{pf.system_area}</span>
                              )}
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${statusColors[pf.status] ?? statusColors.tracking}`}>
                                {pf.status.replace(/_/g, " ")}
                              </span>
                              {pf.ai_generated && (
                                <span className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded flex items-center gap-0.5">
                                  <Zap className="w-2.5 h-2.5" /> AI
                                </span>
                              )}
                              {pf.qa_reviewed && (
                                <span className="text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded flex items-center gap-0.5">
                                  <BadgeCheck className="w-2.5 h-2.5" /> QA Reviewed
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1 flex-shrink-0">
                            <button
                              onClick={() => handleQaFinding(pf.id)}
                              title={pf.qa_reviewed ? "Remove QA review" : "Mark QA reviewed"}
                              className={`p-1.5 rounded-lg text-xs border transition-colors ${
                                pf.qa_reviewed
                                  ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                                  : "border-border text-muted-foreground hover:text-emerald-600 hover:border-emerald-300"
                              }`}>
                              <BadgeCheck className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                if (isEditing) { setEditingFinding(null); return; }
                                setEditingFinding(pf.id);
                                setEditFindingData({ ...pf, cfr_citations: pf.cfr_citations });
                              }}
                              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => setExpandedFinding(isExpanded ? null : pf.id)}
                              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                            </button>
                            <button onClick={() => handleDeleteFinding(pf.id)}
                              className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-red-500 transition-colors">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && !isEditing && (
                      <div className="border-t px-4 py-3 space-y-3 bg-muted/20">
                        {pf.inspector_framing && (
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">How Inspector Would Write It</p>
                            <p className="text-xs text-muted-foreground italic border-l-2 border-amber-300 pl-3">{pf.inspector_framing}</p>
                          </div>
                        )}
                        {pf.defense_summary && (
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Internal Defense</p>
                            <p className="text-xs">{pf.defense_summary}</p>
                          </div>
                        )}
                        {pf.cfr_citations?.length > 0 && (
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">CFR Citations</p>
                            <div className="flex flex-wrap gap-1">
                              {pf.cfr_citations.map(c => (
                                <span key={c} className="text-[10px] px-2 py-0.5 bg-primary/10 border border-primary/20 text-primary rounded font-mono">{c}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {pf.linked_request_ids?.length > 0 && (
                          <div>
                            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                              Linked Requests ({pf.linked_request_ids.length})
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {pf.linked_request_ids.map(rid => {
                                const req = (inspection?.requests ?? []).find(r => r.id === rid);
                                return (
                                  <span key={rid} className="text-[10px] px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-700 rounded">
                                    {req ? `REQ-${String(req.request_number).padStart(3, "0")}` : rid.slice(0, 8)}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        {/* Status change */}
                        <div className="flex gap-2 pt-1">
                          {["tracking", "responded", "resolved", "escalated_to_483"].map(s => (
                            <button key={s} onClick={() => inspectionsApi.updatePotentialFinding(id, pf.id, { status: s }).then(r => setPotentialFindings(prev => prev.map(f => f.id === pf.id ? r.data : f)))}
                              className={`text-[10px] px-2 py-1 rounded border font-medium transition-colors ${
                                pf.status === s
                                  ? "bg-primary text-primary-foreground border-primary"
                                  : "border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                              }`}>
                              {s.replace(/_/g, " ")}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Edit form */}
                    {isEditing && (
                      <div className="border-t px-4 py-3 space-y-3 bg-muted/20">
                        <textarea
                          placeholder="How inspector would write this"
                          value={(editFindingData.inspector_framing as string) ?? ""}
                          onChange={e => setEditFindingData(d => ({ ...d, inspector_framing: e.target.value }))}
                          rows={2}
                          className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none resize-none"
                        />
                        <textarea
                          placeholder="Internal defense notes"
                          value={(editFindingData.defense_summary as string) ?? ""}
                          onChange={e => setEditFindingData(d => ({ ...d, defense_summary: e.target.value }))}
                          rows={2}
                          className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none resize-none"
                        />
                        <div className="grid grid-cols-2 gap-3">
                          <input
                            placeholder="System area"
                            value={(editFindingData.system_area as string) ?? ""}
                            onChange={e => setEditFindingData(d => ({ ...d, system_area: e.target.value }))}
                            className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none"
                          />
                          <select
                            value={(editFindingData.confidence as string) ?? "medium"}
                            onChange={e => setEditFindingData(d => ({ ...d, confidence: e.target.value }))}
                            className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none">
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="certain">Certain</option>
                          </select>
                        </div>
                        <input
                          placeholder="CFR citations (comma-separated)"
                          value={Array.isArray(editFindingData.cfr_citations) ? editFindingData.cfr_citations.join(", ") : ""}
                          onChange={e => setEditFindingData(d => ({ ...d, cfr_citations: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }))}
                          className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none"
                        />
                        <div className="flex gap-2 justify-end">
                          <button type="button" onClick={() => setEditingFinding(null)}
                            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-accent">Cancel</button>
                          <button type="button" onClick={() => handleUpdateFinding(pf.id)}
                            className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90">
                            Save
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Chat Tab ──────────────────────────────────────────────────────────── */}
      {tab === "chat" && (
        <div className="flex flex-col h-[calc(100vh-280px)] min-h-[480px]">
          {/* Internal-only banner */}
          <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-xl mb-3 text-xs text-amber-800">
            <Lock className="w-3.5 h-3.5 flex-shrink-0" />
            <span><strong>Internal only</strong> — Messages in this channel are never visible to the inspector. Keep this channel for team coordination only.</span>
          </div>

          {/* Room filter */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            {[
              { key: "all", label: "All Rooms" },
              { key: "front", label: "Front Room" },
              { key: "back", label: "Back Room" },
              { key: "prep", label: "Prep Room" },
            ].map(r => (
              <button key={r.key} onClick={() => { setChatRoom(r.key); loadTabData("chat"); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  chatRoom === r.key
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}>
                {r.label}
              </button>
            ))}
          </div>

          {/* Message list */}
          <div className="flex-1 overflow-y-auto space-y-1 pr-1 mb-3">
            {chatMessages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <Hash className="w-8 h-8 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No messages yet</p>
                <p className="text-xs text-muted-foreground mt-1">Use this channel to coordinate your team during the inspection</p>
              </div>
            ) : (
              chatMessages
                .filter(m => chatRoom === "all" || m.room === chatRoom || m.room === "all")
                .map(m => {
                  const typeConfig: Record<string, { label: string; color: string; icon: any }> = {
                    general: { label: "General", color: "bg-muted text-muted-foreground", icon: MessageCircle },
                    sme_call: { label: "SME Call", color: "bg-blue-100 text-blue-700", icon: AtSign },
                    clarification: { label: "Clarification", color: "bg-purple-100 text-purple-700", icon: Info },
                    urgent: { label: "Urgent", color: "bg-red-100 text-red-700", icon: Flame },
                  };
                  const cfg = typeConfig[m.message_type] ?? typeConfig.general;
                  const MsgIcon = cfg.icon;
                  const isConverted = !!m.converted_to_request_id;
                  const isConverting = convertingMsg === m.id;

                  return (
                    <div key={m.id} className={`group flex gap-3 px-3 py-2.5 rounded-xl hover:bg-muted/40 transition-colors ${
                      m.message_type === "urgent" ? "bg-red-50/50 border border-red-100" : ""
                    }`}>
                      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-[10px] font-bold text-primary">{m.sender_name.slice(0, 2).toUpperCase()}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold">{m.sender_name}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cfg.color}`}>
                            {cfg.label}
                          </span>
                          {m.room !== "all" && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                              #{m.room}
                            </span>
                          )}
                          <span className="text-[10px] text-muted-foreground ml-auto">
                            {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        <p className="text-sm mt-0.5 leading-relaxed">{m.content}</p>
                        {isConverted ? (
                          <span className="text-[10px] text-emerald-600 flex items-center gap-1 mt-1">
                            <CheckCircle2 className="w-3 h-3" /> Converted to request
                          </span>
                        ) : (
                          <button
                            onClick={() => handleConvertToRequest(m.id)}
                            disabled={isConverting}
                            className="opacity-0 group-hover:opacity-100 text-[10px] text-muted-foreground hover:text-primary flex items-center gap-1 mt-1 transition-opacity">
                            {isConverting ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowUpRight className="w-3 h-3" />}
                            {isConverting ? "Converting…" : "Convert to request"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Compose bar */}
          <form onSubmit={handleSendChat} className="flex gap-2 items-end border rounded-xl p-3 bg-card">
            <div className="flex-1 space-y-2">
              <div className="flex gap-2">
                <select value={chatRoom} onChange={e => setChatRoom(e.target.value)}
                  className="text-xs border rounded-lg px-2 py-1.5 bg-background">
                  <option value="all">All rooms</option>
                  <option value="front">Front room</option>
                  <option value="back">Back room</option>
                  <option value="prep">Prep room</option>
                </select>
                <select value={chatType} onChange={e => setChatType(e.target.value)}
                  className="text-xs border rounded-lg px-2 py-1.5 bg-background">
                  <option value="general">General</option>
                  <option value="sme_call">SME Call</option>
                  <option value="clarification">Clarification</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
              <textarea
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendChat(e as any); } }}
                placeholder="Message the team… (Enter to send, Shift+Enter for new line)"
                rows={2}
                className="w-full text-sm border-0 bg-transparent resize-none focus:outline-none placeholder:text-muted-foreground"
              />
            </div>
            <button type="submit" disabled={sendingChat || !chatInput.trim()}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 self-end">
              {sendingChat ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            </button>
          </form>
        </div>
      )}

      {/* ── People Tab ────────────────────────────────────────────────────────── */}
      {/* ── Team Tab ─────────────────────────────────────────────────────────── */}
      {tab === "team" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="font-semibold flex items-center gap-2"><Users className="w-4 h-4 text-primary" /> Inspection Team</h2>
              <p className="text-xs text-muted-foreground mt-0.5">All personnel involved — front room, prep room, SMEs, and FDA investigators.</p>
            </div>
            <button onClick={() => setShowAddTeamMember(f => !f)}
              className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
              <Plus className="w-3.5 h-3.5" /> Add Member
            </button>
          </div>

          {showAddTeamMember && (
            <form onSubmit={async e => {
              e.preventDefault();
              if (!newTeamMember.name.trim()) return;
              setSavingTeamMember(true);
              try {
                const res = await inspectionsApi.addTeamMember(id, {
                  ...newTeamMember,
                  topics: newTeamMember.topics.split(",").map(s => s.trim()).filter(Boolean),
                  focus_areas: [],
                });
                setTeamMembers(prev => [...prev, res.data]);
                setNewTeamMember({ name: "", title: "", email: "", phone: "", room: "prep", role: "", functional_area: "", topics: "", fda_district: "", notes: "" });
                setShowAddTeamMember(false);
              } finally { setSavingTeamMember(false); }
            }} className="bg-card border rounded-xl p-5 space-y-3">
              <h3 className="text-sm font-semibold">Add Team Member</h3>
              <div className="grid grid-cols-2 gap-3">
                <input placeholder="Full name *" value={newTeamMember.name} onChange={e => setNewTeamMember(f => ({ ...f, name: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <input placeholder="Title / Role" value={newTeamMember.title} onChange={e => setNewTeamMember(f => ({ ...f, title: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <select value={newTeamMember.room} onChange={e => setNewTeamMember(f => ({ ...f, room: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                  <option value="front">Front Room</option>
                  <option value="prep">Prep Room</option>
                  <option value="sme">SME / SPOC</option>
                  <option value="inspector">FDA Inspector</option>
                </select>
                <select value={newTeamMember.role} onChange={e => setNewTeamMember(f => ({ ...f, role: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                  <option value="">Select role…</option>
                  <optgroup label="Front Room">
                    <option value="host">Host</option>
                    <option value="scribe">Scribe</option>
                    <option value="front_runner">Front Runner</option>
                  </optgroup>
                  <optgroup label="Prep Room">
                    <option value="prep_lead">Prep Lead</option>
                    <option value="liaison">Functional Liaison</option>
                    <option value="runner">Runner / Fetcher</option>
                    <option value="doc_control">Document Control</option>
                    <option value="qa_reviewer">QA Reviewer</option>
                    <option value="tech_reviewer">Technical Reviewer</option>
                  </optgroup>
                  <optgroup label="SME / SPOC">
                    <option value="sme">SME</option>
                    <option value="spoc">SPOC</option>
                  </optgroup>
                  <optgroup label="External">
                    <option value="inspector">FDA Inspector</option>
                    <option value="observer">Observer</option>
                    <option value="consultant">Consultant</option>
                  </optgroup>
                </select>
                <input placeholder="Email" value={newTeamMember.email} onChange={e => setNewTeamMember(f => ({ ...f, email: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <input placeholder="FDA District (for inspectors)" value={newTeamMember.fda_district} onChange={e => setNewTeamMember(f => ({ ...f, fda_district: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              </div>
              <input placeholder="Topics / areas of expertise (comma-separated)"
                value={newTeamMember.topics} onChange={e => setNewTeamMember(f => ({ ...f, topics: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setShowAddTeamMember(false)} className="px-3 py-2 text-sm border rounded-lg hover:bg-accent">Cancel</button>
                <button type="submit" disabled={savingTeamMember}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-60">
                  {savingTeamMember ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  {savingTeamMember ? "Adding…" : "Add Member"}
                </button>
              </div>
            </form>
          )}

          {/* Room sections */}
          {(["front", "prep", "sme", "inspector"] as const).map(room => {
            const ROOM_META: Record<string, { label: string; icon: any; desc: string; color: string }> = {
              front: { label: "Front Room", icon: Shield, desc: "Host, scribe, and front runner", color: "text-blue-700 bg-blue-50 border-blue-200" },
              prep: { label: "Prep Room", icon: Users, desc: "Lead, liaisons, runners, reviewers", color: "text-emerald-700 bg-emerald-50 border-emerald-200" },
              sme: { label: "SMEs & SPOCs", icon: Star, desc: "Subject-matter experts on standby", color: "text-amber-700 bg-amber-50 border-amber-200" },
              inspector: { label: "FDA Investigators", icon: AlertTriangle, desc: "External inspection team", color: "text-red-700 bg-red-50 border-red-200" },
            };
            const meta = ROOM_META[room];
            const Icon = meta.icon;
            // Combine new team members + legacy SMEs (for sme room) + legacy inspectors (for inspector room)
            const newMembers = teamMembers.filter(m => m.room === room);
            const legacyMembers: any[] = room === "sme" ? smes : room === "inspector" ? inspectors : [];
            const allMembers = [...newMembers, ...legacyMembers];
            if (allMembers.length === 0 && room !== "prep") return null;
            return (
              <div key={room}>
                <div className="flex items-center gap-2 mb-3">
                  <span className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${meta.color}`}>
                    <Icon className="w-3 h-3" /> {meta.label}
                  </span>
                  <span className="text-xs text-muted-foreground">{meta.desc}</span>
                  {allMembers.length > 0 && <span className="text-xs font-bold text-muted-foreground ml-auto">{allMembers.length} member{allMembers.length !== 1 ? "s" : ""}</span>}
                </div>
                {allMembers.length === 0 ? (
                  <div className="bg-muted/20 border border-dashed rounded-xl px-4 py-6 text-center">
                    <p className="text-xs text-muted-foreground">No {meta.label.toLowerCase()} members added yet</p>
                    <button onClick={() => { setNewTeamMember(f => ({ ...f, room })); setShowAddTeamMember(true); }}
                      className="text-xs text-primary hover:underline mt-1">+ Add one</button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {newMembers.map(m => {
                      const avail = m.availability;
                      const availColors: Record<string, string> = {
                        available: "bg-emerald-100 text-emerald-800",
                        in_audit_room: "bg-red-100 text-red-800",
                        on_standby: "bg-blue-100 text-blue-800",
                        in_prep: "bg-amber-100 text-amber-800",
                        unavailable: "bg-gray-100 text-gray-600",
                        do_not_call: "bg-red-200 text-red-900",
                      };
                      const isExpanded = expandedTeamMember === m.id;
                      return (
                        <div key={m.id} className="bg-card border rounded-xl overflow-hidden">
                          <div className="flex items-start gap-3 px-4 py-3">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                              <span className="text-xs font-bold text-primary">{m.name.slice(0,2).toUpperCase()}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <p className="text-sm font-semibold">{m.name}</p>
                                  <p className="text-xs text-muted-foreground">{[m.title, m.functional_area].filter(Boolean).join(" · ")}</p>
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    {m.role && <span className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground capitalize">{m.role.replace(/_/g, " ")}</span>}
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${availColors[avail] ?? availColors.available}`}>{avail.replace(/_/g, " ")}</span>
                                    {m.topics.slice(0,3).map(t => <span key={t} className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded">{t}</span>)}
                                  </div>
                                </div>
                                <div className="flex gap-1 flex-shrink-0">
                                  <select value={avail} onChange={async e => {
                                    const res = await inspectionsApi.updateTeamMember(id, m.id, { availability: e.target.value });
                                    setTeamMembers(prev => prev.map(x => x.id === m.id ? res.data : x));
                                  }} className="text-[10px] border rounded px-1.5 py-1 bg-background">
                                    {["available","in_audit_room","on_standby","in_prep","unavailable","do_not_call"].map(s => <option key={s} value={s}>{s.replace(/_/g," ")}</option>)}
                                  </select>
                                  <button onClick={() => setExpandedTeamMember(isExpanded ? null : m.id)}
                                    className="p-1.5 rounded-lg border border-border text-muted-foreground hover:bg-accent">
                                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                                  </button>
                                  <button onClick={async () => { await inspectionsApi.deleteTeamMember(id, m.id); setTeamMembers(prev => prev.filter(x => x.id !== m.id)); }}
                                    className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-red-500">
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>
                            </div>
                          </div>
                          {isExpanded && (
                            <div className="border-t px-4 py-3 space-y-3 bg-muted/20">
                              {m.approved_talking_points.length > 0 && (
                                <div>
                                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Approved Talking Points</p>
                                  <ul className="space-y-1">{m.approved_talking_points.map((tp, i) => <li key={i} className="flex items-start gap-2 text-xs"><CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 flex-shrink-0" />{tp}</li>)}</ul>
                                </div>
                              )}
                              {m.do_not_volunteer.length > 0 && (
                                <div>
                                  <p className="text-[10px] font-semibold text-red-600 uppercase tracking-wide mb-1.5">Do NOT Volunteer</p>
                                  <ul className="space-y-1">{m.do_not_volunteer.map((dnv, i) => <li key={i} className="flex items-start gap-2 text-xs text-red-700"><XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />{dnv}</li>)}</ul>
                                </div>
                              )}
                              {m.likely_questions.length > 0 && (
                                <div>
                                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Mock Q&A</p>
                                  <div className="space-y-2">{m.likely_questions.map((qa, i) => <div key={i} className="bg-card border rounded-lg p-2.5"><p className="text-xs font-medium mb-0.5">Q: {qa.question}</p><p className="text-xs text-muted-foreground">A: {qa.recommended_answer}</p></div>)}</div>
                                </div>
                              )}
                              {m.fda_district && <p className="text-xs text-muted-foreground">FDA District: {m.fda_district}</p>}
                              {m.notes && <p className="text-xs text-muted-foreground italic">{m.notes}</p>}
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {/* Legacy SMEs rendered in sme room */}
                    {room === "sme" && smes.map(sme => {
                      const availColors: Record<string, string> = {
                        available: "bg-emerald-100 text-emerald-800",
                        in_audit_room: "bg-red-100 text-red-800",
                        on_standby: "bg-blue-100 text-blue-800",
                        in_prep: "bg-amber-100 text-amber-800",
                        unavailable: "bg-gray-100 text-gray-600",
                        do_not_call: "bg-red-200 text-red-900",
                      };
                      const isExpanded = expandedSME === sme.id;
                      const isCoaching = coachingSME === sme.id;
                      return (
                        <div key={sme.id} className="bg-card border rounded-xl overflow-hidden">
                          <div className="flex items-start gap-3 p-4">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                              <span className="text-xs font-bold text-primary">{sme.name.slice(0,2).toUpperCase()}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <p className="text-sm font-semibold">{sme.name}</p>
                                  <p className="text-xs text-muted-foreground">{[sme.title, sme.department].filter(Boolean).join(" · ")}</p>
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${availColors[sme.availability] ?? availColors.available}`}>{sme.availability.replace(/_/g," ")}</span>
                                    {sme.qa_cleared && <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 flex items-center gap-0.5 font-medium"><BadgeCheck className="w-2.5 h-2.5" />QA Cleared</span>}
                                    {sme.topics.slice(0,3).map(t => <span key={t} className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded">{t}</span>)}
                                  </div>
                                </div>
                                <div className="flex gap-1 flex-shrink-0">
                                  <select value={sme.availability} onChange={async e => {
                                    const res = await inspectionsApi.updateSME(id, sme.id, { availability: e.target.value });
                                    setSMEs(prev => prev.map(s => s.id === sme.id ? res.data : s));
                                  }} className="text-[10px] border rounded px-1.5 py-1 bg-background">
                                    {["available","in_audit_room","on_standby","in_prep","unavailable","do_not_call"].map(s => <option key={s} value={s}>{s.replace(/_/g," ")}</option>)}
                                  </select>
                                  <button onClick={() => inspectionsApi.qaClearSME(id, sme.id).then(r => setSMEs(prev => prev.map(s => s.id === sme.id ? r.data : s)))}
                                    className={`p-1.5 rounded-lg border text-xs transition-colors ${sme.qa_cleared ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "border-border text-muted-foreground hover:text-emerald-600"}`}
                                    title="Toggle QA clearance"><BadgeCheck className="w-3.5 h-3.5" /></button>
                                  <button onClick={() => handleCoachSME(sme.id)} disabled={isCoaching}
                                    className="flex items-center gap-1 px-2 py-1.5 text-[10px] border rounded-lg font-medium hover:bg-accent disabled:opacity-50">
                                    {isCoaching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3 text-primary" />}{isCoaching ? "…" : "AI Coach"}
                                  </button>
                                  <button onClick={() => setExpandedSME(isExpanded ? null : sme.id)}
                                    className="p-1.5 rounded-lg border border-border text-muted-foreground hover:bg-accent">
                                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                                  </button>
                                  <button onClick={async () => { await inspectionsApi.deleteSME(id, sme.id); setSMEs(prev => prev.filter(s => s.id !== sme.id)); }}
                                    className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                                </div>
                              </div>
                            </div>
                          </div>
                          {isExpanded && (
                            <div className="border-t px-4 py-3 space-y-3 bg-muted/20">
                              {sme.approved_talking_points.length > 0 && (
                                <div><p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Approved Talking Points</p><ul className="space-y-1">{sme.approved_talking_points.map((tp, i) => <li key={i} className="flex items-start gap-2 text-xs"><CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 flex-shrink-0" />{tp}</li>)}</ul></div>
                              )}
                              {sme.do_not_volunteer.length > 0 && (
                                <div><p className="text-[10px] font-semibold text-red-600 uppercase tracking-wide mb-1.5">Do NOT Volunteer</p><ul className="space-y-1">{sme.do_not_volunteer.map((dnv, i) => <li key={i} className="flex items-start gap-2 text-xs text-red-700"><XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />{dnv}</li>)}</ul></div>
                              )}
                              {sme.likely_questions.length > 0 && (
                                <div><p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Mock Q&A</p><div className="space-y-2">{sme.likely_questions.map((qa, i) => <div key={i} className="bg-card border rounded-lg p-2.5"><p className="text-xs font-medium mb-0.5">Q: {qa.question}</p><p className="text-xs text-muted-foreground">A: {qa.recommended_answer}</p></div>)}</div></div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {/* Legacy inspectors rendered in inspector room */}
                    {room === "inspector" && inspectors.map(insp => {
                      const brief = inspectorBriefs[insp.id];
                      const isExpanded = expandedBrief === insp.id;
                      const isBriefing = briefingInspector === insp.id;
                      return (
                        <div key={insp.id} className="bg-card border rounded-xl overflow-hidden">
                          <div className="px-4 py-3 flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <p className="font-semibold text-sm">{insp.name}</p>
                                <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 border border-amber-200 rounded text-amber-800 capitalize">{insp.role.replace("_", " ")}</span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-0.5">{insp.fda_district || "District not specified"}{insp.email && ` · ${insp.email}`}</p>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <button onClick={async () => {
                                if (brief) { setExpandedBrief(isExpanded ? null : insp.id); return; }
                                setBriefingInspector(insp.id); setExpandedBrief(insp.id);
                                try { const res = await inspectionsApi.briefInspector(id, insp.id); setInspectorBriefs(b => ({ ...b, [insp.id]: res.data.brief })); }
                                catch { setInspectorBriefs(b => ({ ...b, [insp.id]: null })); }
                                finally { setBriefingInspector(null); }
                              }} disabled={isBriefing}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors disabled:opacity-60 ${brief ? "bg-primary/10 border-primary/20 text-primary" : "bg-muted border-border text-muted-foreground hover:text-foreground"}`}>
                                {isBriefing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                                {isBriefing ? "Briefing…" : brief ? (isExpanded ? "Hide Brief" : "View Brief") : "AI Brief"}
                              </button>
                              <button onClick={async () => { await inspectionsApi.deleteInspector(id, insp.id); await loadTabData("team"); }}
                                className="text-muted-foreground hover:text-red-500 p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                            </div>
                          </div>
                          {isExpanded && (
                            <div className="border-t bg-muted/10 px-4 py-3">
                              {isBriefing ? <div className="flex items-center gap-3 text-sm text-muted-foreground py-2"><Loader2 className="w-4 h-4 animate-spin text-primary" />Researching inspector background…</div>
                              : brief ? (
                                <div className="space-y-3">
                                  {brief.district_profile && <div className="bg-card border rounded-lg px-3 py-2"><p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide mb-1">District Profile</p><p className="text-xs">{brief.district_profile}</p></div>}
                                  {brief.likely_focus_areas?.length > 0 && <div><p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide mb-1.5">Expected Focus Areas</p><div className="flex flex-wrap gap-1.5">{brief.likely_focus_areas.map((f: string, i: number) => <span key={i} className="text-xs px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-full text-amber-800">{f}</span>)}</div></div>}
                                  {brief.red_flags?.length > 0 && <div className="bg-red-50 border border-red-100 rounded-lg px-3 py-2"><p className="text-[10px] font-bold text-red-700 uppercase tracking-wide mb-1">Prepare These Areas</p><ul className="space-y-0.5">{brief.red_flags.map((f: string, i: number) => <li key={i} className="text-xs text-red-800">• {f}</li>)}</ul></div>}
                                </div>
                              ) : <p className="text-xs text-muted-foreground py-1">Brief failed. Try again.</p>}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                {room === "inspector" && (
                  <form onSubmit={handleSaveInspector} className="mt-3 bg-card border rounded-xl p-4 space-y-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Add Investigator</p>
                    <div className="grid grid-cols-2 gap-3">
                      <input value={newInspector.name} onChange={e => setNewInspector(f => ({ ...f, name: e.target.value }))} placeholder="Full name *" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      <input value={newInspector.fda_district} onChange={e => setNewInspector(f => ({ ...f, fda_district: e.target.value }))} placeholder="FDA District / Agency office" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      <input value={newInspector.email} onChange={e => setNewInspector(f => ({ ...f, email: e.target.value }))} placeholder="Email (optional)" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      <select value={newInspector.role} onChange={e => setNewInspector(f => ({ ...f, role: e.target.value }))} className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                        <option value="lead">Lead Investigator</option>
                        <option value="secondary">Secondary</option>
                        <option value="observer">Observer</option>
                      </select>
                    </div>
                    <input value={newInspector.notes} onChange={e => setNewInspector(f => ({ ...f, notes: e.target.value }))} placeholder="Known focus areas, previous inspections…" className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                    <div className="flex justify-end">
                      <button type="submit" disabled={savingInspector || !newInspector.name.trim()}
                        className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                        {savingInspector ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Add
                      </button>
                    </div>
                  </form>
                )}
                {room === "sme" && (
                  <form onSubmit={handleSaveSME} className="mt-3 bg-card border rounded-xl p-4 space-y-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Add SME / SPOC</p>
                    <div className="grid grid-cols-2 gap-3">
                      <input placeholder="Name *" value={newSME.name} onChange={e => setNewSME(f => ({ ...f, name: e.target.value }))} className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      <input placeholder="Title" value={newSME.title} onChange={e => setNewSME(f => ({ ...f, title: e.target.value }))} className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      <input placeholder="Department" value={newSME.department} onChange={e => setNewSME(f => ({ ...f, department: e.target.value }))} className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      <input placeholder="Email" value={newSME.email} onChange={e => setNewSME(f => ({ ...f, email: e.target.value }))} className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                    </div>
                    <input placeholder="Topics (comma-separated)" value={newSME.topics} onChange={e => setNewSME(f => ({ ...f, topics: e.target.value }))} className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                    <div className="flex gap-2 justify-end">
                      <button type="button" onClick={() => setShowAddSME(false)} className="px-3 py-2 text-sm border rounded-lg hover:bg-accent">Cancel</button>
                      <button type="submit" disabled={savingSME}
                        className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-60">
                        {savingSME ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}{savingSME ? "Saving…" : "Add SME"}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Scribe Tab ────────────────────────────────────────────────────────── */}
      {tab === "scribe" && (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Real-time scribe — capture every observation, question, and action item as it happens.
              {voiceSupported
                ? " Tap the mic to dictate, review the transcript, then save."
                : " (Voice input not available in this browser — Chrome or Edge recommended.)"}
            </p>
            {voiceSupported && (
              <div className={`flex-shrink-0 flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full border ${
                isRecording ? "bg-red-50 border-red-200 text-red-700" : "bg-muted border-border text-muted-foreground"
              }`}>
                {isRecording ? <><span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" /> Recording</> : <><Mic className="w-3 h-3" /> Voice ready</>}
              </div>
            )}
          </div>

          <form onSubmit={handleScribe} className="bg-card border rounded-xl p-5 space-y-4">
            <div className="flex gap-2 flex-wrap">
              {ENTRY_TYPES.map(t => (
                <button key={t.value} type="button" onClick={() => setScribeType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    scribeType === t.value ? "bg-primary text-primary-foreground border-primary" : "bg-background border-border text-muted-foreground hover:text-foreground"
                  }`}>
                  {t.label}
                </button>
              ))}
            </div>

            {voiceSupported && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {isRecording ? "Listening — speak normally, you can still edit below" : "Click mic to start dictating"}
                </span>
                <div className="flex items-center gap-2">
                  {lastFinalRef.current && (
                    <button type="button" onClick={handleRedoLast}
                      className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors">
                      ↩ Undo last
                    </button>
                  )}
                  <button type="button" onClick={toggleRecording} title={isRecording ? "Stop recording" : "Start voice capture"}
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all shadow-sm ${
                      isRecording ? "bg-red-500 border-red-500 text-white shadow-red-200 shadow-md" : "bg-background border-border hover:border-primary hover:text-primary hover:shadow"
                    }`}>
                    {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <textarea
                rows={isRecording ? 3 : 4}
                placeholder={voiceSupported ? `Dictate or type ${ENTRY_TYPES.find(t => t.value === scribeType)?.label.toLowerCase() ?? "note"}… transcript appears here` : `Enter ${ENTRY_TYPES.find(t => t.value === scribeType)?.label.toLowerCase() ?? "note"}…`}
                value={scribeText}
                onChange={e => setScribeText(e.target.value)}
                className={`w-full border rounded-lg px-3 py-2.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none transition-colors ${isRecording ? "border-red-200 ring-1 ring-red-100" : ""}`}
              />
              {interimText && (
                <div className="flex items-start gap-2 px-3 py-2 border border-dashed border-primary/30 rounded-lg bg-primary/5">
                  <span className="text-[10px] font-bold text-primary/60 uppercase tracking-wide flex-shrink-0 mt-0.5">live</span>
                  <p className="text-sm italic text-muted-foreground/80 leading-relaxed">{interimText}</p>
                </div>
              )}
            </div>

            {isRecording && (
              <p className="text-[11px] text-muted-foreground flex items-center gap-1.5 -mt-1">
                <Info className="w-3 h-3 flex-shrink-0" />
                Always review the transcript — voice can mis-hear names, numbers, and regulatory terms. Edit directly above before saving.
              </p>
            )}

            <div className="flex items-center justify-between">
              {scribeText.trim() && (
                <button type="button" onClick={() => { setScribeText(""); lastFinalRef.current = ""; }}
                  className="text-xs text-muted-foreground hover:text-red-600 transition-colors">Clear</button>
              )}
              <button type="submit" disabled={sendingScribe || !scribeText.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 ml-auto">
                {sendingScribe ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                {sendingScribe ? "Saving…" : "Save Entry"}
              </button>
            </div>
          </form>

          {log.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Timeline</p>
              {[...log].reverse().map(entry => (
                <div key={entry.id} className="group">
                  <LogEntryCard entry={entry} />
                  <div className="hidden group-hover:flex items-center gap-1 px-4 pb-2 -mt-1">
                    <span className="text-[10px] text-muted-foreground mr-1">Convert to:</span>
                    <button onClick={async () => {
                      const res = await inspectionsApi.createRequest(id, { request_text: entry.content, criticality: "medium", category: "question" });
                      setInspection(r => r ? { ...r, requests: [...(r.requests ?? []), res.data], total_requests: (r.total_requests || 0) + 1 } : r);
                      addToast("Converted to request", "info");
                    }} className="text-[10px] px-2 py-0.5 border rounded text-muted-foreground hover:text-primary hover:border-primary transition-colors">
                      Request
                    </button>
                    <button onClick={async () => {
                      const res = await inspectionsApi.createPotentialFinding(id, { title: entry.content.slice(0, 80), defense_summary: entry.content });
                      setPotentialFindings(prev => [res.data, ...prev]);
                      addToast("Converted to potential finding", "info");
                    }} className="text-[10px] px-2 py-0.5 border rounded text-muted-foreground hover:text-amber-600 hover:border-amber-400 transition-colors">
                      Finding
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Pre-Inspection Prep Tab ───────────────────────────────────────────── */}
      {tab === "prep" && (
        <div className="space-y-5">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="font-semibold flex items-center gap-2"><BookMarked className="w-4 h-4 text-primary" /> Pre-Inspection Prep</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Pre-stage required documents, track readiness, and log every hand-off with chain of custody.</p>
            </div>
            <div className="flex gap-2">
              {binderDocs.length === 0 && (
                <button onClick={async () => {
                  setSeedingBinder(true);
                  try {
                    await inspectionsApi.seedBinder(id);
                    const r = await inspectionsApi.listBinder(id);
                    setBinderDocs(r.data.binder_docs ?? []);
                  } finally { setSeedingBinder(false); }
                }} disabled={seedingBinder}
                  className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-60">
                  {seedingBinder ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  Pre-fill Standard Docs
                </button>
              )}
              <button onClick={() => setShowAddBinder(f => !f)}
                className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                <Plus className="w-3.5 h-3.5" /> Add Document
              </button>
            </div>
          </div>

          {/* Add form */}
          {showAddBinder && (
            <div className="bg-card border rounded-xl p-4 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Add Binder Document</p>
              <div className="grid grid-cols-2 gap-3">
                <input value={newBinderDoc.title} onChange={e => setNewBinderDoc(f => ({ ...f, title: e.target.value }))}
                  placeholder="Document title *"
                  className="col-span-2 border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
                <select value={newBinderDoc.category} onChange={e => setNewBinderDoc(f => ({ ...f, category: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none">
                  {[["company_profile","Company Profile"],["org_chart","Org Chart"],["sop_index","SOP Index"],["site_master_file","Site Master File"],
                    ["capa_summary","CAPA Summary"],["deviation_log","Deviation Log"],["training_records","Training Records"],["batch_records","Batch Records"],
                    ["validation_summary","Validation Summary"],["equipment_list","Equipment List"],["calibration_log","Calibration Log"],
                    ["environmental_monitoring","Environmental Monitoring"],["supplier_qualification","Supplier List"],["change_control","Change Control"],
                    ["complaint_log","Complaint / OOS Log"],["other","Other"]].map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
                <input value={newBinderDoc.version} onChange={e => setNewBinderDoc(f => ({ ...f, version: e.target.value }))}
                  placeholder="Version (e.g. v3.2)"
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowAddBinder(false)} className="px-3 py-1.5 text-sm border rounded-lg hover:bg-accent">Cancel</button>
                <button disabled={savingBinder || !newBinderDoc.title.trim()} onClick={async () => {
                  setSavingBinder(true);
                  try {
                    await inspectionsApi.addBinderDoc(id, {
                      title: newBinderDoc.title,
                      category: newBinderDoc.category,
                      version: newBinderDoc.version || undefined,
                    });
                    const r = await inspectionsApi.listBinder(id);
                    setBinderDocs(r.data.binder_docs ?? []);
                    setNewBinderDoc({ title: "", category: "other", filename: "", version: "" });
                    setShowAddBinder(false);
                  } finally { setSavingBinder(false); }
                }}
                  className="flex items-center gap-1.5 px-4 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                  {savingBinder ? <Loader2 className="w-3 h-3 animate-spin" /> : null} Save
                </button>
              </div>
            </div>
          )}

          {/* Binder completeness summary */}
          {binderDocs.length > 0 && (() => {
            const required = binderDocs.filter(d => d.required);
            const ready = required.filter(d => d.status === "ready" || d.status === "delivered");
            const pct = required.length > 0 ? Math.round((ready.length / required.length) * 100) : 100;
            return (
              <div className="bg-card border rounded-xl px-4 py-3 flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold">Binder Completeness</span>
                    <span className="text-xs font-bold">{pct}%</span>
                  </div>
                  <ProgressBar value={pct} />
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-bold">{ready.length}<span className="text-muted-foreground font-normal">/{required.length}</span></p>
                  <p className="text-[10px] text-muted-foreground">required ready</p>
                </div>
              </div>
            );
          })()}

          {/* Document checklist */}
          {binderDocs.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-10 text-center">
              <BookMarked className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm font-medium mb-1">Binder is empty</p>
              <p className="text-xs text-muted-foreground">Click "Pre-fill Standard Docs" to load the standard pharma inspection document checklist.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {binderDocs.map(doc => (
                <div key={doc.id} className={`border rounded-xl px-4 py-3 flex items-center gap-3 ${
                  doc.status === "delivered" ? "bg-emerald-50 border-emerald-200" :
                  doc.status === "ready" ? "bg-blue-50 border-blue-200" :
                  doc.status === "staged" ? "bg-amber-50 border-amber-200" :
                  "bg-card"
                }`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{doc.title}</span>
                      {doc.version && <span className="text-[10px] text-muted-foreground">{doc.version}</span>}
                      {doc.required && <span className="text-[10px] text-red-600 font-semibold">required</span>}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-muted-foreground capitalize">{doc.category.replace(/_/g, " ")}</span>
                      {doc.delivered_to && <span className="text-[10px] text-muted-foreground">· Delivered to {doc.delivered_to}</span>}
                    </div>
                  </div>
                  <select value={doc.status} onChange={async e => {
                    const newStatus = e.target.value;
                    await inspectionsApi.updateBinderDoc(id, doc.id, { status: newStatus });
                    const r = await inspectionsApi.listBinder(id);
                    setBinderDocs(r.data.binder_docs ?? []);
                  }} className={`text-[11px] font-semibold px-2 py-1 rounded border cursor-pointer ${
                    doc.status === "delivered" ? "bg-emerald-100 text-emerald-800 border-emerald-300" :
                    doc.status === "ready" ? "bg-blue-100 text-blue-800 border-blue-300" :
                    doc.status === "staged" ? "bg-amber-100 text-amber-800 border-amber-300" :
                    "bg-muted text-muted-foreground border-border"
                  }`}>
                    <option value="missing">Missing</option>
                    <option value="staged">Staged</option>
                    <option value="ready">Ready</option>
                    <option value="delivered">Delivered</option>
                  </select>
                  <button onClick={async () => {
                    await inspectionsApi.deleteBinderDoc(id, doc.id);
                    setBinderDocs(prev => prev.filter(d => d.id !== doc.id));
                  }} className="text-muted-foreground hover:text-red-600 transition-colors flex-shrink-0">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Divider */}
          <div className="border-t pt-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Package className="w-3.5 h-3.5" /> Delivery Log
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-xs text-blue-800">
            <p className="font-semibold mb-1 flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> Chain of custody</p>
            <p>Always get verbal acknowledgment when handing over documents. Log the investigator's name and method — this is your defence if FDA claims a document was "not provided."</p>
          </div>

          {deliveries.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-6 text-center">
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

          {/* Exports */}
          <div className="bg-card border rounded-xl p-4">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Download className="w-3.5 h-3.5" /> Export Reports
            </p>
            <div className="flex gap-2 flex-wrap">
              {[
                { label: "Requests CSV", fn: () => inspectionsApi.exportRequestsCsv(id), filename: "requests.csv" },
                { label: "Scribe Log TXT", fn: () => inspectionsApi.exportScribeTxt(id), filename: "scribe.txt" },
                { label: "Commitments CSV", fn: () => inspectionsApi.exportCommitmentsCsv(id), filename: "commitments.csv" },
              ].map(exp => (
                <button key={exp.label} onClick={async () => {
                  try {
                    const r = await exp.fn();
                    const url = window.URL.createObjectURL(new Blob([r.data]));
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = exp.filename;
                    a.click();
                    window.URL.revokeObjectURL(url);
                  } catch {}
                }}
                  className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-xs font-medium hover:bg-muted transition-colors">
                  <Download className="w-3 h-3" /> {exp.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Post-Inspection Tab ────────────────────────────────────────────────── */}
      {tab === "post" && (
        <div className="space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="font-semibold flex items-center gap-2"><ClipboardList className="w-4 h-4 text-primary" /> Post-Inspection Workspace</h2>
              <p className="text-xs text-muted-foreground mt-0.5">483s, CAPAs, closing readiness, outcome, and lessons learned.</p>
            </div>
            <div className="flex items-center gap-2">
              {inspection.status === "active" && (
                <button onClick={handleClose} disabled={closing}
                  className="flex items-center gap-2 px-4 py-2 bg-muted border rounded-lg text-sm font-medium hover:bg-accent disabled:opacity-60">
                  {closing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
                  End Inspection
                </button>
              )}
              <button onClick={() => loadTabData("post")} className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent">
                <RefreshCw className="w-3.5 h-3.5" /> Refresh
              </button>
            </div>
          </div>

          {/* Closing Meeting Readiness Checklist */}
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <ClipboardList className="w-3.5 h-3.5 text-primary" /> Closing Meeting Readiness
            </p>
            <div className="space-y-2">
              {[
                { text: "All open requests fulfilled or declined", done: openRequests.length === 0, note: openRequests.length > 0 ? `${openRequests.length} still active` : undefined },
                { text: "483 observations documented with response drafts", done: observations.length > 0 && observations.every(o => o.draft_response), note: observations.filter(o => !o.draft_response).length > 0 ? `${observations.filter(o => !o.draft_response).length} missing draft` : undefined },
                { text: "All potential 483 items have root cause hypothesis", done: observations.every(o => o.root_cause_hypothesis) },
                { text: "Document delivery log complete", done: deliveries.length > 0 },
                { text: "Potential findings reviewed and responded to", done: potentialFindings.filter(f => f.status === "tracking").length === 0, note: potentialFindings.filter(f => f.status === "tracking").length > 0 ? `${potentialFindings.filter(f => f.status === "tracking").length} unaddressed` : undefined },
                { text: "Inspection log reviewed and complete", done: log.length > 0 },
                { text: "Post-inspection CAPAs identified", done: capas.length > 0 },
              ].map(item => (
                <div key={item.text} className="flex items-start gap-2.5">
                  {item.done ? <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" /> : <Circle className="w-4 h-4 text-muted-foreground/40 flex-shrink-0 mt-0.5" />}
                  <div className="min-w-0">
                    <span className={`text-sm ${item.done ? "text-foreground" : "text-muted-foreground"}`}>{item.text}</span>
                    {(item as any).note && <span className="text-[10px] text-red-600 ml-2">— {(item as any).note}</span>}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 bg-muted/30 border rounded-lg">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">Leadership Closing Script</p>
              <div className="space-y-1 text-xs text-muted-foreground">
                <p>1. Acknowledge observations professionally — avoid defensiveness.</p>
                <p>2. "We appreciate the observation. We will provide a comprehensive written response within 15 business days."</p>
                <p>3. Confirm all commitments made — name the responsible person, not a team.</p>
                <p>4. Do NOT volunteer corrective actions not yet planned or approved.</p>
                <p>5. Close: "Quality is our highest priority. We are committed to continuous improvement."</p>
              </div>
            </div>
          </div>

          {/* 483 Observations */}
          <div className="bg-card border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold flex items-center gap-2"><Flag className="w-4 h-4 text-amber-500" /> 483 Observations</h3>
              <span className="text-xs text-muted-foreground">{observations.length} logged</span>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-900 mb-3">
              You have <strong>15 business days</strong> to submit a written response after the inspector issues a 483.
            </div>
            {observations.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">No observations logged yet.</p>
            ) : (
              <div className="space-y-3">
                {observations.map(obs => {
                  const daysLeft = obs.response_deadline
                    ? Math.ceil((new Date(obs.response_deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
                    : null;
                  return (
                    <div key={obs.id} className="border rounded-xl overflow-hidden">
                      <div className="px-4 py-3 border-b bg-amber-50/40">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] font-bold text-amber-800 font-mono">OBS-{String(obs.observation_number).padStart(3, "0")}</span>
                            {obs.system_area && <span className="text-[10px] text-muted-foreground">· {obs.system_area}</span>}
                            {obs.verbal_concern && <span className="text-[10px] font-bold bg-orange-100 text-orange-800 border border-orange-200 px-1.5 py-0.5 rounded flex items-center gap-1"><Mic className="w-2.5 h-2.5" /> Verbal</span>}
                            {obs.factual_accuracy_confirmed && <span className="text-[10px] font-semibold text-emerald-700 flex items-center gap-0.5"><CheckCircle2 className="w-2.5 h-2.5" /> Facts Verified</span>}
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {daysLeft !== null && (
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${daysLeft <= 0 ? "bg-red-100 text-red-800 border-red-300" : daysLeft <= 5 ? "bg-amber-100 text-amber-800 border-amber-300" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`}>
                                {daysLeft <= 0 ? "OVERDUE" : `${daysLeft}d left`}
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-sm font-medium mt-1.5 leading-snug">{obs.observation_text}</p>
                      </div>
                      <div className="px-4 py-3 space-y-2">
                        <textarea rows={2} defaultValue={obs.root_cause_hypothesis ?? ""}
                          onBlur={async e => {
                            if (e.target.value !== obs.root_cause_hypothesis) {
                              await inspectionsApi.updateObservation(id, obs.id, { root_cause_hypothesis: e.target.value });
                              const r = await inspectionsApi.listObservations(id);
                              setObservations(r.data.observations ?? []);
                            }
                          }}
                          placeholder="Root cause hypothesis…"
                          className="w-full border rounded-lg px-3 py-2 text-xs bg-background focus:outline-none resize-none" />
                        <div className="flex gap-2">
                          <button onClick={async () => {
                            await inspectionsApi.updateObservation(id, obs.id, { verbal_concern: !obs.verbal_concern });
                            const r = await inspectionsApi.listObservations(id);
                            setObservations(r.data.observations ?? []);
                          }} className={`text-[11px] flex items-center gap-1 px-2 py-1 rounded border font-medium ${obs.verbal_concern ? "bg-orange-100 text-orange-800 border-orange-300" : "bg-muted text-muted-foreground border-border"}`}>
                            <Mic className="w-3 h-3" /> {obs.verbal_concern ? "Verbal flagged" : "Flag verbal"}
                          </button>
                          <button onClick={async () => {
                            await inspectionsApi.updateObservation(id, obs.id, { factual_accuracy_confirmed: !obs.factual_accuracy_confirmed });
                            const r = await inspectionsApi.listObservations(id);
                            setObservations(r.data.observations ?? []);
                          }} className={`text-[11px] flex items-center gap-1 px-2 py-1 rounded border font-medium ${obs.factual_accuracy_confirmed ? "bg-emerald-100 text-emerald-800 border-emerald-300" : "bg-muted text-muted-foreground border-border"}`}>
                            <CheckSquare className="w-3 h-3" /> {obs.factual_accuracy_confirmed ? "Facts verified" : "Verify facts"}
                          </button>
                          {!obs.draft_response && (
                            <button onClick={() => handleDraftObsResponse(obs.id)} disabled={draftingObs === obs.id}
                              className="text-[11px] flex items-center gap-1 px-2 py-1 rounded border font-medium bg-muted text-muted-foreground border-border hover:text-primary hover:border-primary disabled:opacity-50">
                              {draftingObs === obs.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                              {draftingObs === obs.id ? "Drafting…" : "AI Draft"}
                            </button>
                          )}
                        </div>
                        {obs.draft_response && <p className="text-xs text-muted-foreground border-l-2 border-primary/30 pl-3 italic">{obs.draft_response}</p>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <form onSubmit={handleSaveObservation} className="mt-4 space-y-3 border-t pt-4">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Log Observation</p>
              <textarea rows={2} value={newObservation.observation_text}
                onChange={e => setNewObservation(f => ({ ...f, observation_text: e.target.value }))}
                placeholder="Paste observation text exactly as written…"
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none resize-none" />
              <div className="grid grid-cols-2 gap-3">
                <input value={newObservation.system_area} onChange={e => setNewObservation(f => ({ ...f, system_area: e.target.value }))}
                  placeholder="System area" className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
                <input type="date" value={newObservation.response_deadline} onChange={e => setNewObservation(f => ({ ...f, response_deadline: e.target.value }))}
                  className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
              </div>
              <div className="flex justify-end">
                <button type="submit" disabled={savingObservation || !newObservation.observation_text.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                  {savingObservation ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Log Observation
                </button>
              </div>
            </form>
          </div>

          {/* CAPAs */}
          <div className="bg-card border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold flex items-center gap-2"><CheckSquare className="w-4 h-4 text-primary" /> CAPAs & Action Items</h3>
              <button onClick={() => setShowAddCAPA(f => !f)}
                className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                <Plus className="w-3.5 h-3.5" /> Add CAPA
              </button>
            </div>
            {showAddCAPA && (
              <form onSubmit={handleSaveCAPA} className="space-y-3 border rounded-xl p-4 mb-4">
                <input placeholder="Title *" value={newCAPA.title} onChange={e => setNewCAPA(f => ({ ...f, title: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
                <div className="grid grid-cols-2 gap-3">
                  <select value={newCAPA.action_type} onChange={e => setNewCAPA(f => ({ ...f, action_type: e.target.value }))}
                    className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none">
                    {["capa","correction","preventive","training","sop_revision","validation","data_integrity","other"].map(t => <option key={t} value={t}>{t.replace(/_/g," ")}</option>)}
                  </select>
                  <select value={newCAPA.criticality} onChange={e => setNewCAPA(f => ({ ...f, criticality: e.target.value }))}
                    className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none">
                    <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
                  </select>
                  <input placeholder="Owner" value={newCAPA.owner_name} onChange={e => setNewCAPA(f => ({ ...f, owner_name: e.target.value }))}
                    className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
                  <input type="date" value={newCAPA.due_date} onChange={e => setNewCAPA(f => ({ ...f, due_date: e.target.value }))}
                    className="border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
                </div>
                <div className="flex gap-2 justify-end">
                  <button type="button" onClick={() => setShowAddCAPA(false)} className="px-3 py-2 text-sm border rounded-lg hover:bg-accent">Cancel</button>
                  <button type="submit" disabled={savingCAPA}
                    className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium disabled:opacity-60">
                    {savingCAPA ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}{savingCAPA ? "Saving…" : "Add CAPA"}
                  </button>
                </div>
              </form>
            )}
            {capas.length === 0 ? (
              <p className="text-xs text-muted-foreground">No CAPAs logged yet</p>
            ) : (
              <div className="divide-y border rounded-xl overflow-hidden">
                {capas.map(capa => (
                  <div key={capa.id} className="flex items-start gap-3 px-4 py-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold">{capa.title}</p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${capa.status === "completed" || capa.status === "verified" ? "bg-emerald-100 text-emerald-800" : capa.status === "in_progress" ? "bg-blue-100 text-blue-800" : capa.status === "overdue" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"}`}>{capa.status.replace(/_/g," ")}</span>
                        <span className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground">{capa.action_type.replace(/_/g," ")}</span>
                        {capa.owner_name && <span className="text-xs text-muted-foreground">{capa.owner_name}</span>}
                        {capa.due_date && <span className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" />{capa.due_date}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <select value={capa.status} onChange={async e => {
                        const res = await inspectionsApi.updateCAPA(id, capa.id, { status: e.target.value });
                        setCAPAs(prev => prev.map(c => c.id === capa.id ? res.data : c));
                      }} className="text-[10px] border rounded px-1.5 py-1 bg-background">
                        {["open","in_progress","completed","verified","closed"].map(s => <option key={s} value={s}>{s.replace(/_/g," ")}</option>)}
                      </select>
                      <button onClick={async () => { await inspectionsApi.deleteCAPA(id, capa.id); setCAPAs(prev => prev.filter(c => c.id !== capa.id)); }}
                        className="p-1.5 text-muted-foreground hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Outcome + notes */}
          <div className="bg-card border rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-semibold">Inspection Outcome</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide block mb-1.5">Outcome</label>
                <select value={postEdit.outcome}
                  onChange={e => setPostEdit(f => ({ ...f, outcome: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none">
                  <option value="">Not set</option>
                  <option value="no_action">No Action</option>
                  <option value="eir_pending">EIR Pending</option>
                  <option value="483_issued">483 Issued</option>
                  <option value="warning_letter_risk">Warning Letter Risk</option>
                  <option value="closed_satisfactorily">Closed Satisfactorily</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide block mb-1.5">Final 483 Count</label>
                <input type="number" min={0} value={postEdit.final_483_count}
                  onChange={e => setPostEdit(f => ({ ...f, final_483_count: parseInt(e.target.value) || 0 }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide block mb-1.5">Post-Inspection Notes</label>
              <textarea value={postEdit.post_inspection_notes}
                onChange={e => setPostEdit(f => ({ ...f, post_inspection_notes: e.target.value }))}
                rows={3} placeholder="Executive summary of inspection outcome, inspector stance, areas of concern…"
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none resize-none" />
            </div>
            <div className="flex justify-end">
              <button onClick={async () => {
                setSavingPost(true);
                try {
                  await inspectionsApi.updatePostInspection(id, {
                    outcome: postEdit.outcome || undefined,
                    final_483_count: postEdit.final_483_count,
                    post_inspection_notes: postEdit.post_inspection_notes || undefined,
                  });
                  addToast("Post-inspection saved", "info");
                } finally { setSavingPost(false); }
              }} disabled={savingPost}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-60">
                {savingPost ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                {savingPost ? "Saving…" : "Save Outcome"}
              </button>
            </div>
          </div>

          {/* §19 Lessons Learned */}
          <div className="bg-card border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <BookMarked className="w-4 h-4 text-primary" /> Lessons Learned
              </h3>
              <span className="text-xs text-muted-foreground">{lessons.length} captured</span>
            </div>
            <div className="space-y-2 mb-4">
              {lessons.length === 0 ? (
                <p className="text-xs text-muted-foreground">No lessons captured yet — add what this inspection taught your team.</p>
              ) : (
                lessons.map((lesson, idx) => (
                  <div key={idx} className="flex items-start gap-2 bg-muted/30 border rounded-lg px-3 py-2.5">
                    <span className="text-primary font-bold text-xs flex-shrink-0 mt-0.5">{idx + 1}.</span>
                    <p className="text-sm flex-1 leading-relaxed">{lesson}</p>
                    <button onClick={async () => {
                      await inspectionsApi.deleteLesson(id, idx);
                      const r = await inspectionsApi.getLessons(id);
                      setLessons(r.data.lessons ?? []);
                    }} className="text-muted-foreground hover:text-red-600 flex-shrink-0">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <input
                value={newLesson}
                onChange={e => setNewLesson(e.target.value)}
                placeholder="Add a lesson learned…"
                onKeyDown={async e => {
                  if (e.key === "Enter" && newLesson.trim()) {
                    setSavingLesson(true);
                    try {
                      await inspectionsApi.addLesson(id, newLesson);
                      const r = await inspectionsApi.getLessons(id);
                      setLessons(r.data.lessons ?? []);
                      setNewLesson("");
                    } finally { setSavingLesson(false); }
                  }
                }}
                className="flex-1 border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              <button disabled={savingLesson || !newLesson.trim()} onClick={async () => {
                setSavingLesson(true);
                try {
                  await inspectionsApi.addLesson(id, newLesson);
                  const r = await inspectionsApi.getLessons(id);
                  setLessons(r.data.lessons ?? []);
                  setNewLesson("");
                } finally { setSavingLesson(false); }
              }}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                {savingLesson ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              </button>
            </div>
          </div>

          {/* §24 Integration stubs */}
          <div className="bg-card border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <GitMerge className="w-4 h-4 text-primary" /> Export to QMS / EDMS
              </h3>
              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded">Coming soon</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { name: "Veeva Vault QMS", icon: Database },
                { name: "MasterControl", icon: Database },
                { name: "TrackWise", icon: Database },
                { name: "SharePoint", icon: Database },
              ].map(sys => {
                const Icon = sys.icon;
                return (
                  <div key={sys.name} className="flex items-center gap-2 bg-muted/40 border rounded-lg px-3 py-2.5 opacity-60">
                    <Icon className="w-4 h-4 text-muted-foreground" />
                    <span className="text-xs font-medium">{sys.name}</span>
                  </div>
                );
              })}
            </div>
            <p className="text-[11px] text-muted-foreground mt-3">
              One-click export of CAPAs, observations, and commitments to your QMS. Contact your Clyira rep to enable early access.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

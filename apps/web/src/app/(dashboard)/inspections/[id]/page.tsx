"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ChevronLeft, Radio, Plus, Send, RefreshCw, Loader2,
  MessageSquare, FileText, Zap, Clock, CheckCircle2,
  AlertTriangle, XCircle, X, PlayCircle, Square,
} from "lucide-react";
import { inspectionsApi } from "@/lib/api";
import { InspStatusBadge } from "@/components/shared/badges";
import { timeAgo } from "@/lib/utils";

interface Inspection {
  id: string;
  title: string;
  agency: string | null;
  inspection_type: string | null;
  status: string;
  start_date: string | null;
  total_requests: number;
  created_at: string;
  requests?: InspRequest[];
}

interface InspRequest {
  id: string;
  request_text: string;
  criticality: string;
  category: string;
  status: string;
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

const CRITICALITY_COLORS: Record<string, string> = {
  high: "border-l-red-500 bg-red-50",
  medium: "border-l-amber-500 bg-amber-50",
  low: "border-l-blue-500 bg-blue-50",
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
};

const ENTRY_TYPES = [
  { value: "scribe_note", label: "Scribe Note" },
  { value: "observation", label: "Observation" },
  { value: "deficiency", label: "Deficiency" },
  { value: "action_item", label: "Action Item" },
  { value: "document_request", label: "Document Request" },
];

const AI_AGENTS = [
  { key: "scribe", label: "Scribe" },
  { key: "prep_manager", label: "Prep Manager" },
  { key: "sme_coach", label: "SME Coach" },
  { key: "qa_agent", label: "QA Agent" },
  { key: "doc_reviewer", label: "Doc Reviewer" },
];

function AddRequestModal({ onClose, onAdd }: { onClose: () => void; onAdd: (d: any) => Promise<void> }) {
  const [form, setForm] = useState({ request_text: "", criticality: "medium", category: "question" });
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
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
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
              placeholder="Describe the inspector's request or question…"
              value={form.request_text}
              onChange={e => setForm(f => ({ ...f, request_text: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Criticality
              </label>
              <select value={form.criticality} onChange={e => setForm(f => ({ ...f, criticality: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Category
              </label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                <option value="question">Question</option>
                <option value="document_request">Document Request</option>
                <option value="observation">Observation</option>
                <option value="deficiency">Deficiency</option>
              </select>
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

export default function WarRoomPage() {
  const { id } = useParams<{ id: string }>();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"requests" | "scribe" | "log">("requests");
  const [showAddRequest, setShowAddRequest] = useState(false);
  const [scribeText, setScribeText] = useState("");
  const [scribeType, setScribeType] = useState("scribe_note");
  const [sendingScribe, setSendingScribe] = useState(false);
  const [activating, setActivating] = useState(false);
  const [closing, setClosing] = useState(false);
  const [loadError, setLoadError] = useState("");
  const logEndRef = useRef<HTMLDivElement>(null);

  const loadAll = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [inspRes, logRes] = await Promise.all([
        inspectionsApi.get(id),
        inspectionsApi.getLog(id),
      ]);
      setInspection(inspRes.data);
      setLog(logRes.data.entries ?? []);
    } catch {
      setLoadError("Could not load inspection. Please refresh.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, [id]);
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [log]);

  const handleAddRequest = async (data: any) => {
    await inspectionsApi.createRequest(id, data);
    const res = await inspectionsApi.get(id);
    setInspection(res.data);
  };

  const handleUpdateRequest = async (reqId: string, status: string) => {
    await inspectionsApi.updateRequest(id, reqId, { req_status: status });
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
    } finally {
      setSendingScribe(false);
    }
  };

  const handleActivate = async () => {
    setActivating(true);
    try {
      await inspectionsApi.activate(id);
      await loadAll();
    } finally {
      setActivating(false);
    }
  };

  const handleClose = async () => {
    if (!confirm("Close this inspection? This action cannot be undone.")) return;
    setClosing(true);
    try {
      await inspectionsApi.close(id);
      await loadAll();
    } finally {
      setClosing(false);
    }
  };

  const openRequests = (inspection?.requests ?? []).filter(r => r.status === "open");
  const otherRequests = (inspection?.requests ?? []).filter(r => r.status !== "open");

  const typeLabel = (t: string | null) => {
    const map: Record<string, string> = {
      routine: "Routine GMP", for_cause: "For Cause",
      pre_approval: "Pre-Approval (PAI)", surveillance: "Surveillance", directed: "Directed",
    };
    return map[t ?? ""] ?? t ?? "Inspection";
  };

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
              <Radio className={`w-5 h-5 ${inspection.status === "active" ? "text-emerald-600" : "text-primary"}`} />
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
                Close Inspection
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Requests", value: inspection.total_requests },
          { label: "Open", value: openRequests.length, highlight: openRequests.length > 0 },
          { label: "Log Entries", value: log.length },
          { label: "AI Agents", value: inspection.status === "active" ? 5 : 0, active: inspection.status === "active" },
        ].map(s => (
          <div key={s.label} className="bg-card border rounded-xl px-4 py-3">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{s.label}</p>
            <p className={`text-2xl font-bold tabular-nums mt-1 ${
              s.highlight ? "text-amber-600" : s.active ? "text-emerald-600" : ""
            }`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* AI Agents Status */}
      <div className="bg-card border rounded-xl p-4">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5 text-primary" />
          AI Agents
        </p>
        <div className="flex gap-2 flex-wrap">
          {AI_AGENTS.map(agent => (
            <div key={agent.key} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${
              inspection.status === "active"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-muted/50 border-border text-muted-foreground"
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${
                inspection.status === "active" ? "bg-emerald-500" : "bg-muted-foreground/40"
              }`} />
              {agent.label}
            </div>
          ))}
        </div>
      </div>

      {/* Main Tabs */}
      <div className="flex border-b gap-1">
        {[
          { key: "requests", label: `Requests${openRequests.length ? ` (${openRequests.length} open)` : ""}` },
          { key: "scribe", label: "Scribe Entry" },
          { key: "log", label: `Log (${log.length})` },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Requests Tab */}
      {tab === "requests" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Inspector requests logged during the audit — track, respond, and fulfill.
            </p>
            <button onClick={() => setShowAddRequest(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
              <Plus className="w-3.5 h-3.5" />
              Log Request
            </button>
          </div>

          {(inspection.requests ?? []).length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
              <MessageSquare className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">No requests logged</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-sm mx-auto">
                Log inspector requests, document requests, and observations as they occur during the inspection.
              </p>
              <button onClick={() => setShowAddRequest(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 mx-auto">
                <Plus className="w-4 h-4" />
                Log First Request
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {openRequests.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Open</p>
                  <div className="space-y-2">
                    {openRequests.map(req => <RequestCard key={req.id} req={req} inspectionId={id} onUpdate={handleUpdateRequest} />)}
                  </div>
                </div>
              )}
              {otherRequests.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 mt-4">Resolved</p>
                  <div className="space-y-2">
                    {otherRequests.map(req => <RequestCard key={req.id} req={req} inspectionId={id} onUpdate={handleUpdateRequest} />)}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Scribe Entry Tab */}
      {tab === "scribe" && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Record real-time observations, deficiencies, and action items during the inspection.
          </p>
          <form onSubmit={handleScribe} className="bg-card border rounded-xl p-5 space-y-4">
            <div className="flex gap-3 flex-wrap">
              {ENTRY_TYPES.map(t => (
                <button key={t.value} type="button"
                  onClick={() => setScribeType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    scribeType === t.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background border-border text-muted-foreground hover:text-foreground"
                  }`}>
                  {t.label}
                </button>
              ))}
            </div>

            <textarea
              rows={4}
              placeholder={`Enter ${ENTRY_TYPES.find(t => t.value === scribeType)?.label.toLowerCase() ?? "note"}…`}
              value={scribeText}
              onChange={e => setScribeText(e.target.value)}
              className="w-full border rounded-lg px-3 py-2.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
            />

            <div className="flex justify-end">
              <button type="submit" disabled={sendingScribe || !scribeText.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
                {sendingScribe ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                {sendingScribe ? "Saving…" : "Add Entry"}
              </button>
            </div>
          </form>

          {/* Recent scribe entries */}
          {log.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Recent Entries</p>
              {log.slice(-5).reverse().map(entry => <LogEntryCard key={entry.id} entry={entry} />)}
            </div>
          )}
        </div>
      )}

      {/* Full Log Tab */}
      {tab === "log" && (
        <div className="space-y-2">
          {log.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-10 text-center">
              <FileText className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm font-semibold mb-1">No log entries yet</p>
              <p className="text-sm text-muted-foreground">Use the Scribe Entry tab to start recording.</p>
            </div>
          ) : (
            <>
              {log.map(entry => <LogEntryCard key={entry.id} entry={entry} />)}
              <div ref={logEndRef} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function RequestCard({
  req,
  inspectionId,
  onUpdate,
}: {
  req: InspRequest;
  inspectionId: string;
  onUpdate: (id: string, status: string) => void;
}) {
  const [expanded, setExpanded] = useState(req.status === "open");
  const [responding, setResponding] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [aiData, setAiData] = useState<{
    talking_points: string[];
    suggested_documents: string[];
    risk_assessment: string;
  } | null>(
    req.ai_talking_points?.length
      ? {
          talking_points: req.ai_talking_points,
          suggested_documents: req.ai_suggested_documents ?? [],
          risk_assessment: req.ai_risk_assessment ?? "",
        }
      : null
  );
  const statusCfg = REQUEST_STATUS_STYLES[req.status] ?? REQUEST_STATUS_STYLES.open;
  const StatusIcon = statusCfg.icon;

  const handleStatusUpdate = async (s: string) => {
    setResponding(true);
    try { await onUpdate(req.id, s); }
    finally { setResponding(false); }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res = await inspectionsApi.analyzeRequest(inspectionId, req.id);
      setAiData({
        talking_points: res.data.ai_talking_points ?? [],
        suggested_documents: res.data.ai_suggested_documents ?? [],
        risk_assessment: res.data.ai_risk_assessment ?? "",
      });
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className={`border-l-4 rounded-r-xl border rounded-xl overflow-hidden ${CRITICALITY_COLORS[req.criticality] ?? "bg-card"}`}>
      <div className="px-4 py-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium leading-snug">{req.request_text}</p>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                {req.criticality}
              </span>
              <span className="text-[10px] text-muted-foreground">·</span>
              <span className="text-[10px] text-muted-foreground capitalize">{req.category}</span>
              <span className="text-[10px] text-muted-foreground">·</span>
              <span className="text-[10px] text-muted-foreground">{timeAgo(req.created_at)}</span>
              {aiData && (
                <>
                  <span className="text-[10px] text-muted-foreground">·</span>
                  <span className="text-[10px] text-primary font-medium flex items-center gap-0.5">
                    <Zap className="w-2.5 h-2.5" /> AI analyzed
                  </span>
                </>
              )}
            </div>
          </div>
          <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border flex-shrink-0 ${statusCfg.className}`}>
            <StatusIcon className="w-2.5 h-2.5" />
            {statusCfg.label}
          </span>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-current/10 pt-3">
          {req.response_text && (
            <div className="bg-white/70 rounded-lg px-3 py-2">
              <p className="text-xs font-semibold text-muted-foreground mb-1">Response</p>
              <p className="text-sm">{req.response_text}</p>
            </div>
          )}

          {/* AI Analysis Panel */}
          {aiData ? (
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 space-y-2.5">
              <p className="text-[10px] font-semibold text-primary uppercase tracking-wide flex items-center gap-1">
                <Zap className="w-3 h-3" /> AI Analysis
              </p>
              {aiData.risk_assessment && (
                <p className="text-xs text-muted-foreground italic">{aiData.risk_assessment}</p>
              )}
              {aiData.talking_points.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-foreground mb-1">Talking Points</p>
                  <ul className="space-y-1">
                    {aiData.talking_points.map((pt, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs">
                        <span className="text-primary mt-0.5 flex-shrink-0">•</span>
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {aiData.suggested_documents.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-foreground mb-1">Suggested Documents</p>
                  <div className="flex flex-wrap gap-1.5">
                    {aiData.suggested_documents.map((doc, i) => (
                      <span key={i} className="text-[10px] px-2 py-0.5 bg-background border rounded-md font-medium">
                        {doc}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <button onClick={handleAnalyze} disabled={analyzing}
                className="text-[10px] text-primary hover:underline font-medium flex items-center gap-1 disabled:opacity-50">
                {analyzing ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <RefreshCw className="w-2.5 h-2.5" />}
                Re-analyze
              </button>
            </div>
          ) : (
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border rounded-lg bg-white hover:bg-primary/5 hover:border-primary/40 hover:text-primary transition-colors disabled:opacity-50"
            >
              {analyzing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              {analyzing ? "Analyzing…" : "Get AI Analysis"}
            </button>
          )}

          {req.status === "open" && (
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => handleStatusUpdate("in_progress")} disabled={responding}
                className="px-3 py-1.5 text-xs font-medium border rounded-lg bg-white hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors disabled:opacity-50">
                Mark In Progress
              </button>
              <button onClick={() => handleStatusUpdate("fulfilled")} disabled={responding}
                className="px-3 py-1.5 text-xs font-medium border rounded-lg bg-white hover:bg-emerald-50 hover:border-emerald-300 hover:text-emerald-700 transition-colors disabled:opacity-50">
                Mark Fulfilled
              </button>
              <button onClick={() => handleStatusUpdate("declined")} disabled={responding}
                className="px-3 py-1.5 text-xs font-medium border rounded-lg bg-white hover:bg-red-50 hover:border-red-300 hover:text-red-700 transition-colors disabled:opacity-50">
                Decline
              </button>
            </div>
          )}
          {req.status === "in_progress" && (
            <button onClick={() => handleStatusUpdate("fulfilled")} disabled={responding}
              className="px-3 py-1.5 text-xs font-medium border rounded-lg bg-white hover:bg-emerald-50 hover:border-emerald-300 hover:text-emerald-700 transition-colors disabled:opacity-50">
              Mark Fulfilled
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function LogEntryCard({ entry }: { entry: LogEntry }) {
  const cfg = LOG_TYPE_CONFIG[entry.entry_type] ?? { label: entry.entry_type, color: "text-muted-foreground bg-muted" };

  return (
    <div className="bg-card border rounded-xl px-4 py-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded ${cfg.color}`}>
          {cfg.label}
        </span>
        <span className="text-[10px] text-muted-foreground">{timeAgo(entry.created_at)}</span>
        {entry.tags?.length > 0 && (
          <div className="flex gap-1 ml-1">
            {entry.tags.map(tag => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground">
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>
      <p className="text-sm leading-relaxed">{entry.content}</p>
    </div>
  );
}

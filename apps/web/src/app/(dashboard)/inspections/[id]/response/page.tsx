"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ChevronLeft, Loader2, Shield, BadgeCheck, FileText,
  CheckCircle2, Clock, AlertTriangle, Zap, X, Calendar,
  Circle, ClipboardList, Copy, CheckSquare, Lock, RefreshCw,
  Package, AlertCircle, BookOpen, Download, ExternalLink,
} from "lucide-react";
import { inspectionsApi } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Inspection {
  id: string;
  title: string;
  agency: string | null;
  inspection_type: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  closed_at: string | null;
  created_at: string;
  sign_offs: Record<string, boolean>;
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

interface Commitment {
  id: string;
  commitment_text: string;
  committed_to: string | null;
  deadline_at: string | null;
  status: string;
}

interface Delivery {
  id: string;
  document_titles: string[];
  delivered_to: string;
  delivered_at: string;
  acknowledgment_received: boolean;
}

interface BinderDoc {
  id: string;
  category: string;
  title: string;
  filename: string | null;
  version: string | null;
  status: string;
  required: boolean;
  staged_at: string | null;
  delivered_at: string | null;
  delivered_to: string | null;
}

// ── Sign-off definitions ──────────────────────────────────────────────────────
const SIGNOFF_ITEMS = [
  { key: "qa_lead", label: "QA Lead review" },
  { key: "site_director", label: "Site Director approval" },
  { key: "reg_affairs", label: "Regulatory Affairs review" },
  { key: "legal", label: "Legal review (if required)" },
] as const;

// ── Deadline Countdown ────────────────────────────────────────────────────────
function DeadlineCountdown({ baseDate }: { baseDate: string }) {
  const deadline = useCallback(() => {
    const start = new Date(baseDate);
    let count = 0;
    const d = new Date(start);
    while (count < 15) {
      d.setDate(d.getDate() + 1);
      const day = d.getDay();
      if (day !== 0 && day !== 6) count++;
    }
    return d;
  }, [baseDate]);

  const dl = deadline();
  const now = new Date();
  const daysLeft = Math.ceil((dl.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  const overdue = daysLeft < 0;
  const urgent = !overdue && daysLeft <= 5;

  return (
    <div className={`rounded-xl px-5 py-4 border flex items-start justify-between gap-4 ${
      overdue ? "bg-red-50 border-red-200" :
      urgent  ? "bg-orange-50 border-orange-200" :
                "bg-amber-50 border-amber-200"
    }`}>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
          FDA 483 Response Deadline · 15 Business Days
        </p>
        <p className={`text-3xl font-bold tabular-nums mt-1 ${
          overdue ? "text-red-700" : urgent ? "text-orange-700" : "text-amber-800"
        }`}>
          {overdue ? "OVERDUE" : `${daysLeft} day${daysLeft !== 1 ? "s" : ""} remaining`}
        </p>
        <p className="text-xs text-amber-700 mt-0.5">
          Due by {dl.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
        </p>
        {urgent && !overdue && (
          <p className="text-xs font-semibold text-orange-800 mt-2 bg-orange-100 rounded px-2 py-1 inline-block">
            Less than 5 business days — prioritize sign-off and submission immediately.
          </p>
        )}
      </div>
      <Clock className={`w-10 h-10 flex-shrink-0 ${overdue ? "text-red-400" : urgent ? "text-orange-400" : "text-amber-400"}`} />
    </div>
  );
}

// ── Observation Response Card ─────────────────────────────────────────────────
function ObservationCard({
  obs,
  inspectionId,
  onUpdate,
}: {
  obs: Observation;
  inspectionId: string;
  onUpdate: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(obs.draft_response ?? "");
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSaveDraft = async () => {
    setSaving(true);
    try {
      await inspectionsApi.updateObservation(inspectionId, obs.id, { draft_response: draftText });
      setEditing(false);
      onUpdate();
    } finally { setSaving(false); }
  };

  const handleAiDraft = async () => {
    setDrafting(true);
    try {
      const r = await inspectionsApi.draftObservationResponse(inspectionId, obs.id);
      setDraftText(r.data.draft_response ?? "");
      setEditing(true);
    } finally { setDrafting(false); }
  };

  const handleSubmit = async () => {
    if (!draftText.trim()) return;
    setSubmitting(true);
    try {
      await inspectionsApi.updateObservation(inspectionId, obs.id, { obs_status: "submitted" });
      onUpdate();
    } finally { setSubmitting(false); }
  };

  const statusColor = ({
    draft:        "bg-muted text-muted-foreground border-border",
    under_review: "bg-blue-50 text-blue-700 border-blue-200",
    submitted:    "bg-emerald-50 text-emerald-700 border-emerald-200",
    closed:       "bg-gray-50 text-gray-500 border-gray-200",
  } as Record<string, string>)[obs.status] ?? "bg-muted text-muted-foreground border-border";

  return (
    <div className="bg-card border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b bg-amber-50/40">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-xs font-bold text-amber-800 font-mono">
                OBS-{String(obs.observation_number).padStart(3, "0")}
              </span>
              {obs.system_area && (
                <span className="text-xs text-muted-foreground">· {obs.system_area}</span>
              )}
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${statusColor}`}>
                {obs.status.replace("_", " ")}
              </span>
              {obs.legal_review_required && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded border bg-purple-50 text-purple-700 border-purple-200">
                  Legal Review Required
                </span>
              )}
            </div>
            <p className="text-sm font-medium leading-snug">{obs.observation_text}</p>
            {obs.cfr_citations?.length > 0 && (
              <div className="flex gap-1 flex-wrap mt-2">
                {obs.cfr_citations.map(c => (
                  <span key={c} className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded border border-amber-200 font-mono">{c}</span>
                ))}
              </div>
            )}
          </div>
          {obs.status === "submitted" && (
            <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
          )}
        </div>
      </div>

      {/* Response area */}
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Response</p>
          <div className="flex gap-2">
            {!obs.draft_response && !editing && (
              <button onClick={handleAiDraft} disabled={drafting}
                className="flex items-center gap-1 text-xs text-primary hover:underline font-medium disabled:opacity-50">
                {drafting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                AI Draft
              </button>
            )}
            {obs.draft_response && !editing && obs.status !== "submitted" && (
              <button onClick={() => setEditing(true)}
                className="text-xs text-primary hover:underline font-medium">
                Edit
              </button>
            )}
            {obs.draft_response && obs.status !== "submitted" && (
              <button onClick={handleAiDraft} disabled={drafting}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary font-medium disabled:opacity-50">
                {drafting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                Re-draft
              </button>
            )}
          </div>
        </div>

        {editing ? (
          <div className="space-y-2">
            <textarea
              rows={7}
              value={draftText}
              onChange={e => setDraftText(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
            <div className="flex gap-2">
              <button onClick={handleSaveDraft} disabled={saving}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium disabled:opacity-60">
                {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                Save Draft
              </button>
              <button onClick={() => { setEditing(false); setDraftText(obs.draft_response ?? ""); }}
                className="px-3 py-1.5 border rounded-lg text-xs font-medium hover:bg-accent">
                Cancel
              </button>
            </div>
          </div>
        ) : obs.draft_response ? (
          <div className="bg-muted/30 rounded-lg px-4 py-3">
            <p className="text-sm leading-relaxed whitespace-pre-wrap text-muted-foreground">{obs.draft_response}</p>
          </div>
        ) : (
          <div className="bg-muted/20 border border-dashed rounded-lg px-4 py-6 text-center">
            <p className="text-sm text-muted-foreground">No response drafted yet</p>
            <p className="text-xs text-muted-foreground mt-1">Use AI Draft to generate a starting point based on your CAPA and inspection data</p>
          </div>
        )}

        {obs.draft_response && obs.status !== "submitted" && obs.status !== "closed" && (
          <button onClick={handleSubmit} disabled={submitting}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700 disabled:opacity-60 w-full justify-center">
            {submitting ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
            Mark Response as Submitted
          </button>
        )}
      </div>
    </div>
  );
}

// ── Close Inspection Modal ────────────────────────────────────────────────────
function CloseInspectionModal({
  inspectionTitle,
  onConfirm,
  onCancel,
  loading,
}: {
  inspectionTitle: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [typed, setTyped] = useState("");
  const confirmed = typed.trim().toLowerCase() === "close";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-card border rounded-2xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-start gap-3 px-6 pt-6 pb-3">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
            <Lock className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <h2 className="font-semibold text-base">Close Inspection</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              This will permanently close <strong className="text-foreground">{inspectionTitle}</strong> and lock the war room. All post-inspection work (483 responses, CAPA tracking) continues in the Response workspace.
            </p>
          </div>
        </div>

        <div className="px-6 pb-2 space-y-3">
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 text-xs text-amber-900 space-y-1">
            <p className="font-semibold flex items-center gap-1.5"><AlertCircle className="w-3.5 h-3.5" /> Before closing, confirm:</p>
            <ul className="ml-4 space-y-0.5 list-disc">
              <li>All inspector requests are fulfilled or formally declined</li>
              <li>All verbal commitments are logged</li>
              <li>All 483 observations have been recorded</li>
            </ul>
          </div>
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Type <span className="text-foreground font-mono">close</span> to confirm
            </label>
            <input
              value={typed}
              onChange={e => setTyped(e.target.value)}
              placeholder="close"
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-red-200 focus:border-red-400"
            />
          </div>
        </div>

        <div className="px-6 pb-6 flex gap-2 justify-end">
          <button onClick={onCancel} className="px-4 py-2 text-sm border rounded-lg hover:bg-accent">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!confirmed || loading}
            className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Lock className="w-3.5 h-3.5" />}
            Close Inspection
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Binder Status Badge ───────────────────────────────────────────────────────
const BINDER_STATUS: Record<string, string> = {
  missing:   "bg-red-50 text-red-700 border-red-200",
  staged:    "bg-amber-50 text-amber-700 border-amber-200",
  ready:     "bg-blue-50 text-blue-700 border-blue-200",
  delivered: "bg-emerald-50 text-emerald-700 border-emerald-200",
  withdrawn: "bg-gray-50 text-gray-500 border-gray-200",
};

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function PostInspectionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [binderDocs, setBinderDocs] = useState<BinderDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [tab, setTab] = useState<"483s" | "commitments" | "binder" | "letter">("483s");
  const [coverLetter, setCoverLetter] = useState("");
  const [generatingLetter, setGeneratingLetter] = useState(false);
  const [copied, setCopied] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);

  // Persisted sign-offs (loaded from + saved to backend)
  const [signoffs, setSignoffs] = useState<Record<string, boolean>>({});
  const [savingSignoff, setSavingSignoff] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [inspRes, obsRes, commitRes, delivRes, binderRes, summaryRes] = await Promise.all([
        inspectionsApi.get(id),
        inspectionsApi.listObservations(id),
        inspectionsApi.listCommitments(id),
        inspectionsApi.listDeliveries(id),
        inspectionsApi.listBinder(id),
        inspectionsApi.getPostInspectionSummary(id),
      ]);
      setInspection(inspRes.data);
      setObservations(obsRes.data.observations ?? []);
      setCommitments(commitRes.data.commitments ?? []);
      setDeliveries(delivRes.data.deliveries ?? []);
      setBinderDocs(binderRes.data.binder_docs ?? []);
      // Restore persisted sign-offs from backend
      const saved: Record<string, boolean> = summaryRes.data.sign_offs ?? {};
      setSignoffs(saved);
    } catch {
      setLoadError("Could not load inspection data. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleToggleSignoff = async (key: string, currentValue: boolean) => {
    const updated = { ...signoffs, [key]: !currentValue };
    setSignoffs(updated);
    setSavingSignoff(true);
    try {
      await inspectionsApi.updatePostInspection(id, { sign_offs: updated });
    } catch {
      setSignoffs(prev => ({ ...prev, [key]: currentValue }));
    } finally {
      setSavingSignoff(false);
    }
  };

  const handleGenerateLetter = async () => {
    setGeneratingLetter(true);
    try {
      const r = await inspectionsApi.generateCoverLetter(id);
      setCoverLetter(r.data.letter ?? "");
    } finally { setGeneratingLetter(false); }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    try {
      await inspectionsApi.finalizeInspection(id);
      router.push("/inspections");
    } finally {
      setFinalizing(false);
      setShowCloseModal(false);
    }
  };

  const submittedObs = observations.filter(o => o.status === "submitted");
  const pendingObs   = observations.filter(o => o.status !== "submitted" && o.status !== "closed");
  const deliveredCommitments = commitments.filter(c => c.status === "delivered");
  const allSignoffsDone = SIGNOFF_ITEMS.every(s => signoffs[s.key]);
  const deliveredBinder = binderDocs.filter(d => d.status === "delivered");

  const readyToFinalize =
    pendingObs.length === 0 &&
    commitments.filter(c => c.status === "pending").length === 0 &&
    allSignoffsDone;

  // Determine deadline base: closed_at → end_date → created_at
  const deadlineBase = inspection?.closed_at ?? inspection?.end_date ?? inspection?.created_at ?? "";

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
        <Link href="/inspections" className="text-sm text-primary hover:underline mt-2 inline-block">← Back</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {showCloseModal && (
        <CloseInspectionModal
          inspectionTitle={inspection.title}
          onConfirm={handleFinalize}
          onCancel={() => setShowCloseModal(false)}
          loading={finalizing}
        />
      )}

      {/* Breadcrumb */}
      <div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <Link href="/inspections" className="hover:text-foreground">Inspections</Link>
          <ChevronLeft className="w-3 h-3 rotate-180" />
          <Link href={`/inspections/${id}`} className="hover:text-foreground">{inspection.title}</Link>
          <ChevronLeft className="w-3 h-3 rotate-180" />
          <span className="text-foreground font-medium">Post-Inspection Response</span>
        </div>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{inspection.title}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {inspection.agency ?? "FDA"} · {inspection.inspection_type ?? "Inspection"} · Post-inspection response workflow
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={loadAll} disabled={loading}
              className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
            <Link href={`/inspections/${id}`}
              className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent">
              <ChevronLeft className="w-3.5 h-3.5" /> War Room
            </Link>
            <button
              onClick={() => setShowCloseModal(true)}
              disabled={!readyToFinalize || finalizing}
              title={!readyToFinalize ? "Complete all observations, commitments, and sign-offs first" : undefined}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed">
              <Lock className="w-3.5 h-3.5" />
              Close Inspection
            </button>
          </div>
        </div>
      </div>

      {/* Deadline countdown — based on closed_at / end_date, not created_at */}
      {deadlineBase && <DeadlineCountdown baseDate={deadlineBase} />}

      {/* Progress overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: "483 Observations",
            value: observations.length,
            sub: `${submittedObs.length} submitted`,
            ok: submittedObs.length === observations.length && observations.length > 0,
          },
          {
            label: "Commitments",
            value: commitments.length,
            sub: `${deliveredCommitments.length} delivered`,
            ok: deliveredCommitments.length === commitments.length && commitments.length > 0,
          },
          {
            label: "Binder Docs",
            value: binderDocs.length,
            sub: `${deliveredBinder.length} delivered`,
            ok: deliveredBinder.length === binderDocs.length && binderDocs.length > 0,
          },
          {
            label: "Sign-offs",
            value: `${SIGNOFF_ITEMS.filter(s => signoffs[s.key]).length}/${SIGNOFF_ITEMS.length}`,
            ok: allSignoffsDone,
          },
        ].map(s => (
          <div key={s.label} className={`bg-card border rounded-xl px-4 py-3 ${s.ok ? "border-emerald-200" : ""}`}>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{s.label}</p>
            <p className={`text-2xl font-bold tabular-nums mt-1 ${s.ok ? "text-emerald-600" : ""}`}>{s.value}</p>
            {s.sub && <p className="text-xs text-muted-foreground">{s.sub}</p>}
          </div>
        ))}
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: main tabs */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex border-b gap-0 overflow-x-auto">
            {[
              { key: "483s",        label: `483 Responses (${observations.length})`,     icon: Shield },
              { key: "commitments", label: `Commitments (${commitments.length})`,         icon: BadgeCheck },
              { key: "binder",      label: `Binder (${binderDocs.length})`,               icon: BookOpen },
              { key: "letter",      label: "Cover Letter",                                icon: FileText },
            ].map(t => {
              const Icon = t.icon;
              return (
                <button key={t.key} onClick={() => setTab(t.key as any)}
                  className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${
                    tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}>
                  <Icon className="w-3 h-3" />
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* 483 Responses */}
          {tab === "483s" && (
            <div className="space-y-4">
              {observations.length === 0 ? (
                <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-10 text-center">
                  <Shield className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm font-semibold mb-1">No 483 observations</p>
                  <p className="text-sm text-muted-foreground">No formal observations were issued in this inspection.</p>
                </div>
              ) : (
                observations.map(obs => (
                  <ObservationCard key={obs.id} obs={obs} inspectionId={id} onUpdate={loadAll} />
                ))
              )}
            </div>
          )}

          {/* Commitments */}
          {tab === "commitments" && (
            <div className="space-y-3">
              {commitments.length === 0 ? (
                <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-10 text-center">
                  <BadgeCheck className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No commitments logged.</p>
                </div>
              ) : (
                commitments.map(c => (
                  <div key={c.id} className={`bg-card border rounded-xl px-4 py-3 ${
                    c.status === "overdue" ? "border-red-200" :
                    c.status === "delivered" ? "border-emerald-200" : ""
                  }`}>
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium flex-1">{c.commitment_text}</p>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border flex-shrink-0 ${
                        c.status === "delivered" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                        c.status === "overdue"   ? "bg-red-50 text-red-700 border-red-200" :
                                                    "bg-amber-50 text-amber-700 border-amber-200"
                      }`}>{c.status}</span>
                    </div>
                    <div className="flex gap-3 mt-1.5 text-[10px] text-muted-foreground">
                      {c.committed_to && <span>To: {c.committed_to}</span>}
                      {c.deadline_at && <span>Due: {new Date(c.deadline_at).toLocaleDateString()}</span>}
                    </div>
                    {c.status === "pending" && (
                      <button
                        onClick={async () => {
                          await inspectionsApi.updateCommitment(id, c.id, { status: "delivered" });
                          await loadAll();
                        }}
                        className="mt-2 flex items-center gap-1 text-[10px] text-emerald-700 hover:underline font-medium">
                        <CheckCircle2 className="w-3 h-3" /> Mark Delivered
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* Binder — shows InspectionBinderDoc items, not delivery receipts */}
          {tab === "binder" && (
            <div className="space-y-3">
              {binderDocs.length === 0 ? (
                <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-10 text-center">
                  <BookOpen className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm font-semibold mb-1">Inspection binder is empty</p>
                  <p className="text-sm text-muted-foreground">Documents staged and delivered during the inspection appear here.</p>
                  <Link href={`/inspections/${id}`}
                    className="inline-flex items-center gap-1.5 mt-3 text-xs text-primary hover:underline font-medium">
                    <ExternalLink className="w-3 h-3" /> Go to war room to seed binder
                  </Link>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                    <span>{deliveredBinder.length} of {binderDocs.length} documents delivered</span>
                    <span>{binderDocs.filter(d => d.required && d.status !== "delivered").length} required items outstanding</span>
                  </div>
                  {binderDocs.map(doc => (
                    <div key={doc.id} className={`bg-card border rounded-xl px-4 py-3 flex items-start gap-3 ${
                      doc.required && doc.status === "missing" ? "border-red-200 bg-red-50/30" : ""
                    }`}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-0.5">
                          <span className="text-sm font-medium truncate">{doc.title}</span>
                          {doc.required && (
                            <span className="text-[10px] font-semibold px-1.5 py-0.5 bg-primary/10 text-primary rounded">Required</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground flex-wrap">
                          <span className="capitalize">{doc.category.replace(/_/g, " ")}</span>
                          {doc.version && <span>v{doc.version}</span>}
                          {doc.filename && <span>{doc.filename}</span>}
                          {doc.delivered_at && <span>Delivered {timeAgo(doc.delivered_at)}{doc.delivered_to ? ` to ${doc.delivered_to}` : ""}</span>}
                        </div>
                      </div>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border flex-shrink-0 ${BINDER_STATUS[doc.status] ?? BINDER_STATUS.missing}`}>
                        {doc.status}
                      </span>
                    </div>
                  ))}
                  {/* Delivery receipts summary */}
                  {deliveries.length > 0 && (
                    <div className="border-t pt-3 mt-3">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Delivery Receipts ({deliveries.length})</p>
                      {deliveries.map(d => (
                        <div key={d.id} className="flex items-center justify-between text-xs text-muted-foreground py-1.5 border-b last:border-0">
                          <span>{new Date(d.delivered_at).toLocaleString()}</span>
                          <span>{d.document_titles.length} doc{d.document_titles.length !== 1 ? "s" : ""} → {d.delivered_to}</span>
                          {d.acknowledgment_received && (
                            <span className="flex items-center gap-1 text-emerald-600 font-medium">
                              <CheckCircle2 className="w-3 h-3" /> Ack
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Cover Letter */}
          {tab === "letter" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  AI-drafted formal response letter to the FDA District Director.
                </p>
                <button onClick={handleGenerateLetter} disabled={generatingLetter}
                  className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-60">
                  {generatingLetter ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                  {generatingLetter ? "Generating…" : coverLetter ? "Regenerate" : "Generate Letter"}
                </button>
              </div>
              {coverLetter ? (
                <div className="bg-card border rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Draft Cover Letter</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(coverLetter);
                          setCopied(true);
                          setTimeout(() => setCopied(false), 2000);
                        }}
                        className="flex items-center gap-1 text-xs text-primary hover:underline font-medium">
                        {copied ? <CheckCircle2 className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        {copied ? "Copied!" : "Copy"}
                      </button>
                      <button
                        onClick={() => {
                          const blob = new Blob([coverLetter], { type: "text/plain" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `483_response_cover_letter.txt`;
                          a.click();
                          URL.revokeObjectURL(url);
                        }}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium">
                        <Download className="w-3 h-3" /> Download
                      </button>
                    </div>
                  </div>
                  <pre className="text-sm leading-relaxed whitespace-pre-wrap font-sans">{coverLetter}</pre>
                </div>
              ) : (
                <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
                  <FileText className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-sm font-semibold mb-1">No cover letter yet</p>
                  <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                    Generate an AI-drafted formal response letter incorporating all observation responses and commitments.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: sign-off + readiness */}
        <div className="space-y-4">
          {/* Sign-off checklist — persisted to backend */}
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <ClipboardList className="w-3.5 h-3.5 text-primary" /> Management Sign-off
              {savingSignoff && <Loader2 className="w-3 h-3 animate-spin text-primary ml-auto" />}
            </p>
            <div className="space-y-2.5">
              {SIGNOFF_ITEMS.map(item => {
                const done = !!signoffs[item.key];
                return (
                  <button
                    key={item.key}
                    onClick={() => handleToggleSignoff(item.key, done)}
                    disabled={savingSignoff}
                    className="flex items-center gap-2.5 w-full text-left group disabled:opacity-60">
                    {done
                      ? <CheckSquare className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      : <Circle className="w-4 h-4 text-muted-foreground/40 flex-shrink-0 group-hover:text-muted-foreground" />
                    }
                    <span className={`text-sm ${done ? "line-through text-muted-foreground" : ""}`}>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Submission readiness */}
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-primary" /> Submission Readiness
            </p>
            <div className="space-y-2">
              {[
                { text: "All 483 responses drafted",           done: observations.length > 0 && pendingObs.length === 0 },
                { text: "All responses marked submitted",      done: submittedObs.length === observations.length && observations.length > 0 },
                { text: "All commitments delivered",           done: deliveredCommitments.length === commitments.length && commitments.length > 0 },
                { text: "Cover letter generated",              done: !!coverLetter },
                { text: "Management sign-offs complete",       done: allSignoffsDone },
              ].map(item => (
                <div key={item.text} className="flex items-center gap-2">
                  {item.done
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                    : <Circle className="w-3.5 h-3.5 text-muted-foreground/30 flex-shrink-0" />
                  }
                  <span className={`text-xs ${item.done ? "text-foreground" : "text-muted-foreground"}`}>{item.text}</span>
                </div>
              ))}
            </div>

            {readyToFinalize && (
              <div className="mt-3 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg">
                <p className="text-xs font-semibold text-emerald-800 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Ready to close
                </p>
              </div>
            )}
          </div>

          {/* Quick stats */}
          <div className="bg-muted/40 border rounded-xl p-4 text-xs text-muted-foreground space-y-1.5">
            <p className="font-semibold text-foreground mb-2">Quick Stats</p>
            <p>{observations.length} observation{observations.length !== 1 ? "s" : ""} · {submittedObs.length} submitted</p>
            <p>{commitments.length} commitment{commitments.length !== 1 ? "s" : ""} · {deliveredCommitments.length} delivered</p>
            <p>{binderDocs.length} binder doc{binderDocs.length !== 1 ? "s" : ""} · {deliveredBinder.length} delivered</p>
            <p>{deliveries.length} delivery receipt{deliveries.length !== 1 ? "s" : ""} logged</p>
            {inspection.end_date && (
              <p className="text-foreground font-medium mt-2 pt-2 border-t">Closed: {new Date(inspection.end_date).toLocaleDateString()}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

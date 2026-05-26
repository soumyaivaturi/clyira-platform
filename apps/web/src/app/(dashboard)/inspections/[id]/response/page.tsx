"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ChevronLeft, Loader2, Shield, BadgeCheck, FileText,
  CheckCircle2, Clock, AlertTriangle, Zap, X, Calendar,
  ArrowRight, TriangleAlert, Circle, ClipboardList, Send,
  Copy, CheckSquare, Lock, RefreshCw, Package,
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

// ── Deadline Countdown ────────────────────────────────────────────────────────
function DeadlineCountdown({ closedAt }: { closedAt: string }) {
  const businessDeadline = useCallback(() => {
    const start = new Date(closedAt);
    let count = 0;
    const d = new Date(start);
    while (count < 15) {
      d.setDate(d.getDate() + 1);
      const day = d.getDay();
      if (day !== 0 && day !== 6) count++;
    }
    return d;
  }, [closedAt]);

  const deadline = businessDeadline();
  const now = new Date();
  const daysLeft = Math.ceil((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  const overdue = daysLeft < 0;
  const urgent = daysLeft >= 0 && daysLeft <= 5;

  return (
    <div className={`rounded-xl px-5 py-4 border ${
      overdue ? "bg-red-50 border-red-200" :
      urgent ? "bg-orange-50 border-orange-200" :
      "bg-amber-50 border-amber-200"
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">FDA 483 Response Deadline</p>
          <p className={`text-3xl font-bold tabular-nums mt-1 ${overdue ? "text-red-700" : urgent ? "text-orange-700" : "text-amber-800"}`}>
            {overdue ? "OVERDUE" : `${daysLeft} days remaining`}
          </p>
          <p className="text-xs text-amber-700 mt-0.5">
            Due by {deadline.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
          </p>
        </div>
        <div className="flex-shrink-0">
          <Clock className={`w-10 h-10 ${overdue ? "text-red-400" : urgent ? "text-orange-400" : "text-amber-400"}`} />
        </div>
      </div>
      {urgent && !overdue && (
        <p className="text-xs font-semibold text-orange-800 mt-2 bg-orange-100 rounded px-2 py-1">
          ⚠ Less than 5 business days remaining — prioritize sign-off and submission immediately.
        </p>
      )}
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
      await inspectionsApi.updateObservation(inspectionId, obs.id, { status: "submitted" });
      onUpdate();
    } finally { setSubmitting(false); }
  };

  const statusColor = {
    draft: "bg-muted text-muted-foreground border-border",
    under_review: "bg-blue-50 text-blue-700 border-blue-200",
    submitted: "bg-emerald-50 text-emerald-700 border-emerald-200",
    closed: "bg-gray-50 text-gray-500 border-gray-200",
  }[obs.status] ?? "bg-muted text-muted-foreground border-border";

  return (
    <div className="bg-card border rounded-xl overflow-hidden">
      {/* Observation header */}
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
          </div>
        </div>

        {editing ? (
          <div className="space-y-2">
            <textarea
              rows={6}
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

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function PostInspectionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [tab, setTab] = useState<"483s" | "commitments" | "binder" | "letter">("483s");
  const [coverLetter, setCoverLetter] = useState("");
  const [generatingLetter, setGeneratingLetter] = useState(false);
  const [copied, setCopied] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

  const [signoffs, setSignoffs] = useState([
    { label: "QA Lead review", done: false },
    { label: "Site Director approval", done: false },
    { label: "Regulatory Affairs review", done: false },
    { label: "Legal review (if required)", done: false },
  ]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [inspRes, obsRes, commitRes, delivRes] = await Promise.all([
        inspectionsApi.get(id),
        inspectionsApi.listObservations(id),
        inspectionsApi.listCommitments(id),
        inspectionsApi.listDeliveries(id),
      ]);
      setInspection(inspRes.data);
      setObservations(obsRes.data.observations ?? []);
      setCommitments(commitRes.data.commitments ?? []);
      setDeliveries(delivRes.data.deliveries ?? []);
    } catch {
      setLoadError("Could not load inspection data. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleGenerateLetter = async () => {
    setGeneratingLetter(true);
    try {
      const r = await inspectionsApi.generateCoverLetter(id);
      setCoverLetter(r.data.letter ?? "");
    } finally { setGeneratingLetter(false); }
  };

  const handleFinalize = async () => {
    if (!confirm("Mark this inspection as fully closed? All response work should be complete.")) return;
    setFinalizing(true);
    try {
      await inspectionsApi.finalizeInspection(id);
      router.push("/inspections");
    } finally { setFinalizing(false); }
  };

  const submittedObs = observations.filter(o => o.status === "submitted");
  const pendingObs = observations.filter(o => o.status !== "submitted" && o.status !== "closed");
  const deliveredCommitments = commitments.filter(c => c.status === "delivered");
  const allSignoffsDone = signoffs.every(s => s.done);

  const readyToFinalize =
    pendingObs.length === 0 &&
    commitments.filter(c => c.status === "pending").length === 0 &&
    allSignoffsDone;

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
            <Link href={`/inspections/${id}`}
              className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent">
              <ChevronLeft className="w-3.5 h-3.5" /> War Room
            </Link>
            <button
              onClick={handleFinalize}
              disabled={!readyToFinalize || finalizing}
              title={!readyToFinalize ? "Complete all observations, commitments, and sign-offs first" : undefined}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed">
              {finalizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Lock className="w-3.5 h-3.5" />}
              Close Inspection
            </button>
          </div>
        </div>
      </div>

      {/* Deadline countdown */}
      <DeadlineCountdown closedAt={inspection.created_at} />

      {/* Progress overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "483 Observations", value: observations.length, sub: `${submittedObs.length} submitted`, ok: submittedObs.length === observations.length && observations.length > 0 },
          { label: "Commitments", value: commitments.length, sub: `${deliveredCommitments.length} delivered`, ok: deliveredCommitments.length === commitments.length && commitments.length > 0 },
          { label: "Deliveries Logged", value: deliveries.length, ok: deliveries.length > 0 },
          { label: "Sign-offs", value: `${signoffs.filter(s => s.done).length}/${signoffs.length}`, ok: allSignoffsDone },
        ].map(s => (
          <div key={s.label} className={`bg-card border rounded-xl px-4 py-3 ${s.ok ? "border-emerald-200" : ""}`}>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{s.label}</p>
            <p className={`text-2xl font-bold tabular-nums mt-1 ${s.ok ? "text-emerald-600" : ""}`}>{s.value}</p>
            {s.sub && <p className="text-xs text-muted-foreground">{s.sub}</p>}
          </div>
        ))}
      </div>

      {/* Main content — two-column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: main tabs */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex border-b gap-0">
            {[
              { key: "483s", label: `483 Responses (${observations.length})`, icon: Shield },
              { key: "commitments", label: `Commitments (${commitments.length})`, icon: BadgeCheck },
              { key: "binder", label: `Binder (${deliveries.length})`, icon: Package },
              { key: "letter", label: "Cover Letter", icon: FileText },
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
                  <div key={c.id} className={`bg-card border rounded-xl px-4 py-3 ${c.status === "overdue" ? "border-red-200" : c.status === "delivered" ? "border-emerald-200" : ""}`}>
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium flex-1">{c.commitment_text}</p>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border flex-shrink-0 ${
                        c.status === "delivered" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                        c.status === "overdue" ? "bg-red-50 text-red-700 border-red-200" :
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

          {/* Binder */}
          {tab === "binder" && (
            <div className="space-y-3">
              {deliveries.length === 0 ? (
                <div className="bg-muted/30 border border-dashed rounded-xl px-6 py-10 text-center">
                  <Package className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No document deliveries logged.</p>
                </div>
              ) : (
                deliveries.map(d => (
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
                        <span key={t} className="text-xs px-2 py-1 bg-muted border rounded-md">{t}</span>
                      ))}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1.5">Delivered to: {d.delivered_to}</p>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Cover Letter */}
          {tab === "letter" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">AI-drafted formal response letter to the FDA District Director.</p>
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
                    <button
                      onClick={() => { navigator.clipboard.writeText(coverLetter); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                      className="flex items-center gap-1 text-xs text-primary hover:underline font-medium">
                      {copied ? <CheckCircle2 className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      {copied ? "Copied!" : "Copy"}
                    </button>
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

        {/* Right: sign-off panel */}
        <div className="space-y-4">
          {/* Sign-off checklist */}
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <ClipboardList className="w-3.5 h-3.5 text-primary" /> Management Sign-off
            </p>
            <div className="space-y-2.5">
              {signoffs.map((item, i) => (
                <button
                  key={item.label}
                  onClick={() => setSignoffs(s => s.map((x, j) => j === i ? { ...x, done: !x.done } : x))}
                  className="flex items-center gap-2.5 w-full text-left group">
                  {item.done
                    ? <CheckSquare className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                    : <Circle className="w-4 h-4 text-muted-foreground/40 flex-shrink-0 group-hover:text-muted-foreground" />
                  }
                  <span className={`text-sm ${item.done ? "line-through text-muted-foreground" : ""}`}>{item.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Readiness checklist */}
          <div className="bg-card border rounded-xl p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-primary" /> Submission Readiness
            </p>
            <div className="space-y-2">
              {[
                { text: "All 483 responses drafted", done: observations.length > 0 && pendingObs.length === 0 },
                { text: "All responses marked submitted", done: submittedObs.length === observations.length && observations.length > 0 },
                { text: "All commitments delivered", done: deliveredCommitments.length === commitments.length && commitments.length > 0 },
                { text: "Cover letter generated", done: !!coverLetter },
                { text: "Management sign-offs complete", done: allSignoffsDone },
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

          {/* Stats */}
          <div className="bg-muted/40 border rounded-xl p-4 text-xs text-muted-foreground space-y-1.5">
            <p className="font-semibold text-foreground mb-2">Quick Stats</p>
            <p>{observations.length} observation{observations.length !== 1 ? "s" : ""} · {submittedObs.length} submitted</p>
            <p>{commitments.length} commitment{commitments.length !== 1 ? "s" : ""} · {deliveredCommitments.length} delivered</p>
            <p>{deliveries.length} document delivery{deliveries.length !== 1 ? "ies" : ""} logged</p>
          </div>
        </div>
      </div>
    </div>
  );
}

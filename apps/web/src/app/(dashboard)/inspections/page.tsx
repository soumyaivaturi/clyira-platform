"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  Radio, Plus, RefreshCw, ChevronRight, Loader2, X,
  AlertTriangle, AlertCircle, CheckCircle2, Clock,
  MapPin, Calendar, Activity, Users, Zap,
  Building2, TrendingUp, Eye,
} from "lucide-react";
import { inspectionsApi } from "@/lib/api";
import { InspStatusBadge } from "@/components/shared/badges";
import { EmptyState } from "@/components/shared/empty-state";

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
  ai_agents_count: number;
  site_name: string | null;
  mode: string;
  sector: string | null;
  day_count: number;
  created_at: string;
}

const INSPECTION_TYPES = [
  { value: "routine", label: "Routine GMP" },
  { value: "for_cause", label: "For Cause" },
  { value: "pre_approval", label: "Pre-Approval (PAI)" },
  { value: "surveillance", label: "Surveillance" },
  { value: "directed", label: "Directed" },
  { value: "client_audit", label: "Client Audit" },
  { value: "supplier_audit", label: "Supplier Audit" },
];

const AGENCIES = ["FDA", "EMA", "MHRA", "TGA", "Health Canada", "PMDA", "ANVISA", "WHO", "Other"];

const PHASE_LABELS: Record<string, string> = {
  opening_meeting: "Opening Meeting",
  facility_tour: "Facility Tour",
  document_review: "Document Review",
  systems_review: "Systems Review",
  closing_meeting: "Closing Meeting",
};

const STATUS_TABS = [
  { key: "active", label: "Live Now" },
  { key: "planned", label: "Upcoming" },
  { key: "post_inspection", label: "Post-Inspection" },
  { key: "closed", label: "Closed" },
  { key: "", label: "All" },
];

function typeLabel(t: string | null) {
  return INSPECTION_TYPES.find(x => x.value === t)?.label ?? t ?? "Inspection";
}

function dayNumber(startDate: string | null): number {
  if (!startDate) return 1;
  const diff = Math.ceil((Date.now() - new Date(startDate).getTime()) / 86400000);
  return Math.max(1, diff);
}

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86400000);
}

// ── Health badge ──────────────────────────────────────────────────────────────
function healthBadge(insp: Inspection): { label: string; cls: string } {
  if (insp.status !== "active") return { label: "—", cls: "text-muted-foreground" };
  const reqs = insp.total_requests;
  if (reqs === 0) return { label: "On Track", cls: "bg-emerald-100 text-emerald-800 border border-emerald-200" };
  if (reqs >= 10) return { label: "At Risk", cls: "bg-red-100 text-red-800 border border-red-200" };
  if (reqs >= 5) return { label: "Watch", cls: "bg-amber-100 text-amber-800 border border-amber-200" };
  return { label: "On Track", cls: "bg-emerald-100 text-emerald-800 border border-emerald-200" };
}

// ── Create Modal ──────────────────────────────────────────────────────────────
function CreateModal({ onClose, onCreate }: { onClose: () => void; onCreate: (data: any) => Promise<void> }) {
  const [form, setForm] = useState({ title: "", agency: "", inspection_type: "routine", start_date: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) { setError("Title is required"); return; }
    setSaving(true); setError("");
    try {
      await onCreate({ ...form, agency: form.agency || undefined, start_date: form.start_date || undefined });
      onClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail ? `Error: ${detail}` : "Failed to create inspection.");
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-semibold">New Inspection</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Schedule a regulatory inspection event</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
        </div>
        <form onSubmit={submit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Inspection Title *</label>
            <input type="text" placeholder="e.g. FDA Pre-Approval Inspection — Site Alpha"
              value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Agency</label>
              <select value={form.agency} onChange={e => setForm(f => ({ ...f, agency: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                <option value="">Select agency</option>
                {AGENCIES.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Type</label>
              <select value={form.inspection_type} onChange={e => setForm(f => ({ ...f, inspection_type: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
                {INSPECTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Expected Start Date</label>
            <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm border rounded-lg hover:bg-accent">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-60">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              {saving ? "Creating…" : "Create Inspection"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Gantt Timeline ────────────────────────────────────────────────────────────
function InspectionTimeline({ inspections }: { inspections: Inspection[] }) {
  const timelined = inspections.filter(i => i.start_date && (i.status === "active" || i.status === "planned"));
  if (timelined.length < 2) return null;

  const today = new Date();
  const starts = timelined.map(i => new Date(i.start_date!).getTime());
  const ends = timelined.map(i => {
    if (i.end_date) return new Date(i.end_date).getTime();
    return new Date(i.start_date!).getTime() + 5 * 86400000;
  });
  const minT = Math.min(...starts) - 86400000;
  const maxT = Math.max(...ends) + 86400000;
  const span = maxT - minT;

  const pct = (t: number) => Math.min(100, Math.max(0, ((t - minT) / span) * 100));
  const todayPct = pct(today.getTime());

  const BAR_COLORS = [
    "bg-emerald-500", "bg-primary", "bg-amber-500", "bg-blue-500", "bg-rose-500",
  ];

  return (
    <div className="bg-card border rounded-xl p-5">
      <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
        <Activity className="w-4 h-4 text-primary" /> Today&apos;s Inspection Timeline
      </h3>
      <div className="space-y-2.5">
        {timelined.map((insp, idx) => {
          const startPct = pct(new Date(insp.start_date!).getTime());
          const endT = insp.end_date ? new Date(insp.end_date).getTime() : new Date(insp.start_date!).getTime() + 5 * 86400000;
          const widthPct = Math.max(2, pct(endT) - startPct);
          return (
            <div key={insp.id} className="flex items-center gap-3">
              <span className="text-[11px] text-muted-foreground w-28 truncate flex-shrink-0 text-right">
                {insp.agency ?? insp.title.split(" ")[0]}
              </span>
              <div className="flex-1 relative h-6 bg-muted/30 rounded-full overflow-hidden">
                <div
                  className={`absolute top-0 h-full rounded-full ${BAR_COLORS[idx % BAR_COLORS.length]} opacity-80 flex items-center px-2`}
                  style={{ left: `${startPct}%`, width: `${widthPct}%` }}
                >
                  {widthPct > 8 && (
                    <span className="text-[10px] text-white font-medium truncate">
                      {insp.status === "active" ? `Day ${dayNumber(insp.start_date)}` : typeLabel(insp.inspection_type)}
                    </span>
                  )}
                </div>
                {/* Today marker */}
                <div className="absolute top-0 bottom-0 w-0.5 bg-foreground/40 z-10" style={{ left: `${todayPct}%` }} />
              </div>
            </div>
          );
        })}
        {/* Time axis labels */}
        <div className="flex items-center gap-3 mt-1">
          <span className="w-28 flex-shrink-0" />
          <div className="flex-1 flex justify-between">
            <span className="text-[10px] text-muted-foreground">{new Date(minT).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
            <span className="text-[10px] text-primary font-medium">Today</span>
            <span className="text-[10px] text-muted-foreground">{new Date(maxT).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function InspectionsPage() {
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("active");
  const [showCreate, setShowCreate] = useState(false);

  const load = async (status = statusFilter) => {
    setLoading(true);
    try {
      // Load all for portfolio health, then filter client-side for tab view
      const res = await inspectionsApi.list(undefined);
      setInspections(res.data.inspections ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (data: any) => {
    await inspectionsApi.create(data);
    load();
  };

  // ── Derived data ────────────────────────────────────────────────────────────
  const active = useMemo(() => inspections.filter(i => i.status === "active"), [inspections]);
  const planned = useMemo(() => inspections.filter(i => i.status === "planned"), [inspections]);
  const post = useMemo(() => inspections.filter(i => i.status === "post_inspection"), [inspections]);

  const totalOpenRequests = useMemo(() => active.reduce((s, i) => s + i.total_requests, 0), [active]);

  const portfolioHealth = useMemo((): "at_risk" | "watch" | "on_track" => {
    if (active.some(i => i.total_requests >= 10)) return "at_risk";
    if (active.some(i => i.total_requests >= 5) || active.length > 1) return "watch";
    return "on_track";
  }, [active]);

  const attentionItems = useMemo(() => {
    const items: { icon: any; color: string; text: string; link?: string }[] = [];
    active.forEach(i => {
      if (i.total_requests >= 5)
        items.push({ icon: AlertTriangle, color: "text-red-600", text: `${i.total_requests} open requests in "${i.title}"`, link: `/inspections/${i.id}` });
    });
    if (active.length > 1)
      items.push({ icon: AlertCircle, color: "text-amber-600", text: `${active.length} concurrent active inspections — verify SME availability` });
    planned.forEach(i => {
      const d = daysUntil(i.start_date);
      if (d !== null && d <= 7 && d >= 0)
        items.push({ icon: Calendar, color: "text-blue-600", text: `"${i.title}" starts in ${d === 0 ? "today" : `${d} day${d !== 1 ? "s" : ""}`} — confirm team assignments`, link: `/inspections/${i.id}` });
    });
    post.forEach(i => {
      items.push({ icon: Clock, color: "text-purple-600", text: `"${i.title}" in post-inspection — check 483 response deadline`, link: `/inspections/${i.id}` });
    });
    if (items.length === 0 && active.length > 0)
      items.push({ icon: CheckCircle2, color: "text-emerald-600", text: `${active.length} active inspection${active.length > 1 ? "s" : ""} — all requests within SLA` });
    if (items.length === 0 && active.length === 0)
      items.push({ icon: CheckCircle2, color: "text-emerald-600", text: "No active inspections. Use this time to run readiness assessments." });
    return items;
  }, [active, planned, post]);

  const resourceConflicts = useMemo(() => {
    const items: { color: string; text: string }[] = [];
    if (active.length > 1)
      items.push({ color: "text-amber-600", text: `${active.length} active inspections — ensure SMEs are not double-booked` });
    active.forEach(i => {
      if (i.total_requests >= 8)
        items.push({ color: "text-red-600", text: `High request volume in "${i.title.length > 30 ? i.title.slice(0, 30) + "…" : i.title}" — consider additional reviewers` });
    });
    if (post.length > 0)
      items.push({ color: "text-purple-600", text: `${post.length} post-inspection ${post.length > 1 ? "inspections" : "inspection"} with pending commitments` });
    return items;
  }, [active, post]);

  // Tab-filtered view
  const displayedInspections = useMemo(() =>
    statusFilter === "" ? inspections : inspections.filter(i => i.status === statusFilter),
  [inspections, statusFilter]);

  const HEALTH_STYLES = {
    at_risk: { label: "AT RISK", cls: "bg-red-100 border-red-300 text-red-800" },
    watch:   { label: "WATCH",   cls: "bg-amber-100 border-amber-300 text-amber-800" },
    on_track:{ label: "ON TRACK",cls: "bg-emerald-100 border-emerald-300 text-emerald-800" },
  };
  const ph = HEALTH_STYLES[portfolioHealth];

  return (
    <div className="space-y-5">
      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreate={handleCreate} />}

      {/* Header — minimal */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold tracking-tight">Inspections</h1>
        <div className="flex items-center gap-2">
          <button onClick={() => load()} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
            <Plus className="w-4 h-4" /> New Inspection
          </button>
        </div>
      </div>

      {inspections.length > 0 && (
        <>
          {/* ── Portfolio Health Strip ──────────────────────────────────────── */}
          <div className="bg-card border rounded-xl px-5 py-3.5 flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2.5">
              <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full border ${ph.cls}`}>
                {ph.label}
              </span>
              <span className="text-xs text-muted-foreground">
                {active.length > 0
                  ? `${active.length} active · ${planned.length} planned · ${post.length} post-inspection`
                  : `${planned.length} upcoming · ${post.length} post-inspection`}
              </span>
            </div>
            <div className="flex items-center gap-1.5 ml-auto flex-wrap">
              {[
                { label: "Live", value: active.length, cls: active.length > 0 ? "bg-emerald-100 text-emerald-800 border-emerald-200" : "bg-muted text-muted-foreground border-border", dot: active.length > 0 },
                { label: "Open Requests", value: totalOpenRequests, cls: totalOpenRequests > 0 ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-muted text-muted-foreground border-border", dot: false },
                { label: "Upcoming", value: planned.length, cls: "bg-blue-50 text-blue-800 border-blue-200", dot: false },
                { label: "Post-Inspection", value: post.length, cls: post.length > 0 ? "bg-purple-50 text-purple-800 border-purple-200" : "bg-muted text-muted-foreground border-border", dot: false },
              ].map(chip => (
                <span key={chip.label} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-semibold ${chip.cls}`}>
                  {chip.dot && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />}
                  <span className="font-bold">{chip.value}</span>
                  <span className="font-medium opacity-70">{chip.label}</span>
                </span>
              ))}
            </div>
          </div>

          {/* ── Attention + Conflicts ─────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            {/* Needs My Attention — 3 cols */}
            <div className="lg:col-span-3 bg-card border rounded-xl p-5">
              <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-primary" /> Needs Attention
              </h3>
              <div className="space-y-2.5">
                {attentionItems.map((item, i) => {
                  const Icon = item.icon;
                  const inner = (
                    <div className="flex items-start gap-2.5 text-sm">
                      <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${item.color}`} />
                      <span className={item.link ? "hover:underline" : ""}>{item.text}</span>
                      {item.link && <ChevronRight className="w-3.5 h-3.5 ml-auto text-muted-foreground flex-shrink-0 mt-0.5" />}
                    </div>
                  );
                  return item.link
                    ? <Link key={i} href={item.link} className="block hover:bg-muted/30 rounded-lg px-2 py-1.5 -mx-2 transition-colors">{inner}</Link>
                    : <div key={i} className="px-2 py-1.5">{inner}</div>;
                })}
              </div>
            </div>

            {/* Resource Conflicts — 2 cols */}
            <div className="lg:col-span-2 bg-card border rounded-xl p-5">
              <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
                <Users className="w-4 h-4 text-amber-500" /> Resource Signals
              </h3>
              {resourceConflicts.length > 0 ? (
                <div className="space-y-2.5">
                  {resourceConflicts.map((c, i) => (
                    <div key={i} className="flex items-start gap-2.5">
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5 ${
                        c.color === "text-red-600" ? "bg-red-500" : c.color === "text-amber-600" ? "bg-amber-500" : "bg-purple-500"
                      }`} />
                      <span className="text-xs text-muted-foreground leading-relaxed">{c.text}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                  No resource conflicts detected
                </p>
              )}
            </div>
          </div>

          {/* ── Gantt Timeline (multi-inspection only) ───────────────────── */}
          <InspectionTimeline inspections={inspections} />
        </>
      )}

      {/* ── Status Filter Tabs ──────────────────────────────────────────────── */}
      <div className="flex border-b">
        {STATUS_TABS.map(t => (
          <button key={t.key} onClick={() => setStatusFilter(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${
              statusFilter === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {t.label}
            {t.key === "active" && active.length > 0 && (
              <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded-full">{active.length}</span>
            )}
            {t.key === "planned" && planned.length > 0 && (
              <span className="text-[10px] font-bold bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded-full">{planned.length}</span>
            )}
            {t.key === "post_inspection" && post.length > 0 && (
              <span className="text-[10px] font-bold bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded-full">{post.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Inspection Portfolio Table ──────────────────────────────────────── */}
      {loading ? (
        <div className="bg-card border rounded-xl divide-y">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex items-center gap-4 px-5 py-4 animate-pulse">
              <div className="w-3 h-3 bg-muted rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-muted rounded w-2/3" />
                <div className="h-3 bg-muted rounded w-1/3" />
              </div>
              <div className="w-20 h-5 bg-muted rounded-full" />
            </div>
          ))}
        </div>
      ) : displayedInspections.length === 0 ? (
        inspections.length === 0 ? (
          <EmptyState
            icon={Radio}
            title="No inspections yet"
            description="Create your first inspection to begin managing audit activities."
            action={
              <button onClick={() => setShowCreate(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                <Plus className="w-4 h-4" /> New Inspection
              </button>
            }
          />
        ) : (
          <div className="bg-card border rounded-xl px-8 py-10 text-center">
            <p className="text-sm text-muted-foreground">No {STATUS_TABS.find(t => t.key === statusFilter)?.label.toLowerCase()} inspections.</p>
          </div>
        )
      ) : (
        <div className="bg-card border rounded-xl overflow-hidden">
          {/* Table header */}
          <div className="hidden md:grid grid-cols-[2fr_1fr_80px_100px_80px_1fr] gap-4 px-5 py-2.5 border-b bg-muted/20 text-[10px] font-bold text-muted-foreground uppercase tracking-wide">
            <span>Inspection</span>
            <span>Phase / Status</span>
            <span>Day</span>
            <span>Health</span>
            <span>Requests</span>
            <span>Action</span>
          </div>

          <div className="divide-y">
            {displayedInspections.map(insp => {
              const hb = healthBadge(insp);
              const dayNum = dayNumber(insp.start_date);
              const phase = PHASE_LABELS[insp.current_phase ?? ""] ?? null;

              return (
                <div key={insp.id} className="grid grid-cols-1 md:grid-cols-[2fr_1fr_80px_100px_80px_1fr] gap-4 px-5 py-4 items-center hover:bg-muted/20 transition-colors">
                  {/* Inspection info */}
                  <div className="flex items-start gap-3 min-w-0">
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1.5 ${
                      insp.status === "active" ? "bg-emerald-500 shadow-sm shadow-emerald-400" :
                      insp.status === "planned" ? "bg-blue-400" :
                      insp.status === "post_inspection" ? "bg-purple-400" : "bg-muted-foreground/40"
                    }`} />
                    <div className="min-w-0">
                      <p className="font-semibold text-sm truncate">{insp.title}</p>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        {insp.agency && (
                          <span className="text-[11px] font-medium text-primary">{insp.agency}</span>
                        )}
                        <span className="text-[11px] text-muted-foreground">{typeLabel(insp.inspection_type)}</span>
                        {insp.site_name && (
                          <span className="text-[11px] text-muted-foreground flex items-center gap-0.5">
                            <MapPin className="w-2.5 h-2.5" />{insp.site_name}
                          </span>
                        )}
                        {insp.mode === "remote" && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded">Remote</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Phase */}
                  <div>
                    {insp.status === "active" && phase ? (
                      <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">{phase}</span>
                    ) : (
                      <InspStatusBadge status={insp.status} />
                    )}
                    {insp.status === "planned" && insp.start_date && (
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {(() => {
                          const d = daysUntil(insp.start_date);
                          return d === null ? "" : d === 0 ? "Starts today" : d > 0 ? `In ${d}d` : `${Math.abs(d)}d ago`;
                        })()}
                      </p>
                    )}
                  </div>

                  {/* Day */}
                  <div>
                    {insp.status === "active" ? (
                      <span className="text-sm font-bold text-foreground">Day {dayNum}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </div>

                  {/* Health */}
                  <div>
                    {insp.status === "active" ? (
                      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${hb.cls}`}>{hb.label}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </div>

                  {/* Requests */}
                  <div>
                    {insp.total_requests > 0 ? (
                      <span className={`text-sm font-bold ${insp.total_requests >= 8 ? "text-red-600" : insp.total_requests >= 4 ? "text-amber-600" : "text-foreground"}`}>
                        {insp.total_requests}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">0</span>
                    )}
                  </div>

                  {/* Action */}
                  <div className="flex items-center gap-2">
                    <Link href={`/inspections/${insp.id}`}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        insp.status === "active"
                          ? "bg-primary text-primary-foreground hover:bg-primary/90"
                          : "border border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                      }`}>
                      {insp.status === "active" ? (
                        <><Radio className="w-3 h-3 animate-pulse" /> War Room</>
                      ) : insp.status === "post_inspection" ? (
                        <><TrendingUp className="w-3 h-3" /> 483 Response</>
                      ) : (
                        <><Eye className="w-3 h-3" /> Open</>
                      )}
                    </Link>
                    {insp.status === "active" && (
                      <ChevronRight className="w-4 h-4 text-muted-foreground hidden lg:block" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

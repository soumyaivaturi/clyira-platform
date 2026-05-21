"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Radio, Plus, Clock, RefreshCw, ChevronRight,
  Loader2, AlertTriangle, Zap, X,
} from "lucide-react";
import { inspectionsApi } from "@/lib/api";
import { InspStatusBadge } from "@/components/shared/badges";
import { EmptyState } from "@/components/shared/empty-state";
import { formatDate } from "@/lib/utils";

interface Inspection {
  id: string;
  title: string;
  agency: string | null;
  inspection_type: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  total_requests: number;
  created_at: string;
}

const INSPECTION_TYPES = [
  { value: "routine", label: "Routine GMP" },
  { value: "for_cause", label: "For Cause" },
  { value: "pre_approval", label: "Pre-Approval (PAI)" },
  { value: "surveillance", label: "Surveillance" },
  { value: "directed", label: "Directed" },
];

const AGENCIES = ["FDA", "EMA", "MHRA", "TGA", "Health Canada", "PMDA", "ANVISA", "WHO", "Other"];

const STATUS_TABS = [
  { key: "", label: "All" },
  { key: "planned", label: "Planned" },
  { key: "active", label: "Active" },
  { key: "post_inspection", label: "Post-Inspection" },
  { key: "closed", label: "Closed" },
];

function CreateModal({ onClose, onCreate }: { onClose: () => void; onCreate: (data: any) => Promise<void> }) {
  const [form, setForm] = useState({ title: "", agency: "", inspection_type: "routine", start_date: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) { setError("Title is required"); return; }
    setSaving(true);
    setError("");
    try {
      await onCreate({ ...form, agency: form.agency || undefined, start_date: form.start_date || undefined });
      onClose();
    } catch {
      setError("Failed to create inspection. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border rounded-2xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-semibold">New Inspection</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Schedule a regulatory inspection event</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={submit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Inspection Title *
            </label>
            <input
              type="text"
              placeholder="e.g. FDA Pre-Approval Inspection — Site Alpha"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Regulatory Agency
              </label>
              <select
                value={form.agency}
                onChange={e => setForm(f => ({ ...f, agency: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              >
                <option value="">Select agency</option>
                {AGENCIES.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                Inspection Type
              </label>
              <select
                value={form.inspection_type}
                onChange={e => setForm(f => ({ ...f, inspection_type: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              >
                {INSPECTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
              Expected Start Date
            </label>
            <input
              type="date"
              value={form.start_date}
              onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm border rounded-lg hover:bg-accent">
              Cancel
            </button>
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

const AI_AGENTS = [
  { key: "scribe", label: "Scribe", desc: "Records observations in real time" },
  { key: "prep_manager", label: "Prep Manager", desc: "Manages document preparation" },
  { key: "sme_coach", label: "SME Coach", desc: "Briefs subject-matter experts" },
  { key: "qa_agent", label: "QA Agent", desc: "Monitors compliance posture" },
  { key: "doc_reviewer", label: "Doc Reviewer", desc: "Retrieves & reviews records" },
];

export default function InspectionsPage() {
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const load = async (status = statusFilter) => {
    setLoading(true);
    try {
      const res = await inspectionsApi.list(status || undefined);
      setInspections(res.data.inspections ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const changeFilter = (s: string) => {
    setStatusFilter(s);
    load(s);
  };

  const handleCreate = async (data: any) => {
    await inspectionsApi.create(data);
    load();
  };

  const activeInsp = inspections.find(i => i.status === "active");

  const typeLabel = (t: string | null) =>
    INSPECTION_TYPES.find(x => x.value === t)?.label ?? t ?? "Inspection";

  return (
    <div className="space-y-6">
      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreate={handleCreate} />}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Real-Time Audit Support</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage live inspections with AI-powered collaboration and response tracking
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => load()} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
            <Plus className="w-4 h-4" />
            New Inspection
          </button>
        </div>
      </div>

      {/* Active Inspection Banner */}
      {activeInsp && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3 flex-shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
            </span>
            <div>
              <p className="font-semibold text-sm text-emerald-900">{activeInsp.title}</p>
              <p className="text-xs text-emerald-700 mt-0.5">
                {activeInsp.agency && `${activeInsp.agency} · `}
                {typeLabel(activeInsp.inspection_type)} ·{" "}
                {activeInsp.total_requests} request{activeInsp.total_requests !== 1 ? "s" : ""} logged ·{" "}
                5 AI agents active
              </p>
            </div>
          </div>
          <Link
            href={`/inspections/${activeInsp.id}`}
            className="flex-shrink-0 flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors">
            Enter War Room
            <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      )}

      {/* AI Agents Panel */}
      <div className="bg-card border rounded-xl p-5">
        <h2 className="font-semibold text-sm flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-primary" />
          AI Agents
          <span className="text-xs text-muted-foreground font-normal ml-1">
            {activeInsp ? "Active during live inspection" : "Standby — activate an inspection to engage"}
          </span>
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {AI_AGENTS.map(agent => (
            <div key={agent.key}
              className={`rounded-lg border p-3 transition-colors ${
                activeInsp
                  ? "bg-emerald-50 border-emerald-200"
                  : "bg-muted/30 border-border"
              }`}>
              <div className="flex items-center gap-1.5 mb-1.5">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  activeInsp ? "bg-emerald-500" : "bg-muted-foreground/40"
                }`} />
                <span className="text-xs font-semibold">{agent.label}</span>
              </div>
              <p className="text-[10px] text-muted-foreground leading-relaxed">{agent.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex border-b gap-1">
        {STATUS_TABS.map(t => (
          <button key={t.key} onClick={() => changeFilter(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              statusFilter === t.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Inspections List */}
      <div className="bg-card border rounded-xl overflow-hidden">
        {loading ? (
          <div className="divide-y">
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-4 px-5 py-4 animate-pulse">
                <div className="w-10 h-10 bg-muted rounded-lg flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-muted rounded w-2/3" />
                  <div className="h-3 bg-muted rounded w-1/3" />
                </div>
                <div className="w-24 h-5 bg-muted rounded-full" />
              </div>
            ))}
          </div>
        ) : inspections.length === 0 ? (
          <EmptyState
            icon={Radio}
            title="No inspections yet"
            description="Create your first inspection to begin managing audit activities with AI support."
            action={
              <button onClick={() => setShowCreate(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
                <Plus className="w-4 h-4" />
                New Inspection
              </button>
            }
          />
        ) : (
          <div className="divide-y">
            {inspections.map(insp => (
              <Link
                key={insp.id}
                href={`/inspections/${insp.id}`}
                className="flex items-center gap-4 px-5 py-4 hover:bg-muted/30 transition-colors"
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  insp.status === "active" ? "bg-emerald-100" : "bg-primary/10"
                }`}>
                  <Radio className={`w-5 h-5 ${insp.status === "active" ? "text-emerald-600" : "text-primary"}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">{insp.title}</p>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    {insp.agency && (
                      <span className="text-xs font-medium text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                        {insp.agency}
                      </span>
                    )}
                    {insp.inspection_type && (
                      <span className="text-xs text-muted-foreground">{typeLabel(insp.inspection_type)}</span>
                    )}
                    {insp.start_date && (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(insp.start_date)}
                      </span>
                    )}
                    {insp.total_requests > 0 && (
                      <span className="text-xs text-amber-700 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        {insp.total_requests} request{insp.total_requests !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <InspStatusBadge status={insp.status} />
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

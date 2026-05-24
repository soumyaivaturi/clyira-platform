"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  ClipboardList, RefreshCw, ChevronRight, Loader2, Filter, X,
  FileText, Shield, Search, CheckCircle2, Clock, AlertTriangle,
  MessageSquare, Upload, Play, Flag,
} from "lucide-react";
import { auditApi } from "@/lib/api";
import { timeAgo, formatDate } from "@/lib/utils";

interface AuditEvent {
  id: string;
  event_type: string;
  resource_type: string;
  resource_id: string;
  resource_label?: string;
  user_email?: string;
  detail?: Record<string, any>;
  created_at: string;
}

const EVENT_TYPE_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  document_uploaded:      { label: "Document Uploaded",     color: "text-blue-700 bg-blue-50 border-blue-200",    icon: Upload },
  assessment_triggered:   { label: "Assessment Started",    color: "text-primary bg-primary/10 border-primary/20", icon: Play },
  assessment_completed:   { label: "Assessment Completed",  color: "text-emerald-700 bg-emerald-50 border-emerald-200", icon: CheckCircle2 },
  finding_resolved:       { label: "Finding Resolved",      color: "text-emerald-700 bg-emerald-50 border-emerald-200", icon: CheckCircle2 },
  finding_in_progress:    { label: "Finding In Progress",   color: "text-blue-700 bg-blue-50 border-blue-200",    icon: Clock },
  finding_acknowledged:   { label: "Finding Acknowledged",  color: "text-amber-700 bg-amber-50 border-amber-200", icon: Flag },
  finding_disputed:       { label: "Finding Disputed",      color: "text-orange-700 bg-orange-50 border-orange-200", icon: AlertTriangle },
  mock_inspection_run:    { label: "Mock Inspection",       color: "text-purple-700 bg-purple-50 border-purple-200", icon: Shield },
  company_updated:        { label: "Company Profile Updated", color: "text-muted-foreground bg-muted border-border", icon: FileText },
};

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  document:   "Document",
  assessment: "Assessment",
  finding:    "Finding",
  company:    "Company",
  inspection: "Inspection",
};

const EVENT_FILTERS = [
  { value: "", label: "All Events" },
  { value: "assessment_completed", label: "Assessments" },
  { value: "finding_resolved", label: "Findings Resolved" },
  { value: "finding_disputed", label: "Findings Disputed" },
  { value: "document_uploaded", label: "Uploads" },
  { value: "mock_inspection_run", label: "Mock Inspections" },
];

function EventRow({ event }: { event: AuditEvent }) {
  const cfg = EVENT_TYPE_CONFIG[event.event_type] ?? {
    label: event.event_type.replace(/_/g, " "),
    color: "text-muted-foreground bg-muted border-border",
    icon: ClipboardList,
  };
  const Icon = cfg.icon;

  const detailSnippet = () => {
    if (!event.detail) return null;
    const d = event.detail;
    const parts: string[] = [];
    if (d.adjusted_score != null) parts.push(`Score: ${d.adjusted_score.toFixed(1)}`);
    if (d.from_status && d.to_status) parts.push(`${d.from_status} → ${d.to_status}`);
    if (d.findings_critical || d.findings_high) {
      parts.push(`${d.findings_critical ?? 0} critical, ${d.findings_high ?? 0} high`);
    }
    return parts.join(" · ") || null;
  };

  const snippet = detailSnippet();
  const resourceHref = event.resource_type === "document"
    ? `/documents/${event.resource_id}`
    : event.resource_type === "assessment"
    ? null
    : null;

  return (
    <div className="flex items-start gap-4 px-5 py-3.5 hover:bg-muted/20 transition-colors">
      <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-muted/50 border mt-0.5">
        <Icon className="w-3.5 h-3.5 text-muted-foreground" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${cfg.color}`}>
            {cfg.label}
          </span>
          {event.resource_type && (
            <span className="text-[10px] text-muted-foreground">
              {RESOURCE_TYPE_LABELS[event.resource_type] ?? event.resource_type}
            </span>
          )}
        </div>

        {event.resource_label && (
          <p className="text-sm font-medium text-foreground truncate">
            {resourceHref ? (
              <Link href={resourceHref} className="hover:text-primary hover:underline">
                {event.resource_label}
              </Link>
            ) : (
              event.resource_label
            )}
          </p>
        )}

        {snippet && (
          <p className="text-xs text-muted-foreground mt-0.5">{snippet}</p>
        )}
      </div>

      <div className="flex-shrink-0 text-right">
        <p className="text-xs text-muted-foreground">{timeAgo(event.created_at)}</p>
        {event.user_email && (
          <p className="text-[10px] text-muted-foreground/60 mt-0.5">{event.user_email}</p>
        )}
      </div>
    </div>
  );
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  const load = useCallback(async (p = page) => {
    setLoading(true);
    try {
      const res = await auditApi.getLog({
        event_type: eventFilter || undefined,
        limit: PAGE_SIZE,
        offset: p * PAGE_SIZE,
      });
      setEvents(res.data.events ?? []);
    } finally {
      setLoading(false);
    }
  }, [eventFilter, page]);

  useEffect(() => {
    setPage(0);
    load(0);
  }, [eventFilter]);

  const filtered = search
    ? events.filter(e =>
        (e.resource_label ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (e.user_email ?? "").toLowerCase().includes(search.toLowerCase()) ||
        e.event_type.toLowerCase().includes(search.toLowerCase())
      )
    : events;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Audit Trail</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Immutable GxP activity log — assessments, finding actions, and quality events
          </p>
        </div>
        <button onClick={() => load()} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Filter by resource or user…"
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20" />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {EVENT_FILTERS.map(f => (
            <button key={f.value} onClick={() => setEventFilter(f.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                eventFilter === f.value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background border-border text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}>
              {f.label}
            </button>
          ))}
        </div>
        {(search || eventFilter) && (
          <button onClick={() => { setSearch(""); setEventFilter(""); }}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <X className="w-3 h-3" /> Clear
          </button>
        )}
      </div>

      {/* GxP compliance note */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-800 flex items-start gap-2">
        <Shield className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600" />
        <span>
          This audit trail is immutable and GxP-compliant. All events are timestamped, attributed to
          a user, and cannot be modified or deleted — providing a full chain of custody for regulatory inspections.
        </span>
      </div>

      {/* Events list */}
      <div className="bg-card border rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b bg-muted/30 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Activity Log
          </span>
          <span className="text-xs text-muted-foreground">{filtered.length} event{filtered.length !== 1 ? "s" : ""}</span>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 px-5 py-10 text-sm text-muted-foreground justify-center">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading audit log…
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <ClipboardList className="w-10 h-10 text-muted-foreground/20 mx-auto mb-3" />
            <p className="text-sm font-semibold mb-1">No events found</p>
            <p className="text-xs text-muted-foreground">Quality events will appear here as users work in Clyira.</p>
          </div>
        ) : (
          <div className="divide-y">
            {filtered.map(event => <EventRow key={event.id} event={event} />)}
          </div>
        )}
      </div>

      {/* Pagination */}
      {!loading && events.length === PAGE_SIZE && (
        <div className="flex justify-center">
          <button onClick={() => { const next = page + 1; setPage(next); load(next); }}
            className="px-4 py-2 border rounded-lg text-sm hover:bg-accent flex items-center gap-1.5">
            Load More
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Bell, X, Lock, Zap, Clock, AlertTriangle, CheckCircle2, ChevronRight,
} from "lucide-react";
import { notificationsApi } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

interface Alert {
  id: string;
  type: string;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  message: string;
  document_id?: string | null;
  assessment_id?: string | null;
  finding_id?: string | null;
  created_at?: string | null;
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: "text-red-700 bg-red-50 border-red-200",
  high: "text-amber-700 bg-amber-50 border-amber-200",
  medium: "text-blue-700 bg-blue-50 border-blue-200",
  low: "text-muted-foreground bg-muted border-border",
};

const TYPE_ICON: Record<string, any> = {
  data_integrity_hold: Lock,
  open_critical_finding: AlertTriangle,
  enforcement_match: Zap,
  overdue_review: Clock,
  open_high_findings: AlertTriangle,
};

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [criticalCount, setCriticalCount] = useState(0);
  const [highCount, setHighCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [lastLoaded, setLastLoaded] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const load = async () => {
    if (Date.now() - lastLoaded < 30_000) return; // 30s cache
    setLoading(true);
    try {
      const res = await notificationsApi.alerts();
      setAlerts(res.data.alerts ?? []);
      setCriticalCount(res.data.critical_count ?? 0);
      setHighCount(res.data.high_count ?? 0);
      setLastLoaded(Date.now());
    } catch {
      // silently fail — notifications are non-critical
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const badgeCount = criticalCount + highCount;
  const href = (alert: Alert) => {
    if (alert.document_id) return `/documents/${alert.document_id}`;
    return null;
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => { setOpen(!open); if (!open) load(); }}
        className="relative p-2 rounded-md hover:bg-accent"
        title="Quality Alerts"
      >
        <Bell className="w-5 h-5 text-muted-foreground" />
        {badgeCount > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center leading-none">
            {badgeCount > 9 ? "9+" : badgeCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 bg-card border rounded-xl shadow-lg z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
            <div>
              <p className="text-sm font-semibold">Quality Alerts</p>
              {!loading && (
                <p className="text-xs text-muted-foreground">
                  {alerts.length === 0 ? "No active alerts" : `${alerts.length} alert${alerts.length !== 1 ? "s" : ""} · ${criticalCount} critical`}
                </p>
              )}
            </div>
            <button onClick={() => setOpen(false)} className="p-1 rounded hover:bg-accent">
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>

          {/* Alert list */}
          <div className="max-h-[420px] overflow-y-auto divide-y">
            {loading ? (
              <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                Loading alerts…
              </div>
            ) : alerts.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                <p className="text-sm font-medium">All clear</p>
                <p className="text-xs text-muted-foreground mt-0.5">No active quality alerts.</p>
              </div>
            ) : (
              alerts.map((alert) => {
                const Icon = TYPE_ICON[alert.type] ?? Bell;
                const link = href(alert);
                const content = (
                  <div className="flex items-start gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border mt-0.5 ${SEVERITY_STYLES[alert.severity]}`}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-foreground leading-tight">{alert.title}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{alert.message}</p>
                      {alert.created_at && (
                        <p className="text-[10px] text-muted-foreground/60 mt-1">{timeAgo(alert.created_at)}</p>
                      )}
                    </div>
                    {link && <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 mt-1" />}
                  </div>
                );
                return link ? (
                  <Link key={alert.id} href={link} onClick={() => setOpen(false)}>
                    {content}
                  </Link>
                ) : (
                  <div key={alert.id}>{content}</div>
                );
              })
            )}
          </div>

          {/* Footer */}
          {alerts.length > 0 && (
            <div className="px-4 py-2.5 border-t bg-muted/20">
              <Link
                href="/readiness"
                onClick={() => setOpen(false)}
                className="text-xs text-primary hover:underline flex items-center justify-center gap-1"
              >
                View full readiness report <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

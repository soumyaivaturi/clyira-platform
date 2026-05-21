"use client";

import { cn, getSeverityConfig } from "@/lib/utils";

// ── Severity Badge ────────────────────────────────────────────────────────────

interface SeverityBadgeProps {
  severity: string;
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const cfg = getSeverityConfig(severity);
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border",
      cfg.color, cfg.bg, cfg.border, className
    )}>
      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", cfg.dot)} />
      {cfg.label}
    </span>
  );
}

// ── Level Badge ───────────────────────────────────────────────────────────────

const LEVEL_LABELS: Record<string, string> = {
  L1: "L1 Structure",
  L2: "L2 Doc Control",
  L3: "L3 Content",
  L4: "L4 ALCOA+",
  L5: "L5 Data Intel",
  L6: "L6 Cross-Doc",
  L7: "L7 Lifecycle",
  L8: "L8 Reg Gap",
  L9: "L9 Enforcement",
  L10: "L10 Longitudinal",
  L11: "L11 Submission",
};

interface LevelBadgeProps {
  level: string;
  compact?: boolean;
  className?: string;
}

export function LevelBadge({ level, compact = false, className }: LevelBadgeProps) {
  return (
    <span className={cn(
      "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-clyira-50 text-clyira-700 border border-clyira-200",
      className
    )}>
      {compact ? level : (LEVEL_LABELS[level] ?? level)}
    </span>
  );
}

// ── Document Status Badge ─────────────────────────────────────────────────────

const DOC_STATUS: Record<string, { label: string; cls: string }> = {
  uploaded:    { label: "Uploaded",    cls: "bg-gray-100 text-gray-600 border-gray-200" },
  processing:  { label: "Processing",  cls: "bg-blue-50 text-blue-700 border-blue-200" },
  ready:       { label: "Ready",       cls: "bg-blue-50 text-blue-700 border-blue-200" },
  assessed:    { label: "Assessed",    cls: "bg-green-50 text-green-700 border-green-200" },
  reviewing:   { label: "In Review",   cls: "bg-amber-50 text-amber-700 border-amber-200" },
  approved:    { label: "Approved",    cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  archived:    { label: "Archived",    cls: "bg-gray-50 text-gray-500 border-gray-200" },
};

export function DocStatusBadge({ status, className }: { status: string; className?: string }) {
  const cfg = DOC_STATUS[status] ?? { label: status, cls: "bg-gray-100 text-gray-600 border-gray-200" };
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border", cfg.cls, className)}>
      {cfg.label}
    </span>
  );
}

// ── Inspection Status Badge ───────────────────────────────────────────────────

const INSP_STATUS: Record<string, { label: string; cls: string; dot?: string }> = {
  planned:         { label: "Planned",         cls: "bg-blue-50 text-blue-700 border-blue-200",      dot: "bg-blue-500" },
  active:          { label: "Active",           cls: "bg-green-50 text-green-700 border-green-200",   dot: "bg-green-500 animate-pulse" },
  post_inspection: { label: "Post-Inspection",  cls: "bg-amber-50 text-amber-700 border-amber-200",   dot: "bg-amber-500" },
  closed:          { label: "Closed",           cls: "bg-gray-50 text-gray-500 border-gray-200",      dot: "bg-gray-400" },
};

export function InspStatusBadge({ status, className }: { status: string; className?: string }) {
  const cfg = INSP_STATUS[status] ?? { label: status, cls: "bg-gray-100 text-gray-600 border-gray-200" };
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border", cfg.cls, className)}>
      {cfg.dot && <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", cfg.dot)} />}
      {cfg.label}
    </span>
  );
}

// ── Finding Status Badge ──────────────────────────────────────────────────────

const FINDING_STATUS: Record<string, { label: string; cls: string }> = {
  open:          { label: "Open",        cls: "bg-red-50 text-red-700 border-red-200" },
  acknowledged:  { label: "Acknowledged", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  in_progress:   { label: "In Progress", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  resolved:      { label: "Resolved",    cls: "bg-green-50 text-green-700 border-green-200" },
  disputed:      { label: "Disputed",    cls: "bg-purple-50 text-purple-700 border-purple-200" },
};

export function FindingStatusBadge({ status, className }: { status: string; className?: string }) {
  const cfg = FINDING_STATUS[status] ?? { label: status, cls: "bg-gray-100 text-gray-600 border-gray-200" };
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border", cfg.cls, className)}>
      {cfg.label}
    </span>
  );
}

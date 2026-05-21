import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ── Score helpers ─────────────────────────────────────────────────────────────

export function getScoreBand(score: number): "Excellent" | "Good" | "Moderate" | "Poor" | "Critical" {
  if (score >= 90) return "Excellent";
  if (score >= 80) return "Good";
  if (score >= 65) return "Moderate";
  if (score >= 50) return "Poor";
  return "Critical";
}

export function getScoreColor(score: number) {
  if (score >= 90) return { text: "text-score-excellent", bg: "bg-score-excellent", light: "bg-score-excellent/10 text-score-excellent" };
  if (score >= 80) return { text: "text-score-good", bg: "bg-score-good", light: "bg-score-good/10 text-score-good" };
  if (score >= 65) return { text: "text-score-moderate", bg: "bg-score-moderate", light: "bg-score-moderate/10 text-score-moderate" };
  if (score >= 50) return { text: "text-score-poor", bg: "bg-score-poor", light: "bg-score-poor/10 text-score-poor" };
  return { text: "text-score-critical", bg: "bg-score-critical", light: "bg-score-critical/10 text-score-critical" };
}

// ── Severity helpers ──────────────────────────────────────────────────────────

type Severity = "critical" | "high" | "medium" | "low" | "info";

export const SEVERITY_CONFIG: Record<Severity, { label: string; color: string; border: string; bg: string; dot: string }> = {
  critical: { label: "Critical",  color: "text-red-700",    border: "border-red-200",    bg: "bg-red-50",    dot: "bg-red-600" },
  high:     { label: "High",      color: "text-orange-700", border: "border-orange-200", bg: "bg-orange-50", dot: "bg-orange-500" },
  medium:   { label: "Medium",    color: "text-amber-700",  border: "border-amber-200",  bg: "bg-amber-50",  dot: "bg-amber-500" },
  low:      { label: "Low",       color: "text-blue-700",   border: "border-blue-200",   bg: "bg-blue-50",   dot: "bg-blue-500" },
  info:     { label: "Info",      color: "text-gray-600",   border: "border-gray-200",   bg: "bg-gray-50",   dot: "bg-gray-400" },
};

export function getSeverityConfig(severity: string) {
  return SEVERITY_CONFIG[severity as Severity] ?? SEVERITY_CONFIG.info;
}

// ── Date helpers ──────────────────────────────────────────────────────────────

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return dateStr;
  }
}

export function timeAgo(dateStr?: string | null): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ── Misc ──────────────────────────────────────────────────────────────────────

export function formatFileSize(bytes?: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

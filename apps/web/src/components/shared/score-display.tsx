"use client";

import { cn, getScoreColor, getScoreBand } from "@/lib/utils";

interface ScoreRingProps {
  score: number | null | undefined;
  size?: "sm" | "md" | "lg";
  showBand?: boolean;
  className?: string;
}

export function ScoreRing({ score, size = "md", showBand = true, className }: ScoreRingProps) {
  if (score == null) {
    return (
      <div className={cn("flex flex-col items-center gap-1", className)}>
        <div className={cn(
          "rounded-full border-4 border-border flex items-center justify-center bg-muted/30",
          size === "sm" && "w-14 h-14",
          size === "md" && "w-20 h-20",
          size === "lg" && "w-28 h-28",
        )}>
          <span className={cn("font-bold text-muted-foreground/50", size === "sm" && "text-base", size === "md" && "text-xl", size === "lg" && "text-3xl")}>—</span>
        </div>
        {showBand && <span className="text-xs text-muted-foreground">Not assessed</span>}
      </div>
    );
  }

  const colors = getScoreColor(score);
  const band = getScoreBand(score);

  return (
    <div className={cn("flex flex-col items-center gap-1", className)}>
      <div className={cn(
        "rounded-full border-4 flex items-center justify-center",
        size === "sm" && "w-14 h-14 border-[3px]",
        size === "md" && "w-20 h-20 border-4",
        size === "lg" && "w-28 h-28 border-[5px]",
        colors.bg + "/20",
        `border-[${colors.bg}]`,
      )}
        style={{ borderColor: getBandHex(band) }}
      >
        <span className={cn(
          "font-bold tabular-nums",
          colors.text,
          size === "sm" && "text-sm",
          size === "md" && "text-xl",
          size === "lg" && "text-3xl",
        )}>
          {score.toFixed(1)}
        </span>
      </div>
      {showBand && (
        <span className={cn("text-xs font-medium", colors.text)}>{band}</span>
      )}
    </div>
  );
}

function getBandHex(band: string) {
  const map: Record<string, string> = {
    Excellent: "#10b981",
    Good: "#34d399",
    Moderate: "#f59e0b",
    Poor: "#ef4444",
    Critical: "#991b1b",
  };
  return map[band] ?? "#94a3b8";
}

interface ScoreBarProps {
  score: number | null | undefined;
  label?: string;
  weight?: number;
  trend?: number;
  className?: string;
}

export function ScoreBar({ score, label, weight, trend, className }: ScoreBarProps) {
  const colors = score != null ? getScoreColor(score) : null;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      {label && <div className="w-36 text-sm font-medium truncate flex-shrink-0">{label}</div>}
      <div className="flex-1 h-7 bg-muted rounded relative overflow-hidden">
        {score != null && (
          <div
            className="h-full rounded transition-all duration-500"
            style={{ width: `${score}%`, backgroundColor: getBandHex(getScoreBand(score)), opacity: 0.75 }}
          />
        )}
        <span className="absolute inset-0 flex items-center px-2.5 text-xs font-semibold">
          {score != null ? score.toFixed(1) : "—"}
        </span>
      </div>
      {trend != null && (
        <span className={cn("text-xs font-medium w-10 text-right flex-shrink-0", trend >= 0 ? "text-score-excellent" : "text-score-poor")}>
          {trend >= 0 ? "+" : ""}{trend.toFixed(1)}
        </span>
      )}
      {weight != null && (
        <span className="text-xs text-muted-foreground w-10 text-right flex-shrink-0">{(weight * 100).toFixed(0)}%</span>
      )}
    </div>
  );
}

interface ScoreBadgeProps {
  score: number | null | undefined;
  className?: string;
}

export function ScoreBadge({ score, className }: ScoreBadgeProps) {
  if (score == null) return <span className="text-xs text-muted-foreground">—</span>;
  const colors = getScoreColor(score);
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold tabular-nums", colors.light, className)}>
      {score.toFixed(1)}
    </span>
  );
}

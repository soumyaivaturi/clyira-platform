"use client";

import { useMemo, useRef, useState, useEffect } from "react";
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, X, BookOpen, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Finding {
  id: string;
  level: string;
  severity: string;
  title: string;
  description: string;
  evidence?: string;
  location?: string;
  regulatory_citation?: string;
  citation_type?: string;
  enforcement_match: boolean;
  enforcement_context?: string;
  severity_elevated: boolean;
  suggestion_draft?: string;
}

interface Section {
  title: string;
  body: string;
  charStart: number;
  charEnd: number;
  findings: Finding[];
}

interface Props {
  documentText: string;
  fileType?: string;
  findings: Finding[];
}

// ── Section detection ─────────────────────────────────────────────────────────

const HEADING_PATTERNS = [
  /^#{1,3}\s+(.+)$/,                          // Markdown headings
  /^([A-Z][A-Z\s\-\/]{3,60})$/,              // ALL CAPS lines
  /^(\d+[\.\d]*\.?\s+[A-Z].{3,60})$/,        // Numbered: "1. Section Name"
  /^([A-Z][a-z].{4,60}):?\s*$/,              // Title Case short line
];

function isHeading(line: string): boolean {
  const t = line.trim();
  if (!t || t.length > 80 || t.length < 3) return false;
  if (t.endsWith(".") && t.split(" ").length > 6) return false; // sentence, not heading
  return HEADING_PATTERNS.some((re) => re.test(t));
}

function detectSections(text: string): Section[] {
  const lines = text.split("\n");
  const sections: Omit<Section, "findings">[] = [];
  let currentTitle = "Document";
  let currentBody = "";
  let currentStart = 0;
  let charOffset = 0;

  for (const line of lines) {
    const lineLen = line.length + 1; // +1 for \n
    if (isHeading(line) && currentBody.trim().length > 0) {
      sections.push({ title: currentTitle, body: currentBody, charStart: currentStart, charEnd: charOffset });
      currentTitle = line.trim().replace(/^#+\s*/, "");
      currentBody = "";
      currentStart = charOffset;
    } else if (isHeading(line)) {
      currentTitle = line.trim().replace(/^#+\s*/, "");
      currentStart = charOffset;
    } else {
      currentBody += line + "\n";
    }
    charOffset += lineLen;
  }
  if (currentBody.trim()) {
    sections.push({ title: currentTitle, body: currentBody, charStart: currentStart, charEnd: charOffset });
  }

  // If no sections detected, treat whole doc as one section
  if (sections.length === 0) {
    sections.push({ title: "Document", body: text, charStart: 0, charEnd: text.length });
  }

  return sections.map((s) => ({ ...s, findings: [] }));
}

// ── Finding-to-section mapping ────────────────────────────────────────────────

function normalize(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function similarity(a: string, b: string): number {
  const na = normalize(a);
  const nb = normalize(b);
  if (na.includes(nb) || nb.includes(na)) return 0.9;
  const wordsA = new Set(na.split(" "));
  const wordsB = nb.split(" ");
  const overlap = wordsB.filter((w) => w.length > 3 && wordsA.has(w)).length;
  return overlap / Math.max(wordsA.size, wordsB.length);
}

function findBestSection(finding: Finding, sections: Section[]): number {
  if (sections.length === 0) return 0;

  const candidates = [
    finding.location,
    // Extract section name from "Required section missing: X"
    finding.title.match(/(?:missing|section):\s*(.+)/i)?.[1],
    // Extract section name from "Weak X analysis"
    finding.title.replace(/^(weak|missing|incomplete|inadequate|no)\s+/i, ""),
    finding.title,
  ].filter(Boolean) as string[];

  let bestIdx = -1;
  let bestScore = 0.25; // minimum threshold

  for (const candidate of candidates) {
    for (let i = 0; i < sections.length; i++) {
      const score = similarity(candidate, sections[i].title);
      if (score > bestScore) {
        bestScore = score;
        bestIdx = i;
      }
    }
  }

  return bestIdx; // -1 means unmapped
}

function assignFindingsToSections(sections: Section[], findings: Finding[]): Section[] {
  const result = sections.map((s) => ({ ...s, findings: [] as Finding[] }));
  const unmapped: Finding[] = [];

  for (const f of findings) {
    const idx = findBestSection(f, result);
    if (idx >= 0) {
      result[idx].findings.push(f);
    } else {
      unmapped.push(f);
    }
  }

  // Unmapped findings go to first section
  if (unmapped.length > 0 && result.length > 0) {
    result[0].findings.push(...unmapped);
  }

  return result;
}

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEV_CONFIG = {
  critical: {
    border: "border-l-red-500",
    bg: "bg-red-50",
    badge: "bg-red-100 text-red-700",
    dot: "bg-red-500",
    icon: AlertTriangle,
    textHighlight: "bg-red-100 border-b-2 border-red-400",
  },
  high: {
    border: "border-l-orange-400",
    bg: "bg-orange-50/60",
    badge: "bg-orange-100 text-orange-700",
    dot: "bg-orange-400",
    icon: AlertTriangle,
    textHighlight: "bg-orange-100 border-b-2 border-orange-300",
  },
  medium: {
    border: "border-l-amber-400",
    bg: "bg-amber-50/40",
    badge: "bg-amber-100 text-amber-700",
    dot: "bg-amber-400",
    icon: AlertCircle,
    textHighlight: "bg-amber-50 border-b-2 border-amber-300",
  },
  low: {
    border: "border-l-blue-400",
    bg: "bg-blue-50/30",
    badge: "bg-blue-100 text-blue-700",
    dot: "bg-blue-400",
    icon: Info,
    textHighlight: "bg-blue-50 border-b-2 border-blue-200",
  },
  info: {
    border: "border-l-gray-300",
    bg: "bg-gray-50/30",
    badge: "bg-gray-100 text-gray-600",
    dot: "bg-gray-300",
    icon: Info,
    textHighlight: "bg-gray-50",
  },
};

function sectionSeverity(section: Section): string {
  const order = ["critical", "high", "medium", "low", "info"];
  for (const sev of order) {
    if (section.findings.some((f) => f.severity === sev)) return sev;
  }
  return "clean";
}

// ── Comment bubble ────────────────────────────────────────────────────────────

function CommentBubble({
  finding,
  index,
  expanded,
  onToggle,
}: {
  finding: Finding;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const cfg = SEV_CONFIG[finding.severity as keyof typeof SEV_CONFIG] ?? SEV_CONFIG.info;
  const Icon = cfg.icon;

  return (
    <div
      className={cn(
        "rounded-lg border shadow-sm cursor-pointer transition-all duration-200",
        expanded ? "shadow-md" : "hover:shadow-md",
        cfg.bg,
        "border-l-4",
        cfg.border
      )}
      onClick={onToggle}
    >
      {/* Header row */}
      <div className="flex items-start gap-2 px-3 py-2.5">
        <Icon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", finding.severity === "critical" || finding.severity === "high" ? "text-red-500" : finding.severity === "medium" ? "text-amber-500" : "text-blue-400")} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide", cfg.badge)}>
              {finding.severity}
            </span>
            <span className="text-[10px] text-muted-foreground font-mono">{finding.level}</span>
            {finding.enforcement_match && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">⚡ Enf</span>
            )}
          </div>
          <p className="text-xs font-medium mt-1 leading-snug line-clamp-2">{finding.title}</p>
          {finding.regulatory_citation && !expanded && (
            <p className="text-[10px] text-muted-foreground mt-0.5 font-mono truncate">{finding.regulatory_citation}</p>
          )}
        </div>
        <button className="shrink-0 text-muted-foreground mt-0.5">
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2.5 border-t border-black/5 pt-2.5">
          <div>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">Description</p>
            <p className="text-xs text-foreground leading-relaxed">{finding.description}</p>
          </div>
          {finding.evidence && (
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">Evidence</p>
              <p className="text-[11px] italic text-muted-foreground leading-relaxed border-l-2 border-muted pl-2">{finding.evidence}</p>
            </div>
          )}
          {finding.regulatory_citation && (
            <div className="flex items-center gap-1.5">
              <BookOpen className="w-3 h-3 text-muted-foreground shrink-0" />
              <span className="text-[11px] font-mono text-primary">{finding.regulatory_citation}</span>
              {finding.citation_type && (
                <span className="text-[10px] text-muted-foreground">· {finding.citation_type}</span>
              )}
            </div>
          )}
          {finding.enforcement_context && (
            <div className="rounded-md bg-purple-50 border border-purple-200 p-2">
              <div className="flex items-center gap-1 mb-1">
                <Zap className="w-3 h-3 text-purple-600" />
                <p className="text-[10px] font-semibold text-purple-700 uppercase tracking-wide">Enforcement Intelligence</p>
              </div>
              <p className="text-[10px] text-purple-800 leading-relaxed line-clamp-4">{finding.enforcement_context}</p>
            </div>
          )}
          {finding.suggestion_draft && (
            <div className="rounded-md bg-green-50 border border-green-200 p-2">
              <p className="text-[10px] font-semibold text-green-700 uppercase tracking-wide mb-1">Suggested Fix</p>
              <p className="text-[11px] text-green-900 leading-relaxed">{finding.suggestion_draft}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Section row ───────────────────────────────────────────────────────────────

function SectionRow({
  section,
  expandedFinding,
  onToggleFinding,
}: {
  section: Section;
  expandedFinding: string | null;
  onToggleFinding: (id: string) => void;
}) {
  const sev = sectionSeverity(section);
  const cfg = SEV_CONFIG[sev as keyof typeof SEV_CONFIG];
  const hasFindings = section.findings.length > 0;

  const borderColor = hasFindings && cfg
    ? cfg.border.replace("border-l-", "border-l-4 border-l-")
    : "border-l-4 border-l-transparent";

  return (
    <div className={cn("flex gap-0 min-h-[2rem]", hasFindings && "bg-card rounded-lg overflow-hidden border border-border/60 shadow-sm mb-2")}>
      {/* Document text pane */}
      <div className={cn("flex-1 min-w-0 border-l-4 px-4 py-3", hasFindings ? borderColor : "border-l-transparent px-4 py-1.5")}>
        {/* Section heading */}
        <h3 className={cn(
          "font-semibold mb-1",
          hasFindings ? "text-sm" : "text-sm text-muted-foreground"
        )}>
          {section.title}
        </h3>
        {/* Body text — highlight if findings present */}
        <div className={cn("text-xs leading-relaxed whitespace-pre-wrap font-mono", hasFindings ? "text-foreground" : "text-muted-foreground")}>
          {section.body.trim() || (
            <span className={cn("italic px-1 rounded", cfg?.textHighlight ?? "")}>
              ⚠ This section was not found in the document
            </span>
          )}
        </div>
      </div>

      {/* Margin comment column */}
      {hasFindings && (
        <div className="w-64 shrink-0 border-l border-border/40 bg-muted/20 px-2 py-2 space-y-1.5">
          {section.findings.map((f, i) => (
            <CommentBubble
              key={f.id}
              finding={f}
              index={i}
              expanded={expandedFinding === f.id}
              onToggle={() => onToggleFinding(f.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function DocumentReviewPane({ documentText, fileType, findings }: Props) {
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);

  const sections = useMemo(() => {
    if (!documentText?.trim()) return [];
    const raw = detectSections(documentText);
    return assignFindingsToSections(raw, findings);
  }, [documentText, findings]);

  const toggleFinding = (id: string) =>
    setExpandedFinding((prev) => (prev === id ? null : id));

  if (!documentText?.trim()) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
        <AlertCircle className="w-10 h-10 mb-3 opacity-30" />
        <p className="font-medium">No document text available</p>
        <p className="text-sm mt-1">The document may not have been processed yet.</p>
      </div>
    );
  }

  const totalAnchored = sections.reduce((n, s) => n + s.findings.length, 0);
  const totalFindings = findings.length;

  return (
    <div className="space-y-1">
      {/* Legend bar */}
      <div className="flex items-center justify-between px-1 pb-2 border-b">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {(["critical", "high", "medium", "low"] as const).map((sev) => {
            const count = findings.filter((f) => f.severity === sev).length;
            if (!count) return null;
            const cfg = SEV_CONFIG[sev];
            return (
              <span key={sev} className="flex items-center gap-1">
                <span className={cn("w-2 h-2 rounded-full", cfg.dot)} />
                <span className="capitalize">{sev} ({count})</span>
              </span>
            );
          })}
        </div>
        <span className="text-xs text-muted-foreground">
          {totalAnchored}/{totalFindings} findings anchored · {sections.length} sections
        </span>
      </div>

      {/* Column headers */}
      <div className="flex gap-0 px-1 pb-1">
        <div className="flex-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Document</div>
        <div className="w-64 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground pl-2">Comments</div>
      </div>

      {/* Sections */}
      <div className="space-y-0.5">
        {sections.map((section, i) => (
          <SectionRow
            key={i}
            section={section}
            expandedFinding={expandedFinding}
            onToggleFinding={toggleFinding}
          />
        ))}
      </div>
    </div>
  );
}

"use client";

import { useMemo, useRef, useState, useCallback, useEffect } from "react";
import {
  AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp,
  BookOpen, Zap, GripVertical, Maximize2, X,
  CheckCircle2, XCircle, MessageSquare, Loader2, Check, Ban,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { assessmentsApi } from "@/lib/api";

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
  status?: string;
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
  documentId?: string;
  assessmentId?: string;
}

// ── Section detection ─────────────────────────────────────────────────────────

const HEADING_PATTERNS = [
  /^#{1,3}\s+(.+)$/,
  /^([A-Z][A-Z\s\-\/]{3,60})$/,
  /^(\d+[\.\d]*\.?\s+[A-Z].{3,60})$/,
  /^([A-Z][a-z].{4,60}):?\s*$/,
];

function isHeading(line: string): boolean {
  const t = line.trim();
  if (!t || t.length > 80 || t.length < 3) return false;
  if (t.endsWith(".") && t.split(" ").length > 6) return false;
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
    const lineLen = line.length + 1;
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
    finding.title.match(/(?:missing|section):\s*(.+)/i)?.[1],
    finding.title.replace(/^(weak|missing|incomplete|inadequate|no)\s+/i, ""),
    finding.title,
  ].filter(Boolean) as string[];

  let bestIdx = -1;
  let bestScore = 0.25;
  for (const candidate of candidates) {
    for (let i = 0; i < sections.length; i++) {
      const score = similarity(candidate, sections[i].title);
      if (score > bestScore) { bestScore = score; bestIdx = i; }
    }
  }
  return bestIdx;
}

function assignFindingsToSections(sections: Section[], findings: Finding[]): Section[] {
  const result = sections.map((s) => ({ ...s, findings: [] as Finding[] }));
  const unmapped: Finding[] = [];
  for (const f of findings) {
    const idx = findBestSection(f, result);
    if (idx >= 0) result[idx].findings.push(f);
    else unmapped.push(f);
  }
  if (unmapped.length > 0 && result.length > 0) result[0].findings.push(...unmapped);
  return result;
}

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEV_CONFIG = {
  critical: { border: "border-l-red-500", bg: "bg-red-50", badge: "bg-red-100 text-red-700", dot: "bg-red-500", icon: AlertTriangle, textHighlight: "bg-red-100 border-b-2 border-red-400", iconColor: "text-red-500" },
  high:     { border: "border-l-orange-400", bg: "bg-orange-50/60", badge: "bg-orange-100 text-orange-700", dot: "bg-orange-400", icon: AlertTriangle, textHighlight: "bg-orange-100 border-b-2 border-orange-300", iconColor: "text-orange-500" },
  medium:   { border: "border-l-amber-400", bg: "bg-amber-50/40", badge: "bg-amber-100 text-amber-700", dot: "bg-amber-400", icon: AlertCircle, textHighlight: "bg-amber-50 border-b-2 border-amber-300", iconColor: "text-amber-500" },
  low:      { border: "border-l-blue-400", bg: "bg-blue-50/30", badge: "bg-blue-100 text-blue-700", dot: "bg-blue-400", icon: Info, textHighlight: "bg-blue-50 border-b-2 border-blue-200", iconColor: "text-blue-400" },
  info:     { border: "border-l-gray-300", bg: "bg-gray-50/30", badge: "bg-gray-100 text-gray-600", dot: "bg-gray-300", icon: Info, textHighlight: "bg-gray-50", iconColor: "text-gray-400" },
};

function sectionSeverity(section: Section): string {
  for (const sev of ["critical", "high", "medium", "low", "info"]) {
    if (section.findings.some((f) => f.severity === sev)) return sev;
  }
  return "clean";
}

// ── Finding Detail Modal ──────────────────────────────────────────────────────

interface FindingCommentEntry {
  id: string;
  user_name: string;
  user_role: string;
  text: string;
  created_at: string;
}

function FindingDetailModal({
  finding,
  assessmentId,
  onClose,
  onActionDone,
}: {
  finding: Finding;
  assessmentId?: string;
  onClose: () => void;
  onActionDone?: (findingId: string, newStatus: string) => void;
}) {
  const cfg = SEV_CONFIG[finding.severity as keyof typeof SEV_CONFIG] ?? SEV_CONFIG.info;
  const Icon = cfg.icon;

  // Review actions state
  const [actionMode, setActionMode] = useState<"accept" | "deny" | null>(null);
  const [disputeText, setDisputeText] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionDone, setActionDone] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  // Comment thread state
  const [comments, setComments] = useState<FindingCommentEntry[]>([]);
  const [commentText, setCommentText] = useState("");
  const [commentLoading, setCommentLoading] = useState(false);
  const [commentError, setCommentError] = useState("");
  const commentsEndRef = useRef<HTMLDivElement>(null);

  // Load + poll comments
  const loadComments = useCallback(async () => {
    if (!assessmentId) return;
    try {
      const res = await assessmentsApi.getComments(assessmentId, finding.id);
      setComments(res.data.comments ?? []);
    } catch { /* non-critical */ }
  }, [assessmentId, finding.id]);

  useEffect(() => {
    loadComments();
    const interval = setInterval(loadComments, 5000);
    return () => clearInterval(interval);
  }, [loadComments]);

  // Scroll to bottom on new comments
  useEffect(() => {
    commentsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [comments.length]);

  // Escape to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submitAction = async () => {
    if (!assessmentId || !actionMode) return;
    setActionLoading(true); setActionError("");
    try {
      const status = actionMode === "accept" ? "resolved" : "disputed";
      const disputeReason = actionMode === "deny" ? disputeText : "";
      await assessmentsApi.actionFinding(assessmentId, finding.id, status, "", disputeReason);
      setActionDone(status);
      onActionDone?.(finding.id, status);
    } catch (e: any) {
      setActionError(e?.response?.data?.detail ?? "Action failed. Please try again.");
    } finally { setActionLoading(false); }
  };

  const sendComment = async () => {
    if (!assessmentId || !commentText.trim()) return;
    setCommentLoading(true); setCommentError("");
    try {
      const res = await assessmentsApi.addComment(assessmentId, finding.id, commentText.trim());
      setComments((prev) => [...prev, res.data]);
      setCommentText("");
    } catch (e: any) {
      setCommentError(e?.response?.data?.detail ?? "Failed to send comment.");
    } finally { setCommentLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-card border rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={cn("flex items-start gap-3 px-5 py-3.5 border-b border-l-4 shrink-0", cfg.border, cfg.bg)}>
          <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", cfg.iconColor)} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide", cfg.badge)}>{finding.severity}</span>
              <span className="text-[10px] font-mono text-muted-foreground">{finding.level}</span>
              {finding.enforcement_match && <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">⚡ Enforcement</span>}
              {finding.status && finding.status !== "open" && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground capitalize font-medium">{finding.status}</span>
              )}
            </div>
            <p className="text-sm font-semibold leading-snug">{finding.title}</p>
          </div>
          <button onClick={onClose} className="shrink-0 p-1 rounded hover:bg-black/10 transition-colors">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Body — 3 columns */}
        <div className="flex-1 flex overflow-hidden min-h-0">

          {/* Finding detail */}
          <div className="flex-1 px-5 py-4 space-y-4 overflow-y-auto border-r">
            <div>
              <p className="text-[10px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Description</p>
              <p className="text-sm leading-relaxed">{finding.description}</p>
            </div>
            {finding.evidence && (
              <div>
                <p className="text-[10px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Evidence</p>
                <p className="text-sm italic text-muted-foreground leading-relaxed border-l-2 border-muted pl-3">"{finding.evidence}"</p>
              </div>
            )}
            {(finding.location || finding.regulatory_citation) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {finding.location && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">Location</p>
                    <p className="text-xs bg-muted rounded px-2 py-1.5">{finding.location}</p>
                  </div>
                )}
                {finding.regulatory_citation && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wide font-semibold text-muted-foreground mb-1.5">
                      Citation{finding.citation_type ? ` · ${finding.citation_type}` : ""}
                    </p>
                    <p className="text-xs font-mono bg-clyira-50 text-clyira-800 border border-clyira-100 rounded px-2 py-1.5 flex items-center gap-1.5">
                      <BookOpen className="w-3 h-3 shrink-0" />{finding.regulatory_citation}
                    </p>
                  </div>
                )}
              </div>
            )}
            {finding.enforcement_context && (
              <div className="rounded-lg bg-purple-50 border border-purple-200 p-3">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Zap className="w-3.5 h-3.5 text-purple-600" />
                  <p className="text-[10px] font-semibold text-purple-700 uppercase tracking-wide">Enforcement Intelligence</p>
                </div>
                <p className="text-xs text-purple-800 leading-relaxed">{finding.enforcement_context}</p>
              </div>
            )}
            {finding.suggestion_draft && (
              <div className="rounded-lg bg-green-50 border border-green-200 p-3">
                <p className="text-[10px] font-semibold text-green-700 uppercase tracking-wide mb-1.5">Suggested Fix</p>
                <p className="text-sm text-green-900 leading-relaxed whitespace-pre-wrap">{finding.suggestion_draft}</p>
              </div>
            )}
          </div>

          {/* Comment thread */}
          <div className="w-72 shrink-0 flex flex-col border-r bg-muted/10">
            <div className="px-3 py-2.5 border-b">
              <p className="text-xs font-semibold flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5 text-muted-foreground" />
                Comments
                {comments.length > 0 && (
                  <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded-full font-medium">{comments.length}</span>
                )}
              </p>
            </div>

            {/* Thread */}
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
              {comments.length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-6">No comments yet. Be the first to comment.</p>
              ) : (
                comments.map((c) => (
                  <div key={c.id} className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <span className="text-[9px] font-bold text-primary">{(c.user_name || "?")[0].toUpperCase()}</span>
                      </div>
                      <span className="text-[10px] font-semibold">{c.user_name || "Unknown"}</span>
                      <span className="text-[9px] text-muted-foreground capitalize">{c.user_role}</span>
                      <span className="text-[9px] text-muted-foreground ml-auto">{new Date(c.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                    <div className="ml-6.5 bg-card border rounded-lg px-2.5 py-2">
                      <p className="text-xs leading-relaxed">{c.text}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={commentsEndRef} />
            </div>

            {/* Comment input */}
            <div className="px-3 py-2.5 border-t space-y-2">
              {commentError && <p className="text-[10px] text-destructive">{commentError}</p>}
              <div className="flex gap-1.5">
                <textarea
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendComment(); } }}
                  placeholder="Add a comment… (Enter to send)"
                  rows={2}
                  className="flex-1 text-xs border rounded-lg px-2.5 py-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
                />
                <button
                  onClick={sendComment}
                  disabled={!commentText.trim() || commentLoading}
                  className="px-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors shrink-0"
                >
                  {commentLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>

          {/* Review actions */}
          {assessmentId && (
            <div className="w-48 shrink-0 px-4 py-4 space-y-3 bg-muted/20">
              <p className="text-[10px] uppercase tracking-wide font-semibold text-muted-foreground">Review Actions</p>

              {actionDone ? (
                <div className="rounded-lg bg-green-50 border border-green-200 p-3 text-center">
                  <CheckCircle2 className="w-5 h-5 text-green-600 mx-auto mb-1" />
                  <p className="text-xs font-semibold text-green-800 capitalize">{actionDone}</p>
                  <p className="text-[10px] text-green-700 mt-0.5">Recorded</p>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => setActionMode(actionMode === "accept" ? null : "accept")}
                    className={cn("w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-all",
                      actionMode === "accept" ? "bg-green-600 text-white border-green-600" : "border-green-300 text-green-700 hover:bg-green-50")}
                  >
                    <Check className="w-3.5 h-3.5" /> Accept Finding
                  </button>

                  <button
                    onClick={() => setActionMode(actionMode === "deny" ? null : "deny")}
                    className={cn("w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-all",
                      actionMode === "deny" ? "bg-red-600 text-white border-red-600" : "border-red-300 text-red-700 hover:bg-red-50")}
                  >
                    <Ban className="w-3.5 h-3.5" /> Dispute
                  </button>

                  {actionMode === "deny" && (
                    <textarea
                      autoFocus
                      value={disputeText}
                      onChange={(e) => setDisputeText(e.target.value)}
                      placeholder="Reason for dispute…"
                      className="w-full text-xs border rounded-lg px-2.5 py-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 min-h-[64px] resize-none"
                    />
                  )}

                  {actionError && <p className="text-[10px] text-destructive">{actionError}</p>}

                  {actionMode && (
                    <button
                      onClick={submitAction}
                      disabled={actionLoading || (actionMode === "deny" && !disputeText.trim())}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
                    >
                      {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      {actionMode === "accept" ? "Confirm Accept" : "Submit Dispute"}
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Comment Bubble ────────────────────────────────────────────────────────────

const COMMENTS_INITIAL = 4;

function CommentBubble({
  finding,
  expanded,
  onToggle,
  onOpenModal,
}: {
  finding: Finding;
  expanded: boolean;
  onToggle: () => void;
  onOpenModal: () => void;
}) {
  const cfg = SEV_CONFIG[finding.severity as keyof typeof SEV_CONFIG] ?? SEV_CONFIG.info;
  const Icon = cfg.icon;

  return (
    <div className={cn("rounded-lg border shadow-sm transition-all duration-200", expanded ? "shadow-md" : "hover:shadow-md", cfg.bg, "border-l-4", cfg.border)}>
      <div className="flex items-start gap-2 px-3 py-2.5">
        <Icon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", cfg.iconColor)} />
        <div className="flex-1 min-w-0 cursor-pointer" onClick={onToggle}>
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide", cfg.badge)}>{finding.severity}</span>
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
        <div className="flex items-center gap-0.5 shrink-0 mt-0.5">
          <button
            onClick={onOpenModal}
            title="Open full detail"
            className="p-0.5 rounded hover:bg-black/10 transition-colors text-muted-foreground"
          >
            <Maximize2 className="w-3 h-3" />
          </button>
          <button onClick={onToggle} className="p-0.5 text-muted-foreground">
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

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
          <button
            onClick={onOpenModal}
            className="w-full text-[10px] text-primary hover:underline font-medium text-left"
          >
            Open full detail + review actions →
          </button>
        </div>
      )}
    </div>
  );
}

// ── Section Row ───────────────────────────────────────────────────────────────

function SectionRow({
  section,
  commentWidth,
  expandedFinding,
  onToggleFinding,
  onOpenModal,
}: {
  section: Section;
  commentWidth: number;
  expandedFinding: string | null;
  onToggleFinding: (id: string) => void;
  onOpenModal: (finding: Finding) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const sev = sectionSeverity(section);
  const cfg = SEV_CONFIG[sev as keyof typeof SEV_CONFIG];
  const hasFindings = section.findings.length > 0;
  const overflow = section.findings.length - COMMENTS_INITIAL;
  const visibleFindings = showAll ? section.findings : section.findings.slice(0, COMMENTS_INITIAL);

  const borderColor = hasFindings && cfg
    ? cfg.border.replace("border-l-", "border-l-4 border-l-")
    : "border-l-4 border-l-transparent";

  return (
    <div className={cn("flex gap-0 min-h-[2rem]", hasFindings && "bg-card rounded-lg overflow-hidden border border-border/60 shadow-sm mb-2")}>
      {/* Document text */}
      <div className={cn("flex-1 min-w-0 border-l-4 px-5 py-4", hasFindings ? borderColor : "border-l-transparent px-5 py-2")}>
        <h3 className={cn(
          "font-bold mb-2",
          hasFindings ? "text-sm text-foreground" : "text-sm text-muted-foreground"
        )}>
          {section.title}
        </h3>
        <div className={cn(
          "text-sm leading-7",
          hasFindings ? "text-foreground" : "text-muted-foreground"
        )}>
          {section.body.trim() ? (
            section.body.trim().split(/\n{2,}/).map((para, i) => (
              <p key={i} className="mb-2 last:mb-0">{para.replace(/\n/g, " ")}</p>
            ))
          ) : (
            <span className={cn("text-xs italic px-1 rounded", cfg?.textHighlight ?? "")}>
              This section was not found in the document
            </span>
          )}
        </div>
      </div>

      {/* Comment column */}
      {hasFindings && (
        <div style={{ width: commentWidth }} className="shrink-0 border-l border-border/40 bg-muted/20 px-2 py-2 space-y-1.5 overflow-y-auto">
          {visibleFindings.map((f) => (
            <CommentBubble
              key={f.id}
              finding={f}
              expanded={expandedFinding === f.id}
              onToggle={() => onToggleFinding(f.id)}
              onOpenModal={() => onOpenModal(f)}
            />
          ))}
          {overflow > 0 && !showAll && (
            <button
              onClick={() => setShowAll(true)}
              className="w-full text-[10px] font-medium text-muted-foreground hover:text-foreground border border-dashed border-border/60 rounded-md py-1.5 transition-colors hover:bg-muted/40"
            >
              + {overflow} more finding{overflow !== 1 ? "s" : ""}
            </button>
          )}
          {showAll && overflow > 0 && (
            <button
              onClick={() => setShowAll(false)}
              className="w-full text-[10px] font-medium text-muted-foreground hover:text-foreground border border-dashed border-border/60 rounded-md py-1.5 transition-colors hover:bg-muted/40"
            >
              Show less
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function DocumentReviewPane({ documentText, fileType, findings, documentId, assessmentId }: Props) {
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);
  const [modalFinding, setModalFinding] = useState<Finding | null>(null);
  const [commentWidth, setCommentWidth] = useState(280);

  // Drag-to-resize comment column
  const dragState = useRef({ active: false, startX: 0, startWidth: 0 });

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragState.current = { active: true, startX: e.clientX, startWidth: commentWidth };

    const onMove = (ev: MouseEvent) => {
      if (!dragState.current.active) return;
      const delta = dragState.current.startX - ev.clientX;
      setCommentWidth(Math.min(520, Math.max(160, dragState.current.startWidth + delta)));
    };
    const onUp = () => {
      dragState.current.active = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [commentWidth]);

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
        <p className="text-sm mt-1 max-w-sm">
          This document has no extracted text — it may be a placeholder created by the AI creator.
          Upload a real PDF or DOCX to see the annotated review.
        </p>
      </div>
    );
  }

  const totalAnchored = sections.reduce((n, s) => n + s.findings.length, 0);

  return (
    <>
      {modalFinding && (
        <FindingDetailModal
          finding={modalFinding}
          assessmentId={assessmentId}
          onClose={() => setModalFinding(null)}
          onActionDone={(findingId, status) => { /* bubble status up if needed */ }}
        />
      )}

      <div className="space-y-1">
        {/* Legend + resize hint */}
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
            {totalAnchored}/{findings.length} anchored · {sections.length} sections · <span className="text-muted-foreground/60">drag divider to resize</span>
          </span>
        </div>

        {/* Column headers */}
        <div className="flex gap-0 px-1 pb-1">
          <div className="flex-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Document</div>
          <div style={{ width: commentWidth }} className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground pl-2 flex items-center gap-1">
            <GripVertical
              className="w-3 h-3 cursor-col-resize text-muted-foreground/40 hover:text-muted-foreground -ml-1 select-none"
              onMouseDown={onDragStart}
            />
            Comments
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-0.5">
          {sections.map((section, i) => (
            <SectionRow
              key={i}
              section={section}
              commentWidth={commentWidth}
              expandedFinding={expandedFinding}
              onToggleFinding={toggleFinding}
              onOpenModal={setModalFinding}
            />
          ))}
        </div>
      </div>
    </>
  );
}

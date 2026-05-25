"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Shield, Target, AlertTriangle, PlayCircle, RefreshCw,
  ChevronRight, FileText, CheckCircle2, Loader2, Zap, Radio,
} from "lucide-react";
import { readinessApi } from "@/lib/api";
import { ScoreRing, ScoreBar, ScoreBadge } from "@/components/shared/score-display";
import { DocStatusBadge } from "@/components/shared/badges";

interface ReadinessDashboard {
  company_score: number;
  score_band: string;
  departments: { department: string; score: number; weight: number; document_count: number }[];
  total_documents: number;
  top_gaps: { missing_assessments: any[]; poor_scores: any[] };
  gap_count: number;
  data_integrity_holds?: number;
  enforcement_matches_total?: number;
}

interface MockResult {
  simulation_id: string;
  readiness_score: number;
  readiness_interpretation?: string;
  questions: {
    category: string; question: string; criticality: string;
    related_document: string | null; regulatory_basis?: string;
    source?: string; observation_count?: number;
  }[];
  departments_assessed: string[];
  data_integrity_holds?: number;
  question_count?: number;
  risk_profile?: { category_id: string; label: string; cfr: string; description: string }[];
  open_critical_findings?: number;
  open_high_findings?: number;
}

interface EnforcementAlert {
  id: string;
  agency: string;
  record_type: string;
  title: string;
  summary: string;
  issue_date: string | null;
  pattern_tags: string[];
  trending: boolean;
  observation_count?: number;
  source: string;
}

interface FullGapAnalysis {
  gaps: {
    missing_assessments: any[];
    poor_scores: any[];
    overdue_review: any[];
    critical_findings: any[];
  };
  total_documents: number;
  assessed_count: number;
  gap_count: number;
}

export default function ReadinessPage() {
  const [readiness, setReadiness] = useState<ReadinessDashboard | null>(null);
  const [fullGaps, setFullGaps] = useState<FullGapAnalysis | null>(null);
  const [mockResult, setMockResult] = useState<MockResult | null>(null);
  const [enforcementAlerts, setEnforcementAlerts] = useState<EnforcementAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [tab, setTab] = useState<"overview" | "gaps" | "mock" | "enforcement">("overview");
  const [error, setError] = useState("");
  const [mockError, setMockError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [dashRes, gapsRes] = await Promise.all([
        readinessApi.dashboard(),
        readinessApi.gaps(),
      ]);
      setReadiness(dashRes.data);
      setFullGaps(gapsRes.data);
    } catch {
      setError("Could not load readiness data. Please refresh.");
    } finally {
      setLoading(false);
    }
  };

  const runMock = async () => {
    setRunning(true);
    setMockError("");
    try {
      const res = await readinessApi.mockInspection();
      setMockResult(res.data);
      setTab("mock");
    } catch {
      setMockError("Failed to generate mock inspection. Please try again.");
    } finally {
      setRunning(false);
    }
  };

  const loadAlerts = async () => {
    setAlertsLoading(true);
    try {
      const res = await readinessApi.enforcementAlerts();
      setEnforcementAlerts(res.data.alerts ?? []);
    } catch {
      // silently fail — enforcement alerts are supplementary
    } finally {
      setAlertsLoading(false);
    }
  };

  useEffect(() => { load(); loadAlerts(); }, []);

  const score = readiness?.company_score;

  const CRITICALITY_STYLE: Record<string, string> = {
    high: "bg-orange-50 border-orange-200 text-orange-800",
    medium: "bg-amber-50 border-amber-200 text-amber-800",
    low: "bg-blue-50 border-blue-200 text-blue-800",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Audit Readiness</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Continuous readiness scoring, gap analysis, and mock inspections</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading} className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button onClick={runMock} disabled={running || loading}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
            {running ? "Generating…" : "Run Mock Inspection"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}
      {mockError && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg px-4 py-3">
          {mockError}
        </div>
      )}

      {/* Company Score Banner */}
      <div className="bg-card border rounded-xl p-6">
        <div className="flex items-center gap-6 flex-wrap">
          <ScoreRing score={score} size="lg" />
          <div className="flex-1">
            <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wide mb-1">Company Clyira Score</p>
            <p className="text-3xl font-bold tabular-nums">{score != null ? score.toFixed(1) : "—"}</p>
            <p className="text-sm text-muted-foreground mt-0.5">{readiness?.score_band ?? "Upload and assess documents to begin"}</p>
            <div className="mt-3 w-full max-w-md h-2 bg-muted rounded-full overflow-hidden">
              {score != null && (
                <div className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${score}%`, backgroundColor: score >= 90 ? "#10b981" : score >= 80 ? "#34d399" : score >= 65 ? "#f59e0b" : score >= 50 ? "#ef4444" : "#991b1b" }} />
              )}
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-1 max-w-md">
              {["Critical", "Poor", "Moderate", "Good", "Excellent"].map(b => (
                <span key={b}>{b}</span>
              ))}
            </div>
          </div>
          {readiness && (
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="bg-muted/40 rounded-lg px-4 py-3">
                <p className="text-2xl font-bold tabular-nums">{readiness.total_documents}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Documents</p>
              </div>
              <div className="bg-muted/40 rounded-lg px-4 py-3">
                <p className="text-2xl font-bold tabular-nums">{readiness.gap_count}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Gaps</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b gap-1">
        {[
          { key: "overview", label: "Department Overview" },
          { key: "gaps", label: `Gaps & Issues${readiness ? ` (${readiness.gap_count})` : ""}` },
          { key: "enforcement", label: `Enforcement Alerts${enforcementAlerts.length > 0 ? ` (${enforcementAlerts.length})` : ""}` },
          { key: "mock", label: "Mock Inspection" },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === "overview" && (
        <div className="space-y-4">
          <div className="bg-card border rounded-xl p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-sm">Department Scores</h2>
              <p className="text-xs text-muted-foreground">Weighted by document count</p>
            </div>
            {loading ? (
              <div className="space-y-3">
                {[1,2,3,4,5].map(i => <div key={i} className="h-8 bg-muted animate-pulse rounded" />)}
              </div>
            ) : readiness?.departments.length ? (
              <div className="space-y-3">
                {readiness.departments.sort((a, b) => b.score - a.score).map(d => (
                  <ScoreBar
                    key={d.department}
                    label={d.department}
                    score={d.score}
                    weight={d.weight}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Shield className="w-8 h-8 text-muted-foreground/30 mb-2" />
                <p className="text-sm text-muted-foreground">No department data yet</p>
                <p className="text-xs text-muted-foreground">Upload and assess documents to build scores</p>
              </div>
            )}
          </div>

          {/* Quick action cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { icon: Target, label: "Gap Analysis", desc: "Missing documents, expired items, and assessment gaps", onClick: () => setTab("gaps"), badge: readiness?.gap_count },
              { icon: Zap, label: "Enforcement Alerts", desc: `${enforcementAlerts.length > 0 ? `${enforcementAlerts.length} active alerts` : "Trending observations and regulatory change alerts"}`, onClick: () => setTab("enforcement"), badge: enforcementAlerts.length || undefined },
              { icon: Radio, label: "Mock Inspection", desc: "AI-powered mock FDA/EMA inspection questions", onClick: () => setTab("mock") },
            ].map(({ icon: Icon, label, desc, onClick, badge }) => (
              <button key={label} onClick={onClick}
                className="bg-card border rounded-xl p-5 text-left hover:border-primary/50 transition-colors relative">
                {badge != null && badge > 0 && (
                  <span className="absolute top-3 right-3 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">{badge}</span>
                )}
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="w-5 h-5 text-primary" />
                  <h3 className="font-semibold text-sm">{label}</h3>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Gaps Tab */}
      {tab === "gaps" && (
        <div className="space-y-4">
          {loading ? (
            <div className="h-48 bg-muted animate-pulse rounded-xl" />
          ) : (
            <>
              {(fullGaps?.gaps.poor_scores.length ?? readiness?.top_gaps.poor_scores.length ?? 0) > 0 ? (
                <div className="bg-card border rounded-xl overflow-hidden">
                  <div className="px-5 py-3.5 border-b bg-red-50">
                    <h2 className="font-semibold text-sm text-red-800 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" /> Documents Below Threshold
                    </h2>
                    <p className="text-xs text-red-700 mt-0.5">Scores below 65 — require immediate attention</p>
                  </div>
                  <div className="divide-y">
                    {(fullGaps?.gaps.poor_scores ?? readiness?.top_gaps.poor_scores ?? []).map((g: any) => (
                      <Link key={g.document_id} href={`/documents/${g.document_id}`}
                        className="flex items-center gap-4 px-5 py-3 hover:bg-muted/30 transition-colors">
                        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{g.title}</p>
                          <p className="text-xs text-muted-foreground">{g.category}</p>
                        </div>
                        <ScoreBadge score={g.score} />
                        <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}

              {(fullGaps?.gaps.missing_assessments.length ?? readiness?.top_gaps.missing_assessments.length ?? 0) > 0 ? (
                <div className="bg-card border rounded-xl overflow-hidden">
                  <div className="px-5 py-3.5 border-b bg-amber-50">
                    <h2 className="font-semibold text-sm text-amber-800 flex items-center gap-2">
                      <Target className="w-4 h-4" /> Pending Assessment
                    </h2>
                    <p className="text-xs text-amber-700 mt-0.5">Documents uploaded but not yet assessed</p>
                  </div>
                  <div className="divide-y">
                    {(fullGaps?.gaps.missing_assessments ?? readiness?.top_gaps.missing_assessments ?? []).map((g: any) => (
                      <Link key={g.document_id} href={`/documents/${g.document_id}`}
                        className="flex items-center gap-4 px-5 py-3 hover:bg-muted/30 transition-colors">
                        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{g.title}</p>
                          <p className="text-xs text-muted-foreground">{g.category} · {g.status}</p>
                        </div>
                        <DocStatusBadge status={g.status} />
                        <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}

              {(fullGaps?.gaps.overdue_review.length ?? 0) > 0 && (
                <div className="bg-card border rounded-xl overflow-hidden">
                  <div className="px-5 py-3.5 border-b bg-purple-50">
                    <h2 className="font-semibold text-sm text-purple-800 flex items-center gap-2">
                      <RefreshCw className="w-4 h-4" /> Overdue for Re-Assessment
                    </h2>
                    <p className="text-xs text-purple-700 mt-0.5">Documents past their review cycle — re-assess to confirm ongoing compliance</p>
                  </div>
                  <div className="divide-y">
                    {fullGaps!.gaps.overdue_review.map((g: any) => (
                      <Link key={g.document_id} href={`/documents/${g.document_id}`}
                        className="flex items-center gap-4 px-5 py-3 hover:bg-muted/30 transition-colors">
                        <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{g.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {g.category} · Last assessed {g.last_assessed_days_ago} days ago
                          </p>
                        </div>
                        <span className="text-[10px] font-medium text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded flex-shrink-0">
                          {g.overdue_by_days}d overdue
                        </span>
                        <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {!fullGaps?.gaps.poor_scores.length && !fullGaps?.gaps.missing_assessments.length && !fullGaps?.gaps.overdue_review.length &&
               !readiness?.top_gaps.poor_scores.length && !readiness?.top_gaps.missing_assessments.length && (
                <div className="bg-green-50 border border-green-200 rounded-xl px-8 py-12 text-center">
                  <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                  <h3 className="font-semibold text-green-800">No gaps identified</h3>
                  <p className="text-sm text-green-700 mt-1">All assessed documents are above threshold and current.</p>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Enforcement Alerts Tab */}
      {tab === "enforcement" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              FDA Warning Letter patterns from BM25 corpus analysis — ranked by observation frequency
            </p>
            <button onClick={loadAlerts} disabled={alertsLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-lg hover:bg-accent disabled:opacity-50">
              <RefreshCw className={`w-3 h-3 ${alertsLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {alertsLoading ? (
            <div className="space-y-3">
              {[1,2,3,4].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-xl" />)}
            </div>
          ) : enforcementAlerts.length === 0 ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
              <Zap className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No enforcement alerts available.</p>
              <p className="text-xs text-muted-foreground mt-1">Assess documents to generate enforcement pattern analysis.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {enforcementAlerts.map((alert) => (
                <div key={alert.id} className={`bg-card border rounded-xl p-5 ${alert.source === "bm25_corpus" ? "border-amber-200" : "border-red-200"}`}>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide ${
                        alert.source === "bm25_corpus"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-red-100 text-red-800"
                      }`}>
                        {alert.agency}
                      </span>
                      <span className="text-[10px] text-muted-foreground capitalize">{alert.record_type.replace(/_/g, " ")}</span>
                      {alert.observation_count != null && (
                        <span className="text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
                          {alert.observation_count} observations
                        </span>
                      )}
                    </div>
                    {alert.trending && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-red-50 text-red-600 border border-red-200 flex-shrink-0">
                        Trending
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold text-sm mb-1">{alert.title}</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">{alert.summary}</p>
                  {alert.pattern_tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {alert.pattern_tags.map(tag => (
                        <span key={tag} className="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded">{tag}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Mock Inspection Tab */}
      {tab === "mock" && (
        <div className="space-y-4">
          {!mockResult ? (
            <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-12 text-center">
              <PlayCircle className="w-12 h-12 text-muted-foreground/40 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">No mock inspection run yet</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-sm mx-auto">
                Generate an AI-powered mock inspection based on your document corpus and readiness scores.
              </p>
              <button onClick={runMock} disabled={running}
                className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 mx-auto disabled:opacity-60">
                {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                {running ? "Generating…" : "Run Mock Inspection"}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Score + interpretation */}
              <div className="bg-card border rounded-xl p-5">
                <div className="flex items-start gap-6 flex-wrap">
                  <div>
                    <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wide mb-1">Readiness Score</p>
                    <p className="text-3xl font-bold tabular-nums">{mockResult.readiness_score?.toFixed(1) ?? "—"}</p>
                    <p className="text-xs text-muted-foreground mt-1">{mockResult.questions.length} inspection questions</p>
                  </div>
                  <div className="flex-1 min-w-0">
                    {mockResult.readiness_interpretation && (
                      <p className="text-sm text-foreground font-medium leading-relaxed">{mockResult.readiness_interpretation}</p>
                    )}
                    <div className="flex flex-wrap gap-3 mt-2">
                      {(mockResult.open_critical_findings ?? 0) > 0 && (
                        <span className="text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-2 py-1 rounded">
                          {mockResult.open_critical_findings} open critical finding{mockResult.open_critical_findings !== 1 ? "s" : ""}
                        </span>
                      )}
                      {(mockResult.open_high_findings ?? 0) > 0 && (
                        <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
                          {mockResult.open_high_findings} open high finding{mockResult.open_high_findings !== 1 ? "s" : ""}
                        </span>
                      )}
                      {(mockResult.data_integrity_holds ?? 0) > 0 && (
                        <span className="text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-2 py-1 rounded">
                          {mockResult.data_integrity_holds} DI hold{mockResult.data_integrity_holds !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">Depts: {mockResult.departments_assessed.join(", ")}</p>
                  </div>
                </div>
              </div>

              {/* FDA 483 Risk Profile */}
              {(mockResult.risk_profile?.length ?? 0) > 0 && (
                <div className="bg-card border rounded-xl p-5">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">FDA 483 Risk Areas Detected</p>
                  <div className="space-y-2">
                    {mockResult.risk_profile!.map((r) => (
                      <div key={r.category_id} className="flex items-start gap-3 py-2 border-b last:border-0">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">{r.label}</p>
                          <p className="text-xs text-muted-foreground">{r.description}</p>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground flex-shrink-0">{r.cfr}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {mockResult.questions.map((q, i) => (
                  <div key={i} className={`border rounded-xl p-5 ${CRITICALITY_STYLE[q.criticality] ?? "bg-card border-border"}`}>
                    <div className="flex items-start justify-between gap-3 mb-2 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold uppercase tracking-wide">{q.category}</span>
                        {q.source === "ai_generated" && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">AI Generated</span>
                        )}
                        {q.source === "enforcement_pattern" && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">
                            {q.observation_count} WL observations
                          </span>
                        )}
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded capitalize border ${CRITICALITY_STYLE[q.criticality] ?? ""}`}>
                        {q.criticality}
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-relaxed">{q.question}</p>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      {q.regulatory_basis && (
                        <span className="text-[10px] font-mono text-muted-foreground">{q.regulatory_basis}</span>
                      )}
                      {q.related_document && (
                        <Link href={`/documents/${q.related_document}`}
                          className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                          <FileText className="w-3 h-3" /> View related document
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

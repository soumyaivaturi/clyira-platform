"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText, Shield, AlertTriangle, ChevronRight,
  Upload, RefreshCw, Lock, Zap, ClipboardCheck, TrendingUp,
} from "lucide-react";
import { readinessApi, documentsApi, assessmentsApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { ScoreRing, ScoreBar, ScoreBadge } from "@/components/shared/score-display";
import { DocStatusBadge } from "@/components/shared/badges";
import { timeAgo } from "@/lib/utils";

interface ReadinessDashboard {
  company_score: number;
  score_band: string;
  departments: { department: string; score: number; weight: number; document_count: number }[];
  total_documents: number;
  top_gaps: { missing_assessments: any[]; poor_scores: any[] };
  gap_count: number;
  data_integrity_holds: number;
  enforcement_matches_total: number;
  assessments_run_total: number;
  findings_critical_total: number;
  findings_high_total: number;
  findings_medium_total: number;
  findings_low_total: number;
}

interface DocSummary {
  id: string; title: string; document_category: string; department_owner: string;
  latest_score: number | null; status: string; created_at: string;
}

interface RecentAssessment {
  id: string;
  document_id: string;
  document_title: string;
  document_category: string;
  clyira_score: number | null;
  adjusted_score: number | null;
  score_band: string | null;
  findings_critical: number;
  findings_high: number;
  data_integrity_hold: boolean;
  created_at: string;
}

function KpiCard({
  label, value, sub, icon: Icon, alert = false, warn = false,
}: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; alert?: boolean; warn?: boolean;
}) {
  return (
    <div className={`bg-card border rounded-xl p-5 ${alert ? "border-red-200 bg-red-50/30" : warn ? "border-amber-200 bg-amber-50/30" : ""}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</p>
        <Icon className={`w-4 h-4 ${alert ? "text-red-500" : warn ? "text-amber-500" : "text-muted-foreground"}`} />
      </div>
      <p className={`text-2xl font-bold tabular-nums ${alert ? "text-red-600" : warn ? "text-amber-600" : ""}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [readiness, setReadiness] = useState<ReadinessDashboard | null>(null);
  const [recentDocs, setRecentDocs] = useState<DocSummary[]>([]);
  const [recentAssessments, setRecentAssessments] = useState<RecentAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [rRes, dRes, aRes] = await Promise.all([
        readinessApi.dashboard(),
        documentsApi.list(),
        assessmentsApi.recent(8),
      ]);
      setReadiness(rRes.data);
      setRecentDocs((dRes.data.documents ?? []).slice(0, 6));
      setRecentAssessments(aRes.data.assessments ?? []);
    } catch {
      setError("Could not load dashboard data. Please refresh or sign in again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const score = readiness?.company_score;
  const totalFindings = (readiness?.findings_critical_total ?? 0)
    + (readiness?.findings_high_total ?? 0)
    + (readiness?.findings_medium_total ?? 0)
    + (readiness?.findings_low_total ?? 0);

  // Severity bar widths
  const sevPct = (n: number) => totalFindings > 0 ? Math.round((n / totalFindings) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Quality intelligence overview · {user?.company_id ? "Company workspace" : ""}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* DI Hold Banner */}
      {(readiness?.data_integrity_holds ?? 0) > 0 && (
        <div className="bg-red-50 border border-red-300 rounded-lg px-4 py-3 flex items-start gap-3">
          <Lock className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-800">
              {readiness!.data_integrity_holds} Data Integrity Hold{readiness!.data_integrity_holds > 1 ? "s" : ""} Active
            </p>
            <p className="text-xs text-red-700 mt-0.5">
              Documents with critical ALCOA+ findings have their scores capped at 50. Resolve findings to lift holds.
            </p>
          </div>
          <Link href="/readiness" className="ml-auto text-xs text-red-700 hover:underline flex-shrink-0 whitespace-nowrap">
            View gaps →
          </Link>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Clyira Score */}
        <div className="bg-card border rounded-xl p-5 flex items-center gap-4 lg:col-span-1">
          <ScoreRing score={score} size="sm" showBand={false} />
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Clyira Score</p>
            <p className="text-2xl font-bold tabular-nums mt-0.5">
              {score != null ? score.toFixed(1) : "—"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{readiness?.score_band ?? "Not assessed"}</p>
          </div>
        </div>

        <KpiCard
          label="Documents"
          value={readiness?.total_documents ?? "—"}
          sub={readiness ? `${readiness.top_gaps.missing_assessments.length} pending assessment` : "Loading…"}
          icon={FileText}
        />

        <KpiCard
          label="Assessments Run"
          value={readiness?.assessments_run_total ?? "—"}
          sub={`${readiness?.departments.length ?? 0} departments covered`}
          icon={TrendingUp}
        />

        <KpiCard
          label="Enforcement Hits"
          value={readiness?.enforcement_matches_total ?? "—"}
          sub="FDA Warning Letter patterns"
          icon={Zap}
          warn={(readiness?.enforcement_matches_total ?? 0) > 0}
        />

        <KpiCard
          label="DI Holds"
          value={readiness?.data_integrity_holds ?? "—"}
          sub={(readiness?.data_integrity_holds ?? 0) > 0 ? "Score caps applied" : "No active holds"}
          icon={Lock}
          alert={(readiness?.data_integrity_holds ?? 0) > 0}
        />
      </div>

      {/* Finding Severity Strip */}
      {totalFindings > 0 && (
        <div className="bg-card border rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-semibold text-sm">Portfolio Finding Severity</h2>
              <p className="text-xs text-muted-foreground mt-0.5">{totalFindings} total findings across all assessed documents</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span><span className="inline-block w-2 h-2 rounded-sm bg-red-600 mr-1" />{readiness!.findings_critical_total} Critical</span>
              <span><span className="inline-block w-2 h-2 rounded-sm bg-orange-500 mr-1" />{readiness!.findings_high_total} High</span>
              <span><span className="inline-block w-2 h-2 rounded-sm bg-amber-400 mr-1" />{readiness!.findings_medium_total} Medium</span>
              <span><span className="inline-block w-2 h-2 rounded-sm bg-blue-400 mr-1" />{readiness!.findings_low_total} Low</span>
            </div>
          </div>
          <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
            {sevPct(readiness!.findings_critical_total) > 0 && (
              <div className="bg-red-600 rounded-l-full" style={{ width: `${sevPct(readiness!.findings_critical_total)}%` }} title={`Critical: ${readiness!.findings_critical_total}`} />
            )}
            {sevPct(readiness!.findings_high_total) > 0 && (
              <div className="bg-orange-500" style={{ width: `${sevPct(readiness!.findings_high_total)}%` }} title={`High: ${readiness!.findings_high_total}`} />
            )}
            {sevPct(readiness!.findings_medium_total) > 0 && (
              <div className="bg-amber-400" style={{ width: `${sevPct(readiness!.findings_medium_total)}%` }} title={`Medium: ${readiness!.findings_medium_total}`} />
            )}
            {sevPct(readiness!.findings_low_total) > 0 && (
              <div className="bg-blue-400 rounded-r-full" style={{ width: `${sevPct(readiness!.findings_low_total)}%` }} title={`Low: ${readiness!.findings_low_total}`} />
            )}
          </div>
          {(readiness!.findings_critical_total > 0 || readiness!.findings_high_total > 0) && (
            <p className="text-xs text-red-700 mt-2">
              {readiness!.findings_critical_total + readiness!.findings_high_total} critical/high findings require attention.{" "}
              <Link href="/readiness" className="underline">View gaps →</Link>
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Department Heatmap */}
        <div className="lg:col-span-2 bg-card border rounded-xl p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-sm">Department Readiness</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Weighted Clyira Score by department</p>
            </div>
            <Link href="/readiness" className="text-xs text-primary hover:underline flex items-center gap-1">
              Full report <ChevronRight className="w-3 h-3" />
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1,2,3,4,5].map(i => (
                <div key={i} className="h-7 bg-muted animate-pulse rounded" />
              ))}
            </div>
          ) : readiness?.departments.length ? (
            <div className="space-y-2.5">
              {readiness.departments
                .sort((a, b) => a.score - b.score)
                .map((d) => (
                  <ScoreBar
                    key={d.department}
                    score={d.score}
                    label={`${d.department} (${d.document_count})`}
                    weight={d.weight}
                  />
                ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Shield className="w-8 h-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No department data yet.</p>
              <p className="text-xs text-muted-foreground mt-0.5">Upload and assess documents to see scores by department.</p>
              <Link href="/documents" className="mt-3 text-xs text-primary hover:underline">Upload a document →</Link>
            </div>
          )}
        </div>

        {/* Quick Actions + Top Gaps */}
        <div className="space-y-4">
          <div className="bg-card border rounded-xl p-5">
            <h2 className="font-semibold text-sm mb-3">Quick Actions</h2>
            <div className="space-y-2">
              <Link
                href="/documents"
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg border hover:bg-accent transition-colors text-sm"
              >
                <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Upload className="w-3.5 h-3.5 text-primary" />
                </div>
                <span>Upload &amp; assess a document</span>
              </Link>
              <Link
                href="/readiness"
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg border hover:bg-accent transition-colors text-sm"
              >
                <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Shield className="w-3.5 h-3.5 text-primary" />
                </div>
                <span>Run mock inspection</span>
              </Link>
              <Link
                href="/inspections"
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg border hover:bg-accent transition-colors text-sm"
              >
                <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <ClipboardCheck className="w-3.5 h-3.5 text-primary" />
                </div>
                <span>View inspections</span>
              </Link>
            </div>
          </div>

          {(readiness?.top_gaps.poor_scores.length ?? 0) > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-5">
              <h2 className="font-semibold text-sm text-red-800 mb-3 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Attention Required
              </h2>
              <div className="space-y-2">
                {readiness!.top_gaps.poor_scores.slice(0, 3).map((g: any) => (
                  <Link key={g.document_id} href={`/documents/${g.document_id}`} className="block">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-red-800 font-medium truncate mr-2">{g.title}</span>
                      <ScoreBadge score={g.score} />
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {(readiness?.top_gaps.missing_assessments.length ?? 0) > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
              <h2 className="font-semibold text-sm text-amber-800 mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Pending Assessment
              </h2>
              <div className="space-y-1.5">
                {readiness!.top_gaps.missing_assessments.slice(0, 3).map((g: any) => (
                  <Link key={g.document_id} href={`/documents/${g.document_id}`} className="block text-xs text-amber-800 hover:underline truncate">
                    {g.title}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <div className="bg-card border rounded-xl">
          <div className="px-5 py-4 border-b flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-sm">Recent Documents</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Latest uploads</p>
            </div>
            <Link href="/documents" className="text-xs text-primary hover:underline flex items-center gap-1">
              View all <ChevronRight className="w-3 h-3" />
            </Link>
          </div>

          {loading ? (
            <div className="divide-y">
              {[1,2,3,4].map(i => (
                <div key={i} className="flex items-center gap-4 px-5 py-3 animate-pulse">
                  <div className="w-8 h-8 bg-muted rounded-lg flex-shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3.5 bg-muted rounded w-3/4" />
                    <div className="h-3 bg-muted rounded w-1/3" />
                  </div>
                  <div className="w-12 h-5 bg-muted rounded-full" />
                </div>
              ))}
            </div>
          ) : recentDocs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <FileText className="w-8 h-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No documents yet.</p>
              <Link href="/documents" className="text-xs text-primary hover:underline mt-1">Upload your first document →</Link>
            </div>
          ) : (
            <div className="divide-y">
              {recentDocs.map((doc) => (
                <Link
                  key={doc.id}
                  href={`/documents/${doc.id}`}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-muted/40 transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-4 h-4 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{doc.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {doc.document_category ?? "—"} · {doc.department_owner ?? "Unassigned"} · {timeAgo(doc.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <ScoreBadge score={doc.latest_score} />
                    <DocStatusBadge status={doc.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Assessments */}
        <div className="bg-card border rounded-xl">
          <div className="px-5 py-4 border-b flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-sm">Recent Assessments</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Latest completed runs</p>
            </div>
            <Link href="/documents" className="text-xs text-primary hover:underline flex items-center gap-1">
              All documents <ChevronRight className="w-3 h-3" />
            </Link>
          </div>

          {loading ? (
            <div className="divide-y">
              {[1,2,3,4].map(i => (
                <div key={i} className="flex items-center gap-4 px-5 py-3 animate-pulse">
                  <div className="w-8 h-8 bg-muted rounded-lg flex-shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3.5 bg-muted rounded w-3/4" />
                    <div className="h-3 bg-muted rounded w-1/3" />
                  </div>
                  <div className="w-10 h-6 bg-muted rounded-full" />
                </div>
              ))}
            </div>
          ) : recentAssessments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ClipboardCheck className="w-8 h-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No assessments yet.</p>
              <p className="text-xs text-muted-foreground mt-0.5">Run an assessment from the Documents page.</p>
            </div>
          ) : (
            <div className="divide-y">
              {recentAssessments.map((a) => (
                <Link
                  key={a.id}
                  href={`/documents/${a.document_id}`}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-muted/40 transition-colors"
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    a.data_integrity_hold ? "bg-red-100" : "bg-emerald-50"
                  }`}>
                    <ClipboardCheck className={`w-4 h-4 ${a.data_integrity_hold ? "text-red-500" : "text-emerald-600"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{a.document_title}</p>
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                      <span className="text-xs text-muted-foreground">{a.document_category ?? "—"}</span>
                      {(a.findings_critical > 0 || a.findings_high > 0) && (
                        <span className="text-[10px] font-medium text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded">
                          {a.findings_critical > 0 ? `${a.findings_critical}C` : ""}
                          {a.findings_critical > 0 && a.findings_high > 0 ? " " : ""}
                          {a.findings_high > 0 ? `${a.findings_high}H` : ""}
                        </span>
                      )}
                      {a.data_integrity_hold && (
                        <span className="text-[10px] font-medium text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                          <Lock className="w-2.5 h-2.5" /> DI Hold
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">· {timeAgo(a.created_at)}</span>
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    <ScoreBadge score={a.adjusted_score ?? a.clyira_score} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

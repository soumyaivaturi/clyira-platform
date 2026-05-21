"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText, Shield, Radio, TrendingUp, TrendingDown,
  AlertTriangle, ChevronRight, Upload, Plus, RefreshCw,
} from "lucide-react";
import { readinessApi, documentsApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { ScoreRing, ScoreBar, ScoreBadge } from "@/components/shared/score-display";
import { SeverityBadge, DocStatusBadge } from "@/components/shared/badges";
import { formatDate, timeAgo } from "@/lib/utils";

interface ReadinessDashboard {
  company_score: number;
  score_band: string;
  departments: { department: string; score: number; weight: number; document_count: number }[];
  total_documents: number;
  top_gaps: { missing_assessments: any[]; poor_scores: any[] };
  gap_count: number;
}

interface DocSummary {
  id: string; title: string; document_category: string; department_owner: string;
  latest_score: number | null; status: string; created_at: string;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [readiness, setReadiness] = useState<ReadinessDashboard | null>(null);
  const [recentDocs, setRecentDocs] = useState<DocSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [rRes, dRes] = await Promise.all([
        readinessApi.dashboard(),
        documentsApi.list(),
      ]);
      setReadiness(rRes.data);
      setRecentDocs((dRes.data.documents ?? []).slice(0, 6));
    } catch {
      setError("Could not load dashboard data. Please refresh the page or sign in again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const totalFindings = 0; // will come from API later
  const score = readiness?.company_score;

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

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Clyira Score */}
        <div className="bg-card border rounded-xl p-5 flex items-center gap-4">
          <ScoreRing score={score} size="sm" showBand={false} />
          <div>
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Clyira Score</p>
            <p className="text-2xl font-bold tabular-nums mt-0.5">
              {score != null ? score.toFixed(1) : "—"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{readiness?.score_band ?? "Not assessed"}</p>
          </div>
        </div>

        {/* Documents */}
        <div className="bg-card border rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Documents</p>
            <FileText className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-2xl font-bold tabular-nums">{readiness?.total_documents ?? "—"}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {readiness ? `${readiness.top_gaps.missing_assessments.length} pending assessment` : "Loading…"}
          </p>
        </div>

        {/* Gap Count */}
        <div className="bg-card border rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Compliance Gaps</p>
            <AlertTriangle className="w-4 h-4 text-score-moderate" />
          </div>
          <p className="text-2xl font-bold tabular-nums">{readiness?.gap_count ?? "—"}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {readiness?.top_gaps.poor_scores.length ? `${readiness.top_gaps.poor_scores.length} documents below threshold` : "Across all departments"}
          </p>
        </div>

        {/* Departments */}
        <div className="bg-card border rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Depts Assessed</p>
            <Shield className="w-4 h-4 text-primary" />
          </div>
          <p className="text-2xl font-bold tabular-nums">{readiness?.departments.length ?? "—"}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {readiness?.departments.length ? "Department scores available" : "Upload documents to begin"}
          </p>
        </div>
      </div>

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
                .sort((a, b) => b.score - a.score)
                .map((d) => (
                  <ScoreBar
                    key={d.department}
                    score={d.score}
                    label={d.department}
                    weight={d.weight}
                  />
                ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Shield className="w-8 h-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No department data yet.</p>
              <p className="text-xs text-muted-foreground mt-0.5">Upload and assess documents to see scores.</p>
            </div>
          )}
        </div>

        {/* Quick Actions */}
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
                <span>Upload a document</span>
              </Link>
              <Link
                href="/documents"
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg border hover:bg-accent transition-colors text-sm"
              >
                <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Plus className="w-3.5 h-3.5 text-primary" />
                </div>
                <span>AI Document Creator</span>
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
                  <Radio className="w-3.5 h-3.5 text-primary" />
                </div>
                <span>Start new inspection</span>
              </Link>
            </div>
          </div>

          {/* Top Gaps */}
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
        </div>
      </div>

      {/* Recent Documents */}
      <div className="bg-card border rounded-xl">
        <div className="px-5 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-sm">Recent Documents</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Latest uploads and assessments</p>
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
    </div>
  );
}

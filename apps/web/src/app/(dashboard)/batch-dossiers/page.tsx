"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Plus, FlaskConical, CheckCircle2, AlertCircle, Clock, XCircle,
  ChevronRight, Search, Filter, RefreshCw,
} from "lucide-react";
import { batchDossiersApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Dossier {
  id: string;
  lot_number: string;
  product_name: string;
  dosage_form?: string;
  status: string;
  readiness_status?: string;
  readiness_score?: number;
  readiness_band?: string;
  record_family: string;
  product_type: string;
  is_sterile: boolean;
  batch_purpose: string;
  manufacturing_date?: string;
  gates: {
    evidence_complete: boolean;
    data_integrity_ok: boolean;
    all_findings_addressed: boolean;
    gray_findings_resolved: boolean;
  };
  documents: Array<{ role: string }>;
  created_at: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  draft:                  { label: "Draft",              color: "text-gray-500 bg-gray-100",         icon: Clock },
  under_review:           { label: "Under Review",       color: "text-blue-700 bg-blue-50",           icon: Clock },
  pending_disposition:    { label: "Pending Disposition",color: "text-amber-700 bg-amber-50",         icon: AlertCircle },
  released:               { label: "Released",           color: "text-emerald-700 bg-emerald-50",     icon: CheckCircle2 },
  conditionally_released: { label: "Cond. Released",     color: "text-teal-700 bg-teal-50",           icon: CheckCircle2 },
  on_hold:                { label: "On Hold",            color: "text-amber-700 bg-amber-100",        icon: AlertCircle },
  rejected:               { label: "Rejected",           color: "text-red-700 bg-red-50",             icon: XCircle },
  reopened:               { label: "Reopened",           color: "text-orange-700 bg-orange-50",       icon: RefreshCw },
};

const READINESS_CONFIG: Record<string, { label: string; color: string }> = {
  ready:       { label: "Ready",          color: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  conditional: { label: "Conditional",   color: "text-amber-700 bg-amber-50 border-amber-200" },
  not_ready:   { label: "Not Ready",     color: "text-red-700 bg-red-50 border-red-200" },
  hold:        { label: "Hold",          color: "text-red-800 bg-red-100 border-red-300" },
};

const RECORD_FAMILY_LABELS: Record<string, string> = {
  pharma_bpr:     "Pharma BPR",
  api_batch:      "API Batch",
  biologics_batch:"Biologics BPR",
  sterile_batch:  "Sterile BPR",
  device_dhr:     "Device DHR",
  supplement_bpr: "Supplement BPR",
  cell_therapy:   "Cell Therapy",
  cdmo_package:   "CDMO Package",
};

function GateIndicator({ pass, label }: { pass: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1" title={label}>
      <div className={`w-2 h-2 rounded-full ${pass ? "bg-emerald-500" : "bg-red-400"}`} />
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BatchDossiersPage() {
  const [dossiers, setDossiers] = useState<Dossier[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");

  const load = async () => {
    setLoading(true);
    try {
      const res = await batchDossiersApi.list();
      setDossiers(res.data);
    } catch {
      setDossiers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = dossiers.filter((d) => {
    const matchSearch = !search ||
      d.lot_number.toLowerCase().includes(search.toLowerCase()) ||
      d.product_name.toLowerCase().includes(search.toLowerCase());
    const matchStatus = filterStatus === "all" || d.status === filterStatus;
    return matchSearch && matchStatus;
  });

  const stats = {
    total: dossiers.length,
    underReview: dossiers.filter(d => d.status === "under_review").length,
    pendingDisposition: dossiers.filter(d => d.status === "pending_disposition").length,
    released: dossiers.filter(d => ["released", "conditionally_released"].includes(d.status)).length,
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-primary" />
            Batch & Lot Record Review
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            AI-assisted review of executed production records — MBR, BPR, DHR
          </p>
        </div>
        <Link
          href="/batch-dossiers/new"
          className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Dossier
        </Link>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Dossiers", value: stats.total, color: "text-foreground" },
          { label: "Under Review", value: stats.underReview, color: "text-blue-600" },
          { label: "Pending Disposition", value: stats.pendingDisposition, color: "text-amber-600" },
          { label: "Released", value: stats.released, color: "text-emerald-600" },
        ].map((s) => (
          <div key={s.label} className="bg-card border rounded-xl p-4">
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search lot or product..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="border rounded-lg text-sm px-3 py-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft</option>
            <option value="under_review">Under Review</option>
            <option value="pending_disposition">Pending Disposition</option>
            <option value="released">Released</option>
            <option value="on_hold">On Hold</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-16 text-muted-foreground text-sm">Loading dossiers…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <FlaskConical className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm font-medium text-muted-foreground">
            {dossiers.length === 0 ? "No dossiers yet" : "No dossiers match your filters"}
          </p>
          {dossiers.length === 0 && (
            <Link
              href="/batch-dossiers/new"
              className="inline-flex items-center gap-1.5 mt-3 text-sm text-primary hover:underline"
            >
              <Plus className="w-4 h-4" /> Create your first dossier
            </Link>
          )}
        </div>
      ) : (
        <div className="bg-card border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground text-xs">Lot / Product</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground text-xs">Type</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground text-xs">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground text-xs">Readiness</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground text-xs">Gates</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground text-xs">Docs</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((d, i) => {
                const statusCfg = STATUS_CONFIG[d.status] ?? STATUS_CONFIG.draft;
                const StatusIcon = statusCfg.icon;
                const readinessCfg = d.readiness_status ? READINESS_CONFIG[d.readiness_status] : null;

                return (
                  <tr key={d.id} className={`border-b last:border-0 hover:bg-muted/20 transition-colors ${i % 2 === 0 ? "" : "bg-muted/10"}`}>
                    <td className="px-4 py-3">
                      <div className="font-medium">{d.lot_number}</div>
                      <div className="text-xs text-muted-foreground truncate max-w-[180px]">
                        {d.product_name}
                        {d.is_sterile && <span className="ml-1 text-[10px] px-1 bg-blue-100 text-blue-700 rounded">Sterile</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-1.5 py-0.5 bg-muted rounded text-muted-foreground">
                        {RECORD_FAMILY_LABELS[d.record_family] ?? d.record_family}
                      </span>
                      {d.batch_purpose !== "commercial" && (
                        <div className="text-[10px] text-muted-foreground mt-0.5 capitalize">{d.batch_purpose}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${statusCfg.color}`}>
                        <StatusIcon className="w-3 h-3" />
                        {statusCfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {readinessCfg ? (
                        <div>
                          <span className={`inline-flex text-xs font-medium px-2 py-0.5 rounded border ${readinessCfg.color}`}>
                            {readinessCfg.label}
                          </span>
                          {d.readiness_score !== null && d.readiness_score !== undefined && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">{d.readiness_score.toFixed(1)}</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        <GateIndicator pass={d.gates.evidence_complete} label="Evidence" />
                        <GateIndicator pass={d.gates.data_integrity_ok} label="Data integrity" />
                        <GateIndicator pass={d.gates.all_findings_addressed} label="Findings" />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {d.documents.length} doc{d.documents.length !== 1 ? "s" : ""}
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/batch-dossiers/${d.id}`} className="flex items-center gap-1 text-primary text-xs hover:underline">
                        Open <ChevronRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

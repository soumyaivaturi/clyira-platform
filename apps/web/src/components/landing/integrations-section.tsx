"use client";

import { AnimateIn } from "@/components/landing/animate-in";
import {
  Database, FileSpreadsheet, FlaskConical, Wrench,
  GraduationCap, Factory, BarChart3, Thermometer,
  FolderOpen, FileText, Globe, ShieldCheck,
  ArrowRight, Layers,
} from "lucide-react";

/* ── system categories shown on the homepage ────────────────────────────── */
const systemCategories = [
  {
    icon: ShieldCheck,
    title: "Quality Management (eQMS)",
    systems: ["Veeva Vault QMS", "MasterControl", "TrackWise Digital", "Qualio", "ETQ Reliance", "Dot Compliance", "Greenlight Guru"],
    color: "text-clyira-600",
    bg: "bg-clyira-50",
  },
  {
    icon: FileText,
    title: "Document Management (EDMS)",
    systems: ["Veeva QualityDocs", "MasterControl Docs", "OpenText Documentum", "SharePoint", "Ennov Doc"],
    color: "text-violet-600",
    bg: "bg-violet-50",
  },
  {
    icon: FlaskConical,
    title: "Lab Information (LIMS)",
    systems: ["LabWare", "STARLIMS", "LabVantage", "Veeva Vault LIMS", "Sapio LIMS", "SampleManager"],
    color: "text-sky-600",
    bg: "bg-sky-50",
  },
  {
    icon: Database,
    title: "ERP Systems",
    systems: ["SAP S/4HANA", "Oracle NetSuite", "Oracle Cloud ERP", "Microsoft Dynamics 365", "Infor CloudSuite"],
    color: "text-emerald-600",
    bg: "bg-emerald-50",
  },
  {
    icon: Factory,
    title: "Manufacturing (MES)",
    systems: ["Werum PAS-X", "Rockwell PharmaSuite", "Emerson Syncade", "Siemens Opcenter", "POMS", "Tulip"],
    color: "text-amber-600",
    bg: "bg-amber-50",
  },
  {
    icon: Wrench,
    title: "Equipment & Calibration",
    systems: ["Blue Mountain RAM", "IBM Maximo", "SAP Plant Maintenance", "eMaint", "Limble CMMS"],
    color: "text-rose-600",
    bg: "bg-rose-50",
  },
  {
    icon: GraduationCap,
    title: "Training (LMS)",
    systems: ["ComplianceWire", "Veeva Vault Training", "Cornerstone", "MasterControl Training", "Absorb"],
    color: "text-indigo-600",
    bg: "bg-indigo-50",
  },
  {
    icon: Thermometer,
    title: "Environmental Monitoring",
    systems: ["Vaisala viewLinc", "MODA-EM", "Particle Measuring Systems", "Ellab", "Rotronic"],
    color: "text-teal-600",
    bg: "bg-teal-50",
  },
  {
    icon: BarChart3,
    title: "Electronic Lab Notebook",
    systems: ["Benchling", "IDBS E-WorkBook", "Revvity Signals", "Sapio ELN", "Dotmatics"],
    color: "text-orange-600",
    bg: "bg-orange-50",
  },
  {
    icon: Globe,
    title: "Regulatory (RIM)",
    systems: ["Veeva Vault RIM", "ArisGlobal LifeSphere", "EXTEDO EURS", "Freyr iREADY"],
    color: "text-cyan-600",
    bg: "bg-cyan-50",
  },
  {
    icon: FolderOpen,
    title: "File Storage & Collaboration",
    systems: ["SharePoint / OneDrive", "Google Drive", "Box", "Dropbox Business", "AWS S3", "Azure Blob", "SFTP"],
    color: "text-gray-600",
    bg: "bg-gray-100",
  },
  {
    icon: FileSpreadsheet,
    title: "Spreadsheets & Manual Logs",
    systems: ["Excel / CSV", "Google Sheets", "Access databases", "PDF forms", "Paper (OCR)"],
    color: "text-green-600",
    bg: "bg-green-50",
  },
];

/* ── The 360° evidence story ─────────────────────────────────────────────── */
const evidenceChecks = [
  { source: "QMS", finding: "Same-lot deviation open — not addressed in investigation", severity: "critical" },
  { source: "CMMS", finding: "Equipment PM overdue by 14 days at time of batch", severity: "critical" },
  { source: "LMS", finding: "Analyst GMP training expired 3 months before event", severity: "high" },
  { source: "LIMS", finding: "3 invalid assay runs on same method in last 60 days", severity: "high" },
  { source: "EMS", finding: "EM excursion in same cleanroom on same day", severity: "medium" },
];

/* ── Component ───────────────────────────────────────────────────────────── */
export function IntegrationsSection() {
  return (
    <>
      {/* ── EVIDENCE FABRIC SPOTLIGHT (DARK SECTION) ──────────────────────── */}
      <section className="bg-[#0d0d0d] py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

            <AnimateIn direction="left">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs font-semibold text-clyira-400 mb-6">
                  <Layers className="w-3.5 h-3.5" />
                  Evidence Fabric
                </div>
                <h2 className="text-4xl sm:text-5xl font-bold text-white leading-tight mb-6">
                  Your document says<br />
                  <span className="text-clyira-400">&ldquo;analyst error.&rdquo;</span><br />
                  <span className="text-gray-500 text-3xl sm:text-4xl">Clyira checks everything else.</span>
                </h2>
                <p className="text-gray-400 text-lg leading-relaxed mb-8">
                  Connect your QMS, LIMS, CMMS, LMS, MES, and ERP. Clyira cross-references every
                  document claim against evidence from across your entire quality ecosystem — finding
                  the gaps a document-only reviewer would miss.
                </p>
                <a
                  href="/auth/register"
                  className="inline-flex items-center gap-2 text-sm font-semibold text-clyira-400 hover:text-clyira-300 transition-colors"
                >
                  See the 360° evidence panel
                  <ArrowRight className="w-4 h-4" />
                </a>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-white/10">
                  <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  <span className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
                    5 evidence gaps found — CAPA-2026-07
                  </span>
                </div>
                <p className="text-[10px] text-gray-500 italic">
                  Document claims &ldquo;root cause: analyst error&rdquo; — Clyira found unaddressed evidence:
                </p>
                <div className="space-y-2">
                  {evidenceChecks.map((item) => (
                    <div key={item.finding} className="bg-white/5 border border-white/10 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wide">
                          {item.source}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                          item.severity === "critical" ? "bg-red-500/20 text-red-400" :
                          item.severity === "high" ? "bg-amber-500/20 text-amber-400" :
                          "bg-yellow-500/20 text-yellow-400"
                        }`}>
                          {item.severity}
                        </span>
                      </div>
                      <p className="text-xs text-gray-300 leading-relaxed">{item.finding}</p>
                    </div>
                  ))}
                </div>
                <div className="border-t border-white/10 pt-3 text-[10px] text-gray-600">
                  Evidence collected from 5 enterprise systems in real time
                </div>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── INTEGRATIONS GRID ────────────────────────────────────────────── */}
      <section id="integrations" className="py-24 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
                Connects to your entire quality ecosystem
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                60+ systems. One compliance view.
              </h2>
              <p className="text-gray-500 max-w-2xl mx-auto text-lg">
                Clyira ingests evidence from every system in your life sciences stack —
                QMS, LIMS, ERP, MES, CMMS, LMS, ELN, EMS, and more — so document
                claims are always verified against the full picture.
              </p>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {systemCategories.map((cat, i) => (
              <AnimateIn key={cat.title} delay={i * 40} direction="up">
                <div className="group h-full p-5 rounded-xl border border-gray-200 bg-white hover:border-clyira-200 hover:shadow-md transition-all">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`w-9 h-9 rounded-lg ${cat.bg} flex items-center justify-center shrink-0`}>
                      <cat.icon className={`w-4.5 h-4.5 ${cat.color}`} />
                    </div>
                    <h3 className="font-semibold text-gray-900 text-sm leading-snug">{cat.title}</h3>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {cat.systems.map((sys) => (
                      <span key={sys} className="text-[11px] text-gray-500 bg-gray-50 border border-gray-100 rounded px-2 py-0.5">
                        {sys}
                      </span>
                    ))}
                  </div>
                </div>
              </AnimateIn>
            ))}
          </div>

          <AnimateIn delay={300}>
            <div className="text-center mt-12">
              <p className="text-sm text-gray-400 mb-4">
                Don&apos;t see your system? Clyira also supports CSV/Excel import, API push, webhooks, and custom connectors.
              </p>
              <a
                href="/auth/register"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-clyira-600 text-white font-semibold text-sm hover:bg-clyira-700 transition-colors shadow-sm"
              >
                Start for free
                <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          </AnimateIn>
        </div>
      </section>
    </>
  );
}

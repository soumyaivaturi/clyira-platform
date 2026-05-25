import Link from "next/link";
import {
  Shield, FileText, Radio, Zap,
  CheckCircle, ArrowRight, Globe, AlertTriangle,
  BarChart3, Lock, ChevronRight,
} from "lucide-react";
import { AnimateIn } from "@/components/landing/animate-in";
import { CountUp } from "@/components/landing/count-up";
import { MarqueeStrip } from "@/components/landing/marquee-strip";
import { LandingNav } from "@/components/landing/landing-nav";

// ── Data ──────────────────────────────────────────────────────────────────────

const features = [
  {
    icon: FileText,
    title: "11-Level Document Assessment",
    description:
      "Every SOP, CAPA, ATM, and Validation report scored against FDA, ICH, and ISO requirements — with exact regulatory citations linking each finding to the source.",
    color: "text-clyira-600",
    bg: "bg-clyira-50",
  },
  {
    icon: Shield,
    title: "Audit Readiness Score",
    description:
      "Department-level Clyira Score updated in real time. See exactly which documents are pulling your score down and get a prioritized remediation plan.",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
  },
  {
    icon: Radio,
    title: "Inspection Copilot",
    description:
      "Live AI support during FDA, EMA, or PMDA inspections. Log inspector requests, draft responses, track outstanding items — all in one place.",
    color: "text-violet-600",
    bg: "bg-violet-50",
  },
  {
    icon: AlertTriangle,
    title: "Enforcement Intelligence",
    description:
      "Warning letters, 483 observations, and consent decrees automatically mapped to your documents. Know which regulations are being actively enforced.",
    color: "text-amber-600",
    bg: "bg-amber-50",
  },
  {
    icon: Zap,
    title: "AI Document Creator",
    description:
      "Generate SOPs, CAPAs, and ATMs that arrive pre-scored above your threshold. Guided by your DTAP profile and regulatory sub-sector.",
    color: "text-rose-600",
    bg: "bg-rose-50",
  },
  {
    icon: Globe,
    title: "Multi-Agency Coverage",
    description:
      "FDA 21 CFR Parts 210/211/820, EMA GMP Annex, ICH Q7-Q12, ISO 13485, USP, and AABB standards — all in a single assessment run.",
    color: "text-sky-600",
    bg: "bg-sky-50",
  },
];

const steps = [
  {
    number: "01",
    title: "Upload your documents",
    description: "Drag and drop any quality document — SOP, CAPA, ATM, Validation Protocol, Batch Record. PDF, DOCX, and Excel supported.",
  },
  {
    number: "02",
    title: "AI runs your assessment",
    description: "Clyira's engine scores the document across 11 regulatory levels in seconds, cross-referencing against 2,000+ regulatory citations.",
  },
  {
    number: "03",
    title: "Act on your score",
    description: "Review findings, acknowledge gaps, respond to each observation, and watch your Clyira Score climb before your next audit.",
  },
];

const plans = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    description: "For small QA teams exploring AI-powered compliance.",
    features: [
      "10 document assessments / month",
      "2 user accounts",
      "L1–L5 assessment levels",
      "Basic readiness dashboard",
      "PDF & DOCX support",
    ],
    cta: "Get started free",
    href: "/auth/register",
    highlighted: false,
  },
  {
    name: "Professional",
    price: "$399",
    period: "/month",
    description: "For QA departments that need full regulatory coverage.",
    features: [
      "Unlimited document assessments",
      "10 user accounts",
      "Full L1–L11 assessment",
      "Enforcement intelligence layer",
      "Inspection Copilot",
      "AI Document Creator",
      "Priority support",
    ],
    cta: "Start 14-day trial",
    href: "/auth/register",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For multi-site organisations with complex compliance needs.",
    features: [
      "Unlimited everything",
      "SSO / SAML integration",
      "Custom regulatory corpus",
      "On-premise deployment option",
      "Dedicated QA success manager",
      "SLA & audit log exports",
    ],
    cta: "Talk to sales",
    href: "mailto:sales@clyira.ai",
    highlighted: false,
  },
];

const regulatoryBodies = ["FDA", "EMA", "ICH Q10", "PMDA", "Health Canada", "TGA", "ISO 13485", "USP", "21 CFR Part 11", "EudraLex Vol 4", "ICH Q7", "AABB", "WHO GMP"];

const complianceBadges = [
  { icon: Lock, label: "21 CFR Part 11" },
  { icon: Shield, label: "SOC 2 Type II" },
  { icon: CheckCircle, label: "GDPR Compliant" },
  { icon: BarChart3, label: "GxP Validated" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white font-sans">

      {/* ── ANNOUNCEMENT BAR ────────────────────────────────────────────────── */}
      <div className="bg-clyira-600 text-white text-center text-xs py-2.5 px-4">
        <span className="font-medium">New: L11 Inspection Readiness is now live — AI scoring against FDA inspection criteria.</span>
        <Link href="/auth/register" className="ml-2 font-bold underline underline-offset-2 hover:no-underline">
          Try it free →
        </Link>
      </div>

      {/* ── NAVIGATION ──────────────────────────────────────────────────────── */}
      <LandingNav />

      {/* ── HERO ────────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-white">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div
            className="absolute -top-64 -right-64 w-[700px] h-[700px] rounded-full opacity-[0.06]"
            style={{ background: "radial-gradient(circle, #7654c9, transparent 70%)" }}
          />
          <div
            className="absolute top-40 -left-32 w-[400px] h-[400px] rounded-full opacity-[0.04]"
            style={{ background: "radial-gradient(circle, #8977d7, transparent 70%)" }}
          />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-20">
          <div className="max-w-3xl mx-auto text-center">

            <AnimateIn delay={0}>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-clyira-200 bg-clyira-50 text-xs font-semibold text-clyira-700 mb-8">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                AI-Powered Regulatory Intelligence for Life Sciences
              </div>
            </AnimateIn>

            <AnimateIn delay={80}>
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1] text-gray-900 mb-6">
                Audit-ready.<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-clyira-600 to-violet-500">
                  Always.
                </span>
              </h1>
            </AnimateIn>

            <AnimateIn delay={160}>
              <p className="text-xl text-gray-500 leading-relaxed mb-10 max-w-2xl mx-auto">
                Clyira gives pharmaceutical, biotech, and medical device teams real-time AI document assessment,
                department-level readiness scores, and live inspection support — built for FDA, EMA, and ICH standards.
              </p>
            </AnimateIn>

            <AnimateIn delay={220}>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
                <Link
                  href="/auth/register"
                  className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-clyira-600 text-white font-semibold text-sm hover:bg-clyira-700 transition-colors shadow-sm"
                >
                  Start for free
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <Link
                  href="#features"
                  className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 rounded-lg border border-gray-200 text-gray-700 font-medium text-sm hover:bg-gray-50 transition-colors"
                >
                  See the platform
                </Link>
              </div>
            </AnimateIn>

            <AnimateIn delay={280}>
              <div className="flex flex-wrap items-center justify-center gap-6">
                {complianceBadges.map(({ icon: Icon, label }) => (
                  <div key={label} className="flex items-center gap-1.5 text-xs text-gray-400">
                    <Icon className="w-3.5 h-3.5" />
                    <span>{label}</span>
                  </div>
                ))}
              </div>
            </AnimateIn>
          </div>

          {/* Dashboard mockup */}
          <AnimateIn delay={120} direction="up" threshold={0.05}>
            <div className="mt-16 mx-auto max-w-4xl">
              <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-[0_20px_60px_-10px_rgba(118,84,201,0.12),0_4px_24px_-4px_rgba(0,0,0,0.08)]">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <div className="w-3 h-3 rounded-full bg-emerald-400" />
                  <div className="ml-4 flex-1 bg-white border border-gray-200 rounded text-xs text-center text-gray-400 py-0.5 px-2 max-w-xs mx-auto">
                    app.clyira.ai/dashboard
                  </div>
                </div>

                <div className="flex h-72 sm:h-80">
                  <div className="hidden sm:flex w-44 border-r border-gray-100 bg-gray-50/80 flex-col p-3 gap-1">
                    <div className="flex items-center gap-2 px-2 py-2 mb-2">
                      <div className="w-6 h-6 rounded bg-clyira-600 flex items-center justify-center">
                        <span className="text-white text-xs font-bold">C</span>
                      </div>
                      <span className="text-xs font-bold text-gray-900 tracking-wide">CLYIRA.AI</span>
                    </div>
                    {["Dashboard", "Documents", "Audit Readiness", "Inspections"].map((item, i) => (
                      <div key={item} className={`px-2 py-1.5 rounded text-xs font-medium ${i === 0 ? "bg-clyira-50 text-clyira-700" : "text-gray-500"}`}>
                        {item}
                      </div>
                    ))}
                  </div>

                  <div className="flex-1 p-4 overflow-hidden bg-gray-50/50">
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      {[
                        { label: "Clyira Score", value: "84.2", sub: "Compliant", subColor: "text-emerald-600" },
                        { label: "Documents", value: "47", sub: "3 pending", subColor: "text-gray-400" },
                        { label: "Gaps", value: "12", sub: "4 critical", subColor: "text-gray-400", valueColor: "text-amber-500" },
                      ].map((k) => (
                        <div key={k.label} className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
                          <div className="text-xs text-gray-400 mb-1">{k.label}</div>
                          <div className={`text-2xl font-bold ${k.valueColor ?? "text-gray-900"}`}>{k.value}</div>
                          <div className={`text-xs mt-0.5 font-medium ${k.subColor}`}>{k.sub}</div>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-2">
                      {[
                        { title: "SOP-042 — Batch Release", score: 91, band: "Compliant", color: "bg-emerald-500" },
                        { title: "CAPA-2026-07 — Sterility Deviation", score: 67, band: "Moderate", color: "bg-amber-500" },
                        { title: "ATM-018 — HPLC Method", score: 88, band: "Compliant", color: "bg-emerald-500" },
                      ].map((doc) => (
                        <div key={doc.title} className="flex items-center gap-3 bg-white border border-gray-100 rounded-lg px-3 py-2 shadow-sm">
                          <div className={`w-1.5 h-8 rounded-full ${doc.color}`} />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-gray-900 truncate">{doc.title}</div>
                            <div className="text-xs text-gray-400">{doc.band}</div>
                          </div>
                          <div className="text-sm font-bold text-gray-700 tabular-nums">{doc.score}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </AnimateIn>
        </div>
      </section>

      {/* ── MARQUEE STRIP ───────────────────────────────────────────────────── */}
      <div className="border-y border-gray-100 bg-gray-50 py-4">
        <p className="text-center text-[10px] font-semibold uppercase tracking-widest text-gray-300 mb-3">
          Regulatory standards covered
        </p>
        <MarqueeStrip items={regulatoryBodies} />
      </div>

      {/* ── IMPACT METRICS ──────────────────────────────────────────────────── */}
      <section className="bg-white border-b border-gray-100 py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <p className="text-center text-xs font-semibold uppercase tracking-widest text-gray-400 mb-12">
              The cost of the problem Clyira solves
            </p>
          </AnimateIn>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 text-center">
            {[
              { prefix: "", end: 74, suffix: "%", label: "of FDA Complete Response Letters cite documentation deficiencies", delay: 0 },
              { prefix: "", end: 65, suffix: "%", label: "of first-cycle FDA submissions require rework before approval", delay: 100 },
              { prefix: "$2–", end: 5, suffix: "M", label: "per site per year lost to compliance labor and rework costs", delay: 200 },
              { prefix: "6–", end: 12, suffix: " mo", label: "approval delays caused by documentation gaps", delay: 300 },
            ].map(({ prefix, end, suffix, label, delay }) => (
              <AnimateIn key={label} delay={delay} direction="up">
                <div className="px-4">
                  <div className="text-3xl sm:text-4xl font-bold text-clyira-600 mb-2 tabular-nums">
                    <CountUp end={end} prefix={prefix} suffix={suffix} />
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed">{label}</p>
                </div>
              </AnimateIn>
            ))}
          </div>

          <AnimateIn delay={200}>
            <p className="text-center text-sm text-gray-400 mt-10 font-medium">
              Clyira replaces reactive compliance fire drills with continuous, AI-validated quality intelligence.
            </p>
          </AnimateIn>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
                Platform capabilities
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                Everything your QA team needs.
              </h2>
              <p className="text-gray-500 max-w-2xl mx-auto text-lg">
                Purpose-built for life sciences — not a generic AI tool bolted onto a document repository.
              </p>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <AnimateIn key={f.title} delay={i * 60} direction="up">
                <div className="group h-full p-6 rounded-xl border border-gray-100 hover:border-clyira-100 hover:shadow-md transition-all">
                  <div className={`w-10 h-10 rounded-lg ${f.bg} flex items-center justify-center mb-4`}>
                    <f.icon className={`w-5 h-5 ${f.color}`} />
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{f.description}</p>
                </div>
              </AnimateIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── SPOTLIGHT: ENFORCEMENT INTELLIGENCE (DARK) ──────────────────────── */}
      <section className="bg-[#0d0d0d] py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

            <AnimateIn direction="left">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs font-semibold text-clyira-400 mb-6">
                  Enforcement Intelligence
                </div>
                <h2 className="text-4xl sm:text-5xl font-bold text-white leading-tight mb-6">
                  2,919 warning letters.<br />
                  <span className="text-clyira-400">Mapped to your docs.</span>
                </h2>
                <p className="text-gray-400 text-lg leading-relaxed mb-8">
                  Clyira's enforcement engine cross-references every active FDA Warning Letter pattern against your quality documents — so you know what's being cited before inspectors arrive.
                </p>
                <Link
                  href="/auth/register"
                  className="inline-flex items-center gap-2 text-sm font-semibold text-clyira-400 hover:text-clyira-300 transition-colors"
                >
                  See enforcement intelligence in action
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-white/10">
                  <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">3 FDA Pattern Matches Detected</span>
                </div>
                <div className="space-y-3">
                  {[
                    { doc: "SOP-042 Batch Release", obs: "Inadequate investigation into root cause of laboratory deviation — 21 CFR 211.192", severity: "Critical", color: "bg-red-500/20 text-red-400" },
                    { doc: "CAPA-2026-07", obs: "Failure to adequately assess the risk of distributed product — 21 CFR 211.198", severity: "High", color: "bg-amber-500/20 text-amber-400" },
                    { doc: "ATM-018 HPLC Method", obs: "Missing specific system suitability requirements — 21 CFR 211.68(b)", severity: "Medium", color: "bg-yellow-500/20 text-yellow-400" },
                  ].map((item) => (
                    <div key={item.doc} className="bg-white/5 border border-white/10 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-white">{item.doc}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ml-2 ${item.color}`}>
                          {item.severity}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 leading-relaxed">{item.obs}</p>
                    </div>
                  ))}
                </div>
                <div className="border-t border-white/10 pt-3 text-[10px] text-gray-600">
                  Matched against 2,919 FDA Warning Letter observations · Updated weekly
                </div>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── ASSESSMENT LEVELS ───────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

            <AnimateIn direction="left">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
                  Assessment engine
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-5">
                  11 levels. Zero guesswork.
                </h2>
                <p className="text-gray-500 mb-8 leading-relaxed">
                  Most QMS tools check formatting. Clyira goes deeper — from document structure and procedure completeness
                  all the way to regulatory enforceability and active enforcement action alignment.
                </p>
                <div className="space-y-2">
                  {[
                    { level: "L1–L3", label: "Structure, Format & Completeness" },
                    { level: "L4–L6", label: "Regulatory Alignment & Citation Accuracy" },
                    { level: "L7–L9", label: "Risk Assessment & CAPA Linkage" },
                    { level: "L10–L11", label: "Enforcement Actions & Inspectability" },
                  ].map((l, i) => (
                    <AnimateIn key={l.level} delay={i * 60} direction="left">
                      <div className="flex items-center gap-3 py-2">
                        <span className="text-xs font-bold text-clyira-600 w-14 shrink-0">{l.level}</span>
                        <div className="flex-1 h-px bg-gray-200" />
                        <span className="text-sm text-gray-700">{l.label}</span>
                      </div>
                    </AnimateIn>
                  ))}
                </div>
                <Link
                  href="/auth/register"
                  className="inline-flex items-center gap-2 mt-8 text-sm font-semibold text-clyira-600 hover:text-clyira-700"
                >
                  Run your first assessment free
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div className="bg-white rounded-2xl border shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">SOP-042 Assessment Result</p>
                    <p className="text-sm font-semibold text-gray-900 mt-0.5">Batch Release SOP — v3.2</p>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-emerald-600">91</div>
                    <div className="text-xs font-semibold text-emerald-600">Compliant</div>
                  </div>
                </div>

                <div className="space-y-2 mb-4">
                  {[
                    { label: "Document Structure", score: 98, color: "bg-emerald-500" },
                    { label: "Regulatory Citations", score: 94, color: "bg-emerald-500" },
                    { label: "CAPA Linkage", score: 87, color: "bg-emerald-500" },
                    { label: "Risk Assessment", score: 82, color: "bg-emerald-400" },
                    { label: "Enforceability", score: 91, color: "bg-emerald-500" },
                  ].map((row) => (
                    <div key={row.label} className="flex items-center gap-3">
                      <span className="text-xs text-gray-500 w-36 shrink-0">{row.label}</span>
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className={`h-full ${row.color} rounded-full`} style={{ width: `${row.score}%` }} />
                      </div>
                      <span className="text-xs font-semibold text-gray-700 w-8 text-right tabular-nums">{row.score}</span>
                    </div>
                  ))}
                </div>

                <div className="border-t pt-4">
                  <p className="text-xs font-semibold text-gray-700 mb-2">2 findings</p>
                  <div className="space-y-2">
                    <div className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold shrink-0">MOD</span>
                      <span className="text-gray-600">Section 4.2 does not reference 21 CFR 211.68 — electronic systems validation requirement.</span>
                    </div>
                    <div className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 px-1.5 py-0.5 rounded bg-clyira-50 text-clyira-700 font-semibold shrink-0">INFO</span>
                      <span className="text-gray-600">Deviation reference in Section 6 should cross-link to current CAPA register per ICH Q10 §3.2.</span>
                    </div>
                  </div>
                </div>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── SPOTLIGHT: INSPECTION COPILOT (LIGHT) ───────────────────────────── */}
      <section className="bg-white py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

            <AnimateIn direction="left">
              <div className="rounded-2xl border border-gray-200 bg-white shadow-xl p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                  <div>
                    <p className="text-xs font-bold text-gray-900">FDA Inspection — Day 2 of 3</p>
                    <p className="text-xs text-gray-400 mt-0.5">3 requests · 1 critical outstanding</p>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Active
                  </div>
                </div>

                <div className="space-y-2">
                  {[
                    { req: "Provide all batch records for Lot 2026-042A", time: "09:14", status: "done", critical: false },
                    { req: "Show deviation investigation for sterility failure", time: "10:31", status: "critical", critical: true },
                    { req: "Training records for QC analysts — last 12 months", time: "11:05", status: "open", critical: false },
                  ].map((r) => (
                    <div
                      key={r.req}
                      className={`flex items-start gap-3 p-3 rounded-lg border ${
                        r.critical ? "border-red-100 bg-red-50/50" : "border-gray-100 bg-gray-50/50"
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-gray-900 leading-snug">{r.req}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5">{r.time}</p>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ${
                        r.status === "done" ? "bg-emerald-100 text-emerald-700" :
                        r.status === "critical" ? "bg-red-100 text-red-700" :
                        "bg-gray-100 text-gray-600"
                      }`}>
                        {r.status === "done" ? "Done" : r.status === "critical" ? "Critical" : "Open"}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="bg-clyira-50 border border-clyira-100 rounded-xl p-4">
                  <p className="text-[10px] font-bold text-clyira-700 mb-2 uppercase tracking-wide">
                    AI Talking Points — Sterility Investigation
                  </p>
                  <ul className="space-y-1.5">
                    {[
                      "Root cause: contamination during environmental monitoring failure",
                      "CAPA-2026-07 initiated within 24h — documented in Section 4.2",
                      "No distributed product affected — batch quarantined immediately",
                    ].map((pt) => (
                      <li key={pt} className="flex items-start gap-1.5 text-[10px] text-clyira-700">
                        <span className="mt-0.5 shrink-0">·</span>
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-50 text-violet-700 text-xs font-semibold mb-6">
                  Inspection Copilot
                </div>
                <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 leading-tight mb-6">
                  The inspector knocks.<br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-clyira-600 to-violet-500">
                    You're already ready.
                  </span>
                </h2>
                <p className="text-gray-500 text-lg leading-relaxed mb-8">
                  Log every inspector request in real time. Get AI-generated talking points and document suggestions within seconds — then close the inspection with zero surprises.
                </p>
                <Link
                  href="/auth/register"
                  className="inline-flex items-center gap-2 text-sm font-semibold text-clyira-600 hover:text-clyira-700 transition-colors"
                >
                  Try Inspection Copilot free
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── INTEGRATIONS ────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-14">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
                System integrations
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                One platform. Every system.
              </h2>
              <p className="text-gray-500 max-w-2xl mx-auto text-lg">
                Your quality data lives in five different silos. Clyira connects them — so you get one unified view of compliance health across your entire operation.
              </p>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
            {[
              { code: "MES", name: "Manufacturing Execution", desc: "Batch records, production orders, and in-process controls flow directly into Clyira assessments." },
              { code: "LIMS", name: "Laboratory Information", desc: "OOS events, analytical results, and method validations pulled in automatically for L4 citation analysis." },
              { code: "VLMS", name: "Vendor & Supplier Mgmt", desc: "Supplier qualifications, AVL status, and supplier audits referenced in every risk-level assessment." },
              { code: "QMS", name: "Quality Management", desc: "CAPAs, deviations, and change controls bi-directionally synced — so findings map to live quality events." },
              { code: "ERP", name: "Enterprise Resource Planning", desc: "Batch disposition, inventory, and release decisions included in your cross-document compliance picture." },
              { code: "API", name: "Custom Integration", desc: "Any internal system connects via bearer-token REST API — create a key in Settings and start streaming data." },
            ].map((s, i) => (
              <AnimateIn key={s.code} delay={i * 60} direction="up">
                <div className="bg-white border border-gray-100 rounded-xl p-5 hover:border-clyira-100 hover:shadow-md transition-all">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-bold px-2 py-1 rounded-md bg-clyira-50 text-clyira-700 uppercase tracking-wide">{s.code}</span>
                  </div>
                  <p className="text-sm font-semibold text-gray-900 mb-1">{s.name}</p>
                  <p className="text-xs text-gray-500 leading-relaxed">{s.desc}</p>
                </div>
              </AnimateIn>
            ))}
          </div>

          <AnimateIn delay={200}>
            <div className="rounded-2xl bg-[#0d0d0d] p-10 flex flex-col md:flex-row items-center gap-8">
              <div className="flex-1">
                <p className="text-xs font-semibold uppercase tracking-widest text-clyira-400 mb-3">No more silos</p>
                <h3 className="text-2xl font-bold text-white mb-4">
                  One quality truth.<br />Across every system.
                </h3>
                <p className="text-gray-400 text-sm leading-relaxed">
                  When your MES flags a deviation, your LIMS logs an OOS event, and your QMS raises a CAPA — Clyira sees all three. It correlates signals across systems and surfaces a single, complete compliance picture you can walk into any inspection with.
                </p>
              </div>
              <div className="flex-shrink-0">
                <Link href="/auth/register"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-clyira-600 text-white font-semibold text-sm hover:bg-clyira-700 transition-colors shadow-sm">
                  Connect your systems
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </AnimateIn>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────────────────────────── */}
      <section id="how-it-works" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
                How it works
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                Upload. Assess. Fix. Repeat.
              </h2>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            <div className="hidden md:block absolute top-10 left-1/3 right-1/3 h-px bg-gray-200" />

            {steps.map((step, i) => (
              <AnimateIn key={step.number} delay={i * 100} direction="up">
                <div className="relative text-center">
                  <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-clyira-600 text-white mb-6 relative z-10 shadow-lg shadow-clyira-600/20">
                    <span className="text-2xl font-bold">{step.number}</span>
                  </div>
                  <h3 className="font-semibold text-gray-900 text-lg mb-3">{step.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{step.description}</p>
                </div>
              </AnimateIn>
            ))}
          </div>

          <AnimateIn delay={300}>
            <div className="mt-12 text-center">
              <Link
                href="/auth/register"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-clyira-600 text-white font-semibold text-sm hover:bg-clyira-700 transition-colors shadow-sm"
              >
                Try it now — it&apos;s free
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </AnimateIn>
        </div>
      </section>

      {/* ── TESTIMONIAL ─────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-[#0d0d0d]">
        <AnimateIn>
          <div className="max-w-3xl mx-auto text-center">
            <div className="flex justify-center mb-6">
              {[1,2,3,4,5].map(i => (
                <svg key={i} className="w-5 h-5 text-amber-400 fill-current" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
            </div>
            <blockquote className="text-2xl sm:text-3xl font-medium text-white leading-relaxed mb-8">
              &ldquo;We went into our FDA inspection with a Clyira Score of 88. The inspector raised three observations. Clyira had already flagged all three. We had our responses ready before she finished writing.&rdquo;
            </blockquote>
            <div className="text-sm text-gray-500">
              <span className="font-semibold text-gray-400">Director of Quality Assurance</span>
              {" · "}
              Mid-size pharmaceutical manufacturer, US
            </div>
          </div>
        </AnimateIn>
      </section>

      {/* ── PRICING ─────────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
                Pricing
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                Start free. Scale as you grow.
              </h2>
              <p className="text-gray-500 max-w-xl mx-auto">
                No per-user pricing traps. No hidden seat fees. One price for your whole QA team.
              </p>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {plans.map((plan, i) => (
              <AnimateIn key={plan.name} delay={i * 80} direction="up">
                <div
                  className={`h-full rounded-2xl p-6 flex flex-col ${
                    plan.highlighted
                      ? "bg-[#0d0d0d] text-white ring-2 ring-clyira-600 ring-offset-2"
                      : "bg-white border border-gray-200"
                  }`}
                >
                  <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <h3 className={`font-semibold text-lg ${plan.highlighted ? "text-white" : "text-gray-900"}`}>
                        {plan.name}
                      </h3>
                      {plan.highlighted && (
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-clyira-600 text-white">
                          Most popular
                        </span>
                      )}
                    </div>
                    <div className="flex items-baseline gap-1 mb-2">
                      <span className={`text-4xl font-bold tabular-nums ${plan.highlighted ? "text-white" : "text-gray-900"}`}>
                        {plan.price}
                      </span>
                      {plan.period && (
                        <span className={`text-sm ${plan.highlighted ? "text-gray-500" : "text-gray-500"}`}>
                          {plan.period}
                        </span>
                      )}
                    </div>
                    <p className={`text-sm ${plan.highlighted ? "text-gray-500" : "text-gray-500"}`}>
                      {plan.description}
                    </p>
                  </div>

                  <ul className="space-y-3 flex-1 mb-8">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2.5 text-sm">
                        <CheckCircle className={`w-4 h-4 mt-0.5 shrink-0 ${plan.highlighted ? "text-clyira-400" : "text-emerald-500"}`} />
                        <span className={plan.highlighted ? "text-gray-300" : "text-gray-600"}>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Link
                    href={plan.href}
                    className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                      plan.highlighted
                        ? "bg-clyira-600 text-white hover:bg-clyira-700"
                        : "border border-gray-200 text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    {plan.cta}
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </AnimateIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ───────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-clyira-600 text-white text-center">
        <AnimateIn>
          <div className="max-w-2xl mx-auto">
            <h2 className="text-3xl sm:text-4xl font-bold mb-5">
              Your next inspection is already scheduled.
            </h2>
            <p className="text-white/70 mb-10 text-lg">
              Join quality teams using Clyira to stay ahead of FDA and EMA expectations — not scrambling to catch up.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/auth/register"
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 rounded-lg bg-white text-clyira-700 font-semibold hover:bg-clyira-50 transition-colors"
              >
                Start for free
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/auth/login"
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 rounded-lg border border-white/30 text-white font-medium hover:bg-white/10 transition-colors"
              >
                Sign in to your account
              </Link>
            </div>
            <p className="mt-6 text-xs text-white/40">
              No credit card required · Free for up to 10 documents/month · Cancel anytime
            </p>
          </div>
        </AnimateIn>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────────── */}
      <footer className="bg-[#0d0d0d] border-t border-white/5 py-12 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            <div className="col-span-2 md:col-span-1">
              <Link href="/" className="flex items-center gap-2.5 mb-4">
                <img src="/clyira-logo.png" alt="Clyira" className="w-10 h-10 object-contain" />
                <span className="font-bold text-white tracking-tight">
                  CLYIRA<span style={{ color: "#7654c9", fontSize: "1.4em", lineHeight: 1 }}>.</span>AI
                </span>
              </Link>
              <p className="text-sm text-gray-600 leading-relaxed">
                AI-powered quality intelligence for pharmaceutical, biotech, and medical device companies.
              </p>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Product</h4>
              <ul className="space-y-3 text-sm text-gray-600">
                <li><Link href="#features" className="hover:text-white transition-colors">Features</Link></li>
                <li><Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                <li><Link href="#how-it-works" className="hover:text-white transition-colors">How it works</Link></li>
                <li><Link href="/auth/register" className="hover:text-white transition-colors">Get started</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Compliance</h4>
              <ul className="space-y-3 text-sm text-gray-600">
                <li>21 CFR Part 11</li>
                <li>SOC 2 Type II</li>
                <li>GDPR</li>
                <li>GxP Validated</li>
              </ul>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Company</h4>
              <ul className="space-y-3 text-sm text-gray-600">
                <li><a href="mailto:hello@clyira.ai" className="hover:text-white transition-colors">Contact</a></li>
                <li><a href="mailto:sales@clyira.ai" className="hover:text-white transition-colors">Sales</a></li>
                <li><a href="mailto:support@clyira.ai" className="hover:text-white transition-colors">Support</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-white/5 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-gray-700">© 2026 Clyira, Inc. All rights reserved.</p>
            <div className="flex items-center gap-6 text-xs text-gray-700">
              <span>Privacy Policy</span>
              <span>Terms of Service</span>
              <span>Security</span>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}

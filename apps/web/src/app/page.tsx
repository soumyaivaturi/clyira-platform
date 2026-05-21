import Link from "next/link";
import {
  Shield, FileText, Radio, TrendingUp, Zap,
  CheckCircle, ArrowRight, Globe, AlertTriangle,
  BarChart3, Lock, ChevronRight,
} from "lucide-react";

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
    title: "Upload Your Documents",
    description:
      "Drag and drop any quality document — SOP, CAPA, ATM, Validation Protocol, Batch Record. PDF, DOCX, and Excel supported.",
  },
  {
    number: "02",
    title: "AI Runs Your Assessment",
    description:
      "Clyira's engine scores the document across 11 regulatory levels in seconds, cross-referencing against 2,000+ regulatory citations.",
  },
  {
    number: "03",
    title: "Act on Your Score",
    description:
      "Review findings, acknowledge gaps, respond to each observation, and watch your Clyira Score climb before your next audit.",
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

const regulatoryBodies = ["FDA", "EMA", "ICH", "PMDA", "Health Canada", "TGA", "ISO 13485", "USP"];

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

      {/* ── NAVIGATION ──────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <img src="/clyira-logo.png" alt="Clyira" className="w-8 h-8 object-contain" />
            <span className="font-semibold text-lg tracking-tight">
              Clyira<span style={{ color: "#8C52FF" }}>.</span>ai
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-500">
            <Link href="#features" className="hover:text-gray-900 transition-colors">Features</Link>
            <Link href="#how-it-works" className="hover:text-gray-900 transition-colors">How It Works</Link>
            <Link href="#pricing" className="hover:text-gray-900 transition-colors">Pricing</Link>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/auth/login"
              className="hidden sm:block text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/auth/register"
              className="text-sm font-medium bg-clyira-600 text-white px-4 py-2 rounded-lg hover:bg-clyira-700 transition-colors"
            >
              Get started free
            </Link>
          </div>
        </div>
      </nav>

      {/* ── HERO ────────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-clyira-950 text-white">
        {/* Gradient orbs */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full opacity-20 blur-3xl" style={{ background: "#8C52FF" }} />
          <div className="absolute top-20 right-0 w-80 h-80 rounded-full opacity-15 blur-3xl bg-clyira-400" />
          <div className="absolute bottom-0 left-1/2 w-64 h-64 rounded-full opacity-10 blur-3xl bg-clyira-300" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-20">
          <div className="max-w-3xl mx-auto text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/20 bg-white/5 text-xs font-medium text-clyira-200 mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              AI-Powered Regulatory Intelligence for Life Sciences
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-tight mb-6">
              Know Your Compliance Score.{" "}
              <span className="text-transparent bg-clip-text" style={{ backgroundImage: "linear-gradient(135deg, #7cc8fb, #8C52FF)" }}>
                Before the Auditor Arrives.
              </span>
            </h1>

            <p className="text-lg text-clyira-200 leading-relaxed mb-10 max-w-2xl mx-auto">
              Clyira gives pharmaceutical, biotech, and medical device teams real-time AI-powered document assessment,
              department-level audit readiness scores, and live inspection support — built natively for FDA, EMA, and ICH standards.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
              <Link
                href="/auth/register"
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-white text-clyira-950 font-semibold text-sm hover:bg-clyira-50 transition-colors"
              >
                Start for free
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="#features"
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 rounded-lg border border-white/20 text-white font-medium text-sm hover:bg-white/5 transition-colors"
              >
                See the platform
              </Link>
            </div>

            {/* Compliance badges */}
            <div className="flex flex-wrap items-center justify-center gap-6">
              {complianceBadges.map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-1.5 text-xs text-clyira-300">
                  <Icon className="w-3.5 h-3.5" />
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Dashboard mockup */}
          <div className="mt-16 mx-auto max-w-4xl">
            <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur overflow-hidden shadow-2xl">
              {/* Window chrome */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-white/5">
                <div className="w-3 h-3 rounded-full bg-red-400/60" />
                <div className="w-3 h-3 rounded-full bg-amber-400/60" />
                <div className="w-3 h-3 rounded-full bg-emerald-400/60" />
                <div className="ml-4 flex-1 bg-white/5 rounded text-xs text-center text-clyira-400 py-0.5 px-2 max-w-xs mx-auto">
                  app.clyira.ai/dashboard
                </div>
              </div>

              {/* App layout */}
              <div className="flex h-72 sm:h-80">
                {/* Sidebar */}
                <div className="hidden sm:flex w-44 border-r border-white/10 bg-clyira-950/80 flex-col p-3 gap-1">
                  <div className="flex items-center gap-2 px-2 py-2 mb-2">
                    <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center">
                      <span className="text-white text-xs font-bold">C</span>
                    </div>
                    <span className="text-xs font-semibold text-white">Clyira.ai</span>
                  </div>
                  {["Dashboard", "Documents", "Audit Readiness", "Inspections"].map((item, i) => (
                    <div
                      key={item}
                      className={`px-2 py-1.5 rounded text-xs font-medium ${
                        i === 0 ? "bg-clyira-600/30 text-clyira-200" : "text-clyira-400 hover:text-white"
                      }`}
                    >
                      {item}
                    </div>
                  ))}
                </div>

                {/* Main content */}
                <div className="flex-1 p-4 overflow-hidden">
                  {/* KPI cards */}
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                      <div className="text-xs text-clyira-400 mb-1">Clyira Score</div>
                      <div className="text-2xl font-bold text-white">84.2</div>
                      <div className="text-xs text-emerald-400 mt-0.5">Compliant</div>
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                      <div className="text-xs text-clyira-400 mb-1">Documents</div>
                      <div className="text-2xl font-bold text-white">47</div>
                      <div className="text-xs text-clyira-400 mt-0.5">3 pending</div>
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-lg p-3">
                      <div className="text-xs text-clyira-400 mb-1">Gaps</div>
                      <div className="text-2xl font-bold text-amber-400">12</div>
                      <div className="text-xs text-clyira-400 mt-0.5">4 critical</div>
                    </div>
                  </div>

                  {/* Document rows */}
                  <div className="space-y-2">
                    {[
                      { title: "SOP-042 — Batch Release", score: 91, band: "Compliant", color: "bg-emerald-500" },
                      { title: "CAPA-2026-07 — Sterility Deviation", score: 67, band: "Moderate", color: "bg-amber-500" },
                      { title: "ATM-018 — HPLC Method", score: 88, band: "Compliant", color: "bg-emerald-500" },
                    ].map((doc) => (
                      <div key={doc.title} className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
                        <div className={`w-1.5 h-8 rounded-full ${doc.color}`} />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-white truncate">{doc.title}</div>
                          <div className="text-xs text-clyira-400">{doc.band}</div>
                        </div>
                        <div className="text-sm font-bold text-white tabular-nums">{doc.score}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── REGULATORY BODIES ───────────────────────────────────────────────── */}
      <section className="border-b bg-gray-50 py-10 px-6">
        <div className="max-w-7xl mx-auto">
          <p className="text-center text-xs font-semibold uppercase tracking-widest text-gray-400 mb-6">
            Regulatory standards covered
          </p>
          <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-10">
            {regulatoryBodies.map((body) => (
              <span key={body} className="text-sm font-semibold text-gray-500 hover:text-gray-800 transition-colors">
                {body}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
              Platform capabilities
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
              Everything your QA team needs, in one platform
            </h2>
            <p className="text-gray-500 max-w-2xl mx-auto text-lg">
              Purpose-built for life sciences — not a generic AI tool bolted onto a document repository.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f) => (
              <div
                key={f.title}
                className="group p-6 rounded-xl border border-gray-100 hover:border-gray-200 hover:shadow-md transition-all"
              >
                <div className={`w-10 h-10 rounded-lg ${f.bg} flex items-center justify-center mb-4`}>
                  <f.icon className={`w-5 h-5 ${f.color}`} />
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ASSESSMENT LEVELS SPOTLIGHT ─────────────────────────────────────── */}
      <section className="py-24 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-50 text-violet-700 text-xs font-semibold mb-4">
                Assessment engine
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-5">
                11 levels of regulatory scrutiny. Applied instantly.
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
                ].map((l) => (
                  <div key={l.level} className="flex items-center gap-3 py-2">
                    <span className="text-xs font-bold text-clyira-600 w-14 shrink-0">{l.level}</span>
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className="text-sm text-gray-700">{l.label}</span>
                  </div>
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

            {/* Score visual */}
            <div className="relative">
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
                      <span className="mt-0.5 px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold shrink-0">INFO</span>
                      <span className="text-gray-600">Deviation reference in Section 6 should cross-link to current CAPA register per ICH Q10 §3.2.</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────────────────────────── */}
      <section id="how-it-works" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-clyira-50 text-clyira-700 text-xs font-semibold mb-4">
              How it works
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
              From upload to audit-ready in minutes
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Connector line */}
            <div className="hidden md:block absolute top-10 left-1/3 right-1/3 h-px bg-gray-200" />

            {steps.map((step, i) => (
              <div key={step.number} className="relative text-center">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-clyira-950 text-white mb-6 relative z-10">
                  <span className="text-2xl font-bold">{step.number}</span>
                </div>
                <h3 className="font-semibold text-gray-900 text-lg mb-3">{step.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{step.description}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 text-center">
            <Link
              href="/auth/register"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-clyira-600 text-white font-semibold text-sm hover:bg-clyira-700 transition-colors"
            >
              Try it now — it&apos;s free
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── TESTIMONIAL ─────────────────────────────────────────────────────── */}
      <section className="py-20 px-6 bg-clyira-50">
        <div className="max-w-3xl mx-auto text-center">
          <div className="flex justify-center mb-4">
            {[1,2,3,4,5].map(i => (
              <svg key={i} className="w-5 h-5 text-amber-400 fill-current" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            ))}
          </div>
          <blockquote className="text-xl sm:text-2xl font-medium text-gray-900 leading-relaxed mb-6">
            &ldquo;We went into our FDA inspection with a Clyira Score of 88. The inspector raised three observations.
            Clyira had already flagged all three as findings in our batch release SOP. We had our responses ready before she finished writing.&rdquo;
          </blockquote>
          <div className="text-sm text-gray-500">
            <span className="font-semibold text-gray-700">Director of Quality Assurance</span>
            {" · "}
            Mid-size pharmaceutical manufacturer, US
          </div>
        </div>
      </section>

      {/* ── PRICING ─────────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
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

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-2xl p-6 flex flex-col ${
                  plan.highlighted
                    ? "bg-clyira-950 text-white ring-2 ring-clyira-600 ring-offset-2"
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
                      <span className={`text-sm ${plan.highlighted ? "text-clyira-300" : "text-gray-500"}`}>
                        {plan.period}
                      </span>
                    )}
                  </div>
                  <p className={`text-sm ${plan.highlighted ? "text-clyira-200" : "text-gray-500"}`}>
                    {plan.description}
                  </p>
                </div>

                <ul className="space-y-3 flex-1 mb-8">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5 text-sm">
                      <CheckCircle className={`w-4 h-4 mt-0.5 shrink-0 ${plan.highlighted ? "text-emerald-400" : "text-emerald-500"}`} />
                      <span className={plan.highlighted ? "text-clyira-100" : "text-gray-600"}>{feature}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.href}
                  className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                    plan.highlighted
                      ? "bg-white text-clyira-950 hover:bg-clyira-50"
                      : "border border-gray-200 text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {plan.cta}
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ───────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-clyira-950 text-white text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold mb-5">
            Get audit-ready before your next inspection.
          </h2>
          <p className="text-clyira-200 mb-10 text-lg">
            Join quality teams using Clyira to stay ahead of FDA and EMA expectations — not scrambling to catch up.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/register"
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 rounded-lg bg-white text-clyira-950 font-semibold hover:bg-clyira-50 transition-colors"
            >
              Start for free
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/auth/login"
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 rounded-lg border border-white/20 text-white font-medium hover:bg-white/5 transition-colors"
            >
              Sign in to your account
            </Link>
          </div>
          <p className="mt-6 text-xs text-clyira-400">
            No credit card required · Free for up to 10 documents/month · Cancel anytime
          </p>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────────── */}
      <footer className="bg-clyira-950 border-t border-white/5 py-12 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            <div className="col-span-2 md:col-span-1">
              <Link href="/" className="flex items-center gap-2 mb-4">
                <img src="/clyira-logo.png" alt="Clyira" className="w-8 h-8 object-contain" />
                <span className="font-semibold text-white">
                  Clyira<span style={{ color: "#8C52FF" }}>.</span>ai
                </span>
              </Link>
              <p className="text-sm text-clyira-400 leading-relaxed">
                AI-powered quality intelligence for pharmaceutical, biotech, and medical device companies.
              </p>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Product</h4>
              <ul className="space-y-3 text-sm text-clyira-400">
                <li><Link href="#features" className="hover:text-white transition-colors">Features</Link></li>
                <li><Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                <li><Link href="#how-it-works" className="hover:text-white transition-colors">How it works</Link></li>
                <li><Link href="/auth/register" className="hover:text-white transition-colors">Get started</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Compliance</h4>
              <ul className="space-y-3 text-sm text-clyira-400">
                <li><span>21 CFR Part 11</span></li>
                <li><span>SOC 2 Type II</span></li>
                <li><span>GDPR</span></li>
                <li><span>GxP Validated</span></li>
              </ul>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Company</h4>
              <ul className="space-y-3 text-sm text-clyira-400">
                <li><a href="mailto:hello@clyira.ai" className="hover:text-white transition-colors">Contact</a></li>
                <li><a href="mailto:sales@clyira.ai" className="hover:text-white transition-colors">Sales</a></li>
                <li><a href="mailto:support@clyira.ai" className="hover:text-white transition-colors">Support</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-white/5 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-clyira-500">
              © 2026 Clyira, Inc. All rights reserved.
            </p>
            <div className="flex items-center gap-6 text-xs text-clyira-500">
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

"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Shield, FileText, Radio,
  CheckCircle, ArrowRight,
  Lock, ChevronRight, Building2, FlaskConical, Microscope, Calendar,
  ChevronDown, AlertTriangle, Zap, Globe, BarChart3, Upload, PenLine,
} from "lucide-react";
import { AnimateIn } from "@/components/landing/animate-in";
import { IntegrationsSection } from "@/components/landing/integrations-section";
import { ClyiraLogo } from "@/components/shared/clyira-logo";

// ── Nav data ──────────────────────────────────────────────────────────────────

const platformMenu = [
  {
    category: "Assess & Score",
    items: [
      { icon: FileText, name: "Document Assessment", desc: "Multi-dimensional scoring on every quality document you upload" },
      { icon: BarChart3, name: "Audit Readiness", desc: "Live department-level compliance score, updated as you remediate" },
    ],
  },
  {
    category: "Intelligence",
    items: [
      { icon: AlertTriangle, name: "Regulatory Intelligence", desc: "Every enforcement pattern that matters, mapped to your documents" },
      { icon: Globe, name: "Multi-Agency Coverage", desc: "FDA, EMA, ICH, ISO 13485, PMDA — one assessment run" },
    ],
  },
  {
    category: "Author & Respond",
    items: [
      { icon: Zap, name: "AI Document Creator", desc: "Generate pre-scored SOPs, CAPAs, validation protocols, and more" },
      { icon: Radio, name: "Inspection Copilot", desc: "Live AI support during FDA, EMA, and PMDA inspections" },
    ],
  },
];

const solutionsMenu = [
  { icon: Building2, name: "Pharmaceutical", desc: "21 CFR 210/211, NDA/BLA submissions, PAI readiness" },
  { icon: FlaskConical, name: "Biotech & Clinical", desc: "IND/BLA filings, GCP documentation, first-inspection prep" },
  { icon: Microscope, name: "Medical Device", desc: "ISO 13485, 21 CFR 820, notified body assessments" },
];

// ── Nav ───────────────────────────────────────────────────────────────────────

function DropdownItem({ icon: Icon, name, desc }: { icon: React.ElementType; name: string; desc: string }) {
  return (
    <Link href="#features" className="flex items-start gap-3 px-2.5 py-2.5 rounded-xl hover:bg-gray-50 transition-colors group">
      <div className="w-8 h-8 rounded-lg bg-clyira-50 flex items-center justify-center shrink-0 mt-0.5 group-hover:bg-clyira-100 transition-colors">
        <Icon className="w-4 h-4 text-clyira-600" />
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-900 leading-tight">{name}</p>
        <p className="text-xs text-gray-500 leading-snug mt-0.5">{desc}</p>
      </div>
    </Link>
  );
}

function PreviewNav() {
  const [scrolled, setScrolled] = useState(false);
  const [openMenu, setOpenMenu] = useState<"platform" | "solutions" | null>(null);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const enter = (menu: "platform" | "solutions") => {
    clearTimeout(timers.current[menu]);
    setOpenMenu(menu);
  };

  const leave = (menu: "platform" | "solutions") => {
    timers.current[menu] = setTimeout(() => setOpenMenu(null), 120);
  };

  const dropdownClass = (active: boolean) =>
    `absolute top-[calc(100%+1px)] bg-white border border-gray-100 rounded-2xl shadow-2xl shadow-black/10 transition-all duration-200 ${
      active ? "opacity-100 translate-y-0 pointer-events-auto" : "opacity-0 -translate-y-2 pointer-events-none"
    }`;

  return (
    <nav className={`sticky top-0 z-50 backdrop-blur border-b transition-all duration-300 ${
      scrolled ? "bg-white/98 border-gray-200 shadow-sm" : "bg-white/95 border-gray-100"
    }`}>
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">

        <Link href="/preview">
          <ClyiraLogo className="h-8 w-auto" />
        </Link>

        <div className="hidden md:flex items-center gap-7 text-sm font-medium text-gray-500">

          {/* Platform dropdown */}
          <div className="relative" onMouseEnter={() => enter("platform")} onMouseLeave={() => leave("platform")}>
            <button className={`flex items-center gap-1 py-5 transition-colors ${openMenu === "platform" ? "text-gray-900" : "hover:text-gray-900"}`}>
              Platform
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${openMenu === "platform" ? "rotate-180" : ""}`} />
            </button>
            <div className={`${dropdownClass(openMenu === "platform")} left-1/2 -translate-x-1/2 w-[660px] p-6`}>
              <div className="absolute -top-[5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-white border-l border-t border-gray-100 rotate-45" />
              <div className="grid grid-cols-3 gap-2">
                {platformMenu.map((col) => (
                  <div key={col.category}>
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-2.5 mb-2">{col.category}</p>
                    <div className="space-y-0.5">
                      {col.items.map((item) => <DropdownItem key={item.name} {...item} />)}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
                <p className="text-xs text-gray-400">Supporting every document in your quality ecosystem</p>
                <Link href="mailto:hello@clyira.ai" className="text-xs font-semibold text-clyira-600 hover:text-clyira-700 flex items-center gap-1">
                  Book a demo <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          </div>

          {/* Solutions dropdown */}
          <div className="relative" onMouseEnter={() => enter("solutions")} onMouseLeave={() => leave("solutions")}>
            <button className={`flex items-center gap-1 py-5 transition-colors ${openMenu === "solutions" ? "text-gray-900" : "hover:text-gray-900"}`}>
              Solutions
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${openMenu === "solutions" ? "rotate-180" : ""}`} />
            </button>
            <div className={`${dropdownClass(openMenu === "solutions")} left-0 w-[320px] p-4`}>
              <div className="absolute -top-[5px] left-8 w-2.5 h-2.5 bg-white border-l border-t border-gray-100 rotate-45" />
              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-2.5 mb-2">By industry</p>
              <div className="space-y-0.5">
                {solutionsMenu.map((item) => <DropdownItem key={item.name} {...item} />)}
              </div>
            </div>
          </div>

          <Link href="#how-it-works" className="hover:text-gray-900 transition-colors">How It Works</Link>
          <Link href="#pricing" className="hover:text-gray-900 transition-colors">Pricing</Link>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/auth/login" className="hidden sm:block text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
            Sign in
          </Link>
          <Link href="mailto:hello@clyira.ai" className="text-sm font-semibold bg-clyira-600 text-white px-4 py-2 rounded-lg hover:bg-clyira-700 transition-colors">
            Book a demo
          </Link>
        </div>
      </div>
    </nav>
  );
}

// ── Page data ─────────────────────────────────────────────────────────────────

const pillars = [
  {
    icon: FileText,
    name: "Document Assessment",
    desc: "Score any quality or regulatory document — SOP, CAPA, validation protocol, batch record, deviation report, ATM, and more — against every standard that matters.",
  },
  {
    icon: Shield,
    name: "Audit Readiness",
    desc: "A live compliance score for every department, updated in real time. Always know where you stand — and exactly which documents are pulling your score down.",
  },
  {
    icon: Radio,
    name: "Inspection Copilot",
    desc: "Log every inspector request during a live FDA, EMA, or PMDA inspection. Get AI-generated talking points and document references in seconds.",
  },
  {
    icon: Zap,
    name: "AI Document Creator",
    desc: "Describe the document you need. Clyira generates a pre-compliant draft — scored above your threshold before you've made a single edit.",
  },
];

const personas = [
  {
    icon: Building2,
    tag: "Pharmaceutical",
    headline: "Your next PAI has a date. Your documents need to survive it.",
    body: "Clyira assesses and authors every quality and regulatory document in your organisation — measured against the full landscape of what regulators actively enforce, so gaps are found before inspectors are.",
  },
  {
    icon: FlaskConical,
    tag: "Biotech & Clinical Stage",
    headline: "First FDA inspection. No margin for documentation errors.",
    body: "Early-stage teams rarely have senior regulatory veterans on staff. Clyira gives every document in your quality ecosystem the same scrutiny a seasoned RA reviewer would apply — in seconds, not weeks.",
  },
  {
    icon: Microscope,
    tag: "Medical Device",
    headline: "ISO 13485 and 21 CFR 820 — both enforced. Both assessed.",
    body: "Device teams face dual-authority scrutiny from FDA and notified bodies. Clyira covers both in a single assessment run and labels each finding by the enforcing agency.",
  },
];

const plans = [
  {
    name: "Starter",
    description: "For small life sciences teams getting started with AI-powered document intelligence.",
    features: [
      "Document assessments",
      "Small team accounts",
      "Core assessment dimensions",
      "Basic readiness dashboard",
      "PDF & DOCX support",
    ],
    cta: "Request access",
    href: "mailto:hello@clyira.ai",
    highlighted: false,
  },
  {
    name: "Professional",
    description: "For quality and regulatory teams that need full coverage across the organisation.",
    features: [
      "Unlimited document assessments",
      "Team accounts",
      "Full multi-dimensional assessment",
      "Regulatory enforcement intelligence",
      "Inspection Copilot",
      "AI Document Creator",
      "Priority support",
    ],
    cta: "Book a demo",
    href: "mailto:sales@clyira.ai",
    highlighted: true,
  },
  {
    name: "Enterprise",
    description: "For multi-site organisations with complex compliance and integration needs.",
    features: [
      "Unlimited everything",
      "SSO / SAML integration",
      "Custom regulatory corpus",
      "On-premise deployment option",
      "Dedicated success manager",
      "SLA & audit log exports",
    ],
    cta: "Talk to sales",
    href: "mailto:sales@clyira.ai",
    highlighted: false,
  },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PreviewPage() {
  return (
    <div className="min-h-screen bg-white font-sans">

      {/* ── PREVIEW BANNER ──────────────────────────────────────────────────── */}
      <div className="bg-amber-500 text-white text-center text-xs py-2.5 px-4 font-semibold">
        PREVIEW — proposed homepage redesign, not the live page.{" "}
        <Link href="/" className="underline underline-offset-2 hover:no-underline">View current homepage →</Link>
      </div>

      {/* ── ANNOUNCEMENT BAR ────────────────────────────────────────────────── */}
      <div className="bg-clyira-600 text-white text-center text-xs py-2.5 px-4">
        <span className="font-medium">Now live — AI-powered assessment and authoring for every life sciences document.</span>
        <Link href="mailto:hello@clyira.ai" className="ml-2 font-bold underline underline-offset-2 hover:no-underline">
          Request early access →
        </Link>
      </div>

      {/* ── NAVIGATION ──────────────────────────────────────────────────────── */}
      <PreviewNav />

      {/* ── HERO ────────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-[#0d0d0d]">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-64 -right-64 w-[700px] h-[700px] rounded-full opacity-[0.08]"
            style={{ background: "radial-gradient(circle, #7654c9, transparent 70%)" }} />
          <div className="absolute top-40 -left-32 w-[400px] h-[400px] rounded-full opacity-[0.05]"
            style={{ background: "radial-gradient(circle, #8977d7, transparent 70%)" }} />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-20">
          <div className="max-w-3xl mx-auto text-center">

            <AnimateIn delay={0}>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs font-semibold text-clyira-400 mb-8">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                FDA · EMA · ICH · ISO 13485 · PMDA
              </div>
            </AnimateIn>

            <AnimateIn delay={80}>
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1] text-white mb-6">
                Every quality document.<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-clyira-400 to-violet-400">
                  Scored before the inspector sees it.
                </span>
              </h1>
            </AnimateIn>

            <AnimateIn delay={160}>
              <p className="text-xl text-gray-400 leading-relaxed mb-4 max-w-2xl mx-auto">
                Clyira assesses and authors every document in your quality ecosystem — SOPs, CAPAs, validation protocols, batch records, deviation reports, ATMs, and more — measured against every regulatory standard and enforcement pattern that matters.
              </p>
            </AnimateIn>

            <AnimateIn delay={200}>
              <p className="text-base text-gray-600 leading-relaxed mb-10 max-w-xl mx-auto">
                Know exactly what an inspector would find. Fix it before they arrive.
              </p>
            </AnimateIn>

            <AnimateIn delay={240}>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-10">
                <Link
                  href="mailto:hello@clyira.ai"
                  className="w-full sm:w-auto flex items-center justify-center gap-2 px-7 py-3.5 rounded-lg bg-clyira-600 text-white font-semibold text-sm hover:bg-clyira-700 transition-colors shadow-lg shadow-clyira-600/30"
                >
                  Book a demo
                  <Calendar className="w-4 h-4" />
                </Link>
                <Link
                  href="#features"
                  className="w-full sm:w-auto flex items-center justify-center gap-2 px-7 py-3.5 rounded-lg border border-white/20 text-gray-300 font-medium text-sm hover:bg-white/5 transition-colors"
                >
                  See it in action
                </Link>
              </div>
            </AnimateIn>
          </div>

          {/* Dashboard mockup */}
          <AnimateIn delay={120} direction="up" threshold={0.05}>
            <div className="mt-16 mx-auto max-w-4xl">
              <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden shadow-[0_20px_80px_-10px_rgba(118,84,201,0.25),0_4px_24px_-4px_rgba(0,0,0,0.3)]">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-white/5">
                  <div className="w-3 h-3 rounded-full bg-red-500/60" />
                  <div className="w-3 h-3 rounded-full bg-amber-500/60" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
                  <div className="ml-4 flex-1 bg-white/5 border border-white/10 rounded text-xs text-center text-gray-600 py-0.5 px-2 max-w-xs mx-auto">
                    app.clyira.ai/dashboard
                  </div>
                </div>
                <div className="flex h-72 sm:h-80">
                  <div className="hidden sm:flex w-44 border-r border-white/10 bg-black/20 flex-col p-3 gap-1">
                    <div className="flex items-center gap-2 px-2 py-2 mb-2">
                      <ClyiraLogo className="h-5 w-auto" style={{ mixBlendMode: "normal", filter: "brightness(0) invert(1)" }} />
                    </div>
                    {["Dashboard", "Documents", "Audit Readiness", "Inspections"].map((item, i) => (
                      <div key={item} className={`px-2 py-1.5 rounded text-xs font-medium ${i === 0 ? "bg-clyira-600/20 text-clyira-400" : "text-gray-600"}`}>
                        {item}
                      </div>
                    ))}
                  </div>
                  <div className="flex-1 p-4 overflow-hidden">
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      {[
                        { label: "Clyira Score", value: "84.2", sub: "Compliant", subColor: "text-emerald-400" },
                        { label: "Documents", value: "47", sub: "3 pending review", subColor: "text-gray-500" },
                        { label: "Open Gaps", value: "12", sub: "4 critical", subColor: "text-gray-500", valueColor: "text-amber-400" },
                      ].map((k) => (
                        <div key={k.label} className="bg-white/5 border border-white/10 rounded-lg p-3">
                          <div className="text-xs text-gray-600 mb-1">{k.label}</div>
                          <div className={`text-2xl font-bold ${k.valueColor ?? "text-white"}`}>{k.value}</div>
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
                        <div key={doc.title} className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
                          <div className={`w-1.5 h-8 rounded-full ${doc.color}`} />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-gray-300 truncate">{doc.title}</div>
                            <div className="text-xs text-gray-600">{doc.band}</div>
                          </div>
                          <div className="text-sm font-bold text-gray-300 tabular-nums">{doc.score}</div>
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

      {/* ── 4 CORE PILLARS ──────────────────────────────────────────────────── */}
      <section id="features" className="py-20 px-6 bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <p className="text-center text-xs font-bold text-gray-400 uppercase tracking-widest mb-12">
              The Clyira platform
            </p>
          </AnimateIn>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {pillars.map((p, i) => (
              <AnimateIn key={p.name} delay={i * 70} direction="up">
                <div className="h-full p-6 rounded-2xl border border-gray-100 hover:border-clyira-100 hover:shadow-md transition-all">
                  <div className="w-10 h-10 rounded-xl bg-clyira-50 flex items-center justify-center mb-4">
                    <p.icon className="w-5 h-5 text-clyira-600" />
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-2">{p.name}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{p.desc}</p>
                </div>
              </AnimateIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── REGULATORY INTELLIGENCE ─────────────────────────────────────────── */}
      <section className="bg-[#0d0d0d] py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

            <AnimateIn direction="left">
              <div>
                <p className="text-xs font-bold text-clyira-500 uppercase tracking-widest mb-5">
                  Regulatory Intelligence
                </p>
                <h2 className="text-4xl sm:text-5xl font-bold text-white leading-tight mb-6">
                  What regulators enforce.<br />
                  <span className="text-clyira-400">Already inside every assessment.</span>
                </h2>
                <p className="text-gray-400 text-lg leading-relaxed mb-5">
                  Inspectors don&apos;t just check that your documents exist. They check them against a body of enforcement knowledge built over decades. Clyira has that knowledge — and runs it against your documents before they do.
                </p>
                <p className="text-gray-600 text-base leading-relaxed mb-8">
                  Every pattern that has ever resulted in an observation, a citation, or an enforcement action is part of how Clyira scores your documents. Your team sees the gaps. The inspector doesn&apos;t.
                </p>
                <Link href="mailto:hello@clyira.ai" className="inline-flex items-center gap-2 text-sm font-semibold text-clyira-400 hover:text-clyira-300 transition-colors">
                  See it in action — book a demo
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-white/10">
                  <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">3 Regulatory Patterns Matched</span>
                </div>
                <div className="space-y-3">
                  {[
                    { doc: "SOP-042 Batch Release", obs: "Inadequate investigation into root cause of laboratory deviation — 21 CFR 211.192", severity: "Critical", color: "bg-red-500/20 text-red-400" },
                    { doc: "CAPA-2026-07", obs: "Failure to adequately assess the risk of distributed product — 21 CFR 211.198", severity: "High", color: "bg-amber-500/20 text-amber-400" },
                    { doc: "Validation Protocol 2026-11", obs: "Acceptance criteria not defined prior to study execution — 21 CFR 211.68(b)", severity: "Medium", color: "bg-yellow-500/20 text-yellow-400" },
                  ].map((item) => (
                    <div key={item.doc} className="bg-white/5 border border-white/10 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-white">{item.doc}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ml-2 ${item.color}`}>{item.severity}</span>
                      </div>
                      <p className="text-xs text-gray-400 leading-relaxed">{item.obs}</p>
                    </div>
                  ))}
                </div>
                <div className="border-t border-white/10 pt-3 text-[10px] text-gray-600">
                  Matched against the full history of regulatory enforcement · Updated continuously
                </div>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── ASSESSMENT ENGINE ───────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

            <AnimateIn direction="left">
              <div>
                <p className="text-xs font-bold text-clyira-600 uppercase tracking-widest mb-5">
                  Assessment Engine
                </p>
                <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-5">
                  Multi-dimensional scrutiny.<br />Every document. Every time.
                </h2>
                <p className="text-gray-500 mb-5 leading-relaxed">
                  Most QMS tools verify that a document exists. Clyira verifies that it would survive scrutiny — running every document through multiple independent regulatory dimensions, from structural completeness through active enforcement alignment.
                </p>
                <p className="text-gray-500 mb-8 leading-relaxed">
                  Every finding links to the exact CFR section, ICH guideline, or regulatory standard that triggered it. Full traceability. No black-box scores.
                </p>
                <div className="space-y-2.5 mb-4">
                  {[
                    "Document structure & completeness",
                    "Regulatory citation accuracy",
                    "Risk assessment & CAPA linkage",
                    "Enforcement pattern alignment",
                    "Inspection readiness",
                  ].map((dim) => (
                    <div key={dim} className="flex items-center gap-2.5 text-sm text-gray-700">
                      <CheckCircle className="w-4 h-4 text-clyira-500 shrink-0" />
                      <span>{dim}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-2.5 text-sm text-gray-400">
                    <span className="w-4 h-4 flex items-center justify-center shrink-0 text-base leading-none">···</span>
                    <span>and much more</span>
                  </div>
                </div>
                <Link href="mailto:hello@clyira.ai" className="inline-flex items-center gap-2 mt-4 text-sm font-semibold text-clyira-600 hover:text-clyira-700">
                  See a live assessment <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div className="bg-white rounded-2xl border shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">Assessment Result</p>
                    <p className="text-sm font-semibold text-gray-900 mt-0.5">CAPA-2026-07 · Sterility Deviation</p>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-amber-500">67</div>
                    <div className="text-xs font-semibold text-amber-500">Moderate</div>
                  </div>
                </div>
                <div className="space-y-2 mb-4">
                  {[
                    { label: "Document Structure", score: 88, color: "bg-emerald-500" },
                    { label: "Regulatory Citations", score: 71, color: "bg-amber-400" },
                    { label: "Root Cause Depth", score: 54, color: "bg-amber-500" },
                    { label: "CAPA Effectiveness", score: 60, color: "bg-amber-500" },
                    { label: "Inspection Readiness", score: 62, color: "bg-amber-400" },
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
                  <p className="text-xs font-semibold text-gray-700 mb-2">3 findings · each linked to source regulation</p>
                  <div className="space-y-2">
                    <div className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 px-1.5 py-0.5 rounded bg-red-50 text-red-700 font-semibold shrink-0">CRIT</span>
                      <span className="text-gray-600">Root cause analysis does not meet depth requirements — systemic cause not identified per 21 CFR 211.192.</span>
                    </div>
                    <div className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-semibold shrink-0">MOD</span>
                      <span className="text-gray-600">Effectiveness check criteria not defined prior to CAPA closure — ICH Q10 §3.2.3.</span>
                    </div>
                  </div>
                </div>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────────────────────────────── */}
      <section id="how-it-works" className="py-24 px-6 bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <p className="text-xs font-bold text-clyira-600 uppercase tracking-widest mb-4">How it works</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
                Two ways to use Clyira.
              </h2>
              <p className="text-gray-500 max-w-xl mx-auto">
                Assess existing documents against every regulatory standard. Or author new ones that arrive pre-compliant. Both in minutes.
              </p>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

            {/* Path 1: Assess */}
            <AnimateIn delay={0} direction="up">
              <div className="h-full rounded-2xl border border-gray-100 bg-gray-50 p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-clyira-50 flex items-center justify-center">
                    <Upload className="w-5 h-5 text-clyira-600" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-clyira-600 uppercase tracking-widest">Assess</p>
                    <h3 className="font-semibold text-gray-900 text-lg leading-tight">Upload any document. Know where it stands.</h3>
                  </div>
                </div>
                <div className="space-y-4">
                  {[
                    { step: "01", text: "Upload any quality or regulatory document — SOP, CAPA, validation protocol, batch record, deviation report, or ATM" },
                    { step: "02", text: "Multi-dimensional assessment runs in seconds, cross-referenced against every standard and enforcement pattern that applies" },
                    { step: "03", text: "Review findings with exact citations — each one linked to the specific regulation that triggered it" },
                    { step: "04", text: "Remediate gaps, watch your Clyira Score climb, and enter your next inspection with confidence" },
                  ].map((s) => (
                    <div key={s.step} className="flex items-start gap-4">
                      <span className="text-xs font-bold text-clyira-400 w-6 shrink-0 mt-0.5">{s.step}</span>
                      <p className="text-sm text-gray-600 leading-relaxed">{s.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </AnimateIn>

            {/* Path 2: Author */}
            <AnimateIn delay={100} direction="up">
              <div className="h-full rounded-2xl border border-gray-100 bg-gray-50 p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                    <PenLine className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-emerald-600 uppercase tracking-widest">Author</p>
                    <h3 className="font-semibold text-gray-900 text-lg leading-tight">Describe what you need. Get a pre-compliant draft.</h3>
                  </div>
                </div>
                <div className="space-y-4">
                  {[
                    { step: "01", text: "Describe the document you need — type, department, regulatory scope, and any specific requirements" },
                    { step: "02", text: "Clyira's AI generates a compliant draft in seconds, built against your DTAP profile and current regulatory landscape" },
                    { step: "03", text: "The document arrives pre-scored — assessed against the same multi-dimensional engine as your existing documents" },
                    { step: "04", text: "Review, refine, and submit with confidence — no remediation cycle before your first inspection" },
                  ].map((s) => (
                    <div key={s.step} className="flex items-start gap-4">
                      <span className="text-xs font-bold text-emerald-500 w-6 shrink-0 mt-0.5">{s.step}</span>
                      <p className="text-sm text-gray-600 leading-relaxed">{s.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── INSPECTION COPILOT ──────────────────────────────────────────────── */}
      <section className="bg-white border-t border-gray-100 py-32 px-6">
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
                    <div key={r.req} className={`flex items-start gap-3 p-3 rounded-lg border ${r.critical ? "border-red-100 bg-red-50/50" : "border-gray-100 bg-gray-50/50"}`}>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-gray-900 leading-snug">{r.req}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5">{r.time}</p>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ${r.status === "done" ? "bg-emerald-100 text-emerald-700" : r.status === "critical" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"}`}>
                        {r.status === "done" ? "Done" : r.status === "critical" ? "Critical" : "Open"}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="bg-clyira-50 border border-clyira-100 rounded-xl p-4">
                  <p className="text-[10px] font-bold text-clyira-700 mb-2 uppercase tracking-wide">AI Talking Points — Sterility Investigation</p>
                  <ul className="space-y-1.5">
                    {[
                      "Root cause: contamination during EM failure — documented in CAPA-2026-07",
                      "CAPA initiated within 24h of OOS result — Section 4.2",
                      "No distributed product affected — batch quarantined at release",
                    ].map((pt) => (
                      <li key={pt} className="flex items-start gap-1.5 text-[10px] text-clyira-700">
                        <span className="mt-0.5 shrink-0">·</span><span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </AnimateIn>

            <AnimateIn direction="right" delay={100}>
              <div>
                <p className="text-xs font-bold text-violet-600 uppercase tracking-widest mb-5">Inspection Copilot</p>
                <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 leading-tight mb-6">
                  The inspector knocks.<br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-clyira-600 to-violet-500">
                    You already have the answer.
                  </span>
                </h2>
                <p className="text-gray-500 text-lg leading-relaxed mb-5">
                  Log every inspector request in real time. Get AI-generated talking points and relevant document references within seconds.
                </p>
                <p className="text-gray-500 leading-relaxed mb-8">
                  When they ask for your sterility deviation investigation, Clyira already knows which documents cover it and what the three key response points are. Close the inspection with nothing outstanding.
                </p>
                <Link href="mailto:hello@clyira.ai" className="inline-flex items-center gap-2 text-sm font-semibold text-clyira-600 hover:text-clyira-700 transition-colors">
                  See Inspection Copilot in action <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimateIn>

          </div>
        </div>
      </section>

      {/* ── INTEGRATIONS ────────────────────────────────────────────────────── */}
      <IntegrationsSection />

      {/* ── WHO THIS IS FOR ─────────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <p className="text-xs font-bold text-clyira-600 uppercase tracking-widest mb-4">Who Clyira is built for</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">The same pressure. Different forms.</h2>
              <p className="text-gray-500 max-w-xl mx-auto">
                From a two-person biotech preparing for their first inspection to a global manufacturer managing thousands of controlled documents — your quality story has to be defensible.
              </p>
            </div>
          </AnimateIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {personas.map((p, i) => (
              <AnimateIn key={p.tag} delay={i * 80} direction="up">
                <div className="h-full p-6 rounded-xl border border-gray-100 hover:border-clyira-100 hover:shadow-md transition-all">
                  <div className="w-10 h-10 rounded-lg bg-clyira-50 flex items-center justify-center mb-4">
                    <p.icon className="w-5 h-5 text-clyira-600" />
                  </div>
                  <div className="text-xs font-semibold text-clyira-600 uppercase tracking-wide mb-2">{p.tag}</div>
                  <h3 className="font-semibold text-gray-900 mb-3 leading-snug">{p.headline}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{p.body}</p>
                </div>
              </AnimateIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── OBJECTION HANDLER ───────────────────────────────────────────────── */}
      <section className="py-20 px-6 bg-gray-50 border-y border-gray-100">
        <div className="max-w-4xl mx-auto text-center">
          <AnimateIn>
            <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-6">Works alongside your existing systems</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-5">
              Clyira isn&apos;t a QMS.<br />
              <span className="text-clyira-600">It&apos;s the intelligence layer your QMS doesn&apos;t have.</span>
            </h2>
            <p className="text-gray-500 max-w-2xl mx-auto text-lg leading-relaxed mb-8">
              MasterControl tracks your documents. Veeva approves them. TrackWise manages your CAPAs. None of them tell you whether those documents would survive regulatory scrutiny — because none of them understand enforcement. Clyira does.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              {["MasterControl", "Veeva Vault", "TrackWise", "Qualio", "SharePoint", "ETQ Reliance", "Greenlight Guru"].map((name) => (
                <span key={name} className="px-3 py-1.5 rounded-full border border-gray-200 bg-white text-xs font-semibold text-gray-500">{name}</span>
              ))}
            </div>
          </AnimateIn>
        </div>
      </section>

      {/* ── FOUNDER CONVICTION ──────────────────────────────────────────────── */}
      <section className="py-24 px-6 bg-[#0d0d0d]">
        <AnimateIn>
          <div className="max-w-3xl mx-auto text-center">
            <p className="text-xs font-bold text-clyira-500 uppercase tracking-widest mb-8">Why Clyira exists</p>
            <blockquote className="text-2xl sm:text-3xl font-medium text-white leading-relaxed mb-8">
              &ldquo;There is a massive information asymmetry between regulators and the teams they inspect. Regulators know exactly what they&apos;re looking for. Most quality and regulatory teams are guessing. Clyira was built to close that gap — to put the intelligence on your side for once.&rdquo;
            </blockquote>
            <p className="text-gray-500 text-sm">
              Decades of regulatory enforcement patterns. Every active standard across FDA, EMA, and ICH.
              Distilled into a 30-second assessment of your actual documents.
            </p>
          </div>
        </AnimateIn>
      </section>

      {/* ── PRICING ─────────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-24 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <AnimateIn>
            <div className="text-center mb-16">
              <p className="text-xs font-bold text-clyira-600 uppercase tracking-widest mb-4">Pricing</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">Built for every life sciences team.</h2>
              <p className="text-gray-500 max-w-xl mx-auto">
                Whether you&apos;re a QA director, regulatory affairs lead, validation engineer, or clinical operations manager — get in touch and we&apos;ll find the right fit.
              </p>
            </div>
          </AnimateIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {plans.map((plan, i) => (
              <AnimateIn key={plan.name} delay={i * 80} direction="up">
                <div className={`h-full rounded-2xl p-6 flex flex-col ${plan.highlighted ? "bg-[#0d0d0d] text-white ring-2 ring-clyira-600 ring-offset-2" : "bg-white border border-gray-200"}`}>
                  <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <h3 className={`font-semibold text-lg ${plan.highlighted ? "text-white" : "text-gray-900"}`}>{plan.name}</h3>
                      {plan.highlighted && <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-clyira-600 text-white">Most popular</span>}
                    </div>
                    <p className={`text-sm ${plan.highlighted ? "text-gray-400" : "text-gray-500"}`}>{plan.description}</p>
                  </div>
                  <ul className="space-y-3 flex-1 mb-8">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2.5 text-sm">
                        <CheckCircle className={`w-4 h-4 mt-0.5 shrink-0 ${plan.highlighted ? "text-clyira-400" : "text-emerald-500"}`} />
                        <span className={plan.highlighted ? "text-gray-300" : "text-gray-600"}>{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href={plan.href} className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-colors ${plan.highlighted ? "bg-clyira-600 text-white hover:bg-clyira-700" : "border border-gray-200 text-gray-700 hover:bg-gray-50"}`}>
                    {plan.cta} <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </AnimateIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ───────────────────────────────────────────────────────── */}
      <section className="py-28 px-6 bg-[#0d0d0d] text-white text-center">
        <AnimateIn>
          <div className="max-w-2xl mx-auto">
            <h2 className="text-4xl sm:text-5xl font-bold mb-5 leading-tight">
              Your next inspection is<br />already on the calendar.
            </h2>
            <p className="text-gray-400 mb-10 text-lg">
              Find out what Clyira finds in your documents — before an inspector does.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="mailto:hello@clyira.ai" className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-10 py-4 rounded-lg bg-clyira-600 text-white font-semibold text-base hover:bg-clyira-700 transition-colors shadow-lg shadow-clyira-600/30">
                Book a demo <Calendar className="w-5 h-5" />
              </Link>
              <Link href="mailto:hello@clyira.ai" className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-10 py-4 rounded-lg border border-white/20 text-gray-300 font-medium text-base hover:bg-white/5 transition-colors">
                Request early access <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
          </div>
        </AnimateIn>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────────── */}
      <footer className="bg-[#0d0d0d] border-t border-white/5 py-12 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            <div className="col-span-2 md:col-span-1">
              <Link href="/preview" className="inline-block mb-4">
                <ClyiraLogo className="h-8 w-auto" style={{ mixBlendMode: "normal", filter: "brightness(0) invert(1)" }} />
              </Link>
              <p className="text-sm text-gray-600 leading-relaxed">
                AI-powered quality intelligence for pharmaceutical, biotech, and medical device companies.
              </p>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Platform</h4>
              <ul className="space-y-3 text-sm text-gray-600">
                <li><Link href="#features" className="hover:text-white transition-colors">Assessment Engine</Link></li>
                <li><Link href="#how-it-works" className="hover:text-white transition-colors">How It Works</Link></li>
                <li><Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                <li><a href="mailto:hello@clyira.ai" className="hover:text-white transition-colors">Book a demo</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-white uppercase tracking-widest mb-4">Compliance</h4>
              <ul className="space-y-3 text-sm text-gray-600">
                <li>21 CFR Part 11</li>
                <li>GxP Validated</li>
                <li>GDPR</li>
                <li>SOC 2 (in progress)</li>
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

"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  FileText, BarChart3, AlertTriangle, Globe,
  Zap, Radio, Building2, FlaskConical, Microscope,
  ChevronDown, ChevronRight,
} from "lucide-react";
import { ClyiraLogo } from "@/components/shared/clyira-logo";

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

export function LandingNav() {
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

        <Link href="/" className="flex items-center gap-2.5">
          <ClyiraLogo className="w-9 h-9" />
          <span className="font-extrabold text-xl tracking-tight text-gray-900">
            CLYIRA<span style={{ color: "#7654c9", fontSize: "1.4em", lineHeight: 1 }}>.</span>AI
          </span>
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

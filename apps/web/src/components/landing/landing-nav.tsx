"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={`sticky top-0 z-50 backdrop-blur border-b transition-all duration-300 ${
        scrolled
          ? "bg-white/98 border-gray-200 shadow-sm"
          : "bg-white/95 border-gray-100"
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <img src="/clyira-logo.png" alt="Clyira" className="w-10 h-10 object-contain" />
          <span className="font-bold text-lg tracking-tight text-gray-900">
            CLYIRA<span style={{ color: "#7654c9" }}>.</span>AI
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
            className="text-sm font-semibold bg-clyira-600 text-white px-4 py-2 rounded-lg hover:bg-clyira-700 transition-colors"
          >
            Get started free
          </Link>
        </div>
      </div>
    </nav>
  );
}

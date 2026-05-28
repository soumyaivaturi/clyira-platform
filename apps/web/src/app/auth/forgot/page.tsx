"use client";

import Link from "next/link";
import { Shield } from "lucide-react";
import { ClyiraLogo } from "@/components/shared/clyira-logo";

export default function ForgotPasswordPage() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <ClyiraLogo className="w-72 h-auto" />
        </div>

        <div className="bg-card border rounded-xl p-8 shadow-sm text-center">
          <h1 className="text-xl font-semibold mb-2">Reset your password</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Password reset is managed by your administrator. Contact your Clyira account manager to reset your password.
          </p>
          <Link
            href="/auth/login"
            className="inline-flex items-center justify-center px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Back to sign in
          </Link>
        </div>

        <div className="mt-6 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Shield className="w-3.5 h-3.5" />
          <span>21 CFR Part 11 compliant · SOC 2 Type II</span>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useRef } from "react";
import { Shield, CheckCircle, Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

export function TermsModal() {
  const { acceptTerms } = useAuth();
  const [scrolledToBottom, setScrolledToBottom] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleScroll = () => {
    const el = contentRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 40) {
      setScrolledToBottom(true);
    }
  };

  const handleAccept = async () => {
    setAccepting(true);
    try {
      await acceptTerms();
    } finally {
      setAccepting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-card border rounded-xl shadow-2xl w-full max-w-lg flex flex-col max-h-[88vh]">

        {/* Header */}
        <div className="flex items-center gap-3 p-6 border-b flex-shrink-0">
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
            <Shield className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="font-semibold text-base">System Use Policy</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              21 CFR Part 11 · Electronic Records &amp; Signatures
            </p>
          </div>
        </div>

        {/* Scrollable policy text */}
        <div
          ref={contentRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-6 space-y-5 text-sm text-muted-foreground"
        >
          <p className="text-foreground font-medium">
            Before using Clyira, read and acknowledge the following policy. Scroll to the bottom to accept.
          </p>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              1. Electronic Records (21 CFR §11.10)
            </h3>
            <p>
              This system creates, modifies, maintains, archives, and retrieves electronic records subject to FDA regulations under 21 CFR Part 11. All records generated in this system carry the same legal standing as equivalent paper records and handwritten signatures.
            </p>
          </section>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              2. User Accountability (21 CFR §11.10(j))
            </h3>
            <p>
              You are personally responsible for all actions performed under your user credentials. Document creation, assessment triggering, finding responses, and record approvals made under your account are equivalent to your handwritten signature and constitute legally binding attestations.
            </p>
          </section>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              3. Credential Security (21 CFR §11.300)
            </h3>
            <p>
              You must never share your username, password, or access credentials with any other person. Each user must have unique, individual credentials. Sharing credentials violates 21 CFR Part 11 and may constitute a GMP compliance failure reportable to regulatory authorities.
            </p>
          </section>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              4. Session Security
            </h3>
            <p>
              Your session will automatically terminate after 30 minutes of inactivity and expires after 8 hours regardless of activity. Always sign out before leaving your workstation unattended. Do not access this system on shared or unsecured devices.
            </p>
          </section>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              5. Audit Trail (21 CFR §11.10(e))
            </h3>
            <p>
              All system actions are recorded in a tamper-evident audit trail that captures your identity, the date and time of each action, and the nature of any change. This audit trail is available for inspection by regulatory authorities and cannot be altered or deleted by any user.
            </p>
          </section>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              6. Security Breach Reporting
            </h3>
            <p>
              Report any suspected unauthorized access, credential compromise, or security incident immediately to your system administrator. Failure to report known security breaches is itself a compliance violation.
            </p>
          </section>

          <section className="space-y-1.5">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground">
              7. Authorized Use Only
            </h3>
            <p>
              This system is for authorized GxP quality activities only. Unauthorized use, data manipulation, or circumvention of system controls is prohibited and may result in disciplinary action and regulatory consequences including FDA enforcement.
            </p>
          </section>

          <p className="text-xs text-muted-foreground/60 pt-4 border-t">
            Policy version 1.0 · Effective 2026-05-25 · Governed by 21 CFR Part 11 and EU GMP Annex 11
          </p>
        </div>

        {/* Footer */}
        <div className="p-6 border-t bg-muted/30 space-y-3 flex-shrink-0">
          {!scrolledToBottom && (
            <p className="text-xs text-muted-foreground text-center">
              Scroll to the bottom to enable acceptance
            </p>
          )}
          <button
            onClick={handleAccept}
            disabled={!scrolledToBottom || accepting}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {accepting
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Confirming…</>
              : <><CheckCircle className="w-4 h-4" /> I have read and agree to the System Use Policy</>
            }
          </button>
          <p className="text-[10px] text-muted-foreground text-center">
            By accepting, you acknowledge your electronic actions carry the same legal weight as a handwritten signature.
          </p>
        </div>
      </div>
    </div>
  );
}

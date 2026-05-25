"use client";

import { useState } from "react";
import { Eye, EyeOff, Loader2, PenLine, Shield } from "lucide-react";
import { signaturesApi } from "@/lib/api";

type Meaning = "authored" | "reviewed" | "approved";

const MEANINGS: { value: Meaning; label: string; description: string }[] = [
  { value: "authored", label: "Authored", description: "I authored or created this document" },
  { value: "reviewed", label: "Reviewed", description: "I have reviewed this document for accuracy" },
  { value: "approved", label: "Approved", description: "I approve this document for use" },
];

interface Props {
  documentId: string;
  documentTitle: string;
  onClose: () => void;
  onSigned: () => void;
}

export function SignatureModal({ documentId, documentTitle, onClose, onSigned }: Props) {
  const [meaning, setMeaning] = useState<Meaning>("reviewed");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) { setError("Password is required"); return; }
    setLoading(true);
    setError("");
    try {
      await signaturesApi.sign(documentId, meaning, password);
      onSigned();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Signature failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-card border rounded-xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center gap-3 p-6 border-b">
          <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
            <PenLine className="w-4.5 h-4.5 text-primary" />
          </div>
          <div>
            <h2 className="font-semibold text-base">Electronic Signature</h2>
            <p className="text-xs text-muted-foreground mt-0.5">21 CFR Part 11 §11.50 · §11.200</p>
          </div>
        </div>

        <form onSubmit={handleSign} className="p-6 space-y-5">
          {/* Document being signed */}
          <div className="bg-muted/40 rounded-lg px-4 py-3">
            <p className="text-xs text-muted-foreground font-medium mb-0.5">Document</p>
            <p className="text-sm font-medium truncate">{documentTitle}</p>
          </div>

          {/* Meaning selector — §11.50(a) */}
          <div>
            <label className="text-sm font-medium block mb-2">Meaning of signature</label>
            <div className="space-y-2">
              {MEANINGS.map((m) => (
                <label
                  key={m.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    meaning === m.value
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/40 hover:bg-muted/30"
                  }`}
                >
                  <input
                    type="radio"
                    name="meaning"
                    value={m.value}
                    checked={meaning === m.value}
                    onChange={() => setMeaning(m.value)}
                    className="mt-0.5 accent-primary"
                  />
                  <div>
                    <p className="text-sm font-medium">{m.label}</p>
                    <p className="text-xs text-muted-foreground">{m.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Password re-authentication — §11.200(b) */}
          <div>
            <label className="text-sm font-medium block mb-1.5" htmlFor="sig-password">
              Confirm your password
            </label>
            <div className="relative">
              <input
                id="sig-password"
                type={showPw ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Re-enter your password to sign"
                className="w-full px-3 py-2.5 pr-10 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5">
              Required by 21 CFR §11.200(b) — each signature act must be accompanied by password re-authentication.
            </p>
          </div>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* Legal notice */}
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
            <Shield className="w-3.5 h-3.5 text-amber-700 flex-shrink-0 mt-0.5" />
            <p className="text-[11px] text-amber-800 leading-relaxed">
              By signing, you certify this action carries the same legal weight as a handwritten signature and will be recorded in the tamper-evident audit trail.
            </p>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 border rounded-lg text-sm hover:bg-accent transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !password}
              className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <PenLine className="w-4 h-4" />}
              {loading ? "Signing…" : "Apply Signature"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

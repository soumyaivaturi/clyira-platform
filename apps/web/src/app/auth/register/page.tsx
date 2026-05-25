"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shield, Eye, EyeOff, Loader2, ChevronRight, ChevronLeft } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

type Step = "account" | "company";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isLoading } = useAuth();

  const [step, setStep] = useState<Step>("account");
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    // Fire-and-forget warmup so Render's free-tier container is awake by
    // the time the user finishes filling the form (~30-60s later).
    fetch("/api/v1/auth/me").catch(() => {});
  }, []);

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    company_name: "",
  });

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleAccountNext = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (new TextEncoder().encode(form.password).length > 72) {
      setError("Password must be 72 characters or fewer");
      return;
    }
    setStep("company");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const attempt = async () => {
      await register(form);
      window.location.href = "/auth/onboarding";
    };
    try {
      await attempt();
    } catch (err: any) {
      if (!err.response) {
        // Network error — likely a cold start. Wait 20s and retry once.
        setRetrying(true);
        setError("Server is starting up — retrying in 20 seconds…");
        await new Promise((r) => setTimeout(r, 20000));
        setRetrying(false);
        setError("");
        try {
          await attempt();
        } catch (err2: any) {
          setError(err2.response?.data?.detail ?? "Registration failed. Please try again.");
        }
      } else {
        setError(err.response?.data?.detail ?? `Server error (${err.response.status})`);
      }
    }
  };

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <img src="/clyira-logo.png" alt="Clyira" className="w-10 h-10 object-contain" />
          <span className="text-2xl font-bold tracking-tight">
            CLYIRA<span style={{ color: "#7654c9", fontSize: "1.4em", lineHeight: 1 }}>.</span>AI
          </span>
        </div>

        <div className="bg-card border rounded-xl p-8 shadow-sm">
          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-6">
            <div className={`flex items-center gap-1.5 text-xs font-medium ${step === "account" ? "text-primary" : "text-muted-foreground"}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step === "account" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>1</div>
              Your account
            </div>
            <div className="flex-1 h-px bg-border" />
            <div className={`flex items-center gap-1.5 text-xs font-medium ${step === "company" ? "text-primary" : "text-muted-foreground"}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step === "company" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>2</div>
              Your company
            </div>
          </div>

          {step === "account" ? (
            <form onSubmit={handleAccountNext} className="space-y-4">
              <div>
                <h1 className="text-xl font-semibold">Create your account</h1>
                <p className="text-sm text-muted-foreground mt-1">Start your 14-day free trial</p>
              </div>

              <div>
                <label className="text-sm font-medium block mb-1.5" htmlFor="full_name">Full name</label>
                <input
                  id="full_name"
                  type="text"
                  required
                  value={form.full_name}
                  onChange={set("full_name")}
                  placeholder="Jane Smith"
                  className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-1.5" htmlFor="email">Work email</label>
                <input
                  id="email"
                  type="email"
                  required
                  value={form.email}
                  onChange={set("email")}
                  placeholder="you@yourcompany.com"
                  className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-1.5" htmlFor="password">Password</label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={form.password}
                    onChange={set("password")}
                    placeholder="8+ chars, uppercase, lowercase, digit"
                    className="w-full px-3 py-2.5 pr-10 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Continue
                <ChevronRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <h1 className="text-xl font-semibold">Your company</h1>
                <p className="text-sm text-muted-foreground mt-1">We'll set up your quality workspace</p>
              </div>

              <div>
                <label className="text-sm font-medium block mb-1.5" htmlFor="company_name">Company name</label>
                <input
                  id="company_name"
                  type="text"
                  required
                  value={form.company_name}
                  onChange={set("company_name")}
                  placeholder="Acme Pharmaceuticals Inc."
                  className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  You'll configure agencies, sub-sectors, and markets in the next step.
                </p>
              </div>

              {error && (
                <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep("account")}
                  className="flex items-center gap-1.5 px-4 py-2.5 border rounded-lg text-sm hover:bg-accent transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isLoading || retrying}
                  className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                >
                  {(isLoading || retrying) && <Loader2 className="w-4 h-4 animate-spin" />}
                  {retrying ? "Retrying…" : "Create account"}
                </button>
              </div>
            </form>
          )}

          <div className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/auth/login" className="text-primary font-medium hover:underline">
              Sign in
            </Link>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <Shield className="w-3.5 h-3.5" />
          <span>21 CFR Part 11 compliant · SOC 2 Type II</span>
        </div>
      </div>
    </div>
  );
}

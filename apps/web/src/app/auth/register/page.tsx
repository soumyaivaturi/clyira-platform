"use client";

import { useState } from "react";
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
    setStep("company");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await register(form);
      router.push("/auth/onboarding");
    } catch (err: any) {
      let msg = "Registration failed. Please try again.";
      if (!err.response) {
        if (err.code === "ECONNABORTED") {
          msg = "Request timed out — server is starting up, please wait 30 seconds and try again.";
        } else {
          msg = `Network error: ${err.message}. Check browser console for CORS details.`;
        }
      } else {
        msg = err.response?.data?.detail ?? `Server error (${err.response.status})`;
      }
      setError(msg);
    }
  };

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-lg">C</span>
          </div>
          <span className="text-2xl font-semibold">Clyira</span>
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
                    placeholder="Min. 8 characters"
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
                  disabled={isLoading}
                  className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                  Create account
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

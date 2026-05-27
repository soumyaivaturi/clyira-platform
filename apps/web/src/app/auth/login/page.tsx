"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Shield, Eye, EyeOff, Loader2, Clock } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { ClyiraLogo } from "@/components/shared/clyira-logo";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);

  const idleTimeout = searchParams.get("reason") === "idle";

  useEffect(() => {
    fetch("/api/v1/auth/me").catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLocked(false);
    try {
      await login(email, password);
      window.location.href = "/dashboard";
    } catch (err: any) {
      if (err?.response?.status === 423) {
        setLocked(true);
        setError(err.response.data.detail);
      } else {
        setError(err?.response?.data?.detail ?? "Invalid email or password");
      }
    }
  };

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <ClyiraLogo className="h-12 w-auto" />
        </div>

        <div className="bg-card border rounded-xl p-8 shadow-sm">
          {idleTimeout && (
            <div className="mb-4 flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
              <Clock className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>You were signed out after 30 minutes of inactivity.</span>
            </div>
          )}

          <div className="mb-6">
            <h1 className="text-xl font-semibold">Sign in to your account</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Quality intelligence for life sciences
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium block mb-1.5" htmlFor="email">
                Work email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yourcompany.com"
                className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium" htmlFor="password">
                  Password
                </label>
                <Link href="/auth/forgot" className="text-xs text-primary hover:underline">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
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
              <div className={`text-sm rounded-lg px-3 py-2 border ${
                locked
                  ? "text-amber-800 bg-amber-50 border-amber-200"
                  : "text-destructive bg-destructive/10 border-destructive/20"
              }`}>
                {locked && <p className="font-medium mb-0.5">Account locked</p>}
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || locked}
              className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
              Sign in
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/auth/register" className="text-primary font-medium hover:underline">
              Create one
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

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}

"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { Settings, User, Building2, Bell, Shield, Key } from "lucide-react";

const TABS = [
  { key: "profile", label: "Profile", icon: User },
  { key: "company", label: "Company", icon: Building2 },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "security", label: "Security", icon: Shield },
  { key: "api", label: "API Keys", icon: Key },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("profile");

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Manage your account, company, and platform preferences</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar nav */}
        <nav className="w-48 flex-shrink-0 space-y-1">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors ${
                tab === t.key
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}>
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </nav>

        {/* Content */}
        <div className="flex-1 space-y-4">
          {tab === "profile" && (
            <div className="bg-card border rounded-xl p-6 space-y-5">
              <h2 className="font-semibold text-sm">Profile Information</h2>

              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-xl font-bold text-primary">
                    {user?.full_name?.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) ?? "?"}
                  </span>
                </div>
                <div>
                  <p className="font-semibold">{user?.full_name ?? "—"}</p>
                  <p className="text-sm text-muted-foreground capitalize">{user?.role ?? ""}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Full Name</label>
                  <input defaultValue={user?.full_name ?? ""} readOnly
                    className="w-full border rounded-lg px-3 py-2 text-sm bg-muted/30 text-muted-foreground cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Email</label>
                  <input defaultValue={user?.email ?? ""} readOnly
                    className="w-full border rounded-lg px-3 py-2 text-sm bg-muted/30 text-muted-foreground cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Role</label>
                  <input defaultValue={user?.role ?? ""} readOnly
                    className="w-full border rounded-lg px-3 py-2 text-sm bg-muted/30 text-muted-foreground cursor-not-allowed capitalize" />
                </div>
              </div>

              <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg px-3 py-2">
                Profile editing will be available in a future release. Contact your administrator to update profile details.
              </p>
            </div>
          )}

          {tab === "company" && (
            <div className="bg-card border rounded-xl p-6 space-y-4">
              <h2 className="font-semibold text-sm">Company Settings</h2>
              <p className="text-sm text-muted-foreground">
                Company details are configured during onboarding. Contact your Clyira account manager to update company information.
              </p>
              <div className="bg-muted/30 rounded-lg px-4 py-3 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Company ID</span>
                  <span className="font-mono text-xs">{user?.company_id ?? "—"}</span>
                </div>
              </div>
            </div>
          )}

          {tab === "notifications" && (
            <div className="bg-card border rounded-xl p-6 space-y-5">
              <h2 className="font-semibold text-sm">Notification Preferences</h2>
              {[
                { label: "Assessment completed", desc: "When a document AI assessment finishes" },
                { label: "Score drops below threshold", desc: "When a department score falls below 65" },
                { label: "Inspection request logged", desc: "When a new inspector request is added" },
                { label: "Enforcement alerts", desc: "New regulatory warning letters and enforcement actions" },
              ].map(n => (
                <div key={n.label} className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">{n.label}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{n.desc}</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
                    <input type="checkbox" defaultChecked className="sr-only peer" />
                    <div className="w-9 h-5 bg-muted rounded-full peer peer-checked:bg-primary transition-colors" />
                    <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
                  </label>
                </div>
              ))}
              <p className="text-xs text-muted-foreground">Notification delivery (email, in-app) will be configurable in a future release.</p>
            </div>
          )}

          {tab === "security" && (
            <div className="bg-card border rounded-xl p-6 space-y-4">
              <h2 className="font-semibold text-sm">Security</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="text-sm font-medium">Password</p>
                    <p className="text-xs text-muted-foreground">Last changed: unknown</p>
                  </div>
                  <button disabled className="px-3 py-1.5 text-xs font-medium border rounded-lg text-muted-foreground cursor-not-allowed opacity-50">
                    Change password
                  </button>
                </div>
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="text-sm font-medium">Two-Factor Authentication</p>
                    <p className="text-xs text-muted-foreground">Add an extra layer of security</p>
                  </div>
                  <button disabled className="px-3 py-1.5 text-xs font-medium border rounded-lg text-muted-foreground cursor-not-allowed opacity-50">
                    Enable 2FA
                  </button>
                </div>
              </div>
              <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg px-3 py-2">
                Advanced security features will be available in a future release.
              </p>
            </div>
          )}

          {tab === "api" && (
            <div className="bg-card border rounded-xl p-6 space-y-4">
              <h2 className="font-semibold text-sm">API Keys</h2>
              <p className="text-sm text-muted-foreground">
                API key management for integrating Clyira with your existing quality management systems.
              </p>
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
                <p className="text-xs text-amber-800 font-medium">API key management is coming in a future release.</p>
                <p className="text-xs text-amber-700 mt-0.5">Contact your Clyira account manager for early access.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { companiesApi, notificationsApi } from "@/lib/api";
import { Settings, User, Building2, Bell, Shield, Key, Save, Loader2, CheckCircle, X, Send, Mail } from "lucide-react";

const TABS = [
  { key: "profile", label: "Profile", icon: User },
  { key: "company", label: "Company", icon: Building2 },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "security", label: "Security", icon: Shield },
  { key: "api", label: "API Keys", icon: Key },
];

const SUB_SECTORS = [
  "Small Molecule API",
  "Biologics / mAb",
  "Cell & Gene Therapy",
  "Medical Devices",
  "Combination Products",
  "Contract Manufacturing (CMO)",
  "Contract Testing (CRO/CDMO)",
  "Nutraceuticals / Supplements",
  "Veterinary Pharma",
  "Diagnostics",
];

const AGENCIES = [
  "FDA (US)",
  "EMA (EU)",
  "MHRA (UK)",
  "Health Canada",
  "TGA (Australia)",
  "PMDA (Japan)",
  "NMPA (China)",
  "ANVISA (Brazil)",
  "CDSCO (India)",
];

const MARKETS = [
  "United States",
  "European Union",
  "United Kingdom",
  "Canada",
  "Australia",
  "Japan",
  "China",
  "Brazil",
  "India",
  "Rest of World",
];

const CERTIFICATIONS = ["ISO 13485", "ISO 9001", "GMP", "GDP", "GCP", "GLP", "HACCP", "ISO 15378"];

function TagSelector({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (opt: string) =>
    onChange(selected.includes(opt) ? selected.filter((s) => s !== opt) : [...selected, opt]);

  return (
    <div>
      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = selected.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                active
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
              }`}
            >
              {opt}
            </button>
          );
        })}
      </div>
      {selected.length === 0 && (
        <p className="text-[11px] text-destructive mt-1.5">Select at least one option</p>
      )}
    </div>
  );
}

function CompanyTab() {
  const [company, setCompany] = useState<{
    name: string;
    sub_sectors: string[];
    agencies: string[];
    markets: string[];
    certifications: string[];
    id: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  // Editable state
  const [name, setName] = useState("");
  const [subSectors, setSubSectors] = useState<string[]>([]);
  const [agencies, setAgencies] = useState<string[]>([]);
  const [markets, setMarkets] = useState<string[]>([]);
  const [certifications, setCertifications] = useState<string[]>([]);

  useEffect(() => {
    companiesApi.me().then((res) => {
      const c = res.data;
      setCompany(c);
      setName(c.name);
      setSubSectors(c.sub_sectors ?? []);
      setAgencies(c.agencies ?? []);
      setMarkets(c.markets ?? []);
      setCertifications(c.certifications ?? []);
    }).catch(() => setError("Could not load company settings."))
      .finally(() => setLoading(false));
  }, []);

  const isDirty =
    name !== (company?.name ?? "") ||
    JSON.stringify([...subSectors].sort()) !== JSON.stringify([...(company?.sub_sectors ?? [])].sort()) ||
    JSON.stringify([...agencies].sort()) !== JSON.stringify([...(company?.agencies ?? [])].sort()) ||
    JSON.stringify([...markets].sort()) !== JSON.stringify([...(company?.markets ?? [])].sort()) ||
    JSON.stringify([...certifications].sort()) !== JSON.stringify([...(company?.certifications ?? [])].sort());

  const canSave = isDirty && subSectors.length > 0 && agencies.length > 0 && markets.length > 0 && name.trim();

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const res = await companiesApi.update({
        name: name.trim(),
        sub_sectors: subSectors,
        agencies,
        markets,
        certifications,
      });
      setCompany(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Save failed. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-card border rounded-xl p-6 space-y-4 animate-pulse">
        {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-muted rounded-lg" />)}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-card border rounded-xl p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-sm">Company Profile</h2>
          <div className="flex items-center gap-2">
            {saved && (
              <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                <CheckCircle className="w-3.5 h-3.5" /> Saved
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={!canSave || saving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              Save Changes
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
            <X className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Company Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <div className="grid grid-cols-2 gap-4 pt-1 text-xs text-muted-foreground border-t">
          <div><span className="font-medium">Company ID</span><br /><span className="font-mono">{company?.id ?? "—"}</span></div>
        </div>
      </div>

      <div className="bg-card border rounded-xl p-6 space-y-5">
        <h2 className="font-semibold text-sm">Regulatory Configuration</h2>
        <p className="text-xs text-muted-foreground -mt-2">
          Clyira uses these settings to tailor assessments, enforcement alerts, and inspection simulations.
        </p>

        <TagSelector
          label="Sub-Sectors *"
          options={SUB_SECTORS}
          selected={subSectors}
          onChange={setSubSectors}
        />

        <TagSelector
          label="Regulatory Agencies *"
          options={AGENCIES}
          selected={agencies}
          onChange={setAgencies}
        />

        <TagSelector
          label="Target Markets *"
          options={MARKETS}
          selected={markets}
          onChange={setMarkets}
        />

        <TagSelector
          label="Certifications"
          options={CERTIFICATIONS}
          selected={certifications}
          onChange={setCertifications}
        />

        <div className="pt-2 flex justify-end">
          <button
            onClick={handleSave}
            disabled={!canSave || saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

function NotificationsTab() {
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ sent: boolean; to?: string; reason?: string } | null>(null);

  const handleTestEmail = async () => {
    setSending(true);
    setResult(null);
    try {
      const res = await notificationsApi.testEmail();
      setResult(res.data);
    } catch {
      setResult({ sent: false, reason: "Request failed — check console for details." });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-card border rounded-xl p-6 space-y-5">
        <h2 className="font-semibold text-sm">Email Notifications</h2>
        <p className="text-xs text-muted-foreground -mt-2">
          Clyira sends email alerts when assessments complete or critical quality events occur.
          Requires <code className="bg-muted px-1 py-0.5 rounded text-[10px] font-mono">RESEND_API_KEY</code> to be set in your Render environment.
        </p>

        {[
          { label: "Assessment completed", desc: "Detailed score and findings summary when an AI assessment finishes", active: true },
          { label: "Data Integrity hold", desc: "Immediate alert when a DI hold is activated (score capped at 50)", active: true },
        ].map(n => (
          <div key={n.label} className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium">{n.label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{n.desc}</p>
            </div>
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold ${
              n.active ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-muted text-muted-foreground border"
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${n.active ? "bg-emerald-500" : "bg-muted-foreground/40"}`} />
              {n.active ? "Active" : "Inactive"}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-card border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-sm">Send Test Email</h2>
        <p className="text-xs text-muted-foreground">
          Verify that email delivery is working by sending a test message to your account email.
        </p>

        <button
          onClick={handleTestEmail}
          disabled={sending}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 transition-colors"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          {sending ? "Sending…" : "Send Test Email"}
        </button>

        {result && (
          <div className={`flex items-start gap-3 p-3 rounded-lg border text-sm ${
            result.sent
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-amber-50 border-amber-200 text-amber-800"
          }`}>
            {result.sent
              ? <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              : <Mail className="w-4 h-4 mt-0.5 flex-shrink-0" />
            }
            <div>
              {result.sent
                ? <p>Test email sent to <strong>{result.to}</strong>. Check your inbox.</p>
                : <p>{result.reason || "Email could not be sent."}</p>
              }
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

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
                    {user?.full_name?.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2) ?? "?"}
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

          {tab === "company" && <CompanyTab />}

          {tab === "notifications" && <NotificationsTab />}

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

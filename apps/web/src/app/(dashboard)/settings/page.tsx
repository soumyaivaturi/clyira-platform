"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { companiesApi, notificationsApi, authApi, apiKeysApi } from "@/lib/api";
import {
  Settings, User, Building2, Bell, Shield, Key, Save, Loader2, CheckCircle, X,
  Send, Mail, Eye, EyeOff, Copy, Trash2, Plus, Plug2, AlertTriangle,
} from "lucide-react";

const TABS = [
  { key: "profile", label: "Profile", icon: User },
  { key: "company", label: "Company", icon: Building2 },
  { key: "notifications", label: "Notifications", icon: Bell },
  { key: "security", label: "Security", icon: Shield },
  { key: "api", label: "API Keys", icon: Key },
  { key: "integrations", label: "Integrations", icon: Plug2 },
];

const SUB_SECTORS = [
  "Small Molecule API", "Biologics / mAb", "Cell & Gene Therapy",
  "Medical Devices", "Combination Products", "Contract Manufacturing (CMO)",
  "Contract Testing (CRO/CDMO)", "Nutraceuticals / Supplements",
  "Veterinary Pharma", "Diagnostics",
];

const AGENCIES = [
  "FDA (US)", "EMA (EU)", "MHRA (UK)", "Health Canada",
  "TGA (Australia)", "PMDA (Japan)", "NMPA (China)", "ANVISA (Brazil)", "CDSCO (India)",
];

const MARKETS = [
  "United States", "European Union", "United Kingdom", "Canada",
  "Australia", "Japan", "China", "Brazil", "India", "Rest of World",
];

const CERTIFICATIONS = ["ISO 13485", "ISO 9001", "GMP", "GDP", "GCP", "GLP", "HACCP", "ISO 15378"];

const INTEGRATION_TYPES = [
  { code: "mes", label: "MES", name: "Manufacturing Execution System", desc: "Sync batch records, production orders, and in-process controls" },
  { code: "lims", label: "LIMS", name: "Laboratory Information Management", desc: "Pull analytical results, OOS events, and method validations" },
  { code: "vlms", label: "VLMS", name: "Vendor / Supplier Management", desc: "Connect supplier qualifications, audits, and approved vendor lists" },
  { code: "qms", label: "QMS", name: "Quality Management System", desc: "Bi-directional sync of CAPAs, deviations, and change controls" },
  { code: "erp", label: "ERP", name: "Enterprise Resource Planning", desc: "Link batch disposition, inventory, and release decisions" },
  { code: "custom", label: "Custom", name: "Custom Integration", desc: "Connect any internal system via REST API using a bearer token" },
];

// ── Shared helpers ─────────────────────────────────────────────────────────────

function TagSelector({
  label, options, selected, onChange,
}: { label: string; options: string[]; selected: string[]; onChange: (v: string[]) => void }) {
  const toggle = (opt: string) =>
    onChange(selected.includes(opt) ? selected.filter((s) => s !== opt) : [...selected, opt]);
  return (
    <div>
      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = selected.includes(opt);
          return (
            <button key={opt} type="button" onClick={() => toggle(opt)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                active
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
              }`}>
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

// ── Company Tab ────────────────────────────────────────────────────────────────

function CompanyTab() {
  const [company, setCompany] = useState<{
    name: string; sub_sectors: string[]; agencies: string[];
    markets: string[]; certifications: string[]; id: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [subSectors, setSubSectors] = useState<string[]>([]);
  const [agencies, setAgencies] = useState<string[]>([]);
  const [markets, setMarkets] = useState<string[]>([]);
  const [certifications, setCertifications] = useState<string[]>([]);

  useEffect(() => {
    companiesApi.me().then((res) => {
      const c = res.data;
      setCompany(c); setName(c.name);
      setSubSectors(c.sub_sectors ?? []); setAgencies(c.agencies ?? []);
      setMarkets(c.markets ?? []); setCertifications(c.certifications ?? []);
    }).catch(() => setError("Could not load company settings."))
      .finally(() => setLoading(false));
  }, []);

  const isDirty = name !== (company?.name ?? "") ||
    JSON.stringify([...subSectors].sort()) !== JSON.stringify([...(company?.sub_sectors ?? [])].sort()) ||
    JSON.stringify([...agencies].sort()) !== JSON.stringify([...(company?.agencies ?? [])].sort()) ||
    JSON.stringify([...markets].sort()) !== JSON.stringify([...(company?.markets ?? [])].sort()) ||
    JSON.stringify([...certifications].sort()) !== JSON.stringify([...(company?.certifications ?? [])].sort());

  const canSave = isDirty && subSectors.length > 0 && agencies.length > 0 && markets.length > 0 && name.trim();

  const handleSave = async () => {
    setSaving(true); setError("");
    try {
      const res = await companiesApi.update({ name: name.trim(), sub_sectors: subSectors, agencies, markets, certifications });
      setCompany(res.data); setSaved(true); setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Save failed. Please try again.");
    } finally { setSaving(false); }
  };

  if (loading) return <div className="bg-card border rounded-xl p-6 space-y-4 animate-pulse">{[1,2,3].map(i => <div key={i} className="h-20 bg-muted rounded-lg" />)}</div>;

  return (
    <div className="space-y-4">
      <div className="bg-card border rounded-xl p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-sm">Company Profile</h2>
          <div className="flex items-center gap-2">
            {saved && <span className="flex items-center gap-1 text-xs text-green-600 font-medium"><CheckCircle className="w-3.5 h-3.5" /> Saved</span>}
            <button onClick={handleSave} disabled={!canSave || saving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              Save Changes
            </button>
          </div>
        </div>
        {error && <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2"><X className="w-4 h-4 flex-shrink-0" />{error}</div>}
        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Company Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
        <div className="grid grid-cols-2 gap-4 pt-1 text-xs text-muted-foreground border-t">
          <div><span className="font-medium">Company ID</span><br /><span className="font-mono">{company?.id ?? "—"}</span></div>
        </div>
      </div>
      <div className="bg-card border rounded-xl p-6 space-y-5">
        <h2 className="font-semibold text-sm">Regulatory Configuration</h2>
        <p className="text-xs text-muted-foreground -mt-2">Clyira uses these settings to tailor assessments, enforcement alerts, and inspection simulations.</p>
        <TagSelector label="Sub-Sectors *" options={SUB_SECTORS} selected={subSectors} onChange={setSubSectors} />
        <TagSelector label="Regulatory Agencies *" options={AGENCIES} selected={agencies} onChange={setAgencies} />
        <TagSelector label="Target Markets *" options={MARKETS} selected={markets} onChange={setMarkets} />
        <TagSelector label="Certifications" options={CERTIFICATIONS} selected={certifications} onChange={setCertifications} />
        <div className="pt-2 flex justify-end">
          <button onClick={handleSave} disabled={!canSave || saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Notifications Tab ──────────────────────────────────────────────────────────

function NotificationsTab() {
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ sent: boolean; to?: string; reason?: string } | null>(null);

  const handleTestEmail = async () => {
    setSending(true); setResult(null);
    try { const res = await notificationsApi.testEmail(); setResult(res.data); }
    catch { setResult({ sent: false, reason: "Request failed — check console for details." }); }
    finally { setSending(false); }
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
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold ${n.active ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-muted text-muted-foreground border"}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${n.active ? "bg-emerald-500" : "bg-muted-foreground/40"}`} />
              {n.active ? "Active" : "Inactive"}
            </div>
          </div>
        ))}
      </div>
      <div className="bg-card border rounded-xl p-6 space-y-4">
        <h2 className="font-semibold text-sm">Send Test Email</h2>
        <p className="text-xs text-muted-foreground">Verify that email delivery is working by sending a test message to your account email.</p>
        <button onClick={handleTestEmail} disabled={sending}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 transition-colors">
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          {sending ? "Sending…" : "Send Test Email"}
        </button>
        {result && (
          <div className={`flex items-start gap-3 p-3 rounded-lg border text-sm ${result.sent ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-amber-50 border-amber-200 text-amber-800"}`}>
            {result.sent ? <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> : <Mail className="w-4 h-4 mt-0.5 flex-shrink-0" />}
            <div>{result.sent ? <p>Test email sent to <strong>{result.to}</strong>. Check your inbox.</p> : <p>{result.reason || "Email could not be sent."}</p>}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Security Tab ───────────────────────────────────────────────────────────────

function SecurityTab() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setSuccess(false);
    if (next.length < 8) { setError("New password must be at least 8 characters"); return; }
    if (next !== confirm) { setError("Passwords do not match"); return; }
    setSaving(true);
    try {
      await authApi.changePassword(current, next);
      setSuccess(true);
      setCurrent(""); setNext(""); setConfirm("");
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Password change failed. Please try again.");
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-4">
      <div className="bg-card border rounded-xl p-6 space-y-5">
        <h2 className="font-semibold text-sm">Change Password</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Current Password</label>
            <div className="relative">
              <input type={showCurrent ? "text" : "password"} required value={current} onChange={e => setCurrent(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
              <button type="button" onClick={() => setShowCurrent(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">New Password</label>
            <div className="relative">
              <input type={showNext ? "text" : "password"} required value={next} onChange={e => setNext(e.target.value)}
                placeholder="8–72 characters"
                className="w-full border rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
              <button type="button" onClick={() => setShowNext(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                {showNext ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Confirm New Password</label>
            <input type="password" required value={confirm} onChange={e => setConfirm(e.target.value)}
              className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              <X className="w-4 h-4 flex-shrink-0" />{error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />Password changed successfully.
            </div>
          )}
          <button type="submit" disabled={saving || !current || !next || !confirm}
            className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {saving ? "Saving…" : "Update Password"}
          </button>
        </form>
      </div>
      <div className="bg-card border rounded-xl p-6 space-y-3">
        <h2 className="font-semibold text-sm">Two-Factor Authentication</h2>
        <p className="text-xs text-muted-foreground">Add an extra layer of security with TOTP authenticator app support.</p>
        <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
          <p className="text-xs text-muted-foreground">2FA enrollment is coming in a future release.</p>
        </div>
      </div>
    </div>
  );
}

// ── API Keys Tab ───────────────────────────────────────────────────────────────

type APIKeyRow = {
  id: string; name: string; key_prefix: string;
  integration_type: string | null; created_at: string | null;
  last_used_at: string | null; is_active: boolean;
};

function APIKeysTab() {
  const [keys, setKeys] = useState<APIKeyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [revealedKey, setRevealedKey] = useState<{ id: string; key: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const load = () =>
    apiKeysApi.list().then(r => setKeys(r.data)).catch(() => setError("Failed to load API keys"))
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true); setError("");
    try {
      const res = await apiKeysApi.create(newName.trim(), newType || undefined);
      setRevealedKey({ id: res.data.id, key: res.data.key });
      setNewName(""); setNewType(""); setShowForm(false);
      load();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to create key");
    } finally { setCreating(false); }
  };

  const handleRevoke = async (id: string) => {
    try {
      await apiKeysApi.revoke(id);
      setKeys(prev => prev.filter(k => k.id !== id));
      if (revealedKey?.id === id) setRevealedKey(null);
    } catch { setError("Failed to revoke key"); }
  };

  const handleCopy = () => {
    if (!revealedKey) return;
    navigator.clipboard.writeText(revealedKey.key);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      {revealedKey && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-900">Copy your API key now — it won&apos;t be shown again</p>
              <p className="text-xs text-amber-700 mt-0.5">Store it securely. After closing this notice, only the key prefix will be visible.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-amber-200 rounded-lg px-3 py-2 text-xs font-mono break-all text-amber-900">
              {revealedKey.key}
            </code>
            <button onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white rounded-lg text-xs font-medium hover:bg-amber-700 transition-colors whitespace-nowrap">
              {copied ? <CheckCircle className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied!" : "Copy"}
            </button>
            <button onClick={() => setRevealedKey(null)}
              className="p-2 text-amber-600 hover:text-amber-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="bg-card border rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-sm">API Keys</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Authenticate external systems with <code className="bg-muted px-1 py-0.5 rounded text-[10px] font-mono">Authorization: Bearer &lt;key&gt;</code></p>
          </div>
          <button onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 transition-colors">
            <Plus className="w-3.5 h-3.5" />
            New Key
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="bg-muted/40 border rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Key Name</label>
                <input required value={newName} onChange={e => setNewName(e.target.value)}
                  placeholder="e.g. MES Production"
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Integration Type</label>
                <select value={newType} onChange={e => setNewType(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="">Select type (optional)</option>
                  {INTEGRATION_TYPES.map(t => <option key={t.code} value={t.code}>{t.label} — {t.name}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={creating || !newName.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Create Key
              </button>
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 border rounded-lg text-xs font-medium hover:bg-accent transition-colors">
                Cancel
              </button>
            </div>
          </form>
        )}

        {error && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
            <X className="w-4 h-4 flex-shrink-0" />{error}
          </div>
        )}

        {loading ? (
          <div className="space-y-2">{[1,2].map(i => <div key={i} className="h-14 bg-muted rounded-lg animate-pulse" />)}</div>
        ) : keys.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Key className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No API keys yet. Create one to connect external systems.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {keys.map(k => (
              <div key={k.id} className="flex items-center justify-between gap-4 p-3 border rounded-lg hover:bg-muted/20 transition-colors">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{k.name}</span>
                    {k.integration_type && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-semibold uppercase">{k.integration_type}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <code className="text-xs font-mono text-muted-foreground">{k.key_prefix}…</code>
                    <span className="text-xs text-muted-foreground">
                      Created {k.created_at ? new Date(k.created_at).toLocaleDateString() : "—"}
                    </span>
                    {k.last_used_at && (
                      <span className="text-xs text-muted-foreground">
                        Last used {new Date(k.last_used_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <button onClick={() => handleRevoke(k.id)}
                  className="flex items-center gap-1 px-2.5 py-1.5 text-destructive border border-destructive/20 bg-destructive/5 rounded-lg text-xs font-medium hover:bg-destructive/10 transition-colors whitespace-nowrap">
                  <Trash2 className="w-3.5 h-3.5" />
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Integrations Tab ───────────────────────────────────────────────────────────

function IntegrationsTab() {
  return (
    <div className="space-y-4">
      <div className="bg-card border rounded-xl p-6 space-y-1">
        <h2 className="font-semibold text-sm">System Integrations</h2>
        <p className="text-xs text-muted-foreground">
          Connect Clyira to your existing quality and manufacturing systems. All integrations use bearer-token auth via API keys — create a key in the <strong>API Keys</strong> tab first.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {INTEGRATION_TYPES.map((intg) => (
          <div key={intg.code} className="bg-card border rounded-xl p-5 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-primary/10 text-primary uppercase tracking-wide">{intg.label}</span>
                </div>
                <p className="text-sm font-semibold mt-1">{intg.name}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{intg.desc}</p>
              </div>
              <span className="flex-shrink-0 text-[10px] px-2 py-1 rounded-full border bg-muted/50 text-muted-foreground font-medium whitespace-nowrap">
                Coming soon
              </span>
            </div>
            <div className="pt-2 border-t">
              <p className="text-[11px] text-muted-foreground">
                Use the REST API with <code className="bg-muted px-1 py-0.5 rounded font-mono">integration_type: {intg.code}</code> today — native connector launching Q3 2026.
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-primary/5 border border-primary/20 rounded-xl p-5">
        <p className="text-sm font-semibold text-primary mb-1">One platform, zero silos</p>
        <p className="text-xs text-muted-foreground">
          Clyira acts as a single unified quality intelligence layer across your MES, LIMS, VLMS, QMS, and ERP. Documents and quality events from any connected system are assessed against the same regulatory corpus — giving you one consistent view of compliance health across the entire operation.
        </p>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

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
        <nav className="w-48 flex-shrink-0 space-y-1">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors ${
                tab === t.key ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`}>
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </nav>

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
          {tab === "security" && <SecurityTab />}
          {tab === "api" && <APIKeysTab />}
          {tab === "integrations" && <IntegrationsTab />}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  FlaskConical, ChevronLeft, Loader2, ChevronRight, Info,
  Upload, Sparkles, CheckCircle2, AlertCircle, BookOpen, X,
} from "lucide-react";
import Link from "next/link";
import { batchDossiersApi, productProfilesApi } from "@/lib/api";

// ── Options ───────────────────────────────────────────────────────────────────

const RECORD_FAMILIES = [
  { value: "pharma_bpr",      label: "Pharma BPR / BMR" },
  { value: "api_batch",       label: "API Batch Record" },
  { value: "biologics_batch", label: "Biologics BPR" },
  { value: "sterile_batch",   label: "Sterile BPR" },
  { value: "device_dhr",      label: "Device DHR" },
  { value: "supplement_bpr",  label: "Supplement BPR / MMR" },
  { value: "cell_therapy",    label: "Cell / Gene Therapy" },
  { value: "cdmo_package",    label: "CDMO Sponsor Package" },
];

const PRODUCT_TYPES = [
  { value: "small_molecule", label: "Small Molecule" },
  { value: "biologic",       label: "Biologic / Biosimilar" },
  { value: "vaccine",        label: "Vaccine" },
  { value: "api",            label: "API / Drug Substance" },
  { value: "combination",    label: "Combination Product" },
  { value: "supplement",     label: "Dietary Supplement" },
  { value: "device",         label: "Medical Device" },
  { value: "cell_therapy",   label: "Cell / Gene Therapy" },
];

const BATCH_PURPOSES = [
  { value: "commercial",    label: "Commercial" },
  { value: "validation",   label: "Validation / PPQ" },
  { value: "exhibit",      label: "Exhibit (Regulatory Filing)" },
  { value: "stability",    label: "Stability" },
  { value: "tech_transfer", label: "Tech Transfer" },
  { value: "clinical",     label: "Clinical" },
  { value: "scale_up",     label: "Scale-Up" },
];

const AGENCIES = ["FDA", "EMA", "PMDA", "MHRA", "Health_Canada", "TGA", "ANVISA"];

// ── UI atoms ──────────────────────────────────────────────────────────────────

function Field({ label, required, children, hint }: {
  label: string; required?: boolean; children: React.ReactNode; hint?: string;
}) {
  return (
    <div>
      <label className="text-sm font-medium block mb-1.5">
        {label}{required && <span className="text-destructive ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

function Input({ scanned, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { scanned?: boolean }) {
  return (
    <div className="relative">
      <input
        className={`w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors ${
          scanned ? "border-emerald-400 bg-emerald-50/40 dark:bg-emerald-950/20" : ""
        }`}
        {...props}
      />
      {scanned && (
        <Sparkles className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-emerald-500 pointer-events-none" />
      )}
    </div>
  );
}

function Select({ ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
      {...props}
    />
  );
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface ScanResult {
  fields: Record<string, string | null>;
  confidence: Record<string, number | null>;
}

interface ProductProfile {
  id: string;
  profile_name: string;
  product_code?: string;
  product_name?: string;
  dosage_form?: string;
  manufacturing_site?: string;
  classification: {
    record_family: string; product_type: string; is_sterile: boolean;
    manufacturing_context: string; batch_purpose: string; target_markets: string[];
  };
  template?: { required_fields?: string[] };
}

// ── Page ─────────────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  lot_number: "",
  product_name: "",
  product_code: "",
  dosage_form: "",
  batch_size: "",
  manufacturing_site: "",
  manufacturing_date: "",
  target_release_date: "",
  record_family: "pharma_bpr",
  product_type: "small_molecule",
  is_sterile: false,
  manufacturing_context: "internal",
  batch_purpose: "commercial",
  target_markets: [] as string[],
  shadow_mode: false,
};

export default function NewDossierPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [scannedFields, setScannedFields] = useState<Set<string>>(new Set());
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState("");
  const [scanDone, setScanDone] = useState(false);

  const [profiles, setProfiles] = useState<ProductProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>("");
  const [profileApplied, setProfileApplied] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    productProfilesApi.list()
      .then((r) => setProfiles(r.data || []))
      .catch(() => {});
  }, []);

  const set = (key: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    // If user edits a scanned field, remove the sparkle highlight
    setScannedFields((prev) => { const s = new Set(prev); s.delete(key); return s; });
  };

  const toggleMarket = (agency: string) =>
    setForm((prev) => ({
      ...prev,
      target_markets: prev.target_markets.includes(agency)
        ? prev.target_markets.filter((m) => m !== agency)
        : [...prev.target_markets, agency],
    }));

  // ── Scan handler ──────────────────────────────────────────────────────────
  const handleScan = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanning(true);
    setScanError("");
    setScanDone(false);
    try {
      const res = await batchDossiersApi.scanDocument(file);
      const { fields, confidence } = res.data as ScanResult;
      const updates: Partial<typeof form> = {};
      const newScanned = new Set<string>();

      const LOT_FIELDS: (keyof typeof form)[] = [
        "lot_number", "product_name", "product_code", "dosage_form",
        "batch_size", "manufacturing_site", "manufacturing_date", "target_release_date",
      ];

      for (const key of LOT_FIELDS) {
        const val = fields[key];
        if (val && confidence[key] && confidence[key]! >= 0.7) {
          (updates as Record<string, unknown>)[key] = val;
          newScanned.add(key);
        }
      }

      setForm((prev) => ({ ...prev, ...updates }));
      setScannedFields(newScanned);
      setScanDone(true);
      if (newScanned.size === 0) setScanError("No fields detected. Fill in manually.");
    } catch {
      setScanError("Scan failed. You can still fill in fields manually.");
    } finally {
      setScanning(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── Profile apply ─────────────────────────────────────────────────────────
  const applyProfile = (profileId: string) => {
    setSelectedProfile(profileId);
    if (!profileId) { setProfileApplied(false); return; }
    const p = profiles.find((x) => x.id === profileId);
    if (!p) return;
    setForm((prev) => ({
      ...prev,
      product_name: prev.product_name || p.product_name || "",
      product_code: prev.product_code || p.product_code || "",
      dosage_form: prev.dosage_form || p.dosage_form || "",
      manufacturing_site: prev.manufacturing_site || p.manufacturing_site || "",
      record_family: p.classification.record_family,
      product_type: p.classification.product_type,
      is_sterile: p.classification.is_sterile,
      manufacturing_context: p.classification.manufacturing_context,
      batch_purpose: p.classification.batch_purpose,
      target_markets: p.classification.target_markets,
    }));
    setProfileApplied(true);
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.lot_number.trim()) { setError("Lot number is required"); return; }
    if (!form.product_name.trim()) { setError("Product name is required"); return; }

    setLoading(true);
    setError("");
    try {
      const res = await batchDossiersApi.create({
        ...form,
        product_code: form.product_code || undefined,
        dosage_form: form.dosage_form || undefined,
        batch_size: form.batch_size || undefined,
        manufacturing_site: form.manufacturing_site || undefined,
        manufacturing_date: form.manufacturing_date || undefined,
        target_release_date: form.target_release_date || undefined,
      });
      router.push(`/batch-dossiers/${res.data.id}`);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Failed to create dossier");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link href="/batch-dossiers" className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-primary" /> New Batch Dossier
          </h1>
          <p className="text-sm text-muted-foreground">Upload a BPR to auto-fill, or enter manually</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* ── Step 0: Quick-fill options ── */}
        <div className="bg-card border rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold">Quick Fill</h2>

          {/* Scan BPR */}
          <div>
            <p className="text-xs text-muted-foreground mb-2">
              Upload your BPR / batch record — Clyira extracts the lot number, dates, site, and product info automatically.
            </p>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                onChange={handleScan}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={scanning}
                className="flex items-center gap-2 px-3 py-2 border rounded-lg text-sm hover:bg-accent transition-colors disabled:opacity-60"
              >
                {scanning ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Scanning…</>
                ) : (
                  <><Upload className="w-4 h-4" /> Scan BPR document</>
                )}
              </button>
              {scanDone && scannedFields.size > 0 && (
                <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {scannedFields.size} field{scannedFields.size !== 1 ? "s" : ""} auto-filled
                  <span className="text-muted-foreground font-normal">(highlighted below — verify before saving)</span>
                </span>
              )}
              {scanError && (
                <span className="flex items-center gap-1.5 text-xs text-amber-600">
                  <AlertCircle className="w-3.5 h-3.5" /> {scanError}
                </span>
              )}
            </div>
          </div>

          {/* Apply product profile */}
          {profiles.length > 0 && (
            <div className="border-t pt-4">
              <p className="text-xs text-muted-foreground mb-2">
                Or apply a saved product profile to fill the classification fields.
              </p>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 flex-1 max-w-xs">
                  <BookOpen className="w-4 h-4 text-muted-foreground shrink-0" />
                  <select
                    value={selectedProfile}
                    onChange={(e) => applyProfile(e.target.value)}
                    className="flex-1 px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="">Select product profile…</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>{p.profile_name}</option>
                    ))}
                  </select>
                </div>
                {profileApplied && (
                  <span className="flex items-center gap-1.5 text-xs text-primary font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Profile applied
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                Don&apos;t see your product?{" "}
                <Link href="/product-profiles" className="underline hover:text-foreground">
                  Set up a product profile
                </Link>
              </p>
            </div>
          )}

          {profiles.length === 0 && (
            <p className="text-xs text-muted-foreground border-t pt-3">
              <Link href="/product-profiles" className="underline hover:text-foreground">
                Set up a product profile
              </Link>{" "}
              to remember classification defaults and avoid re-entering them every time.
            </p>
          )}
        </div>

        {/* ── Lot identification ── */}
        <div className="bg-card border rounded-xl p-5">
          <h2 className="text-sm font-semibold mb-4">Lot Identification</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Lot / Batch Number" required>
              <Input
                value={form.lot_number}
                onChange={set("lot_number")}
                placeholder="e.g. ABC-2026-0042"
                scanned={scannedFields.has("lot_number")}
                required
              />
            </Field>
            <Field label="Product Name" required>
              <Input
                value={form.product_name}
                onChange={set("product_name")}
                placeholder="e.g. Amoxicillin 500mg Capsules"
                scanned={scannedFields.has("product_name")}
                required
              />
            </Field>
            <Field label="Product Code">
              <Input
                value={form.product_code}
                onChange={set("product_code")}
                placeholder="e.g. PROD-001"
                scanned={scannedFields.has("product_code")}
              />
            </Field>
            <Field label="Dosage Form">
              <Input
                value={form.dosage_form}
                onChange={set("dosage_form")}
                placeholder="e.g. Capsule, Injection"
                scanned={scannedFields.has("dosage_form")}
              />
            </Field>
            <Field label="Batch Size">
              <Input
                value={form.batch_size}
                onChange={set("batch_size")}
                placeholder="e.g. 100,000 units"
                scanned={scannedFields.has("batch_size")}
              />
            </Field>
            <Field label="Manufacturing Site">
              <Input
                value={form.manufacturing_site}
                onChange={set("manufacturing_site")}
                placeholder="e.g. Site A — Building 3"
                scanned={scannedFields.has("manufacturing_site")}
              />
            </Field>
            <Field label="Manufacturing Date">
              <Input
                type="date"
                value={form.manufacturing_date}
                onChange={set("manufacturing_date")}
                scanned={scannedFields.has("manufacturing_date")}
              />
            </Field>
            <Field label="Target Release Date">
              <Input
                type="date"
                value={form.target_release_date}
                onChange={set("target_release_date")}
                scanned={scannedFields.has("target_release_date")}
              />
            </Field>
          </div>

          {scannedFields.size > 0 && (
            <p className="mt-3 text-xs text-emerald-600 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              Highlighted fields were auto-extracted — please verify before saving.
              <button
                type="button"
                onClick={() => setScannedFields(new Set())}
                className="text-muted-foreground hover:text-foreground underline ml-1"
              >
                Dismiss
              </button>
            </p>
          )}
        </div>

        {/* ── Layer 0 Classification ── */}
        <div className="bg-card border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-sm font-semibold">Layer 0 Classification</h2>
            <Info className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            Determines which review packs activate. These are saved to your product profile for next time.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Record Family" required>
              <Select value={form.record_family} onChange={set("record_family")}>
                {RECORD_FAMILIES.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </Select>
            </Field>
            <Field label="Product Type" required>
              <Select value={form.product_type} onChange={set("product_type")}>
                {PRODUCT_TYPES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </Select>
            </Field>
            <Field label="Manufacturing Context">
              <Select value={form.manufacturing_context} onChange={set("manufacturing_context")}>
                <option value="internal">Internal site</option>
                <option value="cdmo_received">CDMO-received lot</option>
              </Select>
            </Field>
            <Field label="Batch Purpose">
              <Select value={form.batch_purpose} onChange={set("batch_purpose")}>
                {BATCH_PURPOSES.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </Select>
            </Field>
          </div>

          {/* Sterile toggle */}
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={() => setForm((p) => ({ ...p, is_sterile: !p.is_sterile }))}
              className={`relative w-10 rounded-full transition-colors ${form.is_sterile ? "bg-primary" : "bg-muted-foreground/30"}`}
              style={{ height: 22, width: 40 }}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${form.is_sterile ? "translate-x-5" : "translate-x-0.5"}`} />
            </button>
            <div>
              <span className="text-sm font-medium">Sterile / Aseptic manufacturing</span>
              <p className="text-xs text-muted-foreground">Activates Sterile/Aseptic Review Pack</p>
            </div>
          </div>

          {/* Target markets */}
          <div className="mt-4">
            <label className="text-sm font-medium block mb-2">Target Markets</label>
            <div className="flex flex-wrap gap-2">
              {AGENCIES.map((a) => (
                <button
                  key={a}
                  type="button"
                  onClick={() => toggleMarket(a)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    form.target_markets.includes(a)
                      ? "bg-primary/10 border-primary/30 text-primary font-medium"
                      : "border-border text-muted-foreground hover:border-muted-foreground/40"
                  }`}
                >
                  {a.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Review options ── */}
        <div className="bg-card border rounded-xl p-5">
          <h2 className="text-sm font-semibold mb-3">Review Options</h2>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.shadow_mode}
              onChange={(e) => setForm((p) => ({ ...p, shadow_mode: e.target.checked }))}
              className="mt-0.5"
            />
            <div>
              <span className="text-sm font-medium">Shadow / Parallel Review Mode</span>
              <p className="text-xs text-muted-foreground mt-0.5">
                AI assessment runs in parallel with human review for GAMP 5 PQ calibration.
              </p>
            </div>
          </label>
        </div>

        {error && (
          <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <Link
            href="/batch-dossiers"
            className="flex items-center gap-1.5 px-4 py-2.5 border rounded-lg text-sm hover:bg-accent transition-colors"
          >
            <ChevronLeft className="w-4 h-4" /> Cancel
          </Link>
          <button
            type="submit"
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 transition-colors"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            Create Dossier
            {!loading && <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </form>
    </div>
  );
}

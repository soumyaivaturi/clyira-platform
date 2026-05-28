"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical, ChevronLeft, Loader2, ChevronRight, Info } from "lucide-react";
import Link from "next/link";
import { batchDossiersApi } from "@/lib/api";

// ── Options ───────────────────────────────────────────────────────────────────

const RECORD_FAMILIES = [
  { value: "pharma_bpr",      label: "Pharma BPR / BMR",      desc: "Pharmaceutical batch production record" },
  { value: "api_batch",       label: "API Batch Record",       desc: "Active pharmaceutical ingredient batch record" },
  { value: "biologics_batch", label: "Biologics BPR",          desc: "Biologics / vaccine batch record" },
  { value: "sterile_batch",   label: "Sterile BPR",            desc: "Sterile / aseptic manufacturing record" },
  { value: "device_dhr",      label: "Device DHR",             desc: "Medical device history record (21 CFR 820)" },
  { value: "supplement_bpr",  label: "Supplement BPR / MMR",   desc: "Dietary supplement batch record" },
  { value: "cell_therapy",    label: "Cell / Gene Therapy",    desc: "COI / COC patient lot dossier" },
  { value: "cdmo_package",    label: "CDMO Sponsor Package",   desc: "CDMO-prepared lot package for sponsor review" },
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
  { value: "commercial",     label: "Commercial" },
  { value: "validation",     label: "Validation / PPQ" },
  { value: "exhibit",        label: "Exhibit (Regulatory Filing)" },
  { value: "stability",      label: "Stability" },
  { value: "tech_transfer",  label: "Tech Transfer" },
  { value: "clinical",       label: "Clinical" },
  { value: "scale_up",       label: "Scale-Up" },
];

const AGENCIES = [
  { value: "FDA", label: "FDA" },
  { value: "EMA", label: "EMA" },
  { value: "PMDA", label: "PMDA" },
  { value: "MHRA", label: "MHRA" },
  { value: "Health_Canada", label: "Health Canada" },
  { value: "TGA", label: "TGA" },
  { value: "ANVISA", label: "ANVISA" },
];

// ── Field ─────────────────────────────────────────────────────────────────────

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

function Input({ ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className="w-full px-3 py-2.5 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
      {...props}
    />
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

// ── Page ─────────────────────────────────────────────────────────────────────

export default function NewDossierPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    lot_number: "",
    product_name: "",
    product_code: "",
    dosage_form: "",
    batch_size: "",
    manufacturing_site: "",
    manufacturing_date: "",
    target_release_date: "",
    // Layer 0
    record_family: "pharma_bpr",
    product_type: "small_molecule",
    is_sterile: false,
    manufacturing_context: "internal",
    batch_purpose: "commercial",
    target_markets: [] as string[],
    shadow_mode: false,
  });

  const set = (key: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const toggleMarket = (agency: string) => {
    setForm((prev) => ({
      ...prev,
      target_markets: prev.target_markets.includes(agency)
        ? prev.target_markets.filter((m) => m !== agency)
        : [...prev.target_markets, agency],
    }));
  };

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
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to create dossier");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/batch-dossiers" className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-primary" />
            New Batch Dossier
          </h1>
          <p className="text-sm text-muted-foreground">Lot identification + Layer 0 classification</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Lot identification */}
        <div className="bg-card border rounded-xl p-6">
          <h2 className="text-sm font-semibold mb-4">Lot Identification</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Lot / Batch Number" required>
              <Input
                value={form.lot_number}
                onChange={set("lot_number")}
                placeholder="e.g. ABC-2026-0042"
                required
              />
            </Field>
            <Field label="Product Name" required>
              <Input
                value={form.product_name}
                onChange={set("product_name")}
                placeholder="e.g. Amoxicillin 500mg Capsules"
                required
              />
            </Field>
            <Field label="Product Code">
              <Input value={form.product_code} onChange={set("product_code")} placeholder="e.g. PROD-001" />
            </Field>
            <Field label="Dosage Form">
              <Input value={form.dosage_form} onChange={set("dosage_form")} placeholder="e.g. Capsule, Injection" />
            </Field>
            <Field label="Batch Size">
              <Input value={form.batch_size} onChange={set("batch_size")} placeholder="e.g. 100,000 units" />
            </Field>
            <Field label="Manufacturing Site">
              <Input value={form.manufacturing_site} onChange={set("manufacturing_site")} placeholder="e.g. Site A — Building 3" />
            </Field>
            <Field label="Manufacturing Date">
              <Input type="date" value={form.manufacturing_date} onChange={set("manufacturing_date")} />
            </Field>
            <Field label="Target Release Date">
              <Input type="date" value={form.target_release_date} onChange={set("target_release_date")} />
            </Field>
          </div>
        </div>

        {/* Layer 0 Classification */}
        <div className="bg-card border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-sm font-semibold">Layer 0 Classification</h2>
            <Info className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            Determines which review packs activate for the assessment (Core + sector-specific checks).
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Record Family" required hint="Type of production record being reviewed">
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
              <Select
                value={form.manufacturing_context}
                onChange={set("manufacturing_context")}
              >
                <option value="internal">Internal site</option>
                <option value="cdmo_received">CDMO-received lot</option>
              </Select>
            </Field>
            <Field label="Batch Purpose" hint="Commercial batches require standard review; exhibit/validation batches require heightened rigor">
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
              className={`relative w-10 h-5.5 rounded-full transition-colors ${form.is_sterile ? "bg-primary" : "bg-muted-foreground/30"}`}
              style={{ height: 22, width: 40 }}
            >
              <span
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${form.is_sterile ? "translate-x-5" : "translate-x-0.5"}`}
              />
            </button>
            <div>
              <span className="text-sm font-medium">Sterile / Aseptic manufacturing</span>
              <p className="text-xs text-muted-foreground">Activates Sterile/Aseptic Review Pack — checks EM data, filter integrity, sterilization records</p>
            </div>
          </div>

          {/* Target markets */}
          <div className="mt-4">
            <label className="text-sm font-medium block mb-2">Target Markets</label>
            <div className="flex flex-wrap gap-2">
              {AGENCIES.map((a) => (
                <button
                  key={a.value}
                  type="button"
                  onClick={() => toggleMarket(a.value)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    form.target_markets.includes(a.value)
                      ? "bg-primary/10 border-primary/30 text-primary font-medium"
                      : "border-border text-muted-foreground hover:border-muted-foreground/40"
                  }`}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Options */}
        <div className="bg-card border rounded-xl p-6">
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
                AI assessment runs in parallel with human review for GAMP 5 PQ calibration. Results are compared but AI does not influence human workflow.
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

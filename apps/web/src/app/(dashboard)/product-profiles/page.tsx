"use client";

import { useEffect, useState, useRef } from "react";
import {
  Plus, Beaker, CheckCircle2, Clock, Upload, FileText,
  ChevronDown, ChevronUp, Trash2, Edit2, Sparkles, X,
  BookOpen, Package, ShieldCheck, Globe, Loader2, AlertCircle,
  FlaskConical,
} from "lucide-react";
import { productProfilesApi, documentsApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProfileClassification {
  record_family: string;
  product_type: string;
  is_sterile: boolean;
  manufacturing_context: string;
  batch_purpose: string;
  target_markets: string[];
}

interface ProfileTemplate {
  document_id: string | null;
  required_fields: string[] | null;
  acceptance_criteria: Record<string, string> | null;
  section_count: string | null;
  analyzed_at: string | null;
}

interface ProductProfile {
  id: string;
  profile_name: string;
  product_code: string | null;
  product_name: string | null;
  dosage_form: string | null;
  manufacturing_site: string | null;
  classification: ProfileClassification;
  template: ProfileTemplate;
  spec_document_ids: string[];
  active: boolean;
  created_at: string;
  updated_at: string;
}

interface Document {
  id: string;
  title: string;
  document_category?: string;
  file_type?: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const RECORD_FAMILY_OPTIONS = [
  { value: "pharma_bpr", label: "Pharma BPR" },
  { value: "api_batch", label: "API Batch" },
  { value: "biologics_batch", label: "Biologics BPR" },
  { value: "sterile_batch", label: "Sterile BPR" },
  { value: "device_dhr", label: "Device DHR" },
  { value: "supplement_bpr", label: "Supplement BPR" },
  { value: "cell_therapy", label: "Cell Therapy" },
  { value: "cdmo_package", label: "CDMO Package" },
];

const PRODUCT_TYPE_OPTIONS = [
  { value: "small_molecule", label: "Small Molecule" },
  { value: "biologic", label: "Biologic / Large Molecule" },
  { value: "cell_therapy", label: "Cell Therapy / Gene Therapy" },
  { value: "device", label: "Medical Device" },
  { value: "combination", label: "Combination Product" },
  { value: "radiopharmaceutical", label: "Radiopharmaceutical" },
  { value: "herbal", label: "Herbal / Botanical" },
];

const MFG_CONTEXT_OPTIONS = [
  { value: "internal", label: "Internal Manufacturing" },
  { value: "cdmo", label: "CDMO / Contract Manufacturing" },
  { value: "sponsor_supply", label: "Sponsor Supply" },
  { value: "clinical", label: "Clinical Supply" },
];

const BATCH_PURPOSE_OPTIONS = [
  { value: "commercial", label: "Commercial" },
  { value: "clinical", label: "Clinical" },
  { value: "validation", label: "Validation / PPQ" },
  { value: "stability", label: "Stability" },
  { value: "engineering", label: "Engineering / Development" },
];

const TARGET_MARKET_OPTIONS = ["US", "EU", "UK", "JP", "CA", "AU", "BR", "IN", "CN", "RoW"];

const DOSAGE_FORM_OPTIONS = [
  "Tablet", "Capsule", "Solution", "Suspension", "Lyophilized Powder",
  "Powder for Injection", "Cream", "Ointment", "Gel", "Patch",
  "Inhalation", "Ophthalmic", "Suppository", "Other",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function labelFor(options: { value: string; label: string }[], value: string) {
  return options.find((o) => o.value === value)?.label ?? value;
}

function FieldTag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-violet-50 text-violet-700 border border-violet-200">
      {label}
    </span>
  );
}

function MarketTag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200">
      {label}
    </span>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────

function EmptyProfiles({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-full bg-violet-50 flex items-center justify-center mb-4">
        <Package className="w-8 h-8 text-violet-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">No product profiles yet</h3>
      <p className="text-sm text-gray-500 max-w-md mb-6">
        Product profiles remember your classification defaults so you don&apos;t have to re-enter them every time you
        create a batch dossier. They also store your blank MBR template so Clyira knows exactly which fields to check.
      </p>
      <button
        onClick={onCreate}
        className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors"
      >
        <Plus className="w-4 h-4" />
        Create your first profile
      </button>
    </div>
  );
}

// ── Create / Edit Profile Modal ───────────────────────────────────────────────

interface ProfileFormData {
  profile_name: string;
  product_code: string;
  product_name: string;
  dosage_form: string;
  manufacturing_site: string;
  record_family: string;
  product_type: string;
  is_sterile: boolean;
  manufacturing_context: string;
  batch_purpose: string;
  target_markets: string[];
}

function ProfileModal({
  existing,
  onClose,
  onSaved,
}: {
  existing?: ProductProfile;
  onClose: () => void;
  onSaved: (profile: ProductProfile) => void;
}) {
  const [form, setForm] = useState<ProfileFormData>({
    profile_name: existing?.profile_name ?? "",
    product_code: existing?.product_code ?? "",
    product_name: existing?.product_name ?? "",
    dosage_form: existing?.dosage_form ?? "",
    manufacturing_site: existing?.manufacturing_site ?? "",
    record_family: existing?.classification.record_family ?? "pharma_bpr",
    product_type: existing?.classification.product_type ?? "small_molecule",
    is_sterile: existing?.classification.is_sterile ?? false,
    manufacturing_context: existing?.classification.manufacturing_context ?? "internal",
    batch_purpose: existing?.classification.batch_purpose ?? "commercial",
    target_markets: existing?.classification.target_markets ?? [],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function set(key: keyof ProfileFormData, value: unknown) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleMarket(m: string) {
    set(
      "target_markets",
      form.target_markets.includes(m)
        ? form.target_markets.filter((x) => x !== m)
        : [...form.target_markets, m]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.profile_name.trim()) { setError("Profile name is required"); return; }
    setSaving(true);
    setError("");
    try {
      let res;
      const payload = {
        profile_name: form.profile_name.trim(),
        product_code: form.product_code.trim() || undefined,
        product_name: form.product_name.trim() || undefined,
        dosage_form: form.dosage_form || undefined,
        manufacturing_site: form.manufacturing_site.trim() || undefined,
        record_family: form.record_family,
        product_type: form.product_type,
        is_sterile: form.is_sterile,
        manufacturing_context: form.manufacturing_context,
        batch_purpose: form.batch_purpose,
        target_markets: form.target_markets,
      };
      if (existing) {
        res = await productProfilesApi.update(existing.id, payload);
      } else {
        res = await productProfilesApi.create(payload);
      }
      onSaved(res.data);
    } catch {
      setError("Failed to save profile. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {existing ? "Edit Product Profile" : "New Product Profile"}
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Saved defaults will pre-fill every new dossier for this product line
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-6">
          {/* Identity */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Profile Identity</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Profile Name <span className="text-red-500">*</span></label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="e.g. Aspirin 500 mg Tablet — Commercial"
                  value={form.profile_name}
                  onChange={(e) => set("profile_name", e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Product Code</label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="ASP-500"
                  value={form.product_code}
                  onChange={(e) => set("product_code", e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Product Name</label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Aspirin Tablets"
                  value={form.product_name}
                  onChange={(e) => set("product_name", e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Dosage Form</label>
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={form.dosage_form}
                  onChange={(e) => set("dosage_form", e.target.value)}
                >
                  <option value="">Select…</option>
                  {DOSAGE_FORM_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Manufacturing Site</label>
                <input
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Site name or address"
                  value={form.manufacturing_site}
                  onChange={(e) => set("manufacturing_site", e.target.value)}
                />
              </div>
            </div>
          </section>

          {/* Classification */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Classification Defaults</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Record Family</label>
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={form.record_family}
                  onChange={(e) => set("record_family", e.target.value)}
                >
                  {RECORD_FAMILY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Product Type</label>
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={form.product_type}
                  onChange={(e) => set("product_type", e.target.value)}
                >
                  {PRODUCT_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Manufacturing Context</label>
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={form.manufacturing_context}
                  onChange={(e) => set("manufacturing_context", e.target.value)}
                >
                  {MFG_CONTEXT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Batch Purpose</label>
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={form.batch_purpose}
                  onChange={(e) => set("batch_purpose", e.target.value)}
                >
                  {BATCH_PURPOSE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => set("is_sterile", !form.is_sterile)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500 ${
                  form.is_sterile ? "bg-violet-600" : "bg-gray-200"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    form.is_sterile ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
              <span className="text-sm text-gray-700">Sterile product</span>
              {form.is_sterile && (
                <span className="text-xs text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full border border-violet-200">
                  Sterile DTAP levels enabled
                </span>
              )}
            </div>
          </section>

          {/* Target Markets */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Target Markets</h3>
            <div className="flex flex-wrap gap-2">
              {TARGET_MARKET_OPTIONS.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => toggleMarket(m)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                    form.target_markets.includes(m)
                      ? "bg-violet-600 text-white border-violet-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-violet-300"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </section>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2 border-t">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {existing ? "Save Changes" : "Create Profile"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Template Upload Panel ─────────────────────────────────────────────────────

function TemplatePanel({
  profile,
  onUpdated,
}: {
  profile: ProductProfile;
  onUpdated: (updated: ProductProfile) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    required_fields_count: number;
    acceptance_criteria_count: number;
    section_count: number;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const hasTemplate = !!profile.template.analyzed_at;

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await productProfilesApi.analyzeTemplate(profile.id, file);
      setResult(res.data);
      const updated = await productProfilesApi.get(profile.id);
      onUpdated(updated.data);
    } catch {
      setError("Failed to analyze template. Ensure it's a readable PDF or DOCX.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      {hasTemplate && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-emerald-800">Template analyzed</p>
              <p className="text-xs text-emerald-600 mt-0.5">
                {profile.template.required_fields?.length ?? 0} required fields ·{" "}
                {Object.keys(profile.template.acceptance_criteria ?? {}).length} acceptance criteria ·{" "}
                {profile.template.section_count} sections
              </p>
              <p className="text-xs text-emerald-600 mt-0.5">
                Analyzed {profile.template.analyzed_at ? new Date(profile.template.analyzed_at).toLocaleDateString() : "—"}
              </p>
            </div>
          </div>
          {profile.template.required_fields && profile.template.required_fields.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-emerald-700 font-medium mb-1.5">Sample fields:</p>
              <div className="flex flex-wrap gap-1">
                {profile.template.required_fields.slice(0, 12).map((f) => (
                  <FieldTag key={f} label={f} />
                ))}
                {profile.template.required_fields.length > 12 && (
                  <span className="text-xs text-gray-400">+{profile.template.required_fields.length - 12} more</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <div>
        <p className="text-xs text-gray-500 mb-3">
          {hasTemplate
            ? "Re-upload to update the template memory with a newer version."
            : "Upload a blank MBR/BPR template (PDF or DOCX). Clyira will extract all required field names and any acceptance criteria written into the form."}
        </p>
        <div
          className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center cursor-pointer hover:border-violet-300 hover:bg-violet-50/30 transition-colors"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) setFile(f);
          }}
        >
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".pdf,.docx,.doc"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
          {file ? (
            <div>
              <p className="text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-500">Drop your blank MBR template here</p>
              <p className="text-xs text-gray-400 mt-1">PDF or DOCX · max 20 MB</p>
            </div>
          )}
        </div>

        {result && (
          <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-3 flex items-center gap-3">
            <Sparkles className="w-4 h-4 text-violet-600 shrink-0" />
            <p className="text-xs text-violet-700">
              Extracted <strong>{result.required_fields_count}</strong> required fields,{" "}
              <strong>{result.acceptance_criteria_count}</strong> acceptance criteria across{" "}
              <strong>{result.section_count}</strong> sections
            </p>
          </div>
        )}

        {error && (
          <div className="mt-2 flex items-center gap-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="mt-3 flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 disabled:opacity-40 transition-colors"
        >
          {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {uploading ? "Analyzing…" : hasTemplate ? "Re-analyze template" : "Analyze template"}
        </button>
      </div>
    </div>
  );
}

// ── Spec Documents Panel ──────────────────────────────────────────────────────

function SpecDocsPanel({
  profile,
  onUpdated,
}: {
  profile: ProductProfile;
  onUpdated: (updated: ProductProfile) => void;
}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [linking, setLinking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    documentsApi.list().then((r) => {
      setDocuments(r.data?.documents ?? r.data ?? []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  async function handleLink() {
    if (!selectedDocId) return;
    setLinking(true);
    setError("");
    try {
      await productProfilesApi.addSpecDocument(profile.id, selectedDocId);
      const updated = await productProfilesApi.get(profile.id);
      onUpdated(updated.data);
      setSelectedDocId("");
    } catch {
      setError("Failed to link document.");
    } finally {
      setLinking(false);
    }
  }

  const linkedDocs = documents.filter((d) => profile.spec_document_ids.includes(d.id));
  const availableDocs = documents.filter((d) => !profile.spec_document_ids.includes(d.id));

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        Link CPP, specification sheets, and analytical methods so Clyira can cross-reference acceptance criteria when reviewing a batch dossier.
      </p>

      {linkedDocs.length > 0 && (
        <div className="space-y-1.5">
          {linkedDocs.map((doc) => (
            <div key={doc.id} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-100 bg-gray-50">
              <FileText className="w-4 h-4 text-gray-400 shrink-0" />
              <span className="text-sm text-gray-700 flex-1 truncate">{doc.title}</span>
              {doc.document_category && (
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{doc.document_category}</span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        {loading ? (
          <div className="flex-1 flex items-center gap-2 text-sm text-gray-400">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading documents…
          </div>
        ) : (
          <select
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
          >
            <option value="">Select a document to link…</option>
            {availableDocs.map((d) => (
              <option key={d.id} value={d.id}>{d.title}</option>
            ))}
          </select>
        )}
        <button
          onClick={handleLink}
          disabled={!selectedDocId || linking}
          className="flex items-center gap-2 px-3 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 disabled:opacity-40 transition-colors"
        >
          {linking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          Link
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}

// ── Profile Card ──────────────────────────────────────────────────────────────

function ProfileCard({
  profile,
  onEdit,
  onDelete,
  onUpdated,
}: {
  profile: ProductProfile;
  onEdit: () => void;
  onDelete: () => void;
  onUpdated: (updated: ProductProfile) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"template" | "specs">("template");

  const hasTemplate = !!profile.template.analyzed_at;
  const specCount = profile.spec_document_ids.length;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Card Header */}
      <div className="px-5 py-4">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-violet-50 flex items-center justify-center shrink-0">
            <FlaskConical className="w-5 h-5 text-violet-600" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-semibold text-gray-900 truncate">{profile.profile_name}</h3>
              {profile.product_code && (
                <span className="text-xs text-gray-400 font-mono">{profile.product_code}</span>
              )}
            </div>

            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {profile.product_name && (
                <span className="text-xs text-gray-500">{profile.product_name}</span>
              )}
              {profile.dosage_form && (
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{profile.dosage_form}</span>
              )}
              {profile.classification.is_sterile && (
                <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                  Sterile
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <span className="text-xs text-gray-400">
                {labelFor(RECORD_FAMILY_OPTIONS, profile.classification.record_family)}
              </span>
              <span className="text-gray-200">·</span>
              <span className="text-xs text-gray-400">
                {labelFor(PRODUCT_TYPE_OPTIONS, profile.classification.product_type)}
              </span>
              <span className="text-gray-200">·</span>
              <span className="text-xs text-gray-400">
                {labelFor(BATCH_PURPOSE_OPTIONS, profile.classification.batch_purpose)}
              </span>
            </div>

            {profile.classification.target_markets.length > 0 && (
              <div className="flex items-center gap-1 mt-2 flex-wrap">
                {profile.classification.target_markets.map((m) => <MarketTag key={m} label={m} />)}
              </div>
            )}
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* Status indicators */}
            <div className="flex items-center gap-2 mr-2">
              <div
                className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${
                  hasTemplate
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-gray-50 text-gray-400 border-gray-200"
                }`}
                title={hasTemplate ? "MBR template analyzed" : "No template uploaded"}
              >
                <BookOpen className="w-3 h-3" />
                <span>Template</span>
                {hasTemplate ? <CheckCircle2 className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
              </div>
              {specCount > 0 && (
                <div className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border bg-blue-50 text-blue-700 border-blue-200">
                  <FileText className="w-3 h-3" />
                  <span>{specCount} spec{specCount !== 1 ? "s" : ""}</span>
                </div>
              )}
            </div>

            <button
              onClick={onEdit}
              className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              title="Edit profile"
            >
              <Edit2 className="w-4 h-4" />
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-500"
              title="Delete profile"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setExpanded((x) => !x)}
              className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400"
              title={expanded ? "Collapse" : "Expand setup"}
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {!hasTemplate && !expanded && (
          <div className="mt-3 flex items-center gap-2 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            Upload a blank MBR template to enable field completeness checking on future dossiers
          </div>
        )}
      </div>

      {/* Expanded Setup Panel */}
      {expanded && (
        <div className="border-t border-gray-100">
          {/* Tabs */}
          <div className="flex border-b border-gray-100 px-5">
            {(["template", "specs"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-3 text-xs font-medium border-b-2 transition-colors ${
                  activeTab === tab
                    ? "border-violet-600 text-violet-700"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {tab === "template" ? (
                  <span className="flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5" />
                    MBR Template
                    {hasTemplate && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    Spec Documents
                    {specCount > 0 && (
                      <span className="ml-0.5 bg-blue-100 text-blue-700 text-[10px] rounded-full px-1.5">{specCount}</span>
                    )}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="px-5 py-4">
            {activeTab === "template" ? (
              <TemplatePanel profile={profile} onUpdated={onUpdated} />
            ) : (
              <SpecDocsPanel profile={profile} onUpdated={onUpdated} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ProductProfilesPage() {
  const [profiles, setProfiles] = useState<ProductProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ProductProfile | null>(null);

  async function fetchProfiles() {
    try {
      const res = await productProfilesApi.list();
      setProfiles(res.data ?? []);
    } catch {
      setError("Failed to load product profiles.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchProfiles(); }, []);

  function handleSaved(profile: ProductProfile) {
    setProfiles((prev) => {
      const idx = prev.findIndex((p) => p.id === profile.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = profile;
        return next;
      }
      return [profile, ...prev];
    });
    setShowCreate(false);
    setEditingProfile(null);
  }

  function handleUpdated(updated: ProductProfile) {
    setProfiles((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  }

  async function handleDelete(profile: ProductProfile) {
    if (!confirm(`Delete profile "${profile.profile_name}"? This cannot be undone.`)) return;
    try {
      await productProfilesApi.delete(profile.id);
      setProfiles((prev) => prev.filter((p) => p.id !== profile.id));
    } catch {
      alert("Failed to delete profile.");
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Product Profiles</h1>
          <p className="text-sm text-gray-500 mt-1">
            Save classification defaults and MBR templates per product line. Profiles auto-fill new batch dossiers — you only enter what&apos;s batch-specific.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors shrink-0"
        >
          <Plus className="w-4 h-4" />
          New Profile
        </button>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 bg-violet-50 border border-violet-200 rounded-xl px-4 py-3">
        <Sparkles className="w-4 h-4 text-violet-600 mt-0.5 shrink-0" />
        <div className="text-xs text-violet-700 space-y-1">
          <p className="font-medium">How product profiles work</p>
          <p>
            <strong>Step 1:</strong> Create a profile for each product line with classification defaults (record family, product type, sterile, markets).
          </p>
          <p>
            <strong>Step 2:</strong> Upload a blank MBR template — Clyira extracts required fields and acceptance criteria from the form.
          </p>
          <p>
            <strong>Step 3:</strong> When creating a dossier, select this profile and Clyira pre-fills all classification fields automatically.
          </p>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading profiles…
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      ) : profiles.length === 0 ? (
        <EmptyProfiles onCreate={() => setShowCreate(true)} />
      ) : (
        <div className="space-y-3">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              onEdit={() => setEditingProfile(profile)}
              onDelete={() => handleDelete(profile)}
              onUpdated={handleUpdated}
            />
          ))}
        </div>
      )}

      {/* Create / Edit Modal */}
      {(showCreate || editingProfile) && (
        <ProfileModal
          existing={editingProfile ?? undefined}
          onClose={() => { setShowCreate(false); setEditingProfile(null); }}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

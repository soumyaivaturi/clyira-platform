"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Upload, FileText, Database, Loader2, X, Check, ChevronRight,
  AlertTriangle, Trash2, Eye, CheckCircle2, ArrowRight, Info,
  Table, Layers, Zap, Plus, RefreshCw,
} from "lucide-react";
import { evidenceApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────
interface EvidenceImport {
  id: string;
  filename: string;
  source_system: string;
  entity_type: string | null;
  record_count: number;
  status: string;
  detected_columns: string[];
  column_mapping: Record<string, string>;
  created_at: string;
}

interface EvidenceObject {
  id: string;
  entity_type: string | null;
  entity_id: string | null;
  entity_name: string | null;
  signal_type: string | null;
  event_date: string | null;
  severity: string | null;
  normalized: Record<string, any>;
  raw_row: Record<string, string>;
}

const ENTITY_TYPES = [
  { value: "deviation", label: "Deviations / Events", desc: "Non-conformances, process deviations, CAPA triggers" },
  { value: "oos", label: "OOS / OOC Results", desc: "Out-of-specification analytical results" },
  { value: "training", label: "Training Records", desc: "Employee training completions and gaps" },
  { value: "equipment", label: "Equipment / Calibration", desc: "Calibration status, PM schedules, breakdowns" },
  { value: "material", label: "Materials / Batches", desc: "Raw material releases, batch records, supplier data" },
  { value: "pm", label: "Preventive Maintenance", desc: "PM work orders, overdue PMs, completion logs" },
  { value: "change_control", label: "Change Controls", desc: "Change control records and approvals" },
  { value: "em_excursion", label: "Environmental Monitoring", desc: "EM excursions, viable/non-viable counts" },
  { value: "complaint", label: "Complaints / Returns", desc: "Customer complaints and returned goods" },
  { value: "batch_record", label: "Batch Records", desc: "MBR/BMR review data, yield, exceptions" },
];

const SOURCE_SYSTEMS = [
  "manual", "qms", "lims", "mes", "cmms", "eln", "erp", "spreadsheet", "other",
];

const FIELD_OPTIONS = [
  { value: "entity_id", label: "Entity ID (equipment #, batch #, etc.)" },
  { value: "entity_name", label: "Entity Name (analyst, equipment name, etc.)" },
  { value: "event_date", label: "Event Date" },
  { value: "signal_type", label: "Signal Type (deviation type, test name, etc.)" },
  { value: "severity", label: "Severity / Criticality" },
  { value: "description", label: "Description / Details" },
  { value: "status", label: "Status" },
  { value: "batch_number", label: "Batch / Lot Number" },
  { value: "analyst", label: "Analyst / Responsible Person" },
  { value: "equipment_id", label: "Equipment ID" },
  { value: "_skip", label: "— Skip this column —" },
];

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  major: "bg-orange-100 text-orange-800 border-orange-200",
  minor: "bg-amber-100 text-amber-800 border-amber-200",
  informational: "bg-blue-100 text-blue-800 border-blue-200",
};

// ── Upload zone ───────────────────────────────────────────────────────────────
function UploadZone({ onUploaded }: { onUploaded: (imp: any) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [sourceSystem, setSourceSystem] = useState("manual");

  const handleFile = async (file: File) => {
    setError("");
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source_system", sourceSystem);
    try {
      const res = await evidenceApi.upload(fd);
      onUploaded(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Upload failed. Please check the file format.");
    } finally { setUploading(false); }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
            Source System
          </label>
          <select value={sourceSystem} onChange={e => setSourceSystem(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/20">
            {SOURCE_SYSTEMS.map(s => (
              <option key={s} value={s} className="capitalize">{s === "manual" ? "Manual / Spreadsheet" : s.toUpperCase()}</option>
            ))}
          </select>
        </div>
      </div>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl px-8 py-12 text-center cursor-pointer transition-colors ${
          dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/20"
        }`}
      >
        <input ref={inputRef} type="file" accept=".csv,.tsv,.txt" className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
        {uploading ? (
          <div className="space-y-2">
            <Loader2 className="w-8 h-8 text-primary mx-auto animate-spin" />
            <p className="text-sm text-muted-foreground">Parsing file…</p>
          </div>
        ) : (
          <div className="space-y-2">
            <Upload className="w-10 h-10 text-muted-foreground/40 mx-auto" />
            <p className="font-semibold text-sm">Drop CSV here or click to browse</p>
            <p className="text-xs text-muted-foreground">CSV or TSV · Max 10 MB · 5,000 rows</p>
          </div>
        )}
      </div>
      {error && (
        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />{error}
        </div>
      )}
    </div>
  );
}

// ── Column Mapper ─────────────────────────────────────────────────────────────
function ColumnMapper({
  imp,
  onMapped,
  onCancel,
}: {
  imp: any;
  onMapped: () => void;
  onCancel: () => void;
}) {
  const [entityType, setEntityType] = useState(imp.detected_entity_type ?? "deviation");
  const [mapping, setMapping] = useState<Record<string, string>>(() => {
    const m: Record<string, string> = {};
    (imp.detected_columns as string[]).forEach(col => { m[col] = "_skip"; });
    return m;
  });
  const [saving, setSaving] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    const cleanMapping: Record<string, string> = {};
    Object.entries(mapping).forEach(([col, field]) => {
      if (field && field !== "_skip") cleanMapping[col] = field;
    });
    if (Object.keys(cleanMapping).length === 0) {
      setError("Map at least one column to a field.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await evidenceApi.mapColumns(imp.import_id, entityType, cleanMapping);
      // Ingest the preview rows
      if (imp.preview?.length > 0) {
        setIngesting(true);
        await evidenceApi.ingest(imp.import_id, imp.preview);
      }
      onMapped();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to save mapping.");
    } finally { setSaving(false); setIngesting(false); }
  };

  return (
    <div className="space-y-5">
      <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-xs text-blue-800">
        <p className="font-semibold mb-1 flex items-center gap-1.5"><Info className="w-3.5 h-3.5" /> Column Mapping</p>
        <p>Tell Clyira what each column means. Map at least Entity ID, Event Date, or Description. Skip columns you don't need.</p>
      </div>

      <div>
        <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Evidence Type *</label>
        <div className="grid grid-cols-2 gap-2">
          {ENTITY_TYPES.map(t => (
            <button key={t.value} type="button" onClick={() => setEntityType(t.value)}
              className={`text-left px-3 py-2 rounded-lg border text-xs transition-colors ${
                entityType === t.value ? "bg-primary/10 border-primary text-primary" : "border-border hover:bg-accent"
              }`}>
              <p className="font-semibold">{t.label}</p>
              <p className="text-muted-foreground mt-0.5 text-[10px]">{t.desc}</p>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Map Columns ({imp.detected_columns?.length ?? 0} detected)
        </label>
        <div className="space-y-2">
          {(imp.detected_columns as string[]).map(col => (
            <div key={col} className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{col}</p>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <select
                value={mapping[col] ?? "_skip"}
                onChange={e => setMapping(m => ({ ...m, [col]: e.target.value }))}
                className="w-56 border rounded-lg px-2 py-1.5 text-xs bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {FIELD_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>

      {/* Preview table */}
      {imp.preview?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Preview (first 5 rows)</p>
          <div className="overflow-x-auto border rounded-lg">
            <table className="text-xs w-full">
              <thead>
                <tr className="bg-muted/40 border-b">
                  {imp.detected_columns.map((col: string) => (
                    <th key={col} className="px-3 py-2 text-left font-semibold text-muted-foreground whitespace-nowrap">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {imp.preview.slice(0, 5).map((row: any, i: number) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/20">
                    {imp.detected_columns.map((col: string) => (
                      <td key={col} className="px-3 py-2 truncate max-w-32">{row[col] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
          <X className="w-4 h-4 flex-shrink-0" />{error}
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving || ingesting}
          className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium disabled:opacity-60">
          {(saving || ingesting) ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
          {ingesting ? "Ingesting…" : saving ? "Saving…" : "Apply Mapping"}
        </button>
        <button onClick={onCancel} className="px-4 py-2.5 border rounded-xl text-sm font-medium hover:bg-accent">Cancel</button>
      </div>
    </div>
  );
}

// ── Import Row ────────────────────────────────────────────────────────────────
function ImportRow({
  imp,
  onDelete,
  onViewObjects,
}: {
  imp: EvidenceImport;
  onDelete: (id: string) => void;
  onViewObjects: (imp: EvidenceImport) => void;
}) {
  const entityLabel = ENTITY_TYPES.find(e => e.value === imp.entity_type)?.label ?? imp.entity_type ?? "Unknown";
  const hasMapped = Object.keys(imp.column_mapping ?? {}).length > 0;

  return (
    <div className="flex items-center justify-between gap-4 p-4 border rounded-xl bg-card hover:bg-muted/20 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
          <Table className="w-4 h-4 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{imp.filename}</p>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <span className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded font-semibold uppercase">{imp.source_system}</span>
            {imp.entity_type && (
              <span className="text-[10px] text-muted-foreground">{entityLabel}</span>
            )}
            <span className="text-[10px] text-muted-foreground">{imp.record_count.toLocaleString()} records</span>
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
              imp.status === "ready" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
              imp.status === "processing" ? "bg-blue-50 text-blue-700 border-blue-200" :
              "bg-red-50 text-red-700 border-red-200"
            }`}>{imp.status}</span>
            {hasMapped && <span className="text-[10px] text-emerald-700 font-medium">✓ Mapped</span>}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button onClick={() => onViewObjects(imp)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-accent">
          <Eye className="w-3 h-3" /> View
        </button>
        <button onClick={() => onDelete(imp.id)}
          className="p-1.5 text-muted-foreground hover:text-destructive transition-colors">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ── Objects Panel ─────────────────────────────────────────────────────────────
function ObjectsPanel({ imp, onClose }: { imp: EvidenceImport; onClose: () => void }) {
  const [objects, setObjects] = useState<EvidenceObject[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    evidenceApi.listObjects(imp.id).then(r => {
      setObjects(r.data.objects ?? []);
      setTotal(r.data.total ?? 0);
    }).finally(() => setLoading(false));
  }, [imp.id]);

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border rounded-t-2xl sm:rounded-2xl shadow-2xl w-full max-w-3xl mx-0 sm:mx-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b flex-shrink-0">
          <div>
            <h3 className="font-semibold">{imp.filename}</h3>
            <p className="text-xs text-muted-foreground">{total.toLocaleString()} evidence objects · {imp.entity_type}</p>
          </div>
          <button onClick={onClose}><X className="w-4 h-4 text-muted-foreground" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : objects.length === 0 ? (
            <div className="text-center py-12">
              <Database className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No objects ingested yet. Apply column mapping to ingest records.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {objects.map(obj => (
                <div key={obj.id} className="bg-muted/30 border rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    {obj.entity_type && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded font-semibold uppercase">{obj.entity_type}</span>
                    )}
                    {obj.entity_id && <span className="text-xs font-mono text-muted-foreground">{obj.entity_id}</span>}
                    {obj.event_date && <span className="text-xs text-muted-foreground">{obj.event_date}</span>}
                    {obj.severity && (
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${SEVERITY_COLORS[obj.severity.toLowerCase()] ?? "bg-muted text-muted-foreground border-border"}`}>
                        {obj.severity}
                      </span>
                    )}
                  </div>
                  {obj.entity_name && <p className="text-sm font-medium">{obj.entity_name}</p>}
                  {Object.keys(obj.normalized ?? {}).length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-2">
                      {Object.entries(obj.normalized).slice(0, 6).map(([k, v]) => (
                        <span key={k} className="text-[10px] text-muted-foreground">
                          <span className="font-semibold">{k}:</span> {String(v).slice(0, 40)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {total > objects.length && (
                <p className="text-xs text-center text-muted-foreground py-2">Showing first {objects.length} of {total.toLocaleString()}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function EvidencePage() {
  const [imports, setImports] = useState<EvidenceImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingImport, setPendingImport] = useState<any>(null);
  const [viewingImport, setViewingImport] = useState<EvidenceImport | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  const loadImports = useCallback(async () => {
    try {
      const r = await evidenceApi.listImports();
      setImports(r.data.imports ?? []);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadImports(); }, [loadImports]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this import and all its evidence objects?")) return;
    await evidenceApi.deleteImport(id);
    setImports(prev => prev.filter(i => i.id !== id));
  };

  const totalRecords = imports.reduce((sum, i) => sum + (i.record_count ?? 0), 0);
  const entityTypes = Array.from(new Set(imports.map(i => i.entity_type).filter(Boolean)));

  return (
    <div className="space-y-6">
      {viewingImport && (
        <ObjectsPanel imp={viewingImport} onClose={() => setViewingImport(null)} />
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Evidence Fabric</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Import quality system data to cross-reference document claims against real-world evidence.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadImports} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm hover:bg-accent disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => { setShowUpload(true); setPendingImport(null); }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90">
            <Plus className="w-4 h-4" /> Import Data
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Evidence Imports", value: imports.length, icon: FileText },
          { label: "Total Records", value: totalRecords.toLocaleString(), icon: Database },
          { label: "Entity Types", value: entityTypes.length, icon: Layers },
          { label: "Ready for Cross-Ref", value: imports.filter(i => i.status === "ready" && Object.keys(i.column_mapping ?? {}).length > 0).length, icon: CheckCircle2 },
        ].map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="bg-card border rounded-xl px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{s.label}</p>
              </div>
              <p className="text-2xl font-bold tabular-nums">{s.value}</p>
            </div>
          );
        })}
      </div>

      {/* Architecture explainer */}
      {imports.length === 0 && !showUpload && (
        <div className="bg-primary/5 border border-primary/20 rounded-xl p-6">
          <p className="font-semibold text-primary mb-2 flex items-center gap-2">
            <Layers className="w-4 h-4" /> How Evidence Fabric works
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            {[
              { step: "1", title: "Import", desc: "Upload a CSV export from your QMS, LIMS, MES, CMMS, or any spreadsheet." },
              { step: "2", title: "Map & Tag", desc: "Tell Clyira which columns hold entity IDs, dates, and quality signals." },
              { step: "3", title: "Cross-Reference", desc: "Clyira checks document claims (e.g. 'root cause: analyst error') against your evidence objects." },
            ].map(s => (
              <div key={s.step} className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold flex-shrink-0">{s.step}</div>
                <div>
                  <p className="text-sm font-semibold">{s.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload / mapping section */}
      {(showUpload || pendingImport) && (
        <div className="bg-card border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm">
              {pendingImport ? "Map Columns" : "Import CSV / TSV"}
            </h2>
            <button onClick={() => { setShowUpload(false); setPendingImport(null); }}
              className="text-muted-foreground hover:text-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>
          {pendingImport ? (
            <ColumnMapper
              imp={pendingImport}
              onMapped={() => { setPendingImport(null); setShowUpload(false); loadImports(); }}
              onCancel={() => { setPendingImport(null); setShowUpload(false); }}
            />
          ) : (
            <UploadZone
              onUploaded={(imp) => { setPendingImport(imp); setShowUpload(false); }}
            />
          )}
        </div>
      )}

      {/* Imports list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="h-20 bg-muted rounded-xl animate-pulse" />)}
        </div>
      ) : imports.length === 0 ? (
        !showUpload && (
          <div className="bg-muted/30 border border-dashed rounded-xl px-8 py-14 text-center">
            <Database className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
            <h3 className="font-semibold mb-1">No evidence imports yet</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
              Start by importing a CSV from your QMS, LIMS, or any spreadsheet. Clyira will normalize the data and make it available for document cross-referencing.
            </p>
            <button onClick={() => setShowUpload(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium mx-auto">
              <Upload className="w-4 h-4" /> Import First Dataset
            </button>
          </div>
        )
      ) : (
        <div className="space-y-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Imported Datasets ({imports.length})
          </p>
          {imports.map(imp => (
            <ImportRow
              key={imp.id}
              imp={imp}
              onDelete={handleDelete}
              onViewObjects={setViewingImport}
            />
          ))}
        </div>
      )}
    </div>
  );
}

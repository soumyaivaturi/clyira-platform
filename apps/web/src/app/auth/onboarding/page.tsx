"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, Loader2, ChevronRight, ChevronLeft, Building2, Globe, ShieldCheck, Sparkles } from "lucide-react";
import { companiesApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

// ── Data ──────────────────────────────────────────────────────────────────────

const SUB_SECTORS = [
  { code: "SS-D1", label: "Pharmaceutical Manufacturing", description: "Drug products, solid oral, liquids, semi-solids" },
  { code: "SS-D2", label: "API / Chemical Manufacturing", description: "Active pharmaceutical ingredients, drug substances" },
  { code: "SS-D3", label: "Sterile Manufacturing", description: "Injectables, ophthalmic, aseptic fill-finish" },
  { code: "SS-D4", label: "OTC / Consumer Health", description: "Over-the-counter and consumer health products" },
  { code: "SS-B1", label: "Biologics / Biotechnology", description: "Biologics, biosimilars, recombinant proteins" },
  { code: "SS-B2", label: "Gene & Cell Therapy", description: "Advanced therapy medicinal products (ATMPs), CGT" },
  { code: "SS-MD1", label: "Medical Devices", description: "Class II/III devices, combination products" },
  { code: "SS-DX1", label: "Diagnostics / IVD", description: "In-vitro diagnostics, laboratory instruments" },
  { code: "SS-CL1", label: "Clinical Research", description: "CROs, clinical trial sites, sponsors" },
  { code: "SS-VAC", label: "Vaccines", description: "Human and veterinary vaccine manufacturing" },
];

const AGENCIES = [
  { code: "FDA", label: "FDA", description: "US Food & Drug Administration", region: "United States" },
  { code: "EMA", label: "EMA", description: "European Medicines Agency", region: "European Union" },
  { code: "MHRA", label: "MHRA", description: "Medicines & Healthcare products Regulatory Agency", region: "United Kingdom" },
  { code: "PMDA", label: "PMDA", description: "Pharmaceuticals and Medical Devices Agency", region: "Japan" },
  { code: "Health_Canada", label: "Health Canada", description: "Health Canada", region: "Canada" },
  { code: "TGA", label: "TGA", description: "Therapeutic Goods Administration", region: "Australia" },
  { code: "ANVISA", label: "ANVISA", description: "Agência Nacional de Vigilância Sanitária", region: "Brazil" },
  { code: "WHO", label: "WHO", description: "World Health Organization (prequalification)", region: "Global" },
  { code: "ICH", label: "ICH", description: "International Council for Harmonisation guidelines", region: "Global" },
];

const MARKETS = [
  { code: "US", label: "United States" },
  { code: "EU", label: "European Union" },
  { code: "UK", label: "United Kingdom" },
  { code: "JP", label: "Japan" },
  { code: "CA", label: "Canada" },
  { code: "AU", label: "Australia" },
  { code: "BR", label: "Brazil" },
  { code: "CN", label: "China" },
  { code: "IN", label: "India" },
  { code: "ROW", label: "Rest of World" },
];

// ── Types ─────────────────────────────────────────────────────────────────────

type Step = "subsectors" | "agencies" | "markets" | "done";

const STEPS: Step[] = ["subsectors", "agencies", "markets"];

// ── Multi-select chip ──────────────────────────────────────────────────────────

function Chip({
  selected,
  onClick,
  label,
  description,
  badge,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  description?: string;
  badge?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left w-full px-4 py-3 rounded-lg border transition-all ${
        selected
          ? "border-primary bg-primary/5 ring-1 ring-primary/30"
          : "border-border hover:border-muted-foreground/40 hover:bg-muted/40"
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center ${
            selected ? "bg-primary border-primary" : "border-muted-foreground/40"
          }`}
        >
          {selected && <CheckCircle className="w-3 h-3 text-primary-foreground" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{label}</span>
            {badge && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {badge}
              </span>
            )}
          </div>
          {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
        </div>
      </div>
    </button>
  );
}

// ── Step indicator ─────────────────────────────────────────────────────────────

function StepBar({ current }: { current: Step }) {
  const steps = [
    { key: "subsectors", label: "Sub-sectors", icon: Building2 },
    { key: "agencies", label: "Agencies", icon: ShieldCheck },
    { key: "markets", label: "Markets", icon: Globe },
  ];
  const currentIdx = STEPS.indexOf(current);

  return (
    <div className="flex items-center gap-0 mb-8">
      {steps.map((s, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <div key={s.key} className="flex items-center flex-1">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                  done
                    ? "bg-primary text-primary-foreground"
                    : active
                    ? "bg-primary/10 text-primary ring-2 ring-primary/40"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {done ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <span className={`text-[10px] font-medium whitespace-nowrap ${active ? "text-primary" : "text-muted-foreground"}`}>
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`flex-1 h-px mx-2 mb-4 ${i < currentIdx ? "bg-primary" : "bg-border"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const { user, refreshMe } = useAuth();

  const [step, setStep] = useState<Step>("subsectors");
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [selectedAgencies, setSelectedAgencies] = useState<string[]>([]);
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  function toggle<T>(arr: T[], val: T): T[] {
    return arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];
  }

  const handleNext = () => {
    if (step === "subsectors") {
      if (selectedSectors.length === 0) { setError("Select at least one sub-sector"); return; }
      setError(""); setStep("agencies");
    } else if (step === "agencies") {
      if (selectedAgencies.length === 0) { setError("Select at least one regulatory agency"); return; }
      setError(""); setStep("markets");
    } else if (step === "markets") {
      if (selectedMarkets.length === 0) { setError("Select at least one target market"); return; }
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (step === "agencies") setStep("subsectors");
    else if (step === "markets") setStep("agencies");
    setError("");
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError("");
    try {
      await companiesApi.onboard({
        sub_sectors: selectedSectors,
        agencies: selectedAgencies,
        markets: selectedMarkets,
      });
      await refreshMe();
      setStep("done");
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Something went wrong. Please try again.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (step === "done") {
    return (
      <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold mb-2">You&apos;re all set!</h1>
          <p className="text-muted-foreground mb-2">
            Your quality workspace is configured for{" "}
            <span className="font-medium text-foreground">{selectedAgencies.join(", ")}</span>.
          </p>
          <p className="text-sm text-muted-foreground mb-8">
            Clyira will now assess your documents against the relevant regulatory frameworks for your sub-sectors and markets.
          </p>
          <button
            onClick={() => router.push("/dashboard")}
            className="w-full bg-primary text-primary-foreground py-3 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Open Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-lg">C</span>
            </div>
            <span className="text-2xl font-semibold">Clyira</span>
          </div>
          <h1 className="text-xl font-semibold">Configure your regulatory workspace</h1>
          <p className="text-sm text-muted-foreground mt-1">
            This determines which frameworks and corpora apply to your assessments
          </p>
        </div>

        <div className="bg-card border rounded-xl p-8 shadow-sm">
          <StepBar current={step} />

          {/* Step: Sub-sectors */}
          {step === "subsectors" && (
            <div>
              <div className="mb-5">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-primary" />
                  What type of life sciences company are you?
                </h2>
                <p className="text-sm text-muted-foreground mt-1">Select all that apply — this shapes your DTAP profiles and enforcement corpus.</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[380px] overflow-y-auto pr-1">
                {SUB_SECTORS.map((s) => (
                  <Chip
                    key={s.code}
                    selected={selectedSectors.includes(s.code)}
                    onClick={() => setSelectedSectors((prev) => toggle(prev, s.code))}
                    label={s.label}
                    description={s.description}
                    badge={s.code}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Step: Agencies */}
          {step === "agencies" && (
            <div>
              <div className="mb-5">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  Which regulatory agencies govern your products?
                </h2>
                <p className="text-sm text-muted-foreground mt-1">Determines which regulations, guidance, and enforcement records are included in assessments.</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[380px] overflow-y-auto pr-1">
                {AGENCIES.map((a) => (
                  <Chip
                    key={a.code}
                    selected={selectedAgencies.includes(a.code)}
                    onClick={() => setSelectedAgencies((prev) => toggle(prev, a.code))}
                    label={a.label}
                    description={a.description}
                    badge={a.region}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Step: Markets */}
          {step === "markets" && (
            <div>
              <div className="mb-5">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <Globe className="w-4 h-4 text-primary" />
                  Which markets do you supply or plan to supply?
                </h2>
                <p className="text-sm text-muted-foreground mt-1">Used to weight regulatory requirements and flag market-specific compliance gaps.</p>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {MARKETS.map((m) => (
                  <Chip
                    key={m.code}
                    selected={selectedMarkets.includes(m.code)}
                    onClick={() => setSelectedMarkets((prev) => toggle(prev, m.code))}
                    label={m.label}
                    badge={m.code}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* Selection summary */}
          <div className="mt-4 flex flex-wrap gap-1.5 min-h-[24px]">
            {step === "subsectors" && selectedSectors.map((s) => (
              <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">{s}</span>
            ))}
            {step === "agencies" && selectedAgencies.map((a) => (
              <span key={a} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">{a}</span>
            ))}
            {step === "markets" && selectedMarkets.map((m) => (
              <span key={m} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">{m}</span>
            ))}
          </div>

          {/* Nav buttons */}
          <div className="mt-6 flex gap-3">
            {step !== "subsectors" && (
              <button
                type="button"
                onClick={handleBack}
                disabled={isSubmitting}
                className="flex items-center gap-1.5 px-4 py-2.5 border rounded-lg text-sm hover:bg-accent transition-colors disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </button>
            )}
            <button
              type="button"
              onClick={handleNext}
              disabled={isSubmitting}
              className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {step === "markets" ? "Complete setup" : "Continue"}
              {step !== "markets" && <ChevronRight className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-4">
          You can update these settings anytime from Company Settings
        </p>
      </div>
    </div>
  );
}

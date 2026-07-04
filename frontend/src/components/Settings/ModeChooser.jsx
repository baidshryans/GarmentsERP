import { Building2, DatabaseZap } from "lucide-react";

/**
 * First-run choice: start a fresh ERP or migrate from an existing (old) ERP.
 * Presentational only — parent owns the selected mode.
 */
export default function ModeChooser({ onSelect }) {
  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">Welcome — let's set up your ERP</h2>
      <p className="text-sm text-muted-foreground mb-6">
        Choose how you want to get started. You can always add data later.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onSelect("new")}
          className="text-left rounded-xl border border-gray-200 p-5 hover:border-primary hover:shadow-sm transition"
        >
          <Building2 className="text-primary mb-3" size={28} />
          <h3 className="font-semibold mb-1">Set up a new ERP</h3>
          <p className="text-sm text-muted-foreground">
            Enter your company, branches, GSTIN and masters step by step.
          </p>
        </button>
        <button
          type="button"
          onClick={() => onSelect("migrate")}
          className="text-left rounded-xl border border-gray-200 p-5 hover:border-primary hover:shadow-sm transition"
        >
          <DatabaseZap className="text-primary mb-3" size={28} />
          <h3 className="font-semibold mb-1">Migrate from an existing ERP</h3>
          <p className="text-sm text-muted-foreground">
            Connect your old ERP database and import company, branches, retails,
            ledgers and masters automatically. Only GSTIN and fiscal year stay manual.
          </p>
        </button>
      </div>
    </div>
  );
}

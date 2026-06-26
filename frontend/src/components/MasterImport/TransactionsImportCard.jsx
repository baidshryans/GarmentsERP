import { useState, useRef } from "react";
import { Upload, Download, Loader2, CheckCircle, XCircle, FileText, Trash2, Eye } from "lucide-react";
import { runMigrationImport, downloadMigrationTemplate, resetMigrationData } from "@/services/apiService";

const RESET_SCOPES = [
  { key: "gl", label: "GL Vouchers" },
  { key: "customer_orders", label: "Customer Orders" },
  { key: "ledger_opening", label: "Ledger Opening Balances" },
  { key: "sales", label: "Sales Vouchers" },
  { key: "purchases", label: "Purchase Vouchers" },
  { key: "ledgers", label: "Non-system ledgers + aliases" },
];

// Each transactional import maps to one management command and its CSV file slots.
const KINDS = [
  {
    kind: "vouchers",
    label: "GL Vouchers",
    desc: "Journal / Payment / Receipt / Contra (Voucher Main + Details).",
    fields: [
      { name: "main",    label: "Voucher Main",    template: "voucher_main" },
      { name: "details", label: "Voucher Details", template: "voucher_details" },
    ],
  },
  {
    kind: "customer_orders",
    label: "Customer Orders",
    desc: "Customer orders + line items. Import ledgers & items first, and before sales.",
    fields: [
      { name: "header", label: "customer_order (header)", template: "customer_order" },
      { name: "items",  label: "customer_order_main (items)", template: "customer_order_main" },
    ],
  },
  {
    kind: "ledger_opening",
    label: "Ledger Opening Balances",
    desc: "Opening debit/credit per ledger per year (ldgr_open_balance). Import ledgers first.",
    fields: [
      { name: "file", label: "ldgr_open_balance", template: "ldgr_open_balance" },
    ],
  },
  {
    kind: "sales",
    label: "Sales Vouchers",
    desc: "Sales invoices, item lines and stone sub-items. Import barcodes & items first.",
    fields: [
      { name: "header",  label: "sales_vou (header)",      template: "sales_vou" },
      { name: "items",   label: "sales_vou_main (items)",  template: "sales_vou_main" },
      { name: "details", label: "sales_vou_detail (subs)", template: "sales_vou_detail" },
    ],
  },
  {
    kind: "purchases",
    label: "Purchase Vouchers",
    desc: "Purchase vouchers, item lines and sub-items. Import barcodes & items first.",
    fields: [
      { name: "header",  label: "purchase_voucher (header)",      template: "purchase_voucher" },
      { name: "items",   label: "purchase_voucher_main (items)",  template: "purchase_voucher_main" },
      { name: "details", label: "purchase_voucher_details (subs)", template: "purchase_voucher_details" },
    ],
  },
  {
    kind: "allocations",
    label: "Bill Allocations",
    desc: "Link receipts/payments to bills (amount tables). Run AFTER vouchers, sales & purchases. Any one file is enough.",
    optional: true,
    fields: [
      { name: "receive", label: "receive_amount", template: "receive_amount" },
      { name: "payment", label: "payment_amount", template: "payment_amount" },
      { name: "journal", label: "journal_amount", template: "journal_amount" },
    ],
  },
];

function FileSlot({ field, file, onPick }) {
  const inputRef = useRef(null);
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <FileText size={14} className="text-gray-400 shrink-0" />
        <span className="text-sm text-gray-700 truncate">{field.label}</span>
        {file && <span className="text-xs text-green-600 truncate">✓ {file.name}</span>}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <button
          type="button"
          onClick={() => downloadMigrationTemplate(field.template)}
          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 px-1.5 py-1"
          title="Download template CSV"
        >
          <Download size={13} /> Template
        </button>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-1 text-xs border border-gray-300 rounded px-2 py-1 hover:bg-gray-50"
        >
          <Upload size={13} /> {file ? "Change" : "Choose"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => onPick(field.name, e.target.files?.[0] || null)}
        />
      </div>
    </div>
  );
}

function MigrationCard({ def }) {
  const [files, setFiles] = useState({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const pick = (name, file) => setFiles((f) => ({ ...f, [name]: file }));

  const chosen = def.fields.filter((f) => files[f.name]);
  const canRun = def.optional ? chosen.length > 0 : chosen.length === def.fields.length;

  const run = async (apply) => {
    setRunning(true);
    setResult(null);
    const fileMap = {};
    def.fields.forEach((f) => { if (files[f.name]) fileMap[f.name] = files[f.name]; });
    const res = await runMigrationImport(def.kind, fileMap, apply);
    setResult(res);
    setRunning(false);
  };

  const output = result?.data?.output || result?.error || "";
  const reports = result?.data?.reports || {};

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <div className="mb-2">
        <h3 className="font-semibold text-gray-800">{def.label}</h3>
        <p className="text-xs text-gray-500">{def.desc}</p>
      </div>

      <div className="mb-3">
        {def.fields.map((f) => (
          <FileSlot key={f.name} field={f} file={files[f.name]} onPick={pick} />
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!canRun || running}
          onClick={() => run(false)}
          className="inline-flex items-center gap-1.5 text-sm text-gray-700 border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />} Dry run
        </button>
        <button
          type="button"
          disabled={!canRun || running}
          onClick={() => {
            if (window.confirm(`Apply ${def.label} import to the database? This writes records.`)) run(true);
          }}
          className="inline-flex items-center gap-1.5 text-sm bg-primary text-white rounded-md px-3 py-1.5 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Apply
        </button>
        {!canRun && (
          <span className="text-xs text-gray-400">
            {def.optional ? "Choose at least one file" : "Choose all files"}
          </span>
        )}
      </div>

      {result && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 text-sm mb-1">
            {result.success ? (
              <CheckCircle size={15} className="text-green-600" />
            ) : (
              <XCircle size={15} className="text-red-600" />
            )}
            <span className={result.success ? "text-green-700" : "text-red-700"}>
              {result.data?.applied ? "Applied" : "Dry run"} {result.success ? "complete" : "failed"}
            </span>
          </div>
          {output && (
            <pre className="text-xs bg-gray-900 text-gray-100 rounded p-2 overflow-auto max-h-56 whitespace-pre-wrap">
              {output}
            </pre>
          )}
          {Object.entries(reports).map(([name, content]) => (
            <details key={name} className="mt-2">
              <summary className="text-xs text-amber-700 cursor-pointer">{name}</summary>
              <pre className="text-xs bg-amber-50 rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap">{content}</pre>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

function ResetCard() {
  const [scope, setScope] = useState(Object.fromEntries(RESET_SCOPES.map((s) => [s.key, true])));
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const toggle = (k) => setScope((s) => ({ ...s, [k]: !s[k] }));
  const selected = RESET_SCOPES.filter((s) => scope[s.key]).map((s) => s.key);

  const run = async (apply) => {
    if (apply && !window.confirm(
      "Permanently delete the selected migrated data? System ledgers and any records still referenced by existing data are preserved. This cannot be undone."
    )) return;
    setRunning(true);
    setResult(null);
    const res = await resetMigrationData(selected, apply);
    setResult(res);
    setRunning(false);
  };

  const rep = result?.data?.report || {};
  return (
    <div className="border border-red-200 bg-red-50/40 rounded-lg p-4 mt-6">
      <h3 className="font-semibold text-red-700">Clear migrated data</h3>
      <p className="text-xs text-gray-600 mb-3">
        Delete non-system-seeded migrated data so you can re-run a sync. System ledgers, config, and
        records referenced by existing data are preserved. Always Preview first.
      </p>
      <div className="flex flex-wrap gap-3 mb-3">
        {RESET_SCOPES.map((s) => (
          <label key={s.key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
            <input type="checkbox" checked={!!scope[s.key]} onChange={() => toggle(s.key)} className="rounded" />
            <span>{s.label}</span>
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={running || !selected.length}
          onClick={() => run(false)}
          className="inline-flex items-center gap-1.5 text-sm text-gray-700 border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />} Preview
        </button>
        <button
          type="button"
          disabled={running || !selected.length}
          onClick={() => run(true)}
          className="inline-flex items-center gap-1.5 text-sm bg-red-600 text-white rounded-md px-3 py-1.5 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />} Delete
        </button>
      </div>
      {result && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 text-sm mb-1">
            {result.success ? (
              <CheckCircle size={15} className="text-green-600" />
            ) : (
              <XCircle size={15} className="text-red-600" />
            )}
            <span className={result.success ? "text-green-700" : "text-red-700"}>
              {result.data?.applied ? "Deleted" : "Preview — nothing deleted"}
              {result.success ? "" : ` — ${result.error || "failed"}`}
            </span>
          </div>
          {Object.keys(rep).length > 0 && (
            <table className="text-xs w-full max-w-md">
              <thead className="text-gray-500">
                <tr>
                  <th className="text-left">Data</th>
                  <th className="text-right pr-3">{result.data?.applied ? "Deleted" : "Would delete"}</th>
                  <th className="text-right">Kept (in use)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(rep).map(([k, v]) => (
                  <tr key={k} className="border-t border-red-100">
                    <td className="py-0.5">{k.replace(/_/g, " ")}</td>
                    <td className="text-right pr-3">{v.deleted}</td>
                    <td className="text-right">{v.skipped_protected ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export default function TransactionsImport() {
  return (
    <div>
      <p className="text-sm text-gray-600 mb-1">
        One-time migration of transactional data from the legacy ERP. Download a template to see the
        exact columns, export the matching legacy table to CSV, then upload here.
      </p>
      <p className="text-xs text-gray-500 mb-4">
        Recommended order: <strong>masters → GL Vouchers → Sales → Purchases → Bill Allocations</strong>.
        Always <strong>Dry run</strong> first and review the output &amp; unresolved reports before <strong>Apply</strong>.
        Imports are idempotent — re-running skips already-imported rows.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {KINDS.map((def) => (
          <MigrationCard key={def.kind} def={def} />
        ))}
      </div>
      <ResetCard />
    </div>
  );
}

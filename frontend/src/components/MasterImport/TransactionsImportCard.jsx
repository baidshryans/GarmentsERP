import { useState, useRef } from "react";
import { Upload, Download, Loader2, CheckCircle, XCircle, FileText } from "lucide-react";
import { runMigrationImport, downloadMigrationTemplate } from "@/services/apiService";

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
          className="inline-flex items-center gap-1.5 text-sm border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : null} Dry run
        </button>
        <button
          type="button"
          disabled={!canRun || running}
          onClick={() => {
            if (window.confirm(`Apply ${def.label} import to the database? This writes records.`)) run(true);
          }}
          className="inline-flex items-center gap-1.5 text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
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
    </div>
  );
}

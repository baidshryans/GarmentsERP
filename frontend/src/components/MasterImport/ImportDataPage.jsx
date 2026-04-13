import { useState, useRef, useEffect } from "react";
import { Upload, RefreshCw, CheckCircle, XCircle, Loader2, Database, Download, Users, Wand2 } from "lucide-react";
import { uploadHSNCSV, uploadItemGroupCSV, uploadItemCSV, uploadPacketGroupCSV, uploadPacketCSV, uploadKarigarMakingCSV, runMySQLSync, downloadLedgerTemplate, uploadLedgerCSV, seedSystemLedgers } from "@/services/apiService";
import apiClient from "@/services/apiClient";

const LEDGER_TYPES = [
  { type: "CO",  label: "Customers",                hint: "ac_name, ac_group_name, salutation, dob (DD/MM/YYYY), anniversary, mobile1, pan, gst, aadhar, address…" },
  { type: "DL",  label: "Dealers",                  hint: "ac_name, ac_group_name, dob, anniversary, mobile1, pan, gst, address…" },
  { type: "KR",  label: "Karigar",                  hint: "ac_name, ac_group_name, mobile1, pan, gst, address…" },
  { type: "VD",  label: "Vendors",                  hint: "ac_name, ac_group_name, mobile1, pan, gst, address…" },
  { type: "SC",  label: "Suppliers / Sundry Creditors", hint: "ac_name, ac_group_name, mobile1, pan, gst, address…" },
  { type: "SD",  label: "Sundry Debtors",           hint: "ac_name, ac_group_name, mobile1, pan, gst, address…" },
  { type: "BA",  label: "Bank Accounts",            hint: "ac_name, ac_group_name, cheque_no (account number), address…" },
  { type: "EXP", label: "Expense Ledgers",          hint: "ac_name, ac_group_name, remarks" },
  { type: "INC", label: "Income Ledgers",           hint: "ac_name, ac_group_name, remarks" },
  { type: "OTH", label: "Others",                   hint: "ac_name, ac_group_name, address, pan, gst, remarks" },
];

const TABLES = [
  { key: "hsn",            label: "HSN Master",            uploadFn: uploadHSNCSV,           hint: "Columns: hsn_no, description, hsn_type, hsn_per_cgst, hsn_per_igst",                                                              dependsOn: null },
  { key: "item_group",     label: "Item Group Master",     uploadFn: uploadItemGroupCSV,      hint: "Columns: id (required — must match old ERP id), name (or item_group_name), short_code",                                          dependsOn: null },
  { key: "item",           label: "Item Master",           uploadFn: uploadItemCSV,           hint: "Columns: id, short_code, item (or item_name), item_type, uom, hsn_no, purchase_ledger, sale_ledger, show_in_pcs_report, grp",      dependsOn: "item_group" },
  { key: "packet_group",   label: "Packet Group Master",   uploadFn: uploadPacketGroupCSV,    hint: "Columns: packet_group (or packet_group_name)",                                                                                     dependsOn: "item" },
  { key: "packet",         label: "Packet Master",         uploadFn: uploadPacketCSV,         hint: "Columns: pckt_no, stone_id, rate_for_retail, rate_for_wholesale, solitare, customer, packet_group",                               dependsOn: "item" },
  { key: "karigar_making", label: "Karigar Making Rates",  uploadFn: uploadKarigarMakingCSV,  hint: "Columns: karigar_name, item_code, purity, making_per_gm, making_per_pc, loss_rate, kr_code (optional)",                           dependsOn: "item" },
];

function ResultBadge({ result }) {
  if (!result) return null;
  const hasErrors = result.errors?.length > 0;
  return (
    <div className="mt-2 text-xs space-y-1">
      <div className="flex gap-3 flex-wrap">
        <span className="text-green-700">Created: <strong>{result.created}</strong></span>
        <span className="text-primary">Updated: <strong>{result.updated}</strong></span>
        {result.items_mapped != null && (
          <span className="text-gray-500">Items mapped: <strong>{result.items_mapped}</strong></span>
        )}
        {hasErrors && <span className="text-red-600">Errors: <strong>{result.errors.length}</strong></span>}
      </div>

      {hasErrors && (
        <details className="text-red-600">
          <summary className="cursor-pointer">View errors</summary>
          <ul className="mt-1 space-y-0.5 list-disc list-inside">
            {result.errors.slice(0, 20).map((e, i) => <li key={i}>{e}</li>)}
            {result.errors.length > 20 && <li>…and {result.errors.length - 20} more</li>}
          </ul>
        </details>
      )}
    </div>
  );
}

function CSVUploadCard({ tableKey, label, uploadFn, hint, blockedBy, onSuccess }) {
  const inputRef = useRef(null);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [fileName, setFileName] = useState("");

  const isBlocked = !!blockedBy;

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setStatus("loading");
    setResult(null);
    setErrorMsg("");
    const res = await uploadFn(file);
    if (res.success) {
      setStatus("success");
      setResult(res.data);
      onSuccess?.(tableKey);
    } else {
      setStatus("error");
      setErrorMsg(res.error || "Upload failed");
    }
    e.target.value = "";
  };

  return (
    <div className={`rounded-lg border p-4 shadow-sm transition-opacity ${isBlocked ? "border-gray-100 bg-gray-50 opacity-60 pointer-events-none" : "border-gray-200 bg-white"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-800">{label}</h3>
          <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{hint}</p>
          {isBlocked && (
            <p className="mt-1.5 text-xs text-amber-600 flex items-center gap-1">
              ⚠ Upload <strong>{blockedBy}</strong> first
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={isBlocked || status === "loading"}
          className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-primary hover:bg-primary text-white disabled:opacity-50 transition-colors shrink-0"
        >
          {status === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          {status === "loading" ? "Uploading…" : "Upload CSV"}
        </button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
      </div>
      {fileName && status !== "idle" && <p className="mt-2 text-xs text-gray-500 truncate">File: {fileName}</p>}
      {status === "success" && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-green-700">
          <CheckCircle size={13} /><span>Import complete</span>
        </div>
      )}
      {status === "error" && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-red-600">
          <XCircle size={13} /><span>{errorMsg}</span>
        </div>
      )}
      <ResultBadge result={result} />
    </div>
  );
}


function LedgerUploadCard({ type, label, hint }) {
  const inputRef = useRef(null);
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [result, setResult]             = useState(null);
  const [errorMsg, setErrorMsg]         = useState("");
  const [fileName, setFileName]         = useState("");
  const [downloading, setDownloading]   = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    await downloadLedgerTemplate(type);
    setDownloading(false);
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setUploadStatus("loading");
    setResult(null);
    setErrorMsg("");
    const res = await uploadLedgerCSV(file, type);
    if (res.success) {
      setUploadStatus("success");
      setResult(res.data);
    } else {
      setUploadStatus("error");
      setErrorMsg(res.error || "Upload failed");
    }
    e.target.value = "";
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-800">{label}</h3>
          <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{hint}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border border-violet-300 bg-violet-50 hover:bg-violet-100 text-primary disabled:opacity-50 transition-colors"
          >
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {downloading ? "…" : "Template"}
          </button>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploadStatus === "loading"}
            className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-primary hover:bg-primary text-white disabled:opacity-50 transition-colors"
          >
            {uploadStatus === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            {uploadStatus === "loading" ? "Uploading…" : "Upload CSV"}
          </button>
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
        </div>
      </div>
      {fileName && uploadStatus !== "idle" && (
        <p className="mt-2 text-xs text-gray-500 truncate">File: {fileName}</p>
      )}
      {uploadStatus === "success" && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-green-700">
          <CheckCircle size={13} /><span>Import complete</span>
        </div>
      )}
      {uploadStatus === "error" && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-red-600">
          <XCircle size={13} /><span>{errorMsg}</span>
        </div>
      )}
      <ResultBadge result={result} />
    </div>
  );
}

function MySQLSyncCard() {
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [selectedTables, setSelectedTables] = useState({
    hsn: true, item: true, packet_group: true, packet: true,
  });

  const toggleTable = (key) => setSelectedTables((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleSync = async () => {
    const tables = Object.entries(selectedTables).filter(([, v]) => v).map(([k]) => k);
    if (!tables.length) return;
    setStatus("loading");
    setResults(null);
    setErrorMsg("");
    const res = await runMySQLSync(tables);
    if (res.success) {
      setStatus("success");
      setResults(res.data.results || {});
    } else {
      setStatus("error");
      setErrorMsg(res.error || "Sync failed");
    }
  };

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-gray-800 flex items-center gap-1.5">
            <Database size={15} className="text-primary" />
            MySQL Sync
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Syncs master tables directly from your source MySQL database (configured in settings).
          </p>
        </div>
        <button
          type="button"
          onClick={handleSync}
          disabled={status === "loading"}
          className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-primary hover:bg-primary text-white disabled:opacity-50 transition-colors shrink-0"
        >
          {status === "loading" ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {status === "loading" ? "Syncing…" : "Sync Now"}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-3">
        {TABLES.map(({ key, label }) => (
          <label key={key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
            <input type="checkbox" checked={!!selectedTables[key]} onChange={() => toggleTable(key)} className="rounded" />
            <span>{label}</span>
          </label>
        ))}
      </div>
      {status === "error" && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-red-600">
          <XCircle size={13} /><span>{errorMsg}</span>
        </div>
      )}
      {status === "success" && results && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-green-700">
            <CheckCircle size={13} /><span>Sync complete</span>
          </div>
          {Object.entries(results).map(([table, r]) => (
            <div key={table} className="bg-white rounded border border-gray-200 px-3 py-2">
              <p className="text-xs font-semibold capitalize text-gray-700">{table.replace('_', ' ')} master</p>
              <ResultBadge result={r} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SeedSystemLedgersCard() {
  const [status, setStatus] = useState("idle");
  const [detail, setDetail] = useState("");

  const handleSeed = async () => {
    setStatus("loading");
    setDetail("");
    const res = await seedSystemLedgers();
    if (res.success) {
      setStatus("success");
      setDetail(res.data?.detail || "Done.");
    } else {
      setStatus("error");
      setDetail(typeof res.error === "string" ? res.error : JSON.stringify(res.error));
    }
  };

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 shadow-sm flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-gray-800 flex items-center gap-1.5">
          <Wand2 size={15} className="text-primary" />
          Seed System Ledgers
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Creates any missing system ledgers (purchase, sales, expense, income, etc.).
          Run this before uploading the Item Master CSV so purchase/sale ledger names resolve correctly.
          Safe to re-run — existing ledgers are never duplicated.
        </p>
        {status === "success" && (
          <p className="mt-2 text-xs text-green-700 flex items-center gap-1"><CheckCircle size={12} /> System ledgers up to date.</p>
        )}
        {status === "error" && (
          <p className="mt-2 text-xs text-red-600 flex items-center gap-1"><XCircle size={12} /> {detail}</p>
        )}
      </div>
      <button
        type="button"
        onClick={handleSeed}
        disabled={status === "loading"}
        className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-primary text-white hover:opacity-90 disabled:opacity-50 transition-colors shrink-0"
      >
        {status === "loading" ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
        {status === "loading" ? "Seeding…" : "Seed Now"}
      </button>
    </div>
  );
}

// Check which tables already have data in the DB
const TABLE_CHECK_URLS = {
  item_group:   '/mastersconfig/api/item_group/?page_size=1',
  item:         '/mastersconfig/api/item/?page_size=1',
  packet_group: '/mastersconfig/api/packet_group/?page_size=1',
  packet:       '/mastersconfig/api/packet/?page_size=1',
};

export default function ImportDataPage() {
  const [completed, setCompleted] = useState(new Set());

  // On mount, check which dependent tables already have data and pre-unlock them
  useEffect(() => {
    const keys = Object.keys(TABLE_CHECK_URLS);
    Promise.all(
      keys.map(key =>
        apiClient.get(TABLE_CHECK_URLS[key])
          .then(r => {
            const count = r.data?.count ?? (Array.isArray(r.data) ? r.data.length : 0);
            return count > 0 ? key : null;
          })
          .catch(() => null)
      )
    ).then(results => {
      const already = new Set(results.filter(Boolean));
      if (already.size) setCompleted(already);
    });
  }, []);

  const handleSuccess = (key) => setCompleted(prev => new Set([...prev, key]));

  // Resolve human-readable label for a dependency key
  const labelOf = (key) => TABLES.find(t => t.key === key)?.label ?? key;

  // A card is blocked if its dependency has not been completed yet
  const blockedBy = (dependsOn) => {
    if (!dependsOn) return null;
    return completed.has(dependsOn) ? null : labelOf(dependsOn);
  };

  return (
    <div className="container mt-5 max-w-3xl">
      <h6 className="text-lg font-semibold mb-1">Import Master Data</h6>
      <p className="text-sm text-gray-500 mb-5">
        Upload CSV files to populate master tables, or sync directly from a connected MySQL database.
      </p>
      <div className="space-y-4">
        <SeedSystemLedgersCard />
        <section>
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">CSV Upload</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {TABLES.map(({ key, dependsOn, ...rest }) => (
              <CSVUploadCard
                key={key}
                tableKey={key}
                blockedBy={blockedBy(dependsOn)}
                onSuccess={handleSuccess}
                {...rest}
              />
            ))}
          </div>
        </section>
        <section>
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Users size={14} className="text-primary" />
            Ledger Masters
          </h2>
          <p className="text-xs text-gray-500 mb-3">
            Download the template for each ledger role, fill it in from your existing records, then upload.
            The first two rows are sample data — delete them before uploading.
            Rows are matched by <code className="bg-gray-100 px-1 rounded">ac_name</code> — re-uploading the same file safely updates existing ledgers.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {LEDGER_TYPES.map(({ type, label, hint }) => (
              <LedgerUploadCard key={type} type={type} label={label} hint={hint} />
            ))}
          </div>
        </section>
        <section>
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">MySQL Sync</h2>
          <MySQLSyncCard />
        </section>
      </div>
    </div>
  );
}

import { useState, useRef, useEffect } from "react";
import { Upload, RefreshCw, CheckCircle, XCircle, Loader2, Database, Download, Users, Wand2, Eye, EyeOff, Tag, Package, ArrowRightLeft } from "lucide-react";
import TransactionsImport from "./TransactionsImportCard";
import { uploadHSNCSV, uploadItemGroupCSV, uploadItemCSV, uploadPacketGroupCSV, uploadPacketCSV, uploadKarigarMakingCSV, runMySQLSync, getMySQLConfig, downloadLedgerTemplate, uploadLedgerCSV, seedSystemLedgers, downloadOpeningStockTemplate, uploadOpeningStockCSV } from "@/services/apiService";
import apiClient from "@/services/apiClient";
import BarcodeOpeningUploadCard from './BarcodeOpeningUploadCard';

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

// Master tables selectable for direct MySQL sync. Mirrors TABLES (the CSV-upload
// masters) plus Retail Master, which is sync-only (no CSV upload card).
const SYNC_MASTER_TABLES = [
  ...TABLES.map(({ key, label }) => ({ key, label })),
  { key: "ledger", label: "Ledger Master" },
  { key: "retail", label: "Retail Master" },
];

// Transactional tables for direct MySQL sync (run after masters).
const TX_SYNC_TABLES = [
  { key: "gl_vouchers", label: "GL Vouchers" },
  { key: "sales",       label: "Sales Vouchers" },
  { key: "purchases",   label: "Purchase Vouchers" },
  { key: "allocations", label: "Bill Allocations" },
];

const TABS = [
  { id: "masters",       label: "Masters",       icon: Database  },
  { id: "ledgers",       label: "Ledgers",       icon: Users     },
  { id: "barcode",       label: "Barcode",       icon: Tag       },
  { id: "opening_stock", label: "Opening Stock", icon: Package   },
  { id: "transactions", label: "Transactions",  icon: ArrowRightLeft },
  { id: "mysql",         label: "MySQL Sync",    icon: RefreshCw },
];

function ResultBadge({ result }) {
  if (!result) return null;
  const hasErrors = result.errors?.length > 0;
  return (
    <div className="mt-2 text-xs space-y-1">
      <div className="flex gap-3 flex-wrap">
        <span className="text-green-700">Created: <strong>{result.created}</strong></span>
        <span className="text-primary">Updated: <strong>{result.updated}</strong></span>
        {result.aliased > 0 && (
          <span className="text-indigo-600" title="Folded onto existing system ledgers (GST/TCS/TDS/etc.)">Aliased: <strong>{result.aliased}</strong></span>
        )}
        {result.items_mapped != null && (
          <span className="text-gray-500">Items mapped: <strong>{result.items_mapped}</strong></span>
        )}
        {hasErrors && <span className="text-red-600">Errors: <strong>{result.errors.length}</strong></span>}
        {result.ungrouped_count > 0 && (
          <span className="text-amber-600">No group match: <strong>{result.ungrouped_count}</strong></span>
        )}
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

      {result.ungrouped?.length > 0 && (
        <details className="text-amber-700">
          <summary className="cursor-pointer flex items-center gap-2">
            Ledgers with no group match ({result.ungrouped_count})
            <button
              type="button"
              onClick={(e) => { e.preventDefault(); downloadUngroupedCsv(result.ungrouped); }}
              className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800"
            >
              <Download size={12} /> CSV
            </button>
          </summary>
          <div className="mt-1 max-h-48 overflow-auto">
            <table className="text-[11px] w-full">
              <thead className="text-gray-500">
                <tr><th className="text-left pr-3">ID</th><th className="text-left pr-3">Ledger</th><th className="text-left">Legacy group (ac_grp)</th></tr>
              </thead>
              <tbody>
                {result.ungrouped.slice(0, 300).map((l, i) => (
                  <tr key={i} className="border-t border-amber-100">
                    <td className="pr-3 py-0.5">{l.id}</td>
                    <td className="pr-3 py-0.5">{l.ac_name}</td>
                    <td className="py-0.5">{l.group || <em className="text-gray-400">(blank)</em>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.ungrouped.length > 300 && (
              <p className="text-gray-400 mt-1">…showing 300 of {result.ungrouped_count}. Download the CSV for the full list.</p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

// Download the "no group match" ledgers as a CSV (client-side, no server call).
function downloadUngroupedCsv(rows) {
  const header = "id,ac_name,legacy_group\n";
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const body = rows.map((r) => [r.id, esc(r.ac_name), esc(r.group)].join(",")).join("\n");
  const blob = new Blob([header + body], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ledgers_without_group.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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

function OpeningStockUploadCard() {
  const inputRef = useRef(null);
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [fileName, setFileName] = useState("");
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    await downloadOpeningStockTemplate();
    setDownloading(false);
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setUploadStatus("loading");
    setResult(null);
    setErrorMsg("");
    const res = await uploadOpeningStockCSV(file);
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
          <h3 className="font-semibold text-gray-800">Opening Stock</h3>
          <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
            Columns: <code className="bg-gray-100 px-1 rounded">item_short_code</code>,
            <code className="bg-gray-100 px-1 rounded ml-1">type</code> (SH/KR/CO),
            <code className="bg-gray-100 px-1 rounded ml-1">ldgr_name</code> (required for KR/CO),
            <code className="bg-gray-100 px-1 rounded ml-1">purity</code>,
            <code className="bg-gray-100 px-1 rounded ml-1">packet_no</code>,
            <code className="bg-gray-100 px-1 rounded ml-1">pcs</code>,
            <code className="bg-gray-100 px-1 rounded ml-1">ct</code>,
            <code className="bg-gray-100 px-1 rounded ml-1">gw</code>,
            <code className="bg-gray-100 px-1 rounded ml-1">wtd_avg_rate</code>. Re-uploading
            updates existing rows matched by item + type + ledger.
          </p>
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


const EMPTY_CONN = { host: "", port: "3306", database: "", user: "", password: "" };

function MySQLSyncCard() {
  const [conn, setConn] = useState(EMPTY_CONN);
  const [showPwd, setShowPwd] = useState(false);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [selectedTables, setSelectedTables] = useState({
    ...Object.fromEntries(SYNC_MASTER_TABLES.map(({ key }) => [key, true])),
    // transactions default OFF — they should be synced after masters exist
    ...Object.fromEntries(TX_SYNC_TABLES.map(({ key }) => [key, false])),
  });

  useEffect(() => {
    getMySQLConfig().then(r => {
      if (r.success && r.data) {
        setConn({
          host:     r.data.host     || "",
          port:     String(r.data.port || "3306"),
          database: r.data.database || "",
          user:     r.data.user     || "",
          password: r.data.password || "",
        });
      }
      setConfigLoaded(true);
    });
  }, []);

  const setField = (k) => (e) => setConn(prev => ({ ...prev, [k]: e.target.value }));
  const toggleTable = (key) => setSelectedTables((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleSync = async () => {
    if (!conn.database.trim()) {
      setStatus("error");
      setErrorMsg("Database name is required");
      return;
    }
    const tables = Object.entries(selectedTables).filter(([, v]) => v).map(([k]) => k);
    if (!tables.length) return;
    setStatus("loading");
    setResults(null);
    setErrorMsg("");
    const res = await runMySQLSync(
      { host: conn.host, port: Number(conn.port) || 3306, database: conn.database, user: conn.user, password: conn.password },
      tables,
    );
    if (res.success) {
      setStatus("success");
      setResults(res.data.results || {});
    } else {
      setStatus("error");
      setErrorMsg(res.error || "Sync failed");
    }
  };

  const inputCls = "h-8 w-full rounded border border-gray-300 bg-white px-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary";

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 shadow-sm space-y-4">
      <div className="flex items-center gap-1.5">
        <Database size={15} className="text-primary" />
        <h3 className="font-semibold text-gray-800 text-sm">MySQL Sync</h3>
      </div>

      {/* Connection form */}
      {configLoaded && (
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Host / IP Address</label>
            <input className={inputCls} placeholder="127.0.0.1" value={conn.host} onChange={setField("host")} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Port</label>
            <input className={inputCls} placeholder="3306" value={conn.port} onChange={setField("port")} type="number" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Database Name</label>
            <input className={inputCls} placeholder="my_database" value={conn.database} onChange={setField("database")} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Username</label>
            <input className={inputCls} placeholder="root" value={conn.user} onChange={setField("user")} />
          </div>
          <div className="col-span-2 flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Password</label>
            <div className="relative">
              <input
                className={`${inputCls} pr-8`}
                type={showPwd ? "text" : "password"}
                placeholder="••••••••"
                value={conn.password}
                onChange={setField("password")}
              />
              <button
                type="button"
                onClick={() => setShowPwd(p => !p)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPwd ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table selection */}
      <div>
        <p className="text-xs text-gray-500 font-medium mb-1.5">Tables to sync</p>
        <div className="flex flex-wrap gap-3">
          {SYNC_MASTER_TABLES.map(({ key, label }) => (
            <label key={key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <input type="checkbox" checked={!!selectedTables[key]} onChange={() => toggleTable(key)} className="rounded" />
              <span>{label}</span>
            </label>
          ))}
        </div>
        <p className="text-xs font-medium text-gray-500 mt-3 mb-1">Transactions <span className="font-normal">(sync after masters)</span></p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {TX_SYNC_TABLES.map(({ key, label }) => (
            <label key={key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <input type="checkbox" checked={!!selectedTables[key]} onChange={() => toggleTable(key)} className="rounded" />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Sync button */}
      <button
        type="button"
        onClick={handleSync}
        disabled={status === "loading"}
        className="inline-flex items-center gap-1.5 text-sm px-4 py-1.5 rounded-md bg-primary text-white disabled:opacity-50 transition-colors"
      >
        {status === "loading" ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
        {status === "loading" ? "Syncing…" : "Sync Now"}
      </button>

      {/* Feedback */}
      {status === "error" && (
        <div className="flex items-center gap-1.5 text-xs text-red-600">
          <XCircle size={13} /><span>{errorMsg}</span>
        </div>
      )}
      {status === "success" && results && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-green-700">
            <CheckCircle size={13} /><span>Sync complete — connection details saved</span>
          </div>
          {Object.entries(results).map(([table, r]) => (
            <div key={table} className="bg-white rounded border border-gray-200 px-3 py-2">
              <p className="text-xs font-semibold capitalize text-gray-700">{table.replace(/_/g, ' ')}</p>
              {r && (r.output != null || r.status) ? (
                <div className="mt-1">
                  <span className={`text-xs ${r.status === "error" ? "text-red-600" : "text-green-700"}`}>
                    {r.status === "error" ? (r.error || "Failed") : "Done"}
                  </span>
                  {r.output && (
                    <pre className="mt-1 text-[11px] bg-gray-900 text-gray-100 rounded p-2 overflow-auto max-h-48 whitespace-pre-wrap">{r.output}</pre>
                  )}
                  {r.reports && Object.entries(r.reports).map(([fn, c]) => (
                    <details key={fn} className="mt-1">
                      <summary className="text-[11px] text-amber-700 cursor-pointer">{fn}</summary>
                      <pre className="text-[11px] bg-amber-50 rounded p-2 overflow-auto max-h-40 whitespace-pre-wrap">{c}</pre>
                    </details>
                  ))}
                </div>
              ) : (
                <ResultBadge result={r} />
              )}
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
  const [activeTab, setActiveTab] = useState("masters");
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

  const labelOf = (key) => TABLES.find(t => t.key === key)?.label ?? key;

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

      {/* Tab bar */}
      <div className="flex gap-1 mb-5 bg-gray-100 rounded-lg p-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveTab(id)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-md font-medium transition-colors ${
              activeTab === id
                ? "bg-primary text-white shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <Icon size={14} />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* Masters tab */}
      {activeTab === "masters" && (
        <div className="space-y-4">
          <SeedSystemLedgersCard />
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
        </div>
      )}

      {/* Ledgers tab */}
      {activeTab === "ledgers" && (
        <div className="space-y-4">
          <p className="text-xs text-gray-500">
            Download the template for each ledger role, fill it in from your existing records, then upload.
            The first two rows are sample data — delete them before uploading.
            Rows are matched by <code className="bg-gray-100 px-1 rounded">ac_name</code> — re-uploading the same file safely updates existing ledgers.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {LEDGER_TYPES.map(({ type, label, hint }) => (
              <LedgerUploadCard key={type} type={type} label={label} hint={hint} />
            ))}
          </div>
        </div>
      )}

      {/* Barcode tab */}
      {activeTab === "barcode" && (
        <div className="space-y-4">
          <p className="text-xs text-gray-500">
            Bulk-upload opening-stock barcodes with their details. Both CSVs are required.
            New barcodes are flagged with <code className="bg-gray-100 px-1 rounded">op_stk=true</code>.
            Existing barcodes can be skipped, updated, or treated as an error.
          </p>
          <BarcodeOpeningUploadCard />
        </div>
      )}

      {/* Opening Stock tab */}
      {activeTab === "opening_stock" && (
        <div className="space-y-4">
          <p className="text-xs text-gray-500">
            Bulk-upload opening stock entries that feed the Closing Stock report. Download the
            template, fill it in (one row per item / type / ledger), then upload. For Stone (S)
            items, leave <code className="bg-gray-100 px-1 rounded">gw</code> blank to auto-derive
            it as <code className="bg-gray-100 px-1 rounded">ct ÷ 5</code>.
          </p>
          <OpeningStockUploadCard />
        </div>
      )}

      {/* MySQL Sync tab */}
      {activeTab === "transactions" && (
        <TransactionsImport />
      )}

      {activeTab === "mysql" && (
        <MySQLSyncCard />
      )}
    </div>
  );
}

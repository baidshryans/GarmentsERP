import { useState, useRef } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Upload, CheckCircle, XCircle, Loader2, AlertTriangle } from "lucide-react";
import apiClient from "@/services/apiClient";

const STATUS_STYLES = {
  MATCHED:  { badge: "bg-green-100 text-green-800",  icon: <CheckCircle size={13} className="text-green-600" /> },
  MISMATCH: { badge: "bg-amber-100 text-amber-800",  icon: <AlertTriangle size={13} className="text-amber-600" /> },
  MISSING:  { badge: "bg-red-100 text-red-800",      icon: <XCircle size={13} className="text-red-600" /> },
};

const TABS = ["All", "MATCHED", "MISMATCH", "MISSING"];

export default function GSTR2BReconcile() {
  const inputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");
  const [tab, setTab] = useState("All");

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setLoading(true);
    setResult(null);
    setError("");

    const form = new FormData();
    form.append("file", file);
    try {
      const res = await apiClient.post("/purchase/api/gstr2b-reconcile/", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.error || "Reconciliation failed");
    }
    setLoading(false);
    e.target.value = "";
  };

  const rows = result
    ? result.results.filter((r) => tab === "All" || r.status === tab)
    : [];

  const fmt = (v) =>
    v == null ? "—" : formatNumber(v, { minDecimals: 2 });

  const diffCell = (v) => {
    if (v == null) return <span className="text-gray-400">—</span>;
    const n = parseFloat(v);
    if (Math.abs(n) < 0.01) return <span className="text-green-600">0.00</span>;
    return <span className={n > 0 ? "text-red-500" : "text-amber-600"}>{n > 0 ? "+" : ""}{fmt(v)}</span>;
  };

  return (
    <div className="container mt-5 max-w-6xl">
      <h6 className="text-lg font-semibold mb-1">GSTR-2B Reconciliation</h6>
      <p className="text-sm text-gray-500 mb-5">
        Upload the GSTR-2B JSON file downloaded from the GST portal. The system will match each invoice
        against your purchase vouchers and flag discrepancies.
      </p>

      {/* Upload card */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm mb-5 flex items-center gap-4 flex-wrap">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-700">
            {fileName || "No file selected"}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">Accepted: .json (GSTR-2B from GST portal)</p>
        </div>
        <Button
          onClick={() => inputRef.current?.click()}
          disabled={loading}
          className="flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          {loading ? "Reconciling…" : "Upload & Reconcile"}
        </Button>
        <input ref={inputRef} type="file" accept=".json,application/json" className="hidden" onChange={handleFile} />
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm mb-4">
          <XCircle size={15} />{error}
        </div>
      )}

      {loading && (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {result && !loading && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            {[
              { label: "Total in 2B",  value: result.summary.total,    color: "text-gray-800" },
              { label: "Matched",      value: result.summary.matched,  color: "text-green-700" },
              { label: "Mismatch",     value: result.summary.mismatch, color: "text-amber-600" },
              { label: "Missing",      value: result.summary.missing,  color: "text-red-600" },
            ].map((c) => (
              <div key={c.label} className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
                <p className="text-xs text-gray-500">{c.label}</p>
                <p className={`text-2xl font-semibold ${c.color}`}>{c.value}</p>
              </div>
            ))}
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mb-3">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  tab === t
                    ? "bg-primary text-white border-primary"
                    : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                }`}
              >
                {t} {t !== "All" && `(${result.summary[t.toLowerCase()] ?? 0})`}
              </button>
            ))}
          </div>

          {/* Table */}
          {rows.length === 0 ? (
            <p className="text-gray-400 text-sm">No records in this category.</p>
          ) : (
            <div className="overflow-x-auto rounded border border-gray-200">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 text-gray-600 uppercase">
                  <tr>
                    <th className="px-2 py-2 text-left">Status</th>
                    <th className="px-2 py-2 text-left">Supplier GSTIN</th>
                    <th className="px-2 py-2 text-left">Supplier</th>
                    <th className="px-2 py-2 text-left">Inv No (2B)</th>
                    <th className="px-2 py-2 text-left">Date (2B)</th>
                    <th className="px-2 py-2 text-right">Value (2B)</th>
                    <th className="px-2 py-2 text-right">CGST 2B</th>
                    <th className="px-2 py-2 text-right">SGST 2B</th>
                    <th className="px-2 py-2 text-right">IGST 2B</th>
                    <th className="px-2 py-2 text-left">Our Bill No</th>
                    <th className="px-2 py-2 text-right">Our CGST</th>
                    <th className="px-2 py-2 text-right">Our SGST</th>
                    <th className="px-2 py-2 text-right">Our IGST</th>
                    <th className="px-2 py-2 text-right">CGST Δ</th>
                    <th className="px-2 py-2 text-right">SGST Δ</th>
                    <th className="px-2 py-2 text-right">IGST Δ</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((r, i) => {
                    const s = STATUS_STYLES[r.status] || {};
                    return (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-2 py-1.5">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-medium ${s.badge}`}>
                            {s.icon}{r.status}
                          </span>
                        </td>
                        <td className="px-2 py-1.5 font-mono">{r.supplier_gstin}</td>
                        <td className="px-2 py-1.5">{r.supplier_name || <span className="text-gray-400">—</span>}</td>
                        <td className="px-2 py-1.5 font-mono">{r.invoice_no_2b}</td>
                        <td className="px-2 py-1.5">{r.invoice_date_2b}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.val_2b)}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.cgst_2b)}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.sgst_2b)}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.igst_2b)}</td>
                        <td className="px-2 py-1.5 font-mono">{r.our_billno || <span className="text-gray-400">—</span>}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.our_cgst)}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.our_sgst)}</td>
                        <td className="px-2 py-1.5 text-right">{fmt(r.our_igst)}</td>
                        <td className="px-2 py-1.5 text-right">{diffCell(r.cgst_diff)}</td>
                        <td className="px-2 py-1.5 text-right">{diffCell(r.sgst_diff)}</td>
                        <td className="px-2 py-1.5 text-right">{diffCell(r.igst_diff)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

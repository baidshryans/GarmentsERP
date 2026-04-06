import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { Printer } from "lucide-react";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];

const fmt = (v) => {
  const n = Number(v);
  if (!n) return "—";
  return Math.abs(n).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const balLabel = (v) => {
  const n = Number(v);
  if (n === 0) return "—";
  return `${fmt(n)} ${n >= 0 ? "Dr" : "Cr"}`;
};

export default function BalanceSheet() {
  const [endDate, setEndDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [combined, setCombined] = useState(false);

  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams({ end_date: endDate });
      if (combined) params.set("combined", "true");
      const res = await apiClient.get(`/accounting/api/bal-sheet?${params}`);
      setData(res.data);
    } catch (e) {
      setError(
        e.response?.data?.error || "Failed to load Balance Sheet data."
      );
    }
    setLoading(false);
  };

  const handlePrint = () => {
    if (!data) return;
    const assets = (data.assets?.accounts || []).filter((a) => Number(a.balance || 0) !== 0);
    const liabilities = (data.liabilities?.accounts || []).filter((a) => Number(a.balance || 0) !== 0);

    const renderSection = (title, accounts, total) => {
      const rows = accounts.map(
        (acc, i) => `<tr${i % 2 === 1 ? ' style="background:#fafafa"' : ""}>
          <td class="pl-8">${acc.id === "net_profit" ? `<em>${acc.name}</em>` : acc.name}</td>
          <td style="text-align:right" class="tabular-nums">${balLabel(acc.balance)}</td>
        </tr>`
      );
      return `<tr class="section-header"><td colspan="2">${title}</td></tr>
        ${rows.join("")}
        <tr class="totals-row"><td>Total ${title}</td><td style="text-align:right" class="tabular-nums">${fmt(total)}</td></tr>`;
    };

    const html = `<table>
      <thead><tr><th>Particulars</th><th style="text-align:right;width:150px">Amount (\u20B9)</th></tr></thead>
      <tbody>
        ${renderSection("Assets", assets, data.assets?.total)}
        ${renderSection("Liabilities", liabilities, data.liabilities?.total)}
      </tbody>
      <tfoot><tr class="totals-row">
        <td style="font-size:12px">Difference (Assets \u2212 Liabilities)</td>
        <td style="text-align:right;font-size:12px" class="tabular-nums font-bold">${fmt(data.net_worth)}</td>
      </tr></tfoot>
    </table>`;

    printReport({
      title: "Balance Sheet",
      subtitle: `As on ${endDate}${combined ? " (Combined — All Retails)" : ""}`,
      html,
    });
  };

  const assetAccounts = (data?.assets?.accounts || []).filter(
    (a) => Number(a.balance || 0) !== 0
  );
  const liabilityAccounts = (data?.liabilities?.accounts || []).filter(
    (a) => Number(a.balance || 0) !== 0
  );

  return (
    <div className="flex flex-col gap-4">
      {/* ── Filters ───────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border print:hidden">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">As on Date</Label>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="h-9 w-40"
          />
        </div>
        {canViewCombined && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="bs-combined"
              checked={combined}
              onChange={(e) => setCombined(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Label htmlFor="bs-combined" className="text-xs cursor-pointer">Combined (All Retails)</Label>
          </div>
        )}
        <Button size="sm" onClick={fetchReport} className="h-9">
          Show
        </Button>
        {data && (
          <Button
            size="sm"
            variant="outline"
            onClick={handlePrint}
            className="h-9 ml-auto"
          >
            <Printer className="w-4 h-4 mr-1.5" /> Print
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      )}

      {data && !loading && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/50">
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Particulars
                </th>
                <th className="px-4 py-3 text-right font-semibold text-xs uppercase tracking-wider text-muted-foreground w-40">
                  Amount (₹)
                </th>
              </tr>
            </thead>

            {/* ── Assets ──────────────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30 border-t border-border">
                <td
                  colSpan={2}
                  className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground"
                >
                  Assets
                </td>
              </tr>
              {assetAccounts.length === 0 && (
                <tr className="border-t border-border/40">
                  <td colSpan={2} className="px-4 py-6 text-center text-muted-foreground">
                    No asset accounts with balance.
                  </td>
                </tr>
              )}
              {assetAccounts.map((acc, i) => (
                <tr
                  key={acc.id}
                  className={`border-t border-border/40 hover:bg-accent/30 transition-colors ${
                    i % 2 === 1 ? "bg-muted/20" : ""
                  }`}
                >
                  <td className="px-4 py-2 pl-8">{acc.name}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {balLabel(acc.balance)}
                  </td>
                </tr>
              ))}
              <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                <td className="px-4 py-2.5">Total Assets</td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {fmt(data.assets?.total)}
                </td>
              </tr>
            </tbody>

            {/* ── Liabilities ─────────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30 border-t border-border">
                <td
                  colSpan={2}
                  className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground"
                >
                  Liabilities
                </td>
              </tr>
              {liabilityAccounts.length === 0 && (
                <tr className="border-t border-border/40">
                  <td colSpan={2} className="px-4 py-6 text-center text-muted-foreground">
                    No liability accounts with balance.
                  </td>
                </tr>
              )}
              {liabilityAccounts.map((acc, i) => (
                <tr
                  key={acc.id}
                  className={`border-t border-border/40 hover:bg-accent/30 transition-colors ${
                    i % 2 === 1 ? "bg-muted/20" : ""
                  }`}
                >
                  <td className="px-4 py-2 pl-8">
                    {acc.id === "net_profit" ? (
                      <span className="italic">{acc.name}</span>
                    ) : (
                      acc.name
                    )}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {balLabel(acc.balance)}
                  </td>
                </tr>
              ))}
              <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                <td className="px-4 py-2.5">Total Liabilities</td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {fmt(data.liabilities?.total)}
                </td>
              </tr>
            </tbody>

            {/* ── Difference ──────────────────────────────── */}
            <tfoot>
              <tr className="border-t-2 border-border bg-muted/50">
                <td className="px-4 py-3 font-semibold text-base">
                  Difference (Assets − Liabilities)
                </td>
                <td className="px-4 py-3 text-right font-bold text-base tabular-nums">
                  {fmt(data.net_worth)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

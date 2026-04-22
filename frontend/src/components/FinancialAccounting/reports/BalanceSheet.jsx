import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { fetchCompanies } from "@/services/apiService";
import { Printer, ChevronRight, ChevronDown, X, Loader2 } from "lucide-react";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];

const fmt = (v) => {
  const n = Number(v);
  if (!n) return "—";
  return Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// Positive = debit balance, negative = credit balance (our Dr-Cr convention)
const balLabel = (v) => {
  const n = Number(v);
  if (n === 0) return "—";
  return `${fmt(n)} ${n >= 0 ? "Dr" : "Cr"}`;
};

/* ── Ledger drill-down modal ──────────────────────────────────────────────── */
function LedgerModal({ groupId, groupName, endDate, onClose }) {
  const [ledgers, setLedgers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");

  useEffect(() => {
    setLoading(true);
    apiClient
      .get(`/accounting/api/bs-group-ledgers/?group_id=${groupId}&end_date=${endDate}`)
      .then((res) => setLedgers(res.data.ledgers || []))
      .catch(() => setError("Failed to load ledgers."))
      .finally(() => setLoading(false));
  }, [groupId, endDate]);

  const total = ledgers?.reduce((s, l) => s + Number(l.balance || 0), 0) ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-xl shadow-2xl w-[92vw] max-w-xl max-h-[80vh] flex flex-col border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            <p className="font-semibold text-foreground text-sm">{groupName}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Ledger balances as on {new Date(endDate + "T00:00:00").toLocaleDateString("en-IN")}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-accent rounded-lg transition-colors">
            <X className="size-4 text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-auto flex-1">
          {loading && (
            <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground text-sm">
              <Loader2 className="size-4 animate-spin" /> Loading…
            </div>
          )}
          {error && <p className="text-center py-16 text-destructive text-sm">{error}</p>}
          {!loading && ledgers?.length === 0 && (
            <p className="text-center py-16 text-muted-foreground text-sm">No ledger balances for this group.</p>
          )}
          {!loading && ledgers && ledgers.length > 0 && (
            <table className="w-full text-sm border-collapse">
              <thead className="bg-muted/50 sticky top-0">
                <tr>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide border-b border-border">
                    Ledger
                  </th>
                  <th className="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide border-b border-border w-36">
                    Balance
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {ledgers.map((l, i) => (
                  <tr key={l.id} className={`hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                    <td className="px-4 py-2 text-foreground">{l.ac_name}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-sm">
                      {balLabel(l.balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/50">
                <tr>
                  <td className="px-4 py-2.5 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                    Total
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-bold text-foreground">
                    {balLabel(total)}
                  </td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Account group row ────────────────────────────────────────────────────── */
function AccountRow({ acc, endDate, onOpen, activeId }) {
  const isSpecial = acc.id === "net_profit" || acc.id === "closing_stock";
  const isActive  = activeId === acc.id;

  return (
    <tr
      onClick={() => !isSpecial && onOpen(acc.id, acc.name)}
      className={`border-t border-border/40 transition-colors
        ${isSpecial ? "opacity-80" : "cursor-pointer hover:bg-primary/5"}
        ${isActive ? "bg-primary/10" : ""}
      `}
    >
      <td className="px-4 py-2 pl-8 flex items-center gap-1.5 text-sm">
        {!isSpecial && (
          isActive
            ? <ChevronDown className="size-3.5 text-primary flex-shrink-0" />
            : <ChevronRight className="size-3.5 text-muted-foreground/50 flex-shrink-0" />
        )}
        {acc.id === "net_profit"
          ? <span className="italic text-muted-foreground">{acc.name}</span>
          : acc.name
        }
      </td>
      <td className="px-4 py-2 text-right tabular-nums text-sm">
        {balLabel(acc.balance)}
      </td>
    </tr>
  );
}

/* ── Main component ───────────────────────────────────────────────────────── */
export default function BalanceSheet() {
  const [endDate, setEndDate]   = useState(today);
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [combined, setCombined] = useState(false);
  const [modal, setModal]       = useState(null); // { id, name }
  const [activeId, setActiveId] = useState(null);
  const [companyName, setCompanyName] = useState("");

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const results = res.data?.results || res.data || [];
        if (results.length > 0) setCompanyName(results[0].company_name || "");
      }
    });
  }, []);

  const user = JSON.parse(sessionStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    setModal(null);
    setActiveId(null);
    try {
      const params = new URLSearchParams({ end_date: endDate });
      if (combined) params.set("combined", "true");
      const res = await apiClient.get(`/accounting/api/bal-sheet?${params}`);
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load Balance Sheet data.");
    }
    setLoading(false);
  };

  const openGroup = useCallback((id, name) => {
    if (activeId === id) {
      setModal(null);
      setActiveId(null);
    } else {
      setModal({ id, name });
      setActiveId(id);
    }
  }, [activeId]);

  const handlePrint = () => {
    if (!data) return;
    const assets      = (data.assets?.accounts || []).filter((a) => Number(a.balance || 0) !== 0);
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
      <thead><tr><th>Particulars</th><th style="text-align:right;width:150px">Amount (₹)</th></tr></thead>
      <tbody>
        ${renderSection("Assets", assets, data.assets?.total)}
        ${renderSection("Liabilities", liabilities, data.liabilities?.total)}
      </tbody>
      <tfoot><tr class="totals-row">
        <td>Difference (Assets − Liabilities)</td>
        <td style="text-align:right" class="tabular-nums font-bold">${fmt(data.net_worth)}</td>
      </tr></tfoot>
    </table>`;

    const [y, m, d] = (endDate || "").split("-");
    const ddmmyyyy  = y && m && d ? `${d}-${m}-${y}` : endDate;
    printReport({
      title: "Balance Sheet",
      subtitle: `As on ${ddmmyyyy}${combined ? " (Combined — All Retails)" : ""}`,
      html,
      company: companyName,
    });
  };

  const assetAccounts     = (data?.assets?.accounts     || []).filter((a) => Number(a.balance || 0) !== 0);
  const liabilityAccounts = (data?.liabilities?.accounts || []).filter((a) => Number(a.balance || 0) !== 0);

  const netWorth = Number(data?.net_worth ?? 0);

  return (
    <div className="flex flex-col gap-4">
      {/* ── Filters ──────────────────────────────────────────────────────── */}
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
              className="size-4 rounded border-gray-300"
            />
            <Label htmlFor="bs-combined" className="text-xs cursor-pointer">Combined (All Retails)</Label>
          </div>
        )}
        <Button size="sm" onClick={fetchReport} className="h-9">Show</Button>
        {data && (
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto">
            <Printer className="size-4 mr-1.5" /> Print
          </Button>
        )}
      </div>

      {data && !loading && (
        <p className="text-[11px] text-muted-foreground -mt-2 print:hidden">
          Click any account group to see its individual ledgers.
        </p>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
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

            {/* ── Assets ─────────────────────────────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30 border-t border-border">
                <td colSpan={2} className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Assets
                </td>
              </tr>
              {assetAccounts.length === 0 && (
                <tr className="border-t border-border/40">
                  <td colSpan={2} className="px-4 py-6 text-center text-muted-foreground">No asset accounts with balance.</td>
                </tr>
              )}
              {assetAccounts.map((acc) => (
                <AccountRow key={acc.id} acc={acc} endDate={endDate} onOpen={openGroup} activeId={activeId} />
              ))}
              <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                <td className="px-4 py-2.5">Total Assets</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{fmt(data.assets?.total)}</td>
              </tr>
            </tbody>

            {/* ── Liabilities ────────────────────────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30 border-t border-border">
                <td colSpan={2} className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Liabilities
                </td>
              </tr>
              {liabilityAccounts.length === 0 && (
                <tr className="border-t border-border/40">
                  <td colSpan={2} className="px-4 py-6 text-center text-muted-foreground">No liability accounts with balance.</td>
                </tr>
              )}
              {liabilityAccounts.map((acc) => (
                <AccountRow key={acc.id} acc={acc} endDate={endDate} onOpen={openGroup} activeId={activeId} />
              ))}
              <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                <td className="px-4 py-2.5">Total Liabilities</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{fmt(data.liabilities?.total)}</td>
              </tr>
            </tbody>

            {/* ── Difference ─────────────────────────────────────────────── */}
            <tfoot>
              <tr className={`border-t-2 border-border ${netWorth === 0 ? "bg-emerald-50" : "bg-amber-50"}`}>
                <td className="px-4 py-3 font-semibold text-base">
                  Difference (Assets − Liabilities)
                </td>
                <td className={`px-4 py-3 text-right font-bold text-base tabular-nums ${netWorth === 0 ? "text-emerald-700" : "text-amber-700"}`}>
                  {netWorth === 0 ? "Balanced ✓" : balLabel(netWorth)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* ── Ledger drill-down modal ─────────────────────────────────────── */}
      {modal && (
        <LedgerModal
          groupId={modal.id}
          groupName={modal.name}
          endDate={endDate}
          onClose={() => { setModal(null); setActiveId(null); }}
        />
      )}
    </div>
  );
}

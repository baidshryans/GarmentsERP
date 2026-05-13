import React, { useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableRow, TableCell, TableBody, TableHead } from "@/components/ui/table";
import { fetchOutstandingBills } from "@/services/apiService";
import { FileText, RefreshCw } from "lucide-react";

/**
 * BillAllocationTable
 *
 * Outstanding-bills picker for Payment/Receipt vouchers. Fetches bills with
 * `due_amt > 0` for the selected ledger and lets the user allocate the
 * payment/receipt amount across one or more bills.
 *
 * Props
 *  - ledgerId      (required) � the party ledger id (vendor for PMNT, customer for RCPT)
 *  - kind          'sales' (RCPT) | 'purchase' (PMNT)
 *  - partyAmount   total amount posted to the party leg of this voucher
 *  - allocations   [{bill_id, billno, amount}, ...]  (controlled value)
 *  - onChange      (nextAllocations) => void
 *
 * The parent is responsible for converting `allocations` into voucher_detail
 * rows with `ref_bill_no` when the form is submitted.
 */
export default function BillAllocationTable({
  ledgerId,
  kind,
  partyAmount,
  allocations = [],
  onChange,
}) {
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hintOpen, setHintOpen] = useState(false);

  // Fetch outstanding bills whenever the ledger changes
  const load = async () => {
    if (!ledgerId || !kind) {
      setBills([]);
      return;
    }
    setLoading(true);
    const res = await fetchOutstandingBills(ledgerId, kind);
    setBills(res.success ? res.data : []);
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ledgerId, kind]);

  // Convenience lookup: bill_id -> current allocation amount
  const allocMap = useMemo(() => {
    const m = {};
    for (const a of allocations) m[a.bill_id] = parseFloat(a.amount || 0);
    return m;
  }, [allocations]);

  const totalAllocated = useMemo(
    () => allocations.reduce((s, a) => s + parseFloat(a.amount || 0), 0),
    [allocations]
  );

  const unallocated = Math.max(0, parseFloat(partyAmount || 0) - totalAllocated);
  const overAllocated = totalAllocated - parseFloat(partyAmount || 0) > 0.01;

  const updateAllocation = (bill, newAmount) => {
    const amt = parseFloat(newAmount || 0);
    const next = allocations.filter((a) => a.bill_id !== bill.id);
    if (amt > 0) {
      next.push({ bill_id: bill.id, billno: bill.billno, amount: amt });
    }
    onChange?.(next);
  };

  const autoFillFIFO = () => {
    let remaining = parseFloat(partyAmount || 0);
    const next = [];
    for (const b of bills) {
      if (remaining <= 0) break;
      const alloc = Math.min(remaining, parseFloat(b.due_amt));
      if (alloc > 0) {
        next.push({ bill_id: b.id, billno: b.billno, amount: alloc });
        remaining -= alloc;
      }
    }
    onChange?.(next);
  };

  const clearAll = () => onChange?.([]);

  if (!ledgerId) {
    return (
      <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 p-4 text-xs text-gray-500">
        Select a party ledger to see outstanding {kind === "sales" ? "sales" : kind === "payable" ? "purchase and journal" : "purchase"} bills.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50/40 p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <FileText className="size-4 text-primary" />
        <span className="text-sm font-semibold text-primary">
          Outstanding {kind === "sales" ? "Sales" : kind === "payable" ? "Payables" : "Purchase"} Bills
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`size-3 mr-1 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={autoFillFIFO}>
            Auto-fill (FIFO)
          </Button>
          <button
            type="button"
            onClick={() => setHintOpen(v => !v)}
            className="text-[11px] text-violet-400 hover:text-violet-600 flex items-center gap-1 transition-colors"
            title="How to use bill allocation"
          >
            <span className={`transition-transform duration-150 ${hintOpen ? "rotate-90" : ""}`}>▶</span>
            How to use
          </button>
          <Button type="button" variant="outline" size="sm" onClick={clearAll}>
            Clear
          </Button>
        </div>
      </div>

      {hintOpen && (
        <div className="mb-3 rounded-md border border-violet-200 bg-white px-3 py-2.5 text-xs text-violet-700">
          <ol className="list-decimal list-inside space-y-0.5">
            <li>Select the {kind === "purchase" ? "vendor / supplier" : "customer"} account and enter the {kind === "purchase" ? "payment (Debit)" : "receipt (Credit)"} amount in the row above.</li>
            <li>Enter how much of that amount applies to each bill below, or use <strong>Auto-fill (FIFO)</strong> to fill oldest bills first.</li>
            <li>Press <kbd className="px-1 py-0.5 rounded bg-violet-100 font-mono">Tab</kbd> from the amount field to commit � one row per bill is added, with any remainder posted <em>on account</em>.</li>
          </ol>
        </div>
      )}

      {loading ? (
        <div className="text-xs text-gray-500 py-3">Loading�</div>
      ) : bills.length === 0 ? (
        <div className="text-xs text-gray-500 py-3">
          No outstanding bills for this ledger.
        </div>
      ) : (
        <Table className="w-full">
          <TableBody>
            <TableRow className="bg-violet-100/60">
              <TableCell className="px-3 py-1.5 text-[11px] font-semibold text-primary uppercase">Bill No</TableCell>
              <TableCell className="px-3 py-1.5 text-[11px] font-semibold text-primary uppercase">Date</TableCell>
              <TableCell className="px-3 py-1.5 text-[11px] font-semibold text-primary uppercase text-right">Total</TableCell>
              <TableCell className="px-3 py-1.5 text-[11px] font-semibold text-primary uppercase text-right">Outstanding</TableCell>
              <TableCell className="px-3 py-1.5 text-[11px] font-semibold text-primary uppercase text-right">Allocate</TableCell>
            </TableRow>
            {bills.map((b) => (
              <TableRow key={b.id} className="bg-white">
                <TableCell className="px-3 py-1.5 text-xs font-medium">
                  <div>{b.label || b.billno}</div>
                  {b.narration && <div className="text-[11px] text-gray-400 truncate max-w-[200px]">{b.narration}</div>}
                </TableCell>
                <TableCell className="px-3 py-1.5 text-xs text-gray-600">{b.date}</TableCell>
                <TableCell className="px-3 py-1.5 text-xs text-right">
                  ₹{parseFloat(b.total).toLocaleString("en-IN")}
                </TableCell>
                <TableCell className="px-3 py-1.5 text-xs text-right font-medium text-rose-600">
                  ₹{parseFloat(b.due_amt).toLocaleString("en-IN")}
                </TableCell>
                <TableCell className="px-3 py-1.5 text-right">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max={b.due_amt}
                    value={allocMap[b.id] ?? ""}
                    onChange={(e) => updateAllocation(b, e.target.value)}
                    className="h-8 text-right text-xs w-28 ml-auto"
                    placeholder="0"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Footer: live reconciliation */}
      <div className="mt-3 flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-gray-600">Party amount:</span>
          <span className="font-semibold">
            ₹{parseFloat(partyAmount || 0).toLocaleString("en-IN")}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-gray-600">Allocated:</span>
          <span className={`font-semibold ${overAllocated ? "text-rose-600" : "text-emerald-700"}`}>
            ₹{totalAllocated.toLocaleString("en-IN")}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-gray-600">Unallocated (on account):</span>
          <span className="font-semibold text-amber-700">
            ₹{unallocated.toLocaleString("en-IN")}
          </span>
        </div>
        {overAllocated && (
          <span className="ml-auto text-[11px] font-semibold text-rose-600">
            ⚠ Allocation exceeds the party amount � fix before saving
          </span>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { Search, Plus, Trash2, Link2, Unlink, CheckCircle2, Circle } from "lucide-react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  fetchBankStatements, createBankStatement, deleteBankStatement,
  matchBankStatement, fetchBankReconBookEntries, getLedgers,
} from "@/services/apiService";

const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const emptyEntry = {
  date: new Date().toISOString().split("T")[0],
  description: "",
  reference: "",
  debit: "",
  credit: "",
};

export default function BankReconciliation() {
  const { toast } = useToast();

  // Filter state
  const [banks, setBanks]           = useState([]);
  const [bankLedger, setBankLedger] = useState("");
  const [fromDate, setFromDate]     = useState("");
  const [toDate, setToDate]         = useState("");

  // Data
  const [stmtRows, setStmtRows]   = useState([]);   // bank statement lines
  const [bookRows, setBookRows]   = useState([]);   // book entries
  const [loading, setLoading]     = useState(false);

  // New entry form
  const [newEntry, setNewEntry]   = useState(emptyEntry);
  const [saving, setSaving]       = useState(false);

  // Selected for matching
  const [selStmt, setSelStmt]     = useState(null);  // bank_statement id
  const [selBook, setSelBook]     = useState(null);  // voucher_detail id

  // Fetch bank ledgers on mount
  useEffect(() => {
    getLedgers({ type: "BA" }).then((res) => {
      if (res.success) {
        const d = res.data?.results ?? (Array.isArray(res.data) ? res.data : []);
        setBanks(d);
      }
    });
  }, []);

  const load = async () => {
    if (!bankLedger) return;
    setLoading(true);
    const params = { bank_ledger: bankLedger, from_date: fromDate, to_date: toDate };
    const [s, b] = await Promise.all([
      fetchBankStatements(params),
      fetchBankReconBookEntries(params),
    ]);
    if (s.success) setStmtRows(Array.isArray(s.data) ? s.data : s.data?.results ?? []);
    if (b.success) setBookRows(Array.isArray(b.data) ? b.data : []);
    setLoading(false);
  };

  const handleAddEntry = async () => {
    if (!bankLedger || !newEntry.date || !newEntry.description) {
      toast({ title: "Fill date and description", variant: "destructive" });
      return;
    }
    setSaving(true);
    const payload = {
      bank_ledger: Number(bankLedger),
      date: newEntry.date,
      description: newEntry.description,
      reference: newEntry.reference,
      debit:  parseFloat(newEntry.debit  || 0),
      credit: parseFloat(newEntry.credit || 0),
    };
    const res = await createBankStatement(payload);
    if (res.success) {
      setStmtRows((prev) => [...prev, res.data]);
      setNewEntry(emptyEntry);
      toast({ title: "Statement entry added" });
    } else {
      toast({ title: "Failed to add entry", variant: "destructive" });
    }
    setSaving(false);
  };

  const handleDelete = async (id) => {
    const res = await deleteBankStatement(id);
    if (res.success) {
      setStmtRows((prev) => prev.filter((r) => r.id !== id));
    }
  };

  const handleMatch = async () => {
    if (!selStmt || !selBook) {
      toast({ title: "Select one bank statement row and one book entry to match", variant: "destructive" });
      return;
    }
    const res = await matchBankStatement(selStmt, selBook);
    if (res.success) {
      toast({ title: "Entries matched" });
      setSelStmt(null);
      setSelBook(null);
      load();
    } else {
      toast({ title: "Match failed", variant: "destructive" });
    }
  };

  const handleUnmatch = async (stmtId) => {
    const res = await matchBankStatement(stmtId, null);
    if (res.success) { toast({ title: "Match cleared" }); load(); }
  };

  // Summary
  const totalStmtDebit  = stmtRows.reduce((s, r) => s + parseFloat(r.debit  || 0), 0);
  const totalStmtCredit = stmtRows.reduce((s, r) => s + parseFloat(r.credit || 0), 0);
  const totalBookDebit  = bookRows.reduce((s, r) => s + parseFloat(r.debit  || 0), 0);
  const totalBookCredit = bookRows.reduce((s, r) => s + parseFloat(r.credit || 0), 0);
  const matchedCount    = stmtRows.filter((r) => r.is_matched).length;
  const unmatchedCount  = stmtRows.filter((r) => !r.is_matched).length;

  return (
    <div className="p-4 flex flex-col gap-5">
      {/* Info */}
      <div className="text-xs text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
        <strong>Bank Reconciliation</strong> — Compare your bank ledger (book entries) with the actual bank statement.
        Select a bank statement row and a book entry, then click <strong>Match</strong> to link them.
        Unmatched entries on either side indicate discrepancies.
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 p-4 rounded-lg border border-border bg-muted/30">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Bank Account</Label>
          <Select value={bankLedger} onValueChange={setBankLedger}>
            <SelectTrigger className="h-9 w-56 text-sm">
              <SelectValue placeholder="Select bank" />
            </SelectTrigger>
            <SelectContent>
              {banks.map((b) => (
                <SelectItem key={b.id} value={String(b.id)}>{b.ac_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input type="date" className="h-9 w-36 text-sm" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input type="date" className="h-9 w-36 text-sm" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </div>
        <Button size="sm" onClick={load} className="bg-violet-700 hover:bg-violet-800 text-white h-9">
          <Search className="size-4 mr-1" /> Load
        </Button>
      </div>

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {!loading && bankLedger && (
        <>
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg border border-border bg-muted/20 px-4 py-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">Statement Debit</div>
              <div className="text-base font-bold text-red-700">₹{fmt(totalStmtDebit)}</div>
            </div>
            <div className="rounded-lg border border-border bg-muted/20 px-4 py-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">Statement Credit</div>
              <div className="text-base font-bold text-green-700">₹{fmt(totalStmtCredit)}</div>
            </div>
            <div className="rounded-lg border border-border bg-muted/20 px-4 py-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">Matched</div>
              <div className="text-base font-bold text-violet-700">{matchedCount}</div>
            </div>
            <div className="rounded-lg border border-border bg-muted/20 px-4 py-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">Unmatched</div>
              <div className={`text-base font-bold ${unmatchedCount > 0 ? "text-amber-700" : "text-green-700"}`}>{unmatchedCount}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* ── Left: Bank Statement ── */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Bank Statement</h3>
                <span className="text-xs text-muted-foreground">{stmtRows.length} entries</span>
              </div>

              {/* Add entry form */}
              <div className="rounded-lg border border-dashed border-violet-200 bg-violet-50/30 p-3 flex flex-col gap-2">
                <p className="text-xs font-medium text-muted-foreground">Add Statement Entry</p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-[10px]">Date</Label>
                    <Input type="date" className="h-7 text-xs" value={newEntry.date}
                      onChange={(e) => setNewEntry((n) => ({ ...n, date: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-[10px]">Reference (Chq/UTR)</Label>
                    <Input className="h-7 text-xs" value={newEntry.reference}
                      onChange={(e) => setNewEntry((n) => ({ ...n, reference: e.target.value }))} />
                  </div>
                  <div className="col-span-2">
                    <Label className="text-[10px]">Description</Label>
                    <Input className="h-7 text-xs" value={newEntry.description}
                      onChange={(e) => setNewEntry((n) => ({ ...n, description: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-[10px]">Debit (withdrawal)</Label>
                    <Input type="number" className="h-7 text-xs" value={newEntry.debit}
                      onChange={(e) => setNewEntry((n) => ({ ...n, debit: e.target.value, credit: "" }))} />
                  </div>
                  <div>
                    <Label className="text-[10px]">Credit (deposit)</Label>
                    <Input type="number" className="h-7 text-xs" value={newEntry.credit}
                      onChange={(e) => setNewEntry((n) => ({ ...n, credit: e.target.value, debit: "" }))} />
                  </div>
                </div>
                <Button size="sm" className="self-end h-7 text-xs bg-violet-700 hover:bg-violet-800 text-white"
                  onClick={handleAddEntry} disabled={saving}>
                  <Plus className="size-3 mr-1" /> Add
                </Button>
              </div>

              {/* Statement rows */}
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
                      <th className="px-2 py-2 text-left w-6"></th>
                      <th className="px-2 py-2 text-left">Date</th>
                      <th className="px-2 py-2 text-left">Description</th>
                      <th className="px-2 py-2 text-right">Debit</th>
                      <th className="px-2 py-2 text-right">Credit</th>
                      <th className="px-2 py-2 text-center w-16">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stmtRows.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">No statement entries. Add entries above.</td></tr>
                    )}
                    {stmtRows.map((r) => (
                      <tr
                        key={r.id}
                        onClick={() => setSelStmt(selStmt === r.id ? null : r.id)}
                        className={`cursor-pointer border-b border-border/30 transition-colors ${
                          r.is_matched ? "bg-green-50" :
                          selStmt === r.id ? "bg-violet-50 border-l-2 border-violet-400" : "hover:bg-muted/30"
                        }`}
                      >
                        <td className="px-2 py-1.5">
                          {r.is_matched
                            ? <CheckCircle2 className="size-3.5 text-green-600" />
                            : <Circle className={`size-3.5 ${selStmt === r.id ? "text-violet-500" : "text-muted-foreground/30"}`} />}
                        </td>
                        <td className="px-2 py-1.5 whitespace-nowrap">{r.date}</td>
                        <td className="px-2 py-1.5 max-w-[140px] truncate" title={r.description}>
                          {r.description}
                          {r.reference && <span className="block text-[9px] text-muted-foreground font-mono">{r.reference}</span>}
                        </td>
                        <td className="px-2 py-1.5 text-right text-red-700">{r.debit > 0 ? fmt(r.debit) : ""}</td>
                        <td className="px-2 py-1.5 text-right text-green-700">{r.credit > 0 ? fmt(r.credit) : ""}</td>
                        <td className="px-2 py-1.5 text-center">
                          <div className="flex items-center justify-center gap-1" onClick={(e) => e.stopPropagation()}>
                            {r.is_matched && (
                              <button onClick={() => handleUnmatch(r.id)} title="Remove match" className="text-amber-500 hover:text-amber-700">
                                <Unlink className="size-3" />
                              </button>
                            )}
                            <button onClick={() => handleDelete(r.id)} className="text-red-400 hover:text-red-600">
                              <Trash2 className="size-3" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── Right: Book Entries ── */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Book Entries (Ledger)</h3>
                <span className="text-xs text-muted-foreground">{bookRows.length} entries · Dr ₹{fmt(totalBookDebit)} / Cr ₹{fmt(totalBookCredit)}</span>
              </div>

              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
                      <th className="px-2 py-2 text-left w-6"></th>
                      <th className="px-2 py-2 text-left">Date</th>
                      <th className="px-2 py-2 text-left">Voucher / Narration</th>
                      <th className="px-2 py-2 text-right">Debit</th>
                      <th className="px-2 py-2 text-right">Credit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bookRows.length === 0 && (
                      <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">No book entries for this period.</td></tr>
                    )}
                    {bookRows.map((r) => (
                      <tr
                        key={r.id}
                        onClick={() => setSelBook(selBook === r.id ? null : r.id)}
                        className={`cursor-pointer border-b border-border/30 transition-colors ${
                          r.is_matched ? "bg-green-50" :
                          selBook === r.id ? "bg-violet-50 border-l-2 border-violet-400" : "hover:bg-muted/30"
                        }`}
                      >
                        <td className="px-2 py-1.5">
                          {r.is_matched
                            ? <CheckCircle2 className="size-3.5 text-green-600" />
                            : <Circle className={`size-3.5 ${selBook === r.id ? "text-violet-500" : "text-muted-foreground/30"}`} />}
                        </td>
                        <td className="px-2 py-1.5 whitespace-nowrap">{r.date}</td>
                        <td className="px-2 py-1.5 max-w-[160px]">
                          <span className="font-mono text-[10px] text-violet-600 block">{r.voucher_no}</span>
                          <span className="truncate block" title={r.narration}>{r.narration}</span>
                          {r.chq_no && <span className="text-[9px] text-muted-foreground">Chq: {r.chq_no}</span>}
                        </td>
                        <td className="px-2 py-1.5 text-right text-red-700">{r.debit > 0 ? fmt(r.debit) : ""}</td>
                        <td className="px-2 py-1.5 text-right text-green-700">{r.credit > 0 ? fmt(r.credit) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Match button */}
          {(selStmt || selBook) && (
            <div className="flex items-center gap-3 p-3 rounded-lg border border-violet-200 bg-violet-50">
              <span className="text-xs text-violet-800">
                {selStmt ? "1 statement entry selected" : "No statement selected"} ·{" "}
                {selBook ? "1 book entry selected" : "No book entry selected"}
              </span>
              <Button
                size="sm"
                className="ml-auto bg-violet-700 hover:bg-violet-800 text-white h-7 text-xs"
                onClick={handleMatch}
                disabled={!selStmt || !selBook}
              >
                <Link2 className="size-3 mr-1" /> Match
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs"
                onClick={() => { setSelStmt(null); setSelBook(null); }}>
                Clear
              </Button>
            </div>
          )}
        </>
      )}

      {!loading && !bankLedger && (
        <div className="text-center text-sm text-muted-foreground py-12">
          Select a bank account and click Load to begin reconciliation.
        </div>
      )}
    </div>
  );
}

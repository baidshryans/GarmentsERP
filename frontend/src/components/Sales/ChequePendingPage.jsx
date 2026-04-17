import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { Landmark } from "lucide-react";
import { getPendingCheques, depositCheque, getLedgers } from "@/services/apiService";

export default function ChequePendingPage() {
  const { toast } = useToast();
  const [cheques, setCheques]         = useState([]);
  const [bankLedgers, setBankLedgers] = useState([]);
  const [loading, setLoading]         = useState(true);
  const [selected, setSelected]       = useState(null);  // BankDetail being deposited
  const [form, setForm]               = useState({ deposit_date: "", bank_ledger_id: "" });
  const [saving, setSaving]           = useState(false);

  async function load() {
    setLoading(true);
    const [cRes, bRes] = await Promise.all([getPendingCheques(), getLedgers({ type: "BA", page: 1 })]);
    if (cRes.success) setCheques(cRes.data);
    if (bRes.success) {
      const list = Array.isArray(bRes.data) ? bRes.data : (bRes.data?.results ?? []);
      setBankLedgers(list);
    }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function openDeposit(cheque) {
    setSelected(cheque);
    setForm({
      deposit_date:   new Date().toISOString().slice(0, 10),
      bank_ledger_id: cheque.deposit_bank_id ? String(cheque.deposit_bank_id) : "",
    });
  }

  async function handleDeposit() {
    if (!form.deposit_date || !form.bank_ledger_id) {
      toast({ title: "Error", description: "Deposit date and bank account are required.", variant: "destructive" });
      return;
    }
    setSaving(true);
    const r = await depositCheque(selected.id, {
      deposit_date:   form.deposit_date,
      bank_ledger_id: form.bank_ledger_id,
    });
    setSaving(false);
    if (r.success) {
      toast({ title: "Cheque deposited", description: `Contra voucher created for ₹${selected.amount.toLocaleString()}` });
      setSelected(null);
      load();
    } else {
      toast({ title: "Error", description: r.error?.detail || "Deposit failed.", variant: "destructive" });
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Landmark className="size-5 text-amber-600" />
        <h2 className="text-lg font-semibold">Pending Cheques</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Cheques received from customers that have not yet been deposited into a bank account.
        Click "Deposit" to record the deposit and create the Contra voucher.
      </p>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : cheques.length === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          No pending cheques.
        </div>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-violet-50">
                <TableHead>Bill No</TableHead>
                <TableHead>Sale Date</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead className="text-right">Amount (₹)</TableHead>
                <TableHead>Cheque No</TableHead>
                <TableHead>Cheque Date</TableHead>
                <TableHead>Drawee Bank</TableHead>
                <TableHead>Expected Deposit Bank</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cheques.map(c => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-xs">{c.bill_no}</TableCell>
                  <TableCell className="text-xs">{c.sale_date}</TableCell>
                  <TableCell className="text-xs">{c.customer}</TableCell>
                  <TableCell className="text-right font-medium">{c.amount?.toLocaleString()}</TableCell>
                  <TableCell className="font-mono text-xs">{c.chq_no}</TableCell>
                  <TableCell className="text-xs">{c.chq_date}</TableCell>
                  <TableCell className="text-xs">{c.bank_name}</TableCell>
                  <TableCell className="text-xs">{c.deposit_bank_name || <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell>
                    <Button size="sm" variant="outline" onClick={() => openDeposit(c)}>
                      Deposit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={open => !open && setSelected(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Deposit Cheque</DialogTitle>
          </DialogHeader>

          {selected && (
            <div className="space-y-4 py-2">
              <div className="rounded-md bg-muted px-3 py-2 text-sm space-y-1">
                <div><span className="text-muted-foreground">Customer:</span> {selected.customer}</div>
                <div><span className="text-muted-foreground">Cheque No:</span> {selected.chq_no}</div>
                <div><span className="text-muted-foreground">Amount:</span> ₹{selected.amount?.toLocaleString()}</div>
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Deposit Date</Label>
                <Input
                  type="date"
                  value={form.deposit_date}
                  onChange={e => setForm(f => ({ ...f, deposit_date: e.target.value }))}
                />
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Deposit Into Bank Account</Label>
                <select
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                  value={form.bank_ledger_id}
                  onChange={e => setForm(f => ({ ...f, bank_ledger_id: e.target.value }))}
                >
                  <option value="">— Select Bank Account —</option>
                  {bankLedgers.map(l => (
                    <option key={l.id} value={String(l.id)}>{l.ac_name}</option>
                  ))}
                </select>
              </div>

              <p className="text-xs text-muted-foreground">
                This will create a Contra voucher: Dr {bankLedgers.find(l => String(l.id) === form.bank_ledger_id)?.ac_name || "Bank A/c"} / Cr Cheques in Hand
              </p>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>Cancel</Button>
            <Button onClick={handleDeposit} disabled={saving}>
              {saving ? "Processing…" : "Confirm Deposit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

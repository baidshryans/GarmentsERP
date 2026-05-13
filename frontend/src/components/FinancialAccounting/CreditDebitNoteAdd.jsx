import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Save, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import {
  getLedgers,
  fetchOutstandingBills,
  fetchNextCNDNNumber,
  createCreditDebitNote,
} from "@/services/apiService";

const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function CreditDebitNoteAdd() {
  const navigate = useNavigate();
  const { toast } = useToast();

  // Form state
  const [noteType, setNoteType] = useState("CN");
  const [noteNo, setNoteNo] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [ldgr, setLdgr] = useState(null);
  const [ldgrSearch, setLdgrSearch] = useState("");
  const [ldgrOptions, setLdgrOptions] = useState([]);
  const [adjustmentLdgr, setAdjustmentLdgr] = useState(null);
  const [adjSearch, setAdjSearch] = useState("");
  const [adjOptions, setAdjOptions] = useState([]);
  const [refInvoice, setRefInvoice] = useState(null);
  const [outstandingBills, setOutstandingBills] = useState([]);
  const [reason, setReason] = useState("");
  const [taxableValue, setTaxableValue] = useState("");
  const [gstRate, setGstRate] = useState("");
  const [isInterState, setIsInterState] = useState(false);
  const [saving, setSaving] = useState(false);

  // Fetch next note number
  const loadNextNo = useCallback(async () => {
    const res = await fetchNextCNDNNumber(noteType);
    if (res.success) setNoteNo(res.data.next_no);
  }, [noteType]);

  useEffect(() => { loadNextNo(); }, [loadNextNo]);

  // Party ledger search
  useEffect(() => {
    if (ldgrSearch.length < 2) { setLdgrOptions([]); return; }
    const role = noteType === "CN" ? "CO,SD,DL" : "VD,SC";
    const timer = setTimeout(async () => {
      const res = await getLedgers({ search: ldgrSearch, type: role, page_size: 20 });
      if (res.success) setLdgrOptions(res.data.results || []);
    }, 300);
    return () => clearTimeout(timer);
  }, [ldgrSearch, noteType]);

  // Adjustment ledger search (any revenue/expense ledger)
  useEffect(() => {
    if (adjSearch.length < 2) { setAdjOptions([]); return; }
    const timer = setTimeout(async () => {
      const res = await getLedgers({ search: adjSearch, type: "", page_size: 20 });
      if (res.success) setAdjOptions(res.data.results || []);
    }, 300);
    return () => clearTimeout(timer);
  }, [adjSearch]);

  // Load outstanding bills when party is selected
  useEffect(() => {
    if (!ldgr) { setOutstandingBills([]); return; }
    const kind = noteType === "CN" ? "sales" : "purchase";
    fetchOutstandingBills(ldgr.id, kind).then((res) => {
      if (res.success) setOutstandingBills(res.data || []);
    });
  }, [ldgr, noteType]);

  // Reset party when note type changes
  useEffect(() => {
    setLdgr(null);
    setLdgrSearch("");
    setRefInvoice(null);
    setOutstandingBills([]);
  }, [noteType]);

  // Computed tax amounts
  const taxable = parseFloat(taxableValue) || 0;
  const rate = parseFloat(gstRate) || 0;
  const cgstAmt = isInterState ? 0 : +(taxable * rate / 200).toFixed(2);
  const sgstAmt = isInterState ? 0 : +(taxable * rate / 200).toFixed(2);
  const igstAmt = isInterState ? +(taxable * rate / 100).toFixed(2) : 0;
  const total = taxable + cgstAmt + sgstAmt + igstAmt;

  const handleSave = async () => {
    if (!ldgr) return toast({ title: "Error", description: "Select a party ledger", variant: "destructive" });
    if (!adjustmentLdgr) return toast({ title: "Error", description: "Select an adjustment ledger", variant: "destructive" });
    if (!taxable || taxable <= 0) return toast({ title: "Error", description: "Enter a valid taxable value", variant: "destructive" });
    if (!reason.trim()) return toast({ title: "Error", description: "Enter a reason", variant: "destructive" });

    setSaving(true);
    const payload = {
      note_type: noteType,
      date,
      ldgr: ldgr.id,
      adjustment_ldgr: adjustmentLdgr.id,
      reason,
      taxable_value: taxable,
      cgst_per: isInterState ? 0 : rate / 2,
      cgst_amt: cgstAmt,
      sgst_per: isInterState ? 0 : rate / 2,
      sgst_amt: sgstAmt,
      igst_per: isInterState ? rate : 0,
      igst_amt: igstAmt,
      amount: total,
    };
    if (refInvoice) {
      if (noteType === "CN") payload.ref_sales_vou = refInvoice.id;
      else payload.ref_purchase_vou = refInvoice.id;
    }

    const res = await createCreditDebitNote(payload);
    setSaving(false);
    if (res.success) {
      toast({ title: "Saved", description: `${noteType === "CN" ? "Credit" : "Debit"} Note created.` });
      navigate("/accounting/credit-debit-notes");
    } else {
      const errMsg = typeof res.error === "string" ? res.error
        : Array.isArray(res.error) ? res.error.join(", ")
        : JSON.stringify(res.error);
      toast({ title: "Error", description: errMsg, variant: "destructive" });
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Note Type Toggle */}
      <div className="flex items-center gap-4">
        <div className="flex rounded-md overflow-hidden border border-border">
          {[
            { k: "CN", lbl: "Credit Note" },
            { k: "DN", lbl: "Debit Note" },
          ].map((t) => (
            <button
              key={t.k}
              onClick={() => setNoteType(t.k)}
              className={`px-5 py-2 text-sm font-medium transition-colors ${
                noteType === t.k
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              {t.lbl}
            </button>
          ))}
        </div>
      </div>

      {/* Top row: Note No + Date */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Note No</Label>
          <Input value={noteNo} readOnly className="h-9 bg-muted/30 font-mono" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Date</Label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="h-9" />
        </div>
      </div>

      {/* Party Ledger */}
      <div className="flex flex-col gap-1 relative">
        <Label className="text-xs">
          {noteType === "CN" ? "Customer (Sundry Debtor)" : "Vendor (Sundry Creditor)"}
        </Label>
        {ldgr ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 px-3 py-1.5 bg-muted/30 rounded-md border text-sm font-medium">
              {ldgr.ac_name}
            </div>
            <Button size="sm" variant="ghost" onClick={() => { setLdgr(null); setLdgrSearch(""); }}>
              Change
            </Button>
          </div>
        ) : (
          <div className="relative">
            <Input
              placeholder={`Search ${noteType === "CN" ? "customer" : "vendor"}…`}
              value={ldgrSearch}
              onChange={(e) => setLdgrSearch(e.target.value)}
              className="h-9"
            />
            {ldgrOptions.length > 0 && (
              <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-background border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                {ldgrOptions.map((l) => (
                  <button
                    key={l.id}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                    onClick={() => { setLdgr(l); setLdgrSearch(""); setLdgrOptions([]); }}
                  >
                    {l.ac_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Against Invoice */}
      {ldgr && outstandingBills.length > 0 && (
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Against Invoice (optional)</Label>
          <div className="rounded-md border border-border overflow-hidden max-h-40 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 sticky top-0">
                <tr>
                  <th className="w-8 px-2 py-1"></th>
                  <th className="text-left px-2 py-1 font-semibold">Bill No</th>
                  <th className="text-left px-2 py-1 font-semibold">Date</th>
                  <th className="text-right px-2 py-1 font-semibold">Total</th>
                  <th className="text-right px-2 py-1 font-semibold">Due</th>
                </tr>
              </thead>
              <tbody>
                {outstandingBills.map((b) => (
                  <tr
                    key={b.id}
                    className={`border-t border-border/40 cursor-pointer hover:bg-muted/20 ${
                      refInvoice?.id === b.id ? "bg-primary/10" : ""
                    }`}
                    onClick={() => setRefInvoice(refInvoice?.id === b.id ? null : b)}
                  >
                    <td className="px-2 py-1 text-center">
                      <input
                        type="radio"
                        checked={refInvoice?.id === b.id}
                        readOnly
                        className="size-3"
                      />
                    </td>
                    <td className="px-2 py-1 font-mono">{b.billno}</td>
                    <td className="px-2 py-1 text-muted-foreground">{b.date}</td>
                    <td className="px-2 py-1 text-right">{fmt(b.total)}</td>
                    <td className="px-2 py-1 text-right font-medium">{fmt(b.due_amt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Adjustment Ledger */}
      <div className="flex flex-col gap-1 relative">
        <Label className="text-xs">Adjustment Ledger (debit/credit to)</Label>
        {adjustmentLdgr ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 px-3 py-1.5 bg-muted/30 rounded-md border text-sm font-medium">
              {adjustmentLdgr.ac_name}
            </div>
            <Button size="sm" variant="ghost" onClick={() => { setAdjustmentLdgr(null); setAdjSearch(""); }}>
              Change
            </Button>
          </div>
        ) : (
          <div className="relative">
            <Input
              placeholder="Search ledger (e.g. Discount Allowed, Sales Rebate)…"
              value={adjSearch}
              onChange={(e) => setAdjSearch(e.target.value)}
              className="h-9"
            />
            {adjOptions.length > 0 && (
              <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-background border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                {adjOptions.map((l) => (
                  <button
                    key={l.id}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                    onClick={() => { setAdjustmentLdgr(l); setAdjSearch(""); setAdjOptions([]); }}
                  >
                    {l.ac_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Reason */}
      <div className="flex flex-col gap-1">
        <Label className="text-xs">Reason</Label>
        <Textarea
          placeholder="Quality allowance, rate difference, overbilling correction…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="min-h-[60px]"
        />
      </div>

      {/* Amount section */}
      <div className="rounded-lg border border-border p-4 bg-muted/10">
        <div className="grid grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Taxable Value</Label>
            <Input
              type="number"
              value={taxableValue}
              onChange={(e) => setTaxableValue(e.target.value)}
              className="h-9"
              placeholder="0.00"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">GST Rate (%)</Label>
            <Input
              type="number"
              value={gstRate}
              onChange={(e) => setGstRate(e.target.value)}
              className="h-9"
              placeholder="e.g. 3"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Tax Type</Label>
            <div className="flex rounded-md overflow-hidden border border-border h-9">
              <button
                onClick={() => setIsInterState(false)}
                className={`flex-1 text-xs font-medium transition-colors ${
                  !isInterState ? "bg-primary text-primary-foreground" : "bg-background text-muted-foreground"
                }`}
              >
                CGST + SGST
              </button>
              <button
                onClick={() => setIsInterState(true)}
                className={`flex-1 text-xs font-medium transition-colors ${
                  isInterState ? "bg-primary text-primary-foreground" : "bg-background text-muted-foreground"
                }`}
              >
                IGST
              </button>
            </div>
          </div>
        </div>

        {/* Tax breakdown */}
        <div className="mt-4 space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Taxable Value</span>
            <span>{fmt(taxable)}</span>
          </div>
          {!isInterState && (
            <>
              <div className="flex justify-between">
                <span className="text-muted-foreground">CGST @ {(rate / 2).toFixed(2)}%</span>
                <span>{fmt(cgstAmt)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">SGST @ {(rate / 2).toFixed(2)}%</span>
                <span>{fmt(sgstAmt)}</span>
              </div>
            </>
          )}
          {isInterState && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">IGST @ {rate.toFixed(2)}%</span>
              <span>{fmt(igstAmt)}</span>
            </div>
          )}
          <div className="flex justify-between pt-2 border-t border-border font-bold text-base">
            <span>Total</span>
            <span className="text-primary">₹{fmt(total)}</span>
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end gap-3">
        <Button variant="outline" onClick={() => navigate("/accounting/credit-debit-notes")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={saving} className="gap-2">
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
          Save {noteType === "CN" ? "Credit Note" : "Debit Note"}
        </Button>
      </div>
    </div>
  );
}

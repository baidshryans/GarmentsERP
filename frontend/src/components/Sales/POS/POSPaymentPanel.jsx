import React, { useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";

// ── formatters ────────────────────────────────────────────────────────────────
const fmtINR = (v) =>
  `₹${(parseFloat(v) || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const PAYMENT_MODES = ["UPI", "CARD", "NEFT", "CHEQUE"];

const emptyBankRow = () => ({
  payment_mode: "UPI",
  amount: "",
  chq_no: "",
  bank_name: "",
  ledger: "",
  ledger_name: "",
  chq_date: "",
});

// ── small label/value row ─────────────────────────────────────────────────────
const SummaryRow = ({ label, value, className = "", valueClass = "" }) => (
  <div className={`flex justify-between items-center py-0.5 ${className}`}>
    <span className="text-[12px] text-muted-foreground">{label}</span>
    <span className={`text-[13px] font-medium text-foreground ${valueClass}`}>{value}</span>
  </div>
);

// ── input style ───────────────────────────────────────────────────────────────
const inputCls =
  "border border-input rounded-md px-2 py-1.5 text-[13px] font-[Assistant] bg-background text-foreground outline-none " +
  "focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors";

export default function POSPaymentPanel({
  customerObj,
  form,
  setForm,
  mrp,
  discount,
  taxableValue,
  cgst_amt,
  sgst_amt,
  igst_amt,
  billTotal,
  oldGoldAdj,
  advanceDeducted,
  cash,
  setCash,
  bankDetails,
  bankLedgers,
  collected,
  dueAmt,
  customerCashInfo,
  selectedPurchase,
  saving,
  onAddBank,
  onDeleteBank,
  onEditBank,
  onClear,
  onSave,
  onSaveAndPrint,
}) {
  const [newBank, setNewBank] = useState(emptyBankRow());

  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  const handleAddBank = () => {
    if (!newBank.amount || Number(newBank.amount) <= 0) return;
    onAddBank({ ...newBank });
    setNewBank(emptyBankRow());
  };

  // 269ST limit
  const cashReceived = parseFloat(customerCashInfo?.cash_received) || 0;
  const totalCashThisBill = parseFloat(cash) || 0;
  const totalCash = cashReceived + totalCashThisBill;

  const progressPct = billTotal > 0 ? Math.min(100, (collected / billTotal) * 100) : 0;

  return (
    <div className="flex flex-col h-full overflow-hidden text-[13px] font-[Assistant]">

      {/* ── Customer strip ── */}
      <div className="px-3 py-2.5 border-b border-border shrink-0">
        {customerObj ? (
          <>
            <div className="text-[15px] font-bold text-foreground">{customerObj.ledger_name}</div>
            <div className="text-[12px] text-muted-foreground mt-0.5 flex gap-3">
              {customerObj.phone && <span>{customerObj.phone}</span>}
              {customerObj.city && <span>{customerObj.city}</span>}
            </div>
          </>
        ) : (
          <div className="text-[13px] text-muted-foreground italic">No customer selected</div>
        )}
      </div>

      {/* ── Bill summary ── */}
      <div className="px-3 py-2.5 border-b border-border shrink-0">
        <SummaryRow label="MRP (Gross)" value={fmtINR(mrp)} />

        {/* Discount — editable */}
        <div className="flex justify-between items-center py-0.5">
          <span className="text-[12px] text-muted-foreground">Discount</span>
          <input
            type="number"
            min={0}
            value={form.discount || ""}
            onChange={e => set("discount", e.target.value)}
            placeholder="0"
            className={`${inputCls} w-[100px] text-right text-[13px] font-semibold text-emerald-600`}
          />
        </div>

        <div className="border-t border-muted my-1" />
        <SummaryRow label="Taxable Value" value={fmtINR(taxableValue)} />

        {cgst_amt > 0 && (
          <SummaryRow label={`CGST (${form.cgst_per}%)`} value={fmtINR(cgst_amt)} />
        )}
        {sgst_amt > 0 && (
          <SummaryRow label={`SGST (${form.sgst_per}%)`} value={fmtINR(sgst_amt)} />
        )}
        {igst_amt > 0 && (
          <SummaryRow label={`IGST (${form.igst_per}%)`} value={fmtINR(igst_amt)} />
        )}

        {/* Round off — editable */}
        <div className="flex justify-between items-center py-0.5">
          <span className="text-[12px] text-muted-foreground">Round Off</span>
          <input
            type="number"
            value={form.round_off || ""}
            onChange={e => set("round_off", e.target.value)}
            placeholder="0"
            className={`${inputCls} w-[80px] text-right`}
          />
        </div>

        <div className="border-t border-border mt-1 pt-1.5">
          <SummaryRow
            label="Bill Total"
            value={fmtINR(billTotal)}
            valueClass="!text-[15px] !font-bold"
            className="font-bold"
          />
        </div>

        {selectedPurchase && (
          <SummaryRow
            label="Old Gold Adjusted"
            value={`− ${fmtINR(oldGoldAdj)}`}
            valueClass="text-primary"
          />
        )}
        {advanceDeducted > 0 && (
          <SummaryRow
            label="Advance"
            value={`− ${fmtINR(advanceDeducted)}`}
            valueClass="text-primary"
          />
        )}
      </div>

      {/* ── Due / Collected hero ── */}
      <div className="px-3 py-3 bg-muted/40 border-b border-border shrink-0">
        <div className="flex justify-between items-end gap-3">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Amount Due</div>
            <div className="text-[28px] font-extrabold text-primary leading-none font-variant-numeric tabular-nums">
              {fmtINR(dueAmt)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Collected</div>
            <div className="text-[28px] font-extrabold text-emerald-600 leading-none font-variant-numeric tabular-nums">
              {fmtINR(collected)}
            </div>
          </div>
        </div>
        <div className="mt-2.5 text-[10px] text-muted-foreground">
          Bill {fmtINR(billTotal)} · Remaining {fmtINR(dueAmt)}
        </div>
        <div className="h-[3px] bg-border rounded-full mt-2 overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* ── Payment section ── */}
      <div className="flex-1 overflow-y-auto px-3 py-2.5 space-y-2">
        <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-2">
          Collect Payment
        </div>

        {/* Cash */}
        <div className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg bg-background focus-within:border-primary transition-colors">
          <span className="text-muted-foreground text-sm w-5 shrink-0">💵</span>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold text-foreground">Cash</div>
            {customerCashInfo && (
              <div className={`text-[10px] mt-0.5 ${totalCash > 200000 ? "text-destructive font-semibold" : "text-muted-foreground"}`}>
                269ST: {fmtINR(totalCash)} / ₹2,00,000
                {totalCash > 200000 && " ⚠️"}
              </div>
            )}
          </div>
          <input
            type="number"
            min={0}
            value={cash || ""}
            onChange={e => setCash(e.target.value)}
            placeholder="0"
            className={`${inputCls} w-[110px] text-right text-[14px] font-bold`}
          />
        </div>

        {/* Existing bank rows */}
        {bankDetails.map((row, idx) => (
          <div key={idx} className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg bg-background">
            <span className="text-[11px] font-semibold text-muted-foreground w-12 shrink-0">{row.payment_mode}</span>
            <span className="flex-1 text-[12px] text-muted-foreground truncate">{row.chq_no || row.bank_name || "—"}</span>
            <span className="text-[13px] font-bold text-foreground">{fmtINR(row.amount)}</span>
            <button
              onClick={() => onDeleteBank(idx)}
              className="text-border hover:text-destructive hover:bg-red-50 rounded p-0.5 transition-colors shrink-0"
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        ))}

        {/* Add bank row */}
        <div className="border border-border rounded-lg px-3 py-2 bg-background space-y-1.5">
          <div className="flex gap-2">
            <select
              className={`${inputCls} w-[80px] shrink-0`}
              value={newBank.payment_mode}
              onChange={e => setNewBank(prev => ({ ...prev, payment_mode: e.target.value }))}
            >
              {PAYMENT_MODES.map(m => <option key={m}>{m}</option>)}
            </select>
            <input
              className={`${inputCls} flex-1 min-w-0`}
              placeholder={newBank.payment_mode === "CHEQUE" ? "Cheque No…" : "UTR / Ref No…"}
              value={newBank.chq_no}
              onChange={e => setNewBank(prev => ({ ...prev, chq_no: e.target.value }))}
            />
            <input
              type="number"
              min={0}
              className={`${inputCls} w-[90px] text-right font-semibold`}
              placeholder="Amount"
              value={newBank.amount}
              onChange={e => setNewBank(prev => ({ ...prev, amount: e.target.value }))}
              onKeyDown={e => e.key === "Enter" && handleAddBank()}
            />
            <button
              onClick={handleAddBank}
              disabled={!newBank.amount || Number(newBank.amount) <= 0}
              className="shrink-0 px-2 py-1 rounded-md bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 transition-colors"
            >
              <Plus className="size-4" />
            </button>
          </div>
          {newBank.payment_mode === "CHEQUE" && (
            <div className="flex gap-2">
              <input
                type="date"
                className={`${inputCls} flex-1`}
                value={newBank.chq_date}
                onChange={e => setNewBank(prev => ({ ...prev, chq_date: e.target.value }))}
              />
              <input
                className={`${inputCls} flex-1`}
                placeholder="Drawee bank…"
                value={newBank.bank_name}
                onChange={e => setNewBank(prev => ({ ...prev, bank_name: e.target.value }))}
              />
            </div>
          )}
        </div>

        <div className="border-t border-dashed border-border my-1" />

        {/* Old Gold Adjusted */}
        <div className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg bg-background focus-within:border-primary transition-colors">
          <span className="text-muted-foreground text-sm w-5 shrink-0">◈</span>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold text-foreground">Old Gold Adjusted</div>
            {selectedPurchase ? (
              <div className="text-[10px] text-muted-foreground mt-0.5">
                {selectedPurchase.billno} · Available {fmtINR(selectedPurchase.available_balance)}
              </div>
            ) : (
              <div className="text-[10px] text-muted-foreground mt-0.5 italic">Link old gold in bill header</div>
            )}
          </div>
          <input
            type="number"
            min={0}
            max={parseFloat(selectedPurchase?.available_balance) || undefined}
            value={form.old_gold_adjusted || ""}
            onChange={e => setForm(prev => ({ ...prev, old_gold_adjusted: e.target.value }))}
            placeholder="0"
            disabled={!selectedPurchase}
            className={`${inputCls} w-[110px] text-right text-[14px] font-bold disabled:opacity-40`}
          />
        </div>

        {/* Credit to account */}
        <div className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg bg-background focus-within:border-primary transition-colors">
          <span className="text-muted-foreground text-sm w-5 shrink-0">◻</span>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold text-foreground">Credit to Account</div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Books outstanding balance to ledger</div>
          </div>
          <div className={`w-[110px] text-right text-[14px] font-bold text-primary px-2 py-1.5`}>
            {fmtINR(dueAmt)}
          </div>
        </div>

      </div>

      {/* ── Action bar ── */}
      <div className="px-3 py-2.5 border-t border-border bg-background flex gap-2 shrink-0">
        <button
          onClick={onClear}
          className="flex-1 py-2.5 rounded-lg text-[14px] font-medium text-muted-foreground border border-border bg-background hover:bg-muted transition-colors"
        >
          Clear
        </button>
        <button
          onClick={onSaveAndPrint}
          disabled={saving}
          className="flex-1 py-2.5 rounded-lg text-[14px] font-semibold text-foreground bg-muted border border-border hover:bg-muted/80 transition-colors disabled:opacity-50"
        >
          Save &amp; Print
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className="flex-1 py-2.5 rounded-lg text-[14px] font-bold text-white bg-primary hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
        >
          {saving && <Loader2 className="size-4 animate-spin" />}
          Save Bill
        </button>
      </div>

    </div>
  );
}

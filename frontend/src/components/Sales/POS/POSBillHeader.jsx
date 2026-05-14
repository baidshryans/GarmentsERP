import React from "react";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";

// ── small label + field wrapper ───────────────────────────────────────────────
const Field = ({ label, children, className = "" }) => (
  <div className={`flex flex-col gap-1 ${className}`}>
    <label className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{label}</label>
    {children}
  </div>
);

const inputCls =
  "border border-input rounded-md px-2 py-1.5 text-[13px] font-[Assistant] text-foreground bg-background outline-none " +
  "focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors";

const selectCls =
  "border border-input rounded-md px-2 py-1.5 text-[13px] font-[Assistant] text-foreground bg-background outline-none " +
  "focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors";

export default function POSBillHeader({
  form,
  setForm,
  statesData,
  customers,
  hsns,
  customerCashInfo,
  b2bPricelist,
  customerPurchases,
  selectedPurchase,
  onCustomerChange,
  onSelectPurchase,
  ldgrName,
  setLdgrName,
}) {
  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  // 269ST cash limit badge
  const cashReceived = parseFloat(customerCashInfo?.cash_received) || 0;
  const cashLimit    = 200000;
  const cashPct      = Math.min(100, (cashReceived / cashLimit) * 100);
  const cashOver     = cashReceived >= cashLimit;

  return (
    <div className="border-b border-border px-3 py-2.5 bg-background shrink-0">
      <div className="flex flex-wrap gap-x-3 gap-y-2 items-end">

        {/* Bill No */}
        <Field label="Bill No" className="min-w-[120px]">
          <input
            className={`${inputCls} bg-muted text-muted-foreground w-[160px]`}
            value={form.billno}
            readOnly
          />
        </Field>

        {/* Date */}
        <Field label="Date" className="min-w-[120px]">
          <input
            type="date"
            className={`${inputCls} w-[128px]`}
            value={form.date1}
            onChange={e => set("date1", e.target.value)}
          />
        </Field>

        {/* Customer */}
        <Field label="Customer" className="min-w-[220px] flex-1">
          <SearchableComboBox
            options={customers}
            labelKey="ac_name"
            searchKeys={["mobile1", "phone1"]}
            value={ldgrName || ""}
            onSelect={opt => {
              setLdgrName(opt.ac_name || "");
              onCustomerChange(opt.id);
            }}
            placeholder="Search customer…"
            className={`${inputCls} w-full`}
          />
          {/* Customer badges */}
          {form.ldgr && (
            <div className="flex flex-wrap gap-1 mt-1">
              {b2bPricelist && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                  B2B Pricelist
                </span>
              )}
              {customerCashInfo && (
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                    cashOver
                      ? "bg-red-50 text-red-700 border-red-200"
                      : "bg-muted text-muted-foreground border-border"
                  }`}
                >
                  Cash ₹{cashReceived.toLocaleString("en-IN")} / ₹2,00,000
                  {cashOver && " ⚠️"}
                </span>
              )}
            </div>
          )}
        </Field>

        {/* Place of Supply */}
        <Field label="Place of Supply" className="min-w-[140px]">
          <select
            className={`${selectCls} w-[148px]`}
            value={form.place_of_supply}
            onChange={e => set("place_of_supply", e.target.value)}
          >
            <option value="">Select state…</option>
            {statesData.map(s => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>

        {/* HSN — dropdown from master */}
        <Field label="HSN Code" className="min-w-[180px]">
          <select
            className={`${selectCls} w-[188px]`}
            value={form.hsn}
            onChange={e => set("hsn", e.target.value)}
          >
            <option value="">Select HSN…</option>
            {hsns.map(h => (
              <option key={h.id} value={h.hsn_no}>
                {h.hsn_no} — {h.description}
              </option>
            ))}
          </select>
        </Field>

        {/* Old Gold Link */}
        <Field label="Old Gold Link" className="min-w-[160px]">
          <select
            className={`${selectCls} w-[168px] text-[12px]`}
            value={form.old_gold_purchase || ""}
            onChange={e => {
              const id = e.target.value;
              const pv = customerPurchases.find(p => String(p.id) === id) || null;
              onSelectPurchase(pv);
            }}
          >
            <option value="">— None —</option>
            {customerPurchases.map(p => (
              <option key={p.id} value={String(p.id)}>
                {p.billno} — ₹{parseFloat(p.available_balance || 0).toLocaleString("en-IN")}
              </option>
            ))}
          </select>
        </Field>

      </div>
    </div>
  );
}

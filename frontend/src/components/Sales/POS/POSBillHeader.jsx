import React from "react";
import { formatNumber } from "@/lib/format";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";

const inputCls =
  "border border-input rounded-md px-2.5 py-2 text-[13px] font-[Assistant] text-foreground bg-background outline-none " +
  "focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors w-full";

const selectCls =
  "border border-input rounded-md px-2.5 py-2 text-[13px] font-[Assistant] text-foreground bg-background outline-none " +
  "focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors w-full";

const Label = ({ children }) => (
  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1">{children}</div>
);

export default function POSBillHeader({
  form,
  setForm,
  statesData,
  customers,
  hsns,
  customerCashInfo,
  b2bPricelist,
  onCustomerChange,
  ldgrName,
  setLdgrName,
}) {
  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();

  const cashReceived = parseFloat(customerCashInfo?.cash_received) || 0;
  const cashOver     = cashReceived >= 200000;

  return (
    <div className="border-b border-border px-4 py-3 bg-background shrink-0">
      <div className="flex items-end gap-3">

        {/* Bill No */}
        <div className="shrink-0" style={{ width: 148 }}>
          <div className="text-[10px] font-bold uppercase tracking-wider text-primary mb-1">Bill No</div>
          <input
            className={`${inputCls} bg-primary/10 border-primary/40 text-primary font-semibold tracking-wide`}
            value={form.billno}
            readOnly
          />
        </div>

        {/* Date */}
        <div className="shrink-0" style={{ width: 136 }}>
          <Label>Date</Label>
          <input
            type="date"
            className={inputCls}
            min={fyMin}
            max={fyMax}
            value={form.date1}
            onChange={e => set("date1", e.target.value)}
          />
        </div>

        {/* Customer — grows to fill available space */}
        <div className="flex-1 min-w-0">
          <Label>Customer</Label>
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
            className={inputCls}
          />
          {/* Badges */}
          {form.ldgr && (
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {b2bPricelist && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                  B2B Pricelist
                </span>
              )}
              {customerCashInfo && (
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  cashOver ? "bg-red-50 text-red-700 border-red-200" : "bg-muted text-muted-foreground border-border"
                }`}>
                  Cash ₹{formatNumber(cashReceived)} / ₹2,00,000{cashOver && " ⚠️"}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Place of Supply */}
        <div className="shrink-0" style={{ width: 164 }}>
          <Label>Place of Supply</Label>
          <select
            className={selectCls}
            value={form.place_of_supply}
            onChange={e => set("place_of_supply", e.target.value)}
          >
            <option value="">Select state…</option>
            {statesData.map(s => (
              <option key={s.code} value={s.code}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* HSN Code */}
        <div className="shrink-0" style={{ width: 200 }}>
          <Label>HSN Code</Label>
          <select
            className={selectCls}
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
        </div>

      </div>
    </div>
  );
}

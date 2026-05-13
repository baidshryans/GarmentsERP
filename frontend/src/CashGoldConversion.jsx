import React, { useEffect, useState } from 'react';
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createGC, getcgbillno, getgcbillno, getLedgers } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";
import { ArrowDownUp, Coins, Banknote } from "lucide-react";

// ── Shared section header (matches SalesVoucherAdd style) ───────────────────
const SectionHeader = ({ icon: Icon, title, subtitle }) => (
  <div className="flex items-center gap-3 mb-6">
    <span className="flex items-center justify-center size-8 rounded-full bg-primary text-white shrink-0">
      <Icon size={16} />
    </span>
    <div>
      <p className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
    </div>
    <div className="flex-1 h-px bg-violet-100" />
  </div>
);

// ── Labelled field wrapper ───────────────────────────────────────────────────
const Field = ({ label, children, unit }) => (
  <div className="flex flex-col gap-1.5">
    <Label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
      {label}
    </Label>
    <div className="flex items-center gap-2">
      {children}
      {unit && <span className="text-xs text-gray-400 whitespace-nowrap">{unit}</span>}
    </div>
  </div>
);

// ── Read-only computed value display ────────────────────────────────────────
const ComputedValue = ({ value, prefix = "" }) => (
  <div className="flex items-center px-3 py-2 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-[120px]">
    {prefix}{value || "�"}
  </div>
);

const CashGoldConversion = () => {
  const { toast } = useToast();
  const [customers, setCustomers] = useState([]);

  // ── Cash → Gold form ────────────────────────────────────────────────────
  const {
    register: regCG,
    handleSubmit: handleCG,
    reset: resetCG,
    watch: watchCG,
    setValue: setValCG,
  } = useForm({
    defaultValues: { date: new Date().toISOString().split("T")[0], fineWt: "", rate: "", cash: "", billno: "", ldgr: "" },
  });

  // ── Gold → Cash form ────────────────────────────────────────────────────
  const {
    register: regGC,
    handleSubmit: handleGC,
    reset: resetGC,
    watch: watchGC,
    setValue: setValGC,
  } = useForm({
    defaultValues: { date: new Date().toISOString().split("T")[0], cash: "", rate: "", fineWt: "", billno: "", ldgr: "" },
  });

  // ── Load initial data ───────────────────────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      const [cust, gc, cg] = await Promise.all([getLedgers(), getgcbillno(), getcgbillno()]);
      if (cust.success) setCustomers(cust.data.results);
      if (gc.success)   setValGC("billno", gc.data.billno);
      if (cg.success)   setValCG("billno", cg.data.billno);
    }
    fetchData();
  }, []);

  // ── Auto-calculations ───────────────────────────────────────────────────
  const cgRate   = watchCG("rate");
  const cgFineWt = watchCG("fineWt");
  useEffect(() => {
    const cash = ((parseFloat(cgRate) || 0) * (parseFloat(cgFineWt) || 0)).toFixed(2);
    setValCG("cash", cash > 0 ? cash : "");
  }, [cgRate, cgFineWt]);

  const gcRate = watchGC("rate");
  const gcCash = watchGC("cash");
  useEffect(() => {
    const rate = parseFloat(gcRate) || 0;
    const cash = parseFloat(gcCash) || 0;
    const fineWt = rate > 0 ? (cash / rate).toFixed(3) : "";
    setValGC("fineWt", fineWt);
  }, [gcRate, gcCash]);

  // ── Party selector helper ───────────────────────────────────────────────
  const PartySelect = ({ listId, onChange }) => (
    <div className="flex flex-col gap-1.5 flex-1">
      <Label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Party Name</Label>
      <Input
        list={listId}
        onChange={onChange}
        placeholder="Select or type party�"
        className="bg-white"
        required
      />
      <datalist id={listId}>
        {customers.map((c, i) => <option key={i} value={c.ac_name} />)}
      </datalist>
    </div>
  );

  // ── Submit handlers ─────────────────────────────────────────────────────
  const onCGSubmit = (data) => {
    createGC({ ...data, gw: parseFloat(data.fineWt).toFixed(3), amount: data.cash, conv_type: "CG" })
      .then((res) => {
        if (res.success) { toast({ title: "Cash → Gold conversion saved." }); resetCG(); }
        else toast({ title: "Conversion failed.", description: res.message, variant: "destructive" });
      })
      .catch((err) => toast({ title: "Error", description: err.message, variant: "destructive" }));
  };

  const onGCSubmit = (data) => {
    createGC({ ...data, gw: parseFloat(data.fineWt).toFixed(3), amount: data.cash, conv_type: "GC" })
      .then((res) => {
        if (res.success) { toast({ title: "Gold → Cash conversion saved." }); resetGC(); }
        else toast({ title: "Conversion failed.", description: res.message, variant: "destructive" });
      })
      .catch((err) => toast({ title: "Error", description: err.message, variant: "destructive" }));
  };

  return (
    <div className="mt-5 space-y-6">

      {/* ══ CASH → GOLD ════════════════════════════════════════════════════ */}
      <div className="p-6 shadow-sm rounded-xl bg-white border border-gray-100">
        <SectionHeader icon={Coins} title="Cash to Gold Conversion" subtitle="Credit cash, issue gold" />

        <form onSubmit={handleCG(onCGSubmit)}>
          {/* Row 1 � meta */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
            <Field label="Bill No">
              <Input
                {...regCG("billno")}
                readOnly
                className="bg-violet-50 border-violet-200 text-primary font-semibold cursor-default"
              />
            </Field>
            <Field label="Date">
              <Input type="date" {...regCG("date", { required: true })} className="bg-white" />
            </Field>
            <div className="sm:col-span-2">
              <PartySelect
                listId="cg_party_list"
                onChange={(e) => {
                  const c = customers.find(x => x.ac_name === e.target.value);
                  if (c) setValCG("ldgr", c.id);
                }}
              />
              <input type="hidden" {...regCG("ldgr")} />
            </div>
          </div>

          {/* Row 2 � transaction fields */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 items-end">
            <Field label="Fine Weight" unit="gm">
              <Input
                type="number" step="0.001"
                {...regCG("fineWt", { required: true })}
                placeholder="0.000"
                className="bg-white"
              />
            </Field>
            <Field label="Rate (₹/gm)">
              <Input
                type="number" step="0.01"
                {...regCG("rate", { required: true })}
                placeholder="0.00"
                className="bg-white"
              />
            </Field>
            <Field label="Cash Amount (₹)">
              <ComputedValue value={watchCG("cash")} prefix="₹ " />
              <input type="hidden" {...regCG("cash")} />
            </Field>
            <div className="flex items-end">
              <Button type="submit" className="w-full bg-primary hover:bg-primary text-white font-semibold tracking-wide">
                <Coins size={15} className="mr-2" /> Save Conversion
              </Button>
            </div>
          </div>
        </form>
      </div>

      {/* ══ DIVIDER ════════════════════════════════════════════════════════ */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-100" />
        <span className="flex items-center justify-center size-8 rounded-full bg-gray-100 text-gray-400">
          <ArrowDownUp size={16} />
        </span>
        <div className="flex-1 h-px bg-gray-100" />
      </div>

      {/* ══ GOLD → CASH ════════════════════════════════════════════════════ */}
      <div className="p-6 shadow-sm rounded-xl bg-white border border-gray-100">
        <SectionHeader icon={Banknote} title="Gold to Cash Conversion" subtitle="Receive gold, debit cash" />

        <form onSubmit={handleGC(onGCSubmit)}>
          {/* Row 1 � meta */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
            <Field label="Bill No">
              <Input
                {...regGC("billno")}
                readOnly
                className="bg-violet-50 border-violet-200 text-primary font-semibold cursor-default"
              />
            </Field>
            <Field label="Date">
              <Input type="date" {...regGC("date", { required: true })} className="bg-white" />
            </Field>
            <div className="sm:col-span-2">
              <PartySelect
                listId="gc_party_list"
                onChange={(e) => {
                  const c = customers.find(x => x.ac_name === e.target.value);
                  if (c) setValGC("ldgr", c.id);
                }}
              />
              <input type="hidden" {...regGC("ldgr")} />
            </div>
          </div>

          {/* Row 2 � transaction fields */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 items-end">
            <Field label="Cash Amount (₹)">
              <Input
                type="number" step="0.01"
                {...regGC("cash", { required: true })}
                placeholder="0.00"
                className="bg-white"
              />
            </Field>
            <Field label="Rate (₹/gm)">
              <Input
                type="number" step="0.01"
                {...regGC("rate", { required: true })}
                placeholder="0.00"
                className="bg-white"
              />
            </Field>
            <Field label="Fine Weight" unit="gm">
              <ComputedValue value={watchGC("fineWt")} />
              <input type="hidden" {...regGC("fineWt")} />
            </Field>
            <div className="flex items-end">
              <Button type="submit" className="w-full bg-primary hover:bg-primary text-white font-semibold tracking-wide">
                <Banknote size={15} className="mr-2" /> Save Conversion
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CashGoldConversion;

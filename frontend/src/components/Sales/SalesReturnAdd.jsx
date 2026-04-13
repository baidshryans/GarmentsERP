import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useEnterAsTab } from "@/hooks/useEnterAsTab";
import { Trash2 } from "lucide-react";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableRow,
  TableCell,
  TableBody,
} from "@/components/ui/table";

import {
  createSalesReturn,
  fetchSalesReturnById,
  updateSalesReturn,
  fetchSaleReturnInitialData,
  fetchDetailsforSaleReturn,
  fetchSystemSettings,
} from "@/services/apiService";

import { useParams, useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../Utils";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";

// ─── Helpers ────────────────────────────────────────────────────────────────
const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 my-5">
    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">
      {number}
    </span>
    <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</span>
    <div className="flex-1 h-px bg-violet-100" />
  </div>
);

const TH = ({ children, className = "" }) => (
  <TableCell
    className={`px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap ${className}`}
  >
    {children}
  </TableCell>
);

const Field = ({ label, children }) => (
  <div className="flex flex-col gap-1.5">
    <Label className="text-xs font-medium text-gray-600">{label}</Label>
    {children}
  </div>
);

const emptyMainItem = {
  item: "", pcs: 0, gw: 0,
  making: 0, making_type: "", discount: 0, value: 0, remarks: "",
};

const emptyDetail = {
  sl_no: 1, packet: "", item: "", pcs: 0, ct: 0, gw: 0,
  metal_purity: "", tunch: 0, rate: 0, amount: 0,
};

// ─── Component ───────────────────────────────────────────────────────────────
const SalesReturnAdd = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();

  const { register, handleSubmit, control, reset, watch, setValue, getValues } =
    useForm({
      defaultValues: {
        form: {
          date1: new Date().toISOString().split("T")[0],
          billno: "",
          ref_bill_no: "",
          ldgr: "",
          ldgr_name: "",
          remarks: "",
          mrp: 0,
          discount: 0,
          cgst_per: 0,
          sgst_per: 0,
          igst_per: 0,
          tcs_per: 0,
          taxable_value: 0,
          cgst_amt: 0,
          sgst_amt: 0,
          igst_amt: 0,
          tcs_amt: 0,
          total_incl_gst: 0,   // taxable + CGST + SGST + IGST (pre-TCS)
          total_bill_value: 0, // grand total = total_incl_gst + TCS
        },
        mainItem: { ...emptyMainItem },
        details:  { ...emptyDetail  },
      },
    });

  // ── State ──────────────────────────────────────────────────────────────────
  const [rs, setRows]                             = useState([]);
  const [fetchedBillItems, setFetchedBillItems]   = useState([]);
  const [selectedIndices, setSelectedIndices]     = useState(new Set());
  const [calculate, setCalculate]                 = useState(0);
  const [autoCalcEnabled, setAutoCalcEnabled]     = useState(false);
  const [customers, setCustomers]                 = useState([]);
  const [mainItemData, setMainItemData]           = useState([]);
  const [purityData, setPurityData]               = useState([]);
  const [packets, setPackets]                     = useState([]);
  const [mainItemDisplay, setMainItemDisplay]     = useState("");
  const [detailItemDisplay, setDetailItemDisplay] = useState("");
  const [detailItem, setDetailItem]               = useState(null); // resolved item object for sub-item

  const packetInputRef   = useRef(null);
  const mainItemInputRef = useRef(null);
  const formRef = useRef(null);
  useEnterAsTab(formRef);

  const w_discount    = watch("form.discount");
  const detailPacket  = watch("details.packet");
  const detailPcs     = watch("details.pcs");
  const detailCt      = watch("details.ct");
  const detailGw      = watch("details.gw");
  const detailRate    = watch("details.rate");

  // ── Derived flags ─────────────────────────────────────────────────────────
  // "R" (raw/gold) items are the only valid sub-item type when entered manually
  const rawItems = mainItemData.filter((m) => m.item_type === "R");

  const isRawItem          = detailItem?.item_type === "R";
  const itemLockedByPacket = !!detailPacket;            // packet chosen → item locked
  const packetLockedByItem = !itemLockedByPacket && !!detailItem; // item typed → packet locked
  const showMetalPurity    = isRawItem && !itemLockedByPacket;    // only for raw items without packet

  // ── Initial data load ──────────────────────────────────────────────────────
  useEffect(() => {
    async function loadAll() {
      try {
        const [res, sysSettings] = await Promise.all([
          fetchSaleReturnInitialData(),
          fetchSystemSettings(),
        ]);
        if (res.success) {
          setCustomers(res.data.ledgers || []);
          setValue("form.billno", res.data.billno);
          if (res.data.items)   setMainItemData(res.data.items);
          if (res.data.purity)  setPurityData(res.data.purity);
          if (res.data.packets) setPackets(res.data.packets);
        } else {
          toast({ title: "Error", description: res.error?.error || "Failed to load form data.", variant: "destructive" });
        }
        if (sysSettings.success) setAutoCalcEnabled(!!sysSettings.data.bill_total_auto_calc);
      } catch (err) {
        console.error("Exception fetching initial data:", err);
      }

      if (id) {
        const data = await fetchSalesReturnById(id);
        if (data.success) {
          const d = data.data;
          reset({
            form: { ...d, ldgr_name: d.ldgr_name || "", ref_bill_no: "" },
            mainItem: { ...emptyMainItem },
            details:  { ...emptyDetail  },
          });
          setRows(JSON.parse(JSON.stringify(d.salereturnitem_set || [])));
          setCalculate((c) => c + 1);
        }
      }
    }
    loadAll();
  }, [setValue]);

  // ── Packet → auto-fill item ────────────────────────────────────────────────
  useEffect(() => {
    if (!detailPacket) {
      // Packet cleared — reset only if it had previously set the item
      if (itemLockedByPacket) {
        setDetailItem(null);
        setDetailItemDisplay("");
        setValue("details.item", "");
        setValue("details.rate", 0);
        setValue("details.metal_purity", "");
      }
      return;
    }
    const pkt = packets.find((p) => p.pckt_no === detailPacket);
    if (pkt?.stone_item_id) {
      const item = pkt.stone_item_id;
      const rate = pkt.rate_for_retail ?? 0;
      setValue("details.item", item.short_code);
      setValue("details.rate", rate);
      setValue("details.metal_purity", ""); // packet items don't use metal purity
      setDetailItem(item);
      setDetailItemDisplay(item.item_name);
    }
  }, [detailPacket, packets]);

  // ── Clear fields when item type changes ───────────────────────────────────
  useEffect(() => {
    if (!isRawItem) {
      setValue("details.metal_purity", "");
    }
  }, [detailItem]);

  // ── Auto-calculation ───────────────────────────────────────────────────────
  useEffect(() => {
    const mrp      = rs.reduce((s, item) => s + parseFloat(item.amount || 0), 0);
    const discount = parseFloat(getValues("form.discount")) || 0;
    const cgst_per = parseFloat(getValues("form.cgst_per")) || 0;
    const sgst_per = parseFloat(getValues("form.sgst_per")) || 0;
    const igst_per = parseFloat(getValues("form.igst_per")) || 0;
    const tcs_per  = parseFloat(getValues("form.tcs_per"))  || 0;

    const taxable   = mrp - discount;
    const cgst_amt  = taxable * cgst_per / 100;
    const sgst_amt  = taxable * sgst_per / 100;
    const igst_amt  = taxable * igst_per / 100;
    const total_incl_gst = taxable + cgst_amt + sgst_amt + igst_amt;
    // TCS is on total consideration including GST (CBDT clarification under Sec 206C(1H))
    const tcs_amt        = total_incl_gst > 5000000 ? total_incl_gst * tcs_per / 100 : 0;
    const total          = total_incl_gst + tcs_amt;

    setValue("form.mrp",              mrp.toFixed(2));
    setValue("form.taxable_value",    taxable.toFixed(2));
    setValue("form.cgst_amt",         cgst_amt.toFixed(2));
    setValue("form.sgst_amt",         sgst_amt.toFixed(2));
    setValue("form.igst_amt",         igst_amt.toFixed(2));
    setValue("form.total_incl_gst",   total_incl_gst.toFixed(2));
    setValue("form.tcs_amt",          tcs_amt.toFixed(2));
    setValue("form.total_bill_value", total.toFixed(2));
  }, [rs, calculate, w_discount]);

  // ── Ref Bill Fetch ─────────────────────────────────────────────────────────
  const handleRefBillFetch = async () => {
    const bill_no = getValues("form.ref_bill_no");
    if (!bill_no) return;
    try {
      const res = await fetchDetailsforSaleReturn(bill_no);
      if (res.success && res.data) {
        const d = res.data;
        setFetchedBillItems(d.salereturnitem_set || []);
        setSelectedIndices(new Set());
        if (d.ldgr)      setValue("form.ldgr",      d.ldgr);
        if (d.ldgr_name) setValue("form.ldgr_name", d.ldgr_name);
        setValue("form.cgst_per", d.cgst_per || 0);
        setValue("form.sgst_per", d.sgst_per || 0);
        setValue("form.igst_per", d.igst_per || 0);
        setValue("form.tcs_per",  d.tcs_per  || 0);
        setCalculate((c) => c + 1);
      } else {
        toast({ title: "Bill not found", description: `No sale voucher found for "${bill_no}"`, variant: "destructive" });
      }
    } catch (err) {
      toast({ title: "Error fetching bill details" });
    }
  };

  const handleRefBillKeyDown = (e) => {
    if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); handleRefBillFetch(); }
  };

  // ── Checkbox selection ────────────────────────────────────────────────────
  const allSelected = fetchedBillItems.length > 0 && selectedIndices.size === fetchedBillItems.length;
  const toggleAll   = () => setSelectedIndices(allSelected ? new Set() : new Set(fetchedBillItems.map((_, i) => i)));
  const toggleOne   = (i) => setSelectedIndices((prev) => { const next = new Set(prev); next.has(i) ? next.delete(i) : next.add(i); return next; });

  const handleAddSelected = () => {
    if (selectedIndices.size === 0) { toast({ title: "No items selected" }); return; }
    setRows((prev) => [...prev, ...fetchedBillItems.filter((_, i) => selectedIndices.has(i))]);
    setFetchedBillItems([]);
    setSelectedIndices(new Set());
    setCalculate((c) => c + 1);
  };

  // ── Manual main item ──────────────────────────────────────────────────────
  const handleAddMainItem = () => {
    const newMain = getValues("mainItem");
    if (!newMain.item) { toast({ title: "Please select an item first" }); return; }
    setRows((prev) => [
      ...prev,
      {
        sale_billno: null,
        barcode: null,
        item: newMain.item,
        item_name: mainItemDisplay || newMain.item,
        pcs: newMain.pcs,
        gw: newMain.gw,
        purity: null,
        making: newMain.making,
        making_type: newMain.making_type,
        making_value: parseFloat(newMain.making) || 0,
        amount: parseFloat(newMain.value) || 0,
        remarks: newMain.remarks,
        salereturndetails_set: [],
      },
    ]);
    setMainItemDisplay("");
    setValue("mainItem", { ...emptyMainItem });
    setCalculate((c) => c + 1);
    setTimeout(() => packetInputRef.current?.focus(), 0);
  };

  const handleKeyDownMainItem = (e) => {
    if (e.key === "Tab") { e.preventDefault(); handleAddMainItem(); }
  };

  // ── Manual sub-item — linked by sl_no to manual main items in rs ──────────
  const manualItems = rs.map((r, i) => ({ r, i })).filter(({ r }) => r.sale_billno === null);

  const handleAddDetail = () => {
    const detail = getValues("details");
    const slNo   = parseInt(detail.sl_no, 10);

    if (!slNo || slNo < 1 || slNo > manualItems.length) {
      toast({
        title: "Invalid Sl No",
        description: manualItems.length === 0
          ? "Add a manual main item first (Step 1)."
          : `Enter a number between 1 and ${manualItems.length}.`,
      });
      return;
    }

    const targetIdx = manualItems[slNo - 1].i;
    setRows((prev) =>
      prev.map((row, i) =>
        i === targetIdx
          ? {
              ...row,
              salereturndetails_set: [
                ...(row.salereturndetails_set || []),
                {
                  sl_no:        slNo,
                  packet:       detail.packet || null,
                  item:         detail.item,
                  item_name:    detailItemDisplay || detail.item,
                  pcs:          detail.pcs,
                  ct:           detail.ct,
                  gw:           detail.gw,
                  metal_purity: detail.metal_purity || null,
                  tunch:        detail.tunch,
                  rate:         detail.rate,
                  amount:       detail.amount,
                },
              ],
            }
          : row
      )
    );
    // Reset but keep sl_no for convenience
    setDetailItemDisplay("");
    setDetailItem(null);
    setValue("details", { ...emptyDetail, sl_no: slNo });
    setTimeout(() => packetInputRef.current?.focus(), 0);
  };

  const handleKeyDownDetail = (e) => {
    if (e.key === "Tab") { e.preventDefault(); handleAddDetail(); }
  };

  // ── Row management ────────────────────────────────────────────────────────
  const handleDeleteItem = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    setCalculate((c) => c + 1);
  };

  const handleDeleteDetail = (itemIdx, detailIdx) => {
    setRows((prev) =>
      prev.map((row, i) =>
        i === itemIdx
          ? { ...row, salereturndetails_set: row.salereturndetails_set.filter((_, j) => j !== detailIdx) }
          : row
      )
    );
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSalesReturnSubmit = async () => {
    if (rs.length === 0) { toast({ title: "Table is empty", description: "Add at least one item." }); return; }
    try {
      const formVals = getValues("form");
      const payload  = { ...formVals, salereturnitem_set: rs };
      delete payload.ref_bill_no;
      delete payload.ldgr_name;
      delete payload.total_bill_value;

      const response = id
        ? await updateSalesReturn(payload, id)
        : await createSalesReturn(payload);

      if (response.success) {
        toast({ title: "Form submitted successfully!" });
        reset();
        setRows([]);
        setTimeout(() => navigate("/sales/salesreturn/list/"), 2000);
      } else {
        toast({ title: "Form submission failed.", description: renderErrorTree(response.error) });
      }
    } catch (error) {
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(handleSalesReturnSubmit));

  const handleAutoCalcFromTotal = () => {
    const enteredTotal = parseFloat(getValues('form.total_bill_value') || 0);
    const mrp          = parseFloat(getValues('form.mrp')             || 0);
    const cgst_per     = parseFloat(getValues('form.cgst_per')        || 0);
    const igst_per     = parseFloat(getValues('form.igst_per')        || 0);
    const sgst_per     = parseFloat(getValues('form.sgst_per')        || 0);
    const tcs_per      = parseFloat(getValues('form.tcs_per')         || 0);

    const gstFactor = 1 + cgst_per / 100 + igst_per / 100 + sgst_per / 100;
    const tcsFactor = 1 + tcs_per / 100;
    // total = taxable_value * gstFactor * tcsFactor
    // taxable_value = mrp - discount
    // => discount = mrp - enteredTotal / (gstFactor * tcsFactor)
    const taxable  = enteredTotal / (gstFactor * tcsFactor);
    const discount = mrp - taxable;
    setValue('form.discount', Math.max(0, parseFloat(discount.toFixed(2))));
    setCalculate((c) => c + 1);
  };

  const billSummaryRows = [
    { label: "MRP",              field: "form.mrp" },
    { label: "Discount",         field: "form.discount", editable: true, step: "0.01" },
    { isSeparator: true },
    { label: "Taxable Value",    field: "form.taxable_value" },
    { label: "CGST",             field: "form.cgst_amt" },
    { label: "SGST",             field: "form.sgst_amt" },
    { label: "IGST",             field: "form.igst_amt" },
    { isSeparator: true },
    { label: "Total Incl. GST",  field: "form.total_incl_gst" },
    { label: "TCS",              field: "form.tcs_amt" },
    { isSeparator: true },
    { label: "Grand Total",      field: "form.total_bill_value", isTotal: true, isEditableTotal: true },
  ];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="mt-5">
      <form
        ref={formRef}
        className="p-6 shadow-sm rounded-xl bg-white border border-gray-100"
        onSubmit={handleSubmit(handleSalesReturnSubmit)}
      >
        {/* Title */}
        <div className="flex items-center gap-3 my-5">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">↩</span>
          <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">Sales Return</span>
          <div className="flex-1 h-px bg-violet-100" />
        </div>

        {/* ══ SECTION 1: Return Details ══════════════════════════════════════ */}
        <SectionHeader number="1" title="Return Details" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4 mb-6">
          <Field label="Date">
            <Input type="date" {...register("form.date1", { required: true })} />
          </Field>
          <Field label="Bill No">
            <div className="flex h-10 items-center px-3 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold">
              {watch("form.billno") || <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>}
            </div>
            <input type="hidden" {...register("form.billno", { required: true })} />
          </Field>
          <Field label="Ref Sale Bill No">
            <div className="flex gap-2">
              <Input type="text" placeholder="Enter bill no and press Fetch" onKeyDown={handleRefBillKeyDown} {...register("form.ref_bill_no")} />
              <Button type="button" variant="outline" className="shrink-0 border-violet-300 text-primary hover:bg-violet-50" onClick={handleRefBillFetch}>
                Fetch
              </Button>
            </div>
          </Field>
          <Field label="Customer">
            <Input list="party_list" placeholder="Type to search…" {...register("form.ldgr_name")}
              onChange={(e) => {
                const sel = customers.find((c) => c.ac_name === e.target.value);
                if (sel) setValue("form.ldgr", sel.id);
              }} required />
            <input type="hidden" {...register("form.ldgr")} />
            <datalist id="party_list">
              {customers.map((c, i) => <option key={i} value={c.ac_name} />)}
            </datalist>
          </Field>
          <Field label="Remarks">
            <Input type="text" {...register("form.remarks")} />
          </Field>
        </div>
        <input type="hidden" {...register("form.cgst_per")} />
        <input type="hidden" {...register("form.sgst_per")} />
        <input type="hidden" {...register("form.igst_per")} />
        <input type="hidden" {...register("form.tcs_per")} />

        {/* ══ SECTION 2: Select from Ref Bill ════════════════════════════════ */}
        {fetchedBillItems.length > 0 && (
          <>
            <SectionHeader number="2" title="Select Items to Return" />
            <p className="text-xs text-gray-500 mb-3">
              Check items to return, then click <strong>Add Selected to Return</strong>.
            </p>
            <div className="overflow-x-auto mb-3">
              <Table className="w-full border-collapse">
                <TableBody>
                  <TableRow className="bg-violet-50">
                    <TH className="w-10">
                      <input type="checkbox" checked={allSelected} onChange={toggleAll} className="accent-violet-700 w-4 h-4 cursor-pointer" />
                    </TH>
                    <TH>#</TH><TH>Barcode</TH><TH>Item</TH><TH>Pcs</TH><TH>GW</TH><TH>Making</TH><TH>Amount</TH>
                  </TableRow>
                  {fetchedBillItems.map((item, i) => (
                    <React.Fragment key={i}>
                      <TableRow className={`cursor-pointer transition-colors ${selectedIndices.has(i) ? "bg-violet-50" : "hover:bg-gray-50"}`} onClick={() => toggleOne(i)}>
                        <TableCell className="px-4 py-2 border">
                          <input type="checkbox" checked={selectedIndices.has(i)} onChange={() => toggleOne(i)} onClick={(e) => e.stopPropagation()} className="accent-violet-700 w-4 h-4 cursor-pointer" />
                        </TableCell>
                        <TableCell className="px-4 py-2 border text-xs font-semibold text-gray-500">{i + 1}</TableCell>
                        <TableCell className="px-4 py-2 border text-xs">{item.barcode}</TableCell>
                        <TableCell className="px-4 py-2 border text-xs">{item.item}</TableCell>
                        <TableCell className="px-4 py-2 border text-xs">{item.pcs}</TableCell>
                        <TableCell className="px-4 py-2 border text-xs">{item.gw}</TableCell>
                        <TableCell className="px-4 py-2 border text-xs">{item.making}</TableCell>
                        <TableCell className="px-4 py-2 border text-xs font-medium">{item.amount}</TableCell>
                      </TableRow>
                      {item.salereturndetails_set?.map((d, di) => (
                        <TableRow key={di} className="bg-gray-50">
                          <TableCell className="px-4 py-1.5 border" />
                          <TableCell className="px-4 py-1.5 border text-xs text-gray-400">↳</TableCell>
                          <TableCell className="px-4 py-1.5 border text-xs text-gray-500 italic" colSpan={5}>
                            {[d.item, d.pcs != null && `Pcs: ${d.pcs}`, d.ct != null && `Ct: ${Number(d.ct).toFixed(3)}`, d.gw != null && `GW: ${d.gw}`, d.metal_purity && `Purity: ${d.metal_purity}`, d.tunch != null && `Tunch: ${d.tunch}`, d.rate != null && `Rate: ${d.rate}`, d.packet && `Pkt: ${d.packet}`].filter(Boolean).join("  ")}
                          </TableCell>
                          <TableCell className="px-4 py-1.5 border text-xs text-gray-500">{d.amount}</TableCell>
                        </TableRow>
                      ))}
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="flex justify-end mb-6">
              <Button type="button" className="bg-primary hover:bg-primary text-white" onClick={handleAddSelected}>
                Add Selected to Return ↓
              </Button>
            </div>
          </>
        )}

        {/* ══ SECTION 3: Manual Items ═════════════════════════════════════════ */}
        <SectionHeader number="3" title="Manual Items (No Barcode)" />

        {/* Step 1 — Main Item */}
        <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-1.5">Step 1 — Main Item</p>
        <p className="text-xs text-gray-400 mb-2">
          Fill in the jewellery piece details, then press <kbd className="px-1 py-0.5 bg-gray-100 border rounded font-mono text-gray-600">Tab</kbd> on Remarks to add.
        </p>
        <div className="overflow-x-auto mb-5">
          <Table className="w-full table-fixed border-collapse">
            <TableBody>
              <TableRow className="bg-violet-50">
                <TH>Item</TH><TH>Pcs</TH><TH>GW</TH>
                <TH>Making</TH><TH>Making Type</TH><TH>Discount</TH><TH>Value</TH><TH>Remarks</TH>
              </TableRow>
              <TableRow>
                <TableCell className="w-40 px-3 py-2 border">
                  <Input list="main_item_list" value={mainItemDisplay} ref={mainItemInputRef}
                    onChange={(e) => {
                      const typed = e.target.value;
                      setMainItemDisplay(typed);
                      const found = mainItemData.find((m) => m.item_name === typed || m.short_code === typed);
                      setValue("mainItem.item", found ? found.short_code : typed);
                    }}
                    placeholder="Item name" />
                  <datalist id="main_item_list">
                    {mainItemData.filter((m) => m.item_type === "M").map((m, i) => <option key={i} value={m.item_name}>{m.short_code}</option>)}
                  </datalist>
                  <input type="hidden" {...register("mainItem.item")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" placeholder="0" {...register("mainItem.pcs")} />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.001" placeholder="0.000" {...register("mainItem.gw")} />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" placeholder="0.00" {...register("mainItem.making")} />
                </TableCell>
                <TableCell className="w-28 px-3 py-2 border">
                  <Controller name="mainItem.making_type" control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value ?? ""}>
                        <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Type" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="per_nw">% of wt</SelectItem>
                          <SelectItem value="val">Value</SelectItem>
                        </SelectContent>
                      </Select>
                    )} />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" placeholder="0.00" {...register("mainItem.discount")} />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" placeholder="0.00" {...register("mainItem.value")} />
                </TableCell>
                <TableCell className="w-32 px-3 py-2 border">
                  <Input placeholder="Remarks" {...register("mainItem.remarks")} onKeyDown={handleKeyDownMainItem} />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* Step 2 — Sub-Items */}
        <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-1.5">Step 2 — Sub-Items / Material Details</p>
        <p className="text-xs text-gray-400 mb-2">
          Enter <strong>Sl No</strong> to attach to a specific manual item above (e.g. 1 = first manual item).
          Press <kbd className="px-1 py-0.5 bg-gray-100 border rounded font-mono text-gray-600">Tab</kbd> on Amount to add.
          {itemLockedByPacket && <span className="ml-2 text-primary font-medium">Packet active — item auto-filled.</span>}
          {packetLockedByItem && <span className="ml-2 text-primary font-medium">Item active — packet disabled.</span>}
        </p>
        <div className="overflow-x-auto mb-6">
          <Table className="w-full table-fixed border-collapse">
            <TableBody>
              <TableRow className="bg-violet-50">
                <TH className="w-14">Sl No</TH>
                {!packetLockedByItem && <TH className="w-28">Packet</TH>}
                {!itemLockedByPacket && <TH className="w-40">Item (R)</TH>}
                {itemLockedByPacket  && <TH className="w-40">Item (from pkt)</TH>}
                <TH className="w-16">Pcs</TH>
                <TH className="w-16">Ct</TH>
                <TH className="w-20">GW</TH>
                {showMetalPurity     && <TH className="w-28">Metal Purity</TH>}
                <TH className="w-20">Tunch</TH>
                <TH className="w-20">Rate</TH>
                <TH className="w-24">Amount</TH>
              </TableRow>
              <TableRow>
                {/* Sl No */}
                <TableCell className="w-14 px-3 py-2 border">
                  <Input type="number" min="1" placeholder="1" {...register("details.sl_no")} className="text-center" />
                </TableCell>

                {/* Packet — hidden when item is active */}
                {!packetLockedByItem && (
                  <TableCell className="w-28 px-3 py-2 border">
                    <Input
                      list="manual_packet_list"
                      placeholder="Packet"
                      {...register("details.packet")}
                      ref={(el) => { register("details.packet").ref(el); packetInputRef.current = el; }}
                    />
                    <datalist id="manual_packet_list">
                      {packets.map((p, i) => <option key={i} value={p.pckt_no} />)}
                    </datalist>
                  </TableCell>
                )}

                {/* Item — disabled when packet is active; only type-R items in datalist */}
                <TableCell className="w-40 px-3 py-2 border">
                  <Input
                    list="detail_item_list"
                    value={detailItemDisplay}
                    disabled={itemLockedByPacket}
                    className={itemLockedByPacket ? "bg-gray-100 text-gray-500 cursor-not-allowed" : ""}
                    onChange={(e) => {
                      const typed = e.target.value;
                      setDetailItemDisplay(typed);
                      const found = rawItems.find((m) => m.item_name === typed || m.short_code === typed);
                      setValue("details.item", found ? found.short_code : typed);
                      setDetailItem(found ?? null);
                    }}
                    placeholder="Raw item"
                  />
                  <datalist id="detail_item_list">
                    {rawItems.map((m, i) => <option key={i} value={m.item_name}>{m.short_code}</option>)}
                  </datalist>
                  <input type="hidden" {...register("details.item")} />
                </TableCell>

                <TableCell className="w-16 px-3 py-2 border">
                  <Input type="number" {...register("details.pcs")} placeholder="Pcs" />
                </TableCell>
                <TableCell className="w-16 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.ct")} placeholder="Ct" />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.gw")} placeholder="GW" />
                </TableCell>

                {/* Metal Purity — only for raw items entered without a packet */}
                {showMetalPurity && (
                  <TableCell className="w-28 px-3 py-2 border">
                    <Controller name="details.metal_purity" control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value ?? ""}>
                          <SelectTrigger className="h-8"><SelectValue placeholder="Purity" /></SelectTrigger>
                          <SelectContent>
                            {purityData.map((p, i) => <SelectItem key={i} value={`${p.purity}`}>{p.purity}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      )} />
                  </TableCell>
                )}

                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.tunch")} placeholder="Tunch" />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.01" {...register("details.rate")} placeholder="Rate" />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" {...register("details.amount")} placeholder="Amount" onKeyDown={handleKeyDownDetail} />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* ══ SECTION 4: All Return Items ═════════════════════════════════════ */}
        <SectionHeader number="4" title="Return Items" />

        {rs.length === 0 ? (
          <p className="text-xs text-gray-400 mb-6 pl-1">
            No items added yet. Fetch a ref bill and select items, or add manual items above.
          </p>
        ) : (
          <div className="overflow-x-auto mb-6">
            <Table className="w-full border-collapse">
              <TableBody>
                <TableRow className="bg-violet-50">
                  <TH className="w-16">Actions</TH>
                  <TH>Type</TH>
                  <TH>Barcode / Packet</TH>
                  <TH>Item</TH>
                  <TH>Pcs</TH>
                  <TH>GW</TH>
                  <TH>Making</TH>
                  <TH>Making Type</TH>
                  <TH>Amount</TH>
                </TableRow>

                {rs.map((item, idx) => {
                  const isManual = item.sale_billno === null;
                  // Find which manual index this is (1-based) for the sl_no label
                  const manualIdx = isManual
                    ? rs.slice(0, idx + 1).filter((r) => r.sale_billno === null).length
                    : null;

                  return (
                    <React.Fragment key={idx}>
                      <TableRow className={isManual ? "bg-sky-50 border-t-2 border-sky-200" : "bg-blue-50/40"}>
                        <TableCell className="px-3 py-2 border">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-gray-400 font-semibold">{idx + 1}</span>
                            <Trash2 size={15} color="#d45959" className="cursor-pointer" onClick={() => handleDeleteItem(idx)} />
                          </div>
                        </TableCell>
                        <TableCell className="px-3 py-2 border text-xs">
                          {isManual
                            ? <span className="text-sky-700 font-semibold">Manual #{manualIdx}</span>
                            : <span className="text-blue-600">Ref Bill</span>}
                        </TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{item.barcode || "—"}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs font-medium">{item.item_name || item.item}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{item.pcs}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{item.gw}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{item.making}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{item.making_type}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs font-medium">{item.amount}</TableCell>
                      </TableRow>

                      {item.salereturndetails_set?.map((detail, detailIdx) => (
                        <TableRow className="bg-white" key={detailIdx}>
                          <TableCell className="px-3 py-1.5 border">
                            <Trash2 size={14} color="#d45959" className="cursor-pointer" onClick={() => handleDeleteDetail(idx, detailIdx)} />
                          </TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs text-gray-400">
                            ↳ #{detailIdx + 1}
                          </TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.packet || "—"}</TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.item_name || detail.item}</TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.pcs}</TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.gw}</TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.metal_purity || "—"}</TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.tunch}</TableCell>
                          <TableCell className="px-3 py-1.5 border text-xs">{detail.amount}</TableCell>
                        </TableRow>
                      ))}
                    </React.Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}

        {/* ══ Bill Summary ══════════════════════════════════════════════════ */}
        <BillSummaryPanel rows={billSummaryRows} register={register} watch={watch} autoCalcTotal={autoCalcEnabled} onAutoCalc={handleAutoCalcFromTotal} />

        {/* ══ Action Buttons ════════════════════════════════════════════════ */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
          <Button type="submit" className="bg-primary hover:bg-primary text-white">Save</Button>
        </div>
      </form>
    </div>
  );
};

export default SalesReturnAdd;

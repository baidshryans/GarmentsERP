import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { renderErrorTree } from "../../Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
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
  fetchMainItem,
  fetchSalesperson,
  fetchPurity,
  fetchPackets,
  getLedgers,
  fetchCustomerOrders,
  createSalesApproval,
  getStates,
  getRetails,
  fetchBarcodeDetail,
  fetchHSNs,
} from "@/services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils.jsx";
import {
  fetchNextSaleAppNo,
  fetchSalesApprovalById,
  updateSalesApproval,
} from "../../services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";

/* ─── helpers ──────────────────────────────────────────────── */
const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 mb-4">
    <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">
      {number}
    </span>
    <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">
      {title}
    </span>
    <div className="flex-1 h-px bg-gray-100" />
  </div>
);

/* ─── component ─────────────────────────────────────────────── */
const SalesApprovalAdd = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();

  const { register, handleSubmit, control, reset, watch, setValue, getValues, formState: { isDirty } } =
    useForm({
      defaultValues: {
        form: {
          date1: new Date().toISOString().split("T")[0],
          billno: "",
          ldgr: "",
          ldgr_name: "",
          sales_person: "",
          sales_person2: "",
          place_of_supply: "",
          narration: "",
          mode_of_transport: "",
          discount: 0,
          taxable_value: 0,
          sgst_per: 0,
          cgst_per: 0,
          igst_per: 0,
        },
        hsn: "711319",
        barcode: "",
      },
    });

  const { fields, append } = useFieldArray({
    control,
    name: "salesvouitem_set",
  });

  /* ── state ── */
  const [saving, setSaving] = useState(false);
  const { canSave, saveLabel, resetTableDirty } = useEditDirty({ id, isDirty });
  const [statesData, setStatesData]       = useState([]);
  const [customers, setCustomers]         = useState([]);
  const [salespersonData, setSalesperson] = useState([]);
  const [hsns, setHsns]                   = useState([]);
  const [retailStateCode, setRetailStateCode] = useState("");
  const [retailStateName, setRetailStateName] = useState("");

  /* ── data fetch on mount ── */
  useEffect(() => {
    async function fetchData() {
      const [states, ledgersRes, billNoRes, mainItemRes, purityRes, hsnRes,
             packetsRes, custOrdersRes, salesPersonRes, retailsRes] = await Promise.all([
        getStates(),
        getLedgers({ type: "CO,VD", page_size: 10000 }),
        fetchNextSaleAppNo(),
        fetchMainItem(),
        fetchPurity(),
        fetchHSNs(),
        fetchPackets(),
        fetchCustomerOrders(),
        fetchSalesperson(),
        getRetails(),
      ]);

      /* Resolve the retail's state from the live API so we don't depend on
         a (possibly stale or empty) sessionStorage value. */
      let liveStateCode = sessionStorage.getItem("state_code") || "";
      let liveStateName = sessionStorage.getItem("state_name") || "";
      if (retailsRes?.success) {
        const activeCode  = sessionStorage.getItem("retail_code") || "";
        const userLoc     = retailsRes.data?.results?.[0] || {};
        const locations   = userLoc.location || [];
        // The response can come back as either {retail_code, retail: {state:{...}}}
        // or as a flat RetailMaster {retail_code, state:{...}} depending on
        // depth/serializer version. Handle both.
        const activeEntry =
          locations.find((l) => (l.retail_code || l.retail?.retail_code) === activeCode) ||
          userLoc.default_location ||
          locations[0] ||
          {};
        const retailObj = activeEntry.retail || activeEntry;
        const st = retailObj?.state;
        if (st && typeof st === "object") {
          liveStateCode = st.code ?? liveStateCode;
          liveStateName = st.name ?? liveStateName;
          sessionStorage.setItem("state_code", liveStateCode);
          sessionStorage.setItem("state_name", liveStateName);
        }
      }
      setRetailStateCode(liveStateCode);
      setRetailStateName(liveStateName);

      if (states.success) {
        const list = states.data.results ?? states.data;
        setStatesData(list);
      }
      if (ledgersRes.success)    setCustomers(ledgersRes.data.results);
      if (salesPersonRes.success) setSalesperson(salesPersonRes.data.results ?? salesPersonRes.data);
      if (hsnRes.success)        setHsns(hsnRes.data.results);
      if (billNoRes.success)     setValue("form.billno", billNoRes.data.billno);

      /* load edit data */
      if (id) {
        const res = await fetchSalesApprovalById(id);
        if (res.success) {
          const d = res.data;
          Object.keys(d).forEach((key) => {
            if (key === "items") {
              d.items.forEach((item) => append(item));
            } else {
              setValue(`form.${key}`, d[key]);
            }
          });
          reset(getValues(), { keepValues: true, keepDirty: false });
          resetTableDirty();
        }
      }
    }
    fetchData();
  }, []);

  /* ── default Place of Supply once both statesData and retail-state are loaded ── */
  useEffect(() => {
    if (id) return;                                 // edit mode: keep stored value
    if (!statesData.length) return;                 // dropdown not ready
    if (getValues("form.place_of_supply")) return;  // already set / user-edited
    if (!retailStateCode && !retailStateName) return;

    const match =
      (retailStateCode && statesData.find((s) => `${s.code}` === `${retailStateCode}`)) ||
      (retailStateName && statesData.find((s) => (s.name || "").toLowerCase() === retailStateName.toLowerCase())) ||
      null;
    if (match) {
      setValue("form.place_of_supply", `${match.code}`);
    } else if (retailStateCode) {
      setValue("form.place_of_supply", retailStateCode);
    }
  }, [id, statesData, retailStateCode, retailStateName]);

  /* ── auto-GST from HSN + place_of_supply ── */
  const hsn_current     = watch("hsn");
  const place_of_supply = watch("form.place_of_supply");

  useEffect(() => {
    if (!hsn_current || hsns.length === 0) return;
    const hsn_ = hsns.find((h) => h.hsn_no === hsn_current);
    if (!hsn_) return;

    /* Determine retail's "canonical" state by matching its code or name
       against statesData (handles WB vs 19 etc.). */
    const retailState =
      statesData.find((s) => `${s.code}` === `${retailStateCode}`) ||
      statesData.find((s) => (s.name || "").toLowerCase() === retailStateName.toLowerCase());
    const selectedState =
      statesData.find((s) => `${s.code}` === `${place_of_supply}`) ||
      statesData.find((s) => (s.name || "").toLowerCase() === `${place_of_supply}`.toLowerCase());

    const isLocal = !!(retailState && selectedState && retailState.id === selectedState.id);

    setValue("form.sgst_per", isLocal ? parseFloat(hsn_.sgst) : 0);
    setValue("form.cgst_per", isLocal ? parseFloat(hsn_.cgst) : 0);
    setValue("form.igst_per", isLocal ? 0 : parseFloat(hsn_.igst));
  }, [hsn_current, place_of_supply, hsns, statesData, retailStateCode, retailStateName]);

  /* ── auto-recalc sub-item amount, main-item amount & taxable_value ── */
  const watchedItems = watch("salesvouitem_set");
  useEffect(() => {
    const items = getValues("salesvouitem_set") || [];
    let billTotal = 0;
    items.forEach((row, i) => {
      const subs = row.main_item_set || [];
      let subTotal = 0;
      subs.forEach((sub, j) => {
        const rate = parseFloat(sub.rate) || 0;
        const uom  = sub.uom;
        const qty  = uom === "Ct"
          ? (parseFloat(sub.ct)  || 0)
          : uom === "Pcs"
            ? (parseFloat(sub.pcs) || 0)
            : (parseFloat(sub.gw)  || 0);
        const amt = +(rate * qty).toFixed(2);
        if (amt !== (parseFloat(sub.amount) || 0)) {
          setValue(`salesvouitem_set.${i}.main_item_set.${j}.amount`, amt, { shouldDirty: false });
        }
        subTotal += amt;
      });
      const making = parseFloat(row.making) || 0;
      const mainAmt = +(subTotal + making).toFixed(2);
      if (mainAmt !== (parseFloat(row.amount) || 0)) {
        setValue(`salesvouitem_set.${i}.amount`, mainAmt, { shouldDirty: false });
      }
      billTotal += mainAmt;
    });
    const tv = +billTotal.toFixed(2);
    if (tv !== (parseFloat(getValues("form.taxable_value")) || 0)) {
      setValue("form.taxable_value", tv, { shouldDirty: false });
    }
  }, [watchedItems]);

  /* ── computed bill summary values ── */
  const taxable_value = parseFloat(watch("form.taxable_value") || 0);
  const discount      = parseFloat(watch("form.discount")      || 0);
  const cgst_per      = parseFloat(watch("form.cgst_per")      || 0);
  const sgst_per      = parseFloat(watch("form.sgst_per")      || 0);
  const igst_per      = parseFloat(watch("form.igst_per")      || 0);

  const net        = taxable_value - discount;
  const cgst_amt   = net * (cgst_per / 100);
  const sgst_amt   = net * (sgst_per / 100);
  const igst_amt   = net * (igst_per / 100);
  const total_gst  = cgst_amt + sgst_amt + igst_amt;
  const grand_total = net + total_gst;

  /* ── barcode scan / append ── */
  const handleBarcodeBlur = async () => {
    const { barcode, hsn } = getValues();
    if (!barcode) return;
    try {
      const data = await fetchBarcodeDetail(barcode, hsn, getValues("form.ldgr"));
      if (data.success) {
        append(data.data);
        setValue("barcode", "");   // clear field for the next scan
      } else {
        const detail = data.error?.detail || (typeof data.error === "string" ? data.error : null);
        if (detail) {
          toast({ title: "Barcode rejected", description: detail });
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  /* ── submit ── */
  const handleSalesVoucherSubmit = async () => {
    if (fields.length === 0) {
      toast({ title: "Item table is empty" });
      return;
    }
    const data = {
      ...getValues("form"),
      items: getValues("salesvouitem_set"),
    };

    setSaving(true);
    const response = id
      ? await updateSalesApproval(data, id)
      : await createSalesApproval(data);

    if (response.success) {
      toast({ title: "Saved successfully!" });
      setTimeout(() => navigate("/sales/salesapproval/list/"), 1500);
    } else {
      setSaving(false);
      toast({
        title: "Submission failed",
        description: renderErrorTree(response.error),
      });
    }
  };

  useF4Submit(handleSubmit(handleSalesVoucherSubmit));

  /* ─────────────────────────────────────────────────────────── */
  return (
    <div className="container mt-4">
      <form
        className="p-6 shadow-sm rounded-xl bg-white border border-gray-100"
        onSubmit={handleSubmit(handleSalesVoucherSubmit)}
      >
        {/* ── 1. Bill Details ─────────────────────────────── */}
        <SectionHeader number="1" title="Bill Details" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          {/* Bill No */}
          <FieldContainer>
            <Label className="text-nowrap">Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                {watch("form.billno") || (
                  <span className="text-violet-400 text-xs font-normal">
                    Auto-generating…
                  </span>
                )}
              </span>
              <input type="hidden" {...register("form.billno")} />
            </div>
          </FieldContainer>

          {/* Date */}
          <FieldContainer>
            <Label className="text-nowrap">Date</Label>
            <Input type="date" {...register("form.date1", { required: true })} />
          </FieldContainer>

          {/* Party Name */}
          <FieldContainer>
            <Label className="text-nowrap">Party Name</Label>
            <SearchableComboBox
              options={customers}
              value={watch("form.ldgr_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.ldgr_name", opt.ac_name)
                setValue("form.ldgr", opt.id)
              }}
              placeholder="Search customer…"
            />
            <input type="hidden" {...register("form.ldgr")} />
          </FieldContainer>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          {/* Sales Person 1 */}
          <FieldContainer>
            <Label className="text-nowrap">Sales Person</Label>
            <Controller
              name="form.sales_person"
              control={control}
              rules={{ required: true }}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={`${field.value}`}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select Sales Person" />
                  </SelectTrigger>
                  <SelectContent>
                    {salespersonData.map((sp, i) => (
                      <SelectItem key={i} value={`${sp.id}`}>
                        {sp.salesperson_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>

          {/* Sales Person 2 */}
          <FieldContainer>
            <Label className="text-nowrap">Sales Person 2</Label>
            <Controller
              name="form.sales_person2"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={`${field.value}`}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select Sales Person 2" />
                  </SelectTrigger>
                  <SelectContent>
                    {salespersonData.map((sp, i) => (
                      <SelectItem key={i} value={`${sp.id}`}>
                        {sp.salesperson_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>

          {/* Place of Supply */}
          <FieldContainer>
            <Label className="text-nowrap">Place of Supply</Label>
            <Controller
              name="form.place_of_supply"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select State" />
                  </SelectTrigger>
                  <SelectContent>
                    {statesData.map((s, i) => (
                      <SelectItem key={i} value={`${s.code}`}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {/* HSN */}
          <FieldContainer>
            <Label className="text-nowrap">HSN Code</Label>
            <Controller
              name="hsn"
              control={control}
              render={({ field }) => (
                <Select
                  disabled={fields.length > 0}
                  onValueChange={field.onChange}
                  value={field.value}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select HSN" />
                  </SelectTrigger>
                  <SelectContent>
                    {hsns.map((h, i) => (
                      <SelectItem key={i} value={`${h.hsn_no}`}>
                        {h.description || h.hsn_no}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>

          {/* Barcode */}
          <FieldContainer>
            <Label className="text-nowrap">Barcode</Label>
            <Input
              type="text"
              disabled={!hsn_current}
              {...register("barcode")}
              onBlur={handleBarcodeBlur}
            />
          </FieldContainer>

          {/* Mode of Transport */}
          <FieldContainer>
            <Label className="text-nowrap">Mode of Transport</Label>
            <Input type="text" {...register("form.mode_of_transport")} />
          </FieldContainer>
        </div>

        {/* ── 2. Item Details ──────────────────────────────── */}
        <SectionHeader number="2" title="Item Details" />

        <div className="overflow-x-auto rounded-lg border border-gray-100 mb-6">
          <Table>
            <TableBody>
              {/* Header row — Packet comes right after Item (col 3) */}
              <TableRow className="bg-violet-50">
                {[
                  { h: "Barcode" },
                  { h: "Item" },
                  { h: "Packet" },
                  { h: "Pcs" },
                  { h: "CT" },
                  { h: "GW" },
                  { h: "Making", w: "w-20" },
                  { h: "Purity" },
                  { h: "Rate",   w: "w-20" },
                  { h: "Amount", w: "w-36" },
                ].map(({ h, w }) => (
                  <TableCell key={h} className={`px-3 py-2 border text-xs font-semibold text-primary text-center whitespace-nowrap ${w || ""}`}>
                    {h}
                  </TableCell>
                ))}
              </TableRow>

              {fields.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} className="text-center text-sm text-gray-400 py-8">
                    Scan a barcode above to add items
                  </TableCell>
                </TableRow>
              )}

              {fields.map((field, index) => (
                <React.Fragment key={field.id}>
                  {/* Main item row */}
                  <TableRow className="bg-violet-50/60">
                    <TableCell className="px-3 py-1 border text-xs">{field?.barcode}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs font-medium">{field?.item_name || field?.item}</TableCell>
                    {/* Packet — col 3 */}
                    <TableCell className="px-3 py-1 border text-xs text-center">—</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.pcs}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{Number(field?.ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.gw}</TableCell>
                    <TableCell className="px-3 py-1 border">
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        {...register(`salesvouitem_set.${index}.making`, { valueAsNumber: true })}
                        placeholder="Making"
                      />
                    </TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.purity}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">—</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-right tabular-nums">
                      {fmt(watch(`salesvouitem_set.${index}.amount`) || 0)}
                      <input type="hidden" {...register(`salesvouitem_set.${index}.amount`, { valueAsNumber: true })} />
                    </TableCell>
                  </TableRow>

                  {/* Sub-item rows */}
                  {(field.main_item_set || []).map((detail, idx) => (
                    <TableRow key={idx} className="bg-gray-50">
                      <TableCell className="px-3 py-1 border" />
                      <TableCell className="px-3 py-1 border text-xs pl-6">{detail?.item_name || detail?.item}</TableCell>
                      {/* Packet — col 3 */}
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.packet}</TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.pcs}</TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-center">{Number(detail?.ct || 0).toFixed(3)}</TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.gw}</TableCell>
                      <TableCell className="px-3 py-1 border" />
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.purity}</TableCell>
                      <TableCell className="px-3 py-1 border">
                        <Input
                          type="number"
                          className="h-7 text-xs"
                          {...register(`salesvouitem_set.${index}.main_item_set.${idx}.rate`, { valueAsNumber: true })}
                          placeholder="Rate"
                        />
                      </TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-right tabular-nums">
                        {fmt(watch(`salesvouitem_set.${index}.main_item_set.${idx}.amount`) || 0)}
                        <input type="hidden" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.amount`, { valueAsNumber: true })} />
                      </TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Narration */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <FieldContainer>
            <Label className="text-nowrap">Narration</Label>
            <Input type="text" {...register("form.narration")} />
          </FieldContainer>
        </div>

        {/* ── 3. Bill Summary ──────────────────────────────── */}
        <SectionHeader number="3" title="Bill Summary" />

        <div className="flex justify-end mb-6">
          <div className="w-full max-w-sm rounded-lg border border-gray-100 overflow-hidden shadow-sm">
            {[
              { label: "Taxable Value", value: fmt(taxable_value) },
              { label: "Discount",      field: "form.discount",      editable: true },
              { separator: true },
              ...(cgst_per > 0 ? [{ label: `CGST @ ${cgst_per}%`, value: fmt(cgst_amt) }] : []),
              ...(sgst_per > 0 ? [{ label: `SGST @ ${sgst_per}%`, value: fmt(sgst_amt) }] : []),
              ...(igst_per > 0 ? [{ label: `IGST @ ${igst_per}%`, value: fmt(igst_amt) }] : []),
              { separator: true },
              { label: "Total", value: fmt(grand_total), bold: true },
            ].map((row, i) => {
              if (row.separator)
                return <div key={i} className="border-t border-gray-100" />;
              return (
                <div
                  key={i}
                  className={`flex items-center justify-between px-4 py-1.5 ${
                    row.bold ? "bg-violet-50 font-bold" : "odd:bg-gray-50/50"
                  }`}
                >
                  <span className="text-xs text-gray-600 whitespace-nowrap">{row.label}</span>
                  {row.editable ? (
                    <Input
                      type="number"
                      step="0.01"
                      className="h-7 w-32 text-right text-xs"
                      {...register(row.field)}
                    />
                  ) : (
                    <span className={`text-sm tabular-nums ${row.bold ? "text-primary" : "text-gray-800"}`}>
                      {row.value}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Actions ──────────────────────────────────────── */}
        <div className="flex justify-center gap-4 pt-2">
          <Button type="submit" disabled={saving || !canSave}>{saveLabel(saving)}</Button>
          <Button variant="outline" type="button" onClick={() => window.history.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
};

export default SalesApprovalAdd;

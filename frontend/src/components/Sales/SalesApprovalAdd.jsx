import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { renderErrorTree } from "../../Utils";
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

/* ─── helpers ──────────────────────────────────────────────── */
const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 mb-4">
    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-violet-700 text-white text-[11px] font-bold shrink-0">
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

  const { register, handleSubmit, control, reset, watch, setValue, getValues } =
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
  const [statesData, setStatesData]       = useState([]);
  const [customers, setCustomers]         = useState([]);
  const [salespersonData, setSalesperson] = useState([]);
  const [hsns, setHsns]                   = useState([]);

  /* ── data fetch on mount ── */
  useEffect(() => {
    async function fetchData() {
      const [states, ledgersRes, billNoRes, mainItemRes, purityRes, hsnRes,
             packetsRes, custOrdersRes, salesPersonRes] = await Promise.all([
        getStates(),
        getLedgers(),
        fetchNextSaleAppNo(),
        fetchMainItem(),
        fetchPurity(),
        fetchHSNs(),
        fetchPackets(),
        fetchCustomerOrders(),
        fetchSalesperson(),
      ]);

      if (states.success) {
        setStatesData(states.data);
        /* Set default place_of_supply from retail's state code */
        const retailStateCode = localStorage.getItem("state_code");
        if (retailStateCode && !id) {
          setValue("form.place_of_supply", retailStateCode);
        }
      }
      if (ledgersRes.success)    setCustomers(ledgersRes.data.results);
      if (salesPersonRes.success) setSalesperson(salesPersonRes.data);
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
        }
      }
    }
    fetchData();
  }, []);

  /* ── auto-GST from HSN + place_of_supply ── */
  const hsn_current     = watch("hsn");
  const place_of_supply = watch("form.place_of_supply");

  useEffect(() => {
    if (!hsn_current || hsns.length === 0) return;
    const hsn_ = hsns.find((h) => h.hsn_no === hsn_current);
    if (!hsn_) return;

    const retailState = localStorage.getItem("state_code");
    const isLocal     = place_of_supply === retailState;

    setValue("form.sgst_per", isLocal ? parseFloat(hsn_.sgst) : 0);
    setValue("form.cgst_per", isLocal ? parseFloat(hsn_.cgst) : 0);
    setValue("form.igst_per", isLocal ? 0 : parseFloat(hsn_.igst));
  }, [hsn_current, place_of_supply, hsns]);

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
    try {
      const data = await fetchBarcodeDetail(barcode, hsn);
      if (data.success) append(data.data);
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

    const response = id
      ? await updateSalesApproval(data, id)
      : await createSalesApproval(data);

    if (response.success) {
      toast({ title: "Saved successfully!" });
      setTimeout(() => navigate("/sales/salesapproval/list/"), 1500);
    } else {
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

        <div className="grid grid-cols-3 gap-4 mb-4">
          {/* Bill No */}
          <FieldContainer>
            <Label className="text-nowrap">Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-violet-800 text-sm font-semibold min-w-0 flex-1 truncate">
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

          {/* Party Name — hidden input + datalist live OUTSIDE FieldContainer */}
          <div className="flex items-center gap-2">
            <Label className="text-nowrap shrink-0">Party Name</Label>
            <Input
              list="party_list"
              className="flex-1"
              {...register("form.ldgr_name")}
              onChange={(e) => {
                const sel = customers.find((c) => c.ac_name === e.target.value);
                if (sel) setValue("form.ldgr", sel.id);
              }}
              required
            />
          </div>
          {/* These must be outside any layout wrapper that measures children */}
          <input type="hidden" {...register("form.ldgr")} />
          <datalist id="party_list">
            {customers.map((c, i) => (
              <option key={i} value={c.ac_name} />
            ))}
          </datalist>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-4">
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

        <div className="grid grid-cols-3 gap-4 mb-6">
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
                        {h.hsn_no}
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
                {["Barcode","Item","Packet","Pcs","CT","GW","Making","Making Type",
                  "Purity","Tunch","Rate","Amount"].map((h) => (
                  <TableCell key={h} className="px-3 py-2 border text-xs font-semibold text-violet-800 text-center whitespace-nowrap">
                    {h}
                  </TableCell>
                ))}
              </TableRow>

              {fields.length === 0 && (
                <TableRow>
                  <TableCell colSpan={12} className="text-center text-sm text-gray-400 py-8">
                    Scan a barcode above to add items
                  </TableCell>
                </TableRow>
              )}

              {fields.map((field, index) => (
                <React.Fragment key={field.id}>
                  {/* Main item row */}
                  <TableRow className="bg-violet-50/60">
                    <TableCell className="px-3 py-1 border text-xs">{field?.barcode}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs font-medium">{field?.item}</TableCell>
                    {/* Packet — col 3 */}
                    <TableCell className="px-3 py-1 border text-xs text-center">—</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.pcs}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.ct}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.gw}</TableCell>
                    <TableCell className="px-3 py-1 border">
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        {...register(`salesvouitem_set.${index}.making`)}
                        placeholder="Making"
                      />
                    </TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.making_type}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.purity}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">{field?.tunch}</TableCell>
                    <TableCell className="px-3 py-1 border text-xs text-center">—</TableCell>
                    <TableCell className="px-3 py-1 border">
                      <Input
                        type="number"
                        className="h-7 text-xs"
                        {...register(`salesvouitem_set.${index}.amount`)}
                        placeholder="Amount"
                      />
                    </TableCell>
                  </TableRow>

                  {/* Sub-item rows */}
                  {(field.main_item_set || []).map((detail, idx) => (
                    <TableRow key={idx} className="bg-gray-50">
                      <TableCell className="px-3 py-1 border" />
                      <TableCell className="px-3 py-1 border text-xs pl-6">{detail?.item}</TableCell>
                      {/* Packet — col 3 */}
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.packet}</TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.pcs}</TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.ct}</TableCell>
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.gw}</TableCell>
                      <TableCell className="px-3 py-1 border" />
                      <TableCell className="px-3 py-1 border" />
                      <TableCell className="px-3 py-1 border text-xs text-center">{detail?.purity}</TableCell>
                      <TableCell className="px-3 py-1 border">
                        <Input
                          type="number"
                          className="h-7 text-xs"
                          {...register(`salesvouitem_set.${index}.main_item_set.${idx}.tunch`)}
                          placeholder="Tunch"
                        />
                      </TableCell>
                      <TableCell className="px-3 py-1 border">
                        <Input
                          type="number"
                          className="h-7 text-xs"
                          {...register(`salesvouitem_set.${index}.main_item_set.${idx}.rate`)}
                          placeholder="Rate"
                        />
                      </TableCell>
                      <TableCell className="px-3 py-1 border">
                        <Input
                          type="number"
                          className="h-7 text-xs"
                          {...register(`salesvouitem_set.${index}.main_item_set.${idx}.amount`)}
                          placeholder="Amount"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Narration */}
        <div className="grid grid-cols-3 gap-4 mb-6">
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
              { label: "Taxable Value", field: "form.taxable_value", editable: true },
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
                    <span className={`text-sm tabular-nums ${row.bold ? "text-violet-700" : "text-gray-800"}`}>
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
          <Button type="submit">Save</Button>
          <Button variant="outline" type="button" onClick={() => window.history.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
};

export default SalesApprovalAdd;

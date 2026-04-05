import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Edit, Trash2 } from "lucide-react";
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
  createPurchaseReturn,
  fetchPurchaseReturnForEdit,
  updatePurchaseReturnForEdit,
  fetchPurchaseReturnInitialData,
  fetchDetailsForPurchaseReturn,
} from "@/services/apiService";

import { useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils.jsx";
import { renderErrorTree } from "../../../Utils";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";

// ─── Helpers ────────────────────────────────────────────────────────────────
const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 my-5">
    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-violet-700 text-white text-[11px] font-bold shrink-0">
      {number}
    </span>
    <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</span>
    <div className="flex-1 h-px bg-violet-100" />
  </div>
);

const TH = ({ children, className = "" }) => (
  <TableCell
    className={`px-4 py-2.5 border text-xs font-semibold text-violet-800 uppercase tracking-wider whitespace-nowrap ${className}`}
  >
    {children}
  </TableCell>
);

const emptyTableRow = {
  sl_no: "",
  item: "",
  pcs: 0,
  gw: 0,
  purity: "",
  making_type: "",
  making_value: 0,
  making: 0,
  remarks: "",
  purchasereturndetails_set: [],
};

const emptyDetails = {
  sl_no: "",
  sub_item: "",
  sub_pcs: 0,
  sub_ct: 0,
  sub_gw: 0,
  metal_purity: "",
  loss: 0,
  tunch: 0,
  rate: 0,
  value: 0,
  packet: "",
};

// ─── Utility: strip id fields when converting a PV → PR ───────────────────
function removeIds(obj) {
  if (Array.isArray(obj)) return obj.map(removeIds);
  if (typeof obj === "object" && obj !== null) {
    return Object.fromEntries(
      Object.entries(obj)
        .filter(([key]) => key !== "id")
        .map(([key, value]) => [key, removeIds(value)])
    );
  }
  return obj;
}

// ─── Component ───────────────────────────────────────────────────────────────
const PurchaseReturnAdd = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();

  const { register, handleSubmit, control, reset, watch, setValue, getValues } =
    useForm({
      defaultValues: {
        form: {
          date1: new Date().toISOString().split("T")[0],
          billno: "",
          pv_billno: "",
          ldgr: "",
          ldgr_name: "",
          narration: "",
          mode_of_transport: "",
          cgst_amt: 0,
          sgst_amt: 0,
          igst_amt: 0,
          tcs_amt: 0,
          discount: 0,
          hallmark_charge: 0,
          freight_amt: 0,
          bill_value: 0,
          round_off: 0,
        },
        table: { ...emptyTableRow },
        details: { ...emptyDetails },
      },
    });

  // ── State ──────────────────────────────────────────────────────────────────
  const [rs, setRows] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [packets, setPackets] = useState([]);

  // ── Initial data load ──────────────────────────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetchPurchaseReturnInitialData();
        if (res.success) {
          const d = res.data;
          setVendors(d.ledgers || []);
          setMainItemData(d.items || []);
          setPurityData(d.purity || []);
          setPackets(d.packets || []);
          setValue("form.billno", d.billno);
        } else {
          console.error("Failed to fetch initial data:", res.error);
          toast({
            title: "Error",
            description:
              res.error?.error ||
              "Failed to load form data. Please ensure you are logged in and have selected a retail location.",
            variant: "destructive",
          });
        }
      } catch (err) {
        console.error("Exception fetching initial data:", err);
      }
    }

    fetchData().then(() => {
      if (id) {
        fetchPurchaseReturnForEdit(id)
          .then((response) => {
            if (response.success || response.data) {
              const data = response.data || response;
              Object.keys(data).forEach((key) => {
                setValue(`form.${key}`, data[key]);
              });
              if (data.purchasereturnitems_set) {
                setRows(JSON.parse(JSON.stringify(data.purchasereturnitems_set)));
              }
            }
          })
          .catch((err) => console.error("Error fetching purchase return:", err));
      }
    });
  }, [setValue]);

  // ── Ref Purchase Voucher auto-populate (Tab on PV Bill No) ────────────────
  const handlePvBillNoKeyDown = async (e) => {
    if (e.key !== "Tab") return;
    const pvBillNo = getValues("form.pv_billno");
    if (!pvBillNo) return;
    try {
      const response = await fetchDetailsForPurchaseReturn(pvBillNo);
      if (response.success && response.data) {
        const cleanData = removeIds(response.data);
        const { billno, bill_no, ...restData } = cleanData;
        reset({
          ...getValues(),
          form: {
            ...getValues("form"),
            ...restData,
            pv_billno: pvBillNo,
            billno: getValues("form.billno"),
          },
        });
        setRows((prev) => [
          ...prev,
          ...(cleanData.purchasereturnitems_set || []),
        ]);
      }
    } catch (err) {
      console.error("Error fetching purchase voucher:", err);
      toast({ title: "Error fetching purchase voucher details" });
    }
  };

  // ── Main item entry (Tab on Remarks) ──────────────────────────────────────
  const handleAddRow = () => {
    const newItem = { ...getValues("table"), purchasereturndetails_set: [] };
    setRows((prev) => [...prev, newItem]);
    reset({ ...getValues(), table: { ...emptyTableRow } });
  };

  const handleKeyDownMain = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      handleAddRow();
    }
  };

  // ── Detail entry (Tab on Packet) ──────────────────────────────────────────
  const handleAddDetail = () => {
    const detail = { ...getValues("details") };
    const idx = parseInt(detail.sl_no, 10) - 1;
    if (idx >= 0 && idx < rs.length) {
      setRows((prev) =>
        prev.map((row, i) =>
          i === idx
            ? {
                ...row,
                purchasereturndetails_set: [
                  ...(Array.isArray(row.purchasereturndetails_set)
                    ? row.purchasereturndetails_set
                    : []),
                  detail,
                ],
              }
            : row
        )
      );
      reset({ ...getValues(), details: { ...emptyDetails } });
    }
  };

  const handleKeyDownDetails = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      handleAddDetail();
    }
  };

  // ── Row management ─────────────────────────────────────────────────────────
  const handleDeleteItem = (index) => setRows((prev) => prev.filter((_, i) => i !== index));

  const handleEdit = (index) => {
    reset({ ...getValues(), table: { ...rs[index] } });
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDeleteDetail = (itemIdx, detailIdx) => {
    setRows((prev) =>
      prev.map((item, idx) =>
        idx === itemIdx
          ? {
              ...item,
              purchasereturndetails_set: item.purchasereturndetails_set.filter(
                (_, i) => i !== detailIdx
              ),
            }
          : item
      )
    );
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmitForm = async () => {
    try {
      if (rs.length === 0) {
        toast({ title: "Table is empty" });
        return;
      }
      const data = { ...getValues("form"), purchasereturnitems_set: rs };
      const response = id
        ? await updatePurchaseReturnForEdit(data, id)
        : await createPurchaseReturn(data);

      if (response.success) {
        toast({ title: "Form submitted successfully!" });
        reset();
        setRows([]);
        setTimeout(() => navigate("/purchase/purchasereturn/list/"), 2000);
      } else {
        toast({
          title: "Form submission failed.",
          description: renderErrorTree(response.error),
        });
      }
    } catch (error) {
      console.error("Error submitting Purchase Return:", error);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(handleSubmitForm));

  const billSummaryRows = [
    { label: "Discount",      field: "form.discount",       editable: true, step: "0.01" },
    { label: "Hallmark Charge", field: "form.hallmark_charge", editable: true, step: "0.01" },
    { label: "Freight",       field: "form.freight_amt",    editable: true, step: "0.01" },
    { label: "Round Off",     field: "form.round_off",      editable: true, step: "0.01" },
    { isSeparator: true },
    { label: "CGST Amount",   field: "form.cgst_amt" },
    { label: "SGST Amount",   field: "form.sgst_amt" },
    { label: "IGST Amount",   field: "form.igst_amt" },
    { label: "TCS Amount",    field: "form.tcs_amt" },
    { label: "Bill Value",    field: "form.bill_value" },
  ];

  return (
    <div className="mt-5">
      <form
        className="p-6 shadow-sm rounded-xl bg-white border border-gray-100"
        onSubmit={handleSubmit(handleSubmitForm)}
      >
        {/* Title */}
        <div className="flex items-center gap-3 my-5">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-violet-700 text-white text-[11px] font-bold shrink-0">
            ↩
          </span>
          <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">
            Purchase Return
          </span>
          <div className="flex-1 h-px bg-violet-100" />
        </div>

        {/* ══ SECTION 1: Header ══════════════════════════════════════════════ */}
        <SectionHeader number="1" title="Return Details" />

        <div className="grid grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label>Date</Label>
            <Input type="date" {...register("form.date1", { required: true })} />
          </FieldContainer>

          <FieldContainer>
            <Label>Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-violet-800 text-sm font-semibold min-w-0 flex-1 truncate">
                {watch("form.billno") || (
                  <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>
                )}
              </span>
              <input type="hidden" {...register("form.billno", { required: true })} />
            </div>
          </FieldContainer>

          <FieldContainer>
            <Label>Ref PV Bill No</Label>
            <Input
              type="text"
              onKeyDown={handlePvBillNoKeyDown}
              {...register("form.pv_billno")}
              placeholder="Tab to auto-fill"
            />
          </FieldContainer>

          <FieldContainer>
            <Label>Vendor / Ledger</Label>
            <Input
              list="vendor_list"
              {...register("form.ldgr_name")}
              onChange={(e) => {
                const selected = vendors.find((v) => v.ac_name === e.target.value);
                if (selected) setValue("form.ldgr", selected.id);
              }}
              required
            />
            <input type="hidden" {...register("form.ldgr")} />
            <datalist id="vendor_list">
              {vendors.map((v, i) => (
                <option key={i} value={v.ac_name}>
                  {v.id}
                </option>
              ))}
            </datalist>
          </FieldContainer>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label>Mode of Transport</Label>
            <Input type="text" {...register("form.mode_of_transport")} />
          </FieldContainer>

          <FieldContainer>
            <Label>Narration</Label>
            <Input type="text" {...register("form.narration")} />
          </FieldContainer>
        </div>

        {/* ══ SECTION 2: Add Return Item ════════════════════════════════════ */}
        <SectionHeader number="2" title="Add Return Item" />
        <p className="text-xs text-gray-500 mb-3">
          Enter item details, then press{" "}
          <kbd className="px-1 py-0.5 bg-gray-100 border rounded text-xs">Tab</kbd> on{" "}
          <strong>Remarks</strong> to add the row.
        </p>

        <div className="overflow-x-auto">
          <Table className="w-full table-fixed border-collapse mb-4">
            <TableBody>
              <TableRow className="bg-violet-50">
                <TH>Sl No</TH>
                <TH>Item</TH>
                <TH>Pcs</TH>
                <TH>GW</TH>
                <TH>Purity</TH>
                <TH>Making Type</TH>
                <TH>Making Value</TH>
                <TH>Making</TH>
                <TH>Remarks</TH>
              </TableRow>
              <TableRow>
                <TableCell className="w-16 px-3 py-2 border">
                  <Input type="number" placeholder="#" {...register("table.sl_no")} />
                </TableCell>
                <TableCell className="w-32 px-3 py-2 border">
                  <Input list="item_list" {...register("table.item")} />
                  <datalist id="item_list">
                    {mainItemData.map((itm, i) => (
                      <option key={i} value={itm.short_code}>
                        {itm.item_name}
                      </option>
                    ))}
                  </datalist>
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" {...register("table.pcs")} />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("table.gw")} />
                </TableCell>
                <TableCell className="w-28 px-3 py-2 border">
                  <Controller
                    name="table.purity"
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger className="h-8">
                          <SelectValue placeholder="Purity" />
                        </SelectTrigger>
                        <SelectContent>
                          {purityData.map((p, i) => (
                            <SelectItem key={i} value={`${p.purity}`}>
                              {p.purity}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>
                <TableCell className="w-28 px-3 py-2 border">
                  <Controller
                    name="table.making_type"
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger className="h-8">
                          <SelectValue placeholder="Type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="per_nw">% of wt</SelectItem>
                          <SelectItem value="val">Value</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("table.making_value")} />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("table.making")} />
                </TableCell>
                <TableCell className="w-36 px-3 py-2 border">
                  <Input
                    type="text"
                    onKeyDown={handleKeyDownMain}
                    {...register("table.remarks")}
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* ══ SECTION 3: Add Sub-Item Details (Stone / Metal) ══════════════ */}
        <SectionHeader number="3" title="Add Sub-Item Details (Stone / Metal)" />
        <p className="text-xs text-gray-500 mb-3">
          Use <strong>Sl No</strong> to link the detail row to an item above (row number).
          Press <kbd className="px-1 py-0.5 bg-gray-100 border rounded text-xs">Tab</kbd> on{" "}
          <strong>Packet</strong> to add.
        </p>

        <div className="overflow-x-auto">
          <Table className="w-full table-fixed border-collapse mb-4">
            <TableBody>
              <TableRow className="bg-violet-50">
                <TH>Sl No</TH>
                <TH>Sub Item</TH>
                <TH>Pcs</TH>
                <TH>Ct</TH>
                <TH>GW</TH>
                <TH>Metal Purity</TH>
                <TH>Loss</TH>
                <TH>Tunch</TH>
                <TH>Rate</TH>
                <TH>Value</TH>
                <TH>Packet</TH>
              </TableRow>
              <TableRow>
                <TableCell className="w-16 px-3 py-2 border">
                  <Input type="number" placeholder="#" {...register("details.sl_no")} />
                </TableCell>
                <TableCell className="w-28 px-3 py-2 border">
                  <Input list="sub_item_list" {...register("details.sub_item")} />
                  <datalist id="sub_item_list">
                    {mainItemData.map((m, i) => (
                      <option key={i} value={m.short_code} />
                    ))}
                  </datalist>
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" {...register("details.sub_pcs")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.sub_ct")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.sub_gw")} />
                </TableCell>
                <TableCell className="w-28 px-3 py-2 border">
                  <Controller
                    name="details.metal_purity"
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger className="h-8">
                          <SelectValue placeholder="Purity" />
                        </SelectTrigger>
                        <SelectContent>
                          {purityData.map((p, i) => (
                            <SelectItem key={i} value={`${p.purity}`}>
                              {p.purity}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.loss")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.tunch")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.rate")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.01" {...register("details.value")} />
                </TableCell>
                <TableCell className="w-28 px-3 py-2 border">
                  <Input
                    list="packet_list"
                    onKeyDown={handleKeyDownDetails}
                    {...register("details.packet")}
                  />
                  <datalist id="packet_list">
                    {packets.map((p, i) => (
                      <option key={i} value={p.pckt_no} />
                    ))}
                  </datalist>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* ══ SECTION 4: Accumulated Items ══════════════════════════════════ */}
        <SectionHeader number="4" title="Return Items" />

        <div className="overflow-x-auto">
          <Table>
            <TableBody>
              <TableRow className="bg-violet-50">
                <TH></TH>
                <TH>Sl No</TH>
                <TH>Item</TH>
                <TH>Pcs</TH>
                <TH>GW</TH>
                <TH>Purity</TH>
                <TH>Making Type</TH>
                <TH>Making Val</TH>
                <TH>Making</TH>
                <TH>Remarks</TH>
                {/* Detail columns */}
                <TH>Sub Item</TH>
                <TH>Pcs</TH>
                <TH>Ct</TH>
                <TH>GW</TH>
                <TH>Metal Purity</TH>
                <TH>Loss</TH>
                <TH>Tunch</TH>
                <TH>Rate</TH>
                <TH>Value</TH>
                <TH>Packet</TH>
              </TableRow>

              {rs.map((item, idx) => (
                <React.Fragment key={idx}>
                  {/* Main item row */}
                  <TableRow className="bg-violet-50">
                    <TableCell className="px-3 py-2 border">
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-400 font-semibold mr-1">{idx + 1}</span>
                        <Edit
                          size={15}
                          className="cursor-pointer text-gray-500 hover:text-violet-700"
                          onClick={() => handleEdit(idx)}
                        />
                        <Trash2
                          size={15}
                          color="#d45959"
                          className="cursor-pointer"
                          onClick={() => handleDeleteItem(idx)}
                        />
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.sl_no}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.item}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.pcs}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.gw}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.purity}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.making_type}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.making_value}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.making}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.remarks}</TableCell>
                    {/* Empty detail columns */}
                    <TableCell className="px-3 py-2 border" colSpan={10}></TableCell>
                  </TableRow>

                  {/* Detail rows */}
                  {Array.isArray(item.purchasereturndetails_set) &&
                    item.purchasereturndetails_set.map((detail, detailIdx) => (
                      <TableRow className="bg-gray-50" key={detailIdx}>
                        <TableCell className="px-3 py-2 border flex items-center justify-center">
                          <Trash2
                            size={14}
                            color="#d45959"
                            className="cursor-pointer"
                            onClick={() => handleDeleteDetail(idx, detailIdx)}
                          />
                        </TableCell>
                        {/* Empty main item columns */}
                        <TableCell className="px-3 py-2 border text-xs text-gray-400">↳</TableCell>
                        <TableCell className="px-3 py-2 border" colSpan={8}></TableCell>
                        {/* Detail data */}
                        <TableCell className="px-3 py-2 border text-xs">{detail.sub_item}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.sub_pcs}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.sub_gw}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.metal_purity}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.loss}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.tunch}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.rate}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.value}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.packet}</TableCell>
                      </TableRow>
                    ))}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>

        <br />
        <br />

        {/* Bill Summary */}
        <BillSummaryPanel rows={billSummaryRows} register={register} watch={watch} />

        {/* Submit buttons */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="button" variant="outline" onClick={() => window.history.back()}>
            Cancel
          </Button>
          <Button type="submit" className="bg-violet-700 hover:bg-violet-800 text-white">
            Save
          </Button>
        </div>
      </form>
    </div>
  );
};

export default PurchaseReturnAdd;

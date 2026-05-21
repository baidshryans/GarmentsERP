import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useF2Navigate } from "@/hooks/useF2Navigate";
import { useEnterAsTab } from "@/hooks/useEnterAsTab";
import { SquarePen, Trash2, ScanBarcode, Loader2, Plus } from "lucide-react";
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
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";

import {
  createPurchaseReturn,
  fetchPurchaseReturnForEdit,
  updatePurchaseReturnForEdit,
  fetchPurchaseReturnInitialData,
  fetchDetailsForPurchaseReturn,
} from "@/services/apiService";
import { fetchBarcodeDetailOnly } from "@/services/api/inventory";

import { useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils.jsx";
import { renderErrorTree } from "../../../Utils";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";
import { useEditDirty } from "@/hooks/useEditDirty";

// ─── Helpers ────────────────────────────────────────────────────────────────
const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 my-5">
    <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">
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
  barcode: null,
  barcode_txt: "",
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

  const { register, handleSubmit, control, reset, watch, setValue, getValues, formState: { isDirty } } =
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
          cgst_per: 0,
          sgst_per: 0,
          igst_per: 0,
          tcs_amt: 0,
          discount: 0,
          hallmark_charge: 0,
          freight_amt: 0,
          other_charge: 0,
          mrp: 0,
          taxable_value: 0,
          total_incl_gst: 0,
          bill_value: 0,
          round_off: 0,
        },
        table: { ...emptyTableRow },
        details: { ...emptyDetails },
      },
    });

  // ── State ──────────────────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false);
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [rs, setRows] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [packets, setPackets] = useState([]);
  const [retailState, setRetailState] = useState("");
  const [barcodeInput, setBarcodeInput] = useState("");
  const [scanning, setScanning] = useState(false);
  const barcodeFetchingRef = useRef(false);
  const loadedPvBillNosRef = useRef(new Set());

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
          setRetailState(d.retail_state || "");
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
              reset(getValues(), { keepValues: true, keepDirty: false });
              resetTableDirty();
            }
          })
          .catch((err) => console.error("Error fetching purchase return:", err));
      }
    });
  }, [setValue]);

  // ── Ref Purchase Voucher auto-populate (Tab on PV Bill No) ────────────────
  const handlePvBillNoKeyDown = async (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const pvBillNo = getValues("form.pv_billno");
    if (!pvBillNo) return;
    if (loadedPvBillNosRef.current.has(pvBillNo)) {
      toast({ title: "Already loaded", description: `PV Bill "${pvBillNo}" items are already added.` });
      return;
    }
    try {
      const response = await fetchDetailsForPurchaseReturn(pvBillNo);
      if (response.success && response.data) {
        const cleanData = removeIds(response.data);

        const isFirstLoad = loadedPvBillNosRef.current.size === 0;

        if (isFirstLoad) {
          // Only on the first PV load: populate header/ledger/GST from the PV
          const { billno, bill_no, ...restData } = cleanData;
          const itemsTotal = (cleanData.purchasereturnitems_set || []).reduce((sum, item) => {
            const making = parseFloat(item.making) || 0;
            const subTotal = (item.purchasereturndetails_set || []).reduce(
              (s, d) => s + (parseFloat(d.value) || parseFloat(d.amt) || 0),
              0
            );
            return sum + making + subTotal;
          }, 0);
          const freight = parseFloat(cleanData.freight_amt) || 0;
          const other = parseFloat(cleanData.other_charge) || 0;
          const discount = parseFloat(cleanData.discount) || 0;
          const taxableBase = itemsTotal + freight + other - discount;
          const cgstAmt = parseFloat(cleanData.cgst_amt) || 0;
          const sgstAmt = parseFloat(cleanData.sgst_amt) || 0;
          const igstAmt = parseFloat(cleanData.igst_amt) || 0;
          const cgstPer = taxableBase > 0 ? Number(((cgstAmt / taxableBase) * 100).toFixed(2)) : 0;
          const sgstPer = taxableBase > 0 ? Number(((sgstAmt / taxableBase) * 100).toFixed(2)) : 0;
          const igstPer = taxableBase > 0 ? Number(((igstAmt / taxableBase) * 100).toFixed(2)) : 0;

          reset({
            ...getValues(),
            form: {
              ...getValues("form"),
              ...restData,
              cgst_per: cgstPer,
              sgst_per: sgstPer,
              igst_per: igstPer,
              pv_billno: pvBillNo,
              billno: getValues("form.billno"),
            },
          });
        } else {
          // Subsequent PV loads: ONLY append items, keep current vendor/charges intact
          setValue("form.pv_billno", "");
        }

        setRows((prev) => [
          ...prev,
          ...(cleanData.purchasereturnitems_set || []),
        ]);
        loadedPvBillNosRef.current.add(pvBillNo);
        markTableDirty();
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
    markTableDirty();
    reset({ ...getValues(), table: { ...emptyTableRow } });
  };

  const handleKeyDownMain = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      handleAddRow();
    }
  };

  // ── Re-apply GST split when rows change (after vendor was already selected) ─
  const watchedLdgr = watch("form.ldgr");
  useEffect(() => {
    if (!watchedLdgr) return;
    const vendor = vendors.find((v) => v.id === watchedLdgr || v.id === Number(watchedLdgr));
    if (vendor) applyGstSplitForVendor(vendor);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rs.length, watchedLdgr, vendors, retailState, mainItemData]);

  // ── Auto-calculate Bill Summary totals ─────────────────────────────────────
  const watchedDiscount = watch("form.discount");
  const watchedFreight = watch("form.freight_amt");
  const watchedOther = watch("form.other_charge");
  const watchedRoundOff = watch("form.round_off");
  const watchedCgstPer = watch("form.cgst_per");
  const watchedSgstPer = watch("form.sgst_per");
  const watchedIgstPer = watch("form.igst_per");

  useEffect(() => {
    const itemsTotal = rs.reduce((sum, item) => {
      const making = parseFloat(item.making) || 0;
      const subTotal = (item.purchasereturndetails_set || []).reduce(
        (s, d) => s + (parseFloat(d.value) || 0),
        0
      );
      return sum + making + subTotal;
    }, 0);

    const freight = parseFloat(watchedFreight) || 0;
    const other = parseFloat(watchedOther) || 0;
    const discount = parseFloat(watchedDiscount) || 0;
    const roundOff = parseFloat(watchedRoundOff) || 0;
    const cgstPer = parseFloat(watchedCgstPer) || 0;
    const sgstPer = parseFloat(watchedSgstPer) || 0;
    const igstPer = parseFloat(watchedIgstPer) || 0;

    const taxableValue = itemsTotal + freight + other - discount;
    const cgstAmt = (taxableValue * cgstPer) / 100;
    const sgstAmt = (taxableValue * sgstPer) / 100;
    const igstAmt = (taxableValue * igstPer) / 100;
    const totalInclGst = taxableValue + cgstAmt + sgstAmt + igstAmt;
    const billValue = totalInclGst + roundOff;

    setValue("form.taxable_value", Number(taxableValue.toFixed(2)));
    setValue("form.cgst_amt", Number(cgstAmt.toFixed(2)));
    setValue("form.sgst_amt", Number(sgstAmt.toFixed(2)));
    setValue("form.igst_amt", Number(igstAmt.toFixed(2)));
    setValue("form.total_incl_gst", Number(totalInclGst.toFixed(2)));
    setValue("form.bill_value", Number(billValue.toFixed(2)));
  }, [rs, watchedDiscount, watchedFreight, watchedOther, watchedRoundOff, watchedCgstPer, watchedSgstPer, watchedIgstPer]);

  // ── Packet → sub_item auto-fill & lock ────────────────────────────────────
  const detailPacket = watch("details.packet");
  useEffect(() => {
    if (!detailPacket) {
      setValue("details.sub_item", "");
      return;
    }
    const pkt = packets.find((p) => p.pckt_no === detailPacket);
    if (pkt?.stone_item_short_code) {
      setValue("details.sub_item", pkt.stone_item_short_code);
    }
  }, [detailPacket, packets]);

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
      markTableDirty();
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
  const handleDeleteItem = (index) => { setRows((prev) => prev.filter((_, i) => i !== index)); markTableDirty(); };

  const handleEdit = (index) => {
    reset({ ...getValues(), table: { ...rs[index] } });
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const getEffectiveGstRate = () => {
    // Prefer existing total GST (e.g. when a Ref PV was loaded with rates)
    const cgstPer = parseFloat(getValues("form.cgst_per")) || 0;
    const sgstPer = parseFloat(getValues("form.sgst_per")) || 0;
    const igstPer = parseFloat(getValues("form.igst_per")) || 0;
    const existing = cgstPer + sgstPer + igstPer;
    if (existing > 0) return existing;

    // Otherwise derive from items' HSN — use the first item's HSN rate
    for (const row of rs) {
      const itm = mainItemData.find((m) => m.short_code === row.item);
      if (itm) {
        const cgst = parseFloat(itm.hsn_cgst) || 0;
        const sgst = parseFloat(itm.hsn_sgst) || 0;
        const igst = parseFloat(itm.hsn_igst) || 0;
        const total = cgst + sgst > 0 ? cgst + sgst : igst;
        if (total > 0) return total;
      }
    }
    return 0;
  };

  const applyGstSplitForVendor = (vendor) => {
    if (!vendor) return;
    const vendorState = (vendor.state || "").trim().toLowerCase();
    const retState = (retailState || "").trim().toLowerCase();
    const totalGst = getEffectiveGstRate();
    if (totalGst <= 0) return;

    const isIntraState = vendorState && retState && vendorState === retState;
    if (isIntraState) {
      const half = Number((totalGst / 2).toFixed(2));
      setValue("form.cgst_per", half);
      setValue("form.sgst_per", half);
      setValue("form.igst_per", 0);
    } else {
      setValue("form.cgst_per", 0);
      setValue("form.sgst_per", 0);
      setValue("form.igst_per", Number(totalGst.toFixed(2)));
    }
  };

  const handleItemMakingChange = (itemIdx, newMaking) => {
    setRows((prev) =>
      prev.map((item, i) =>
        i === itemIdx
          ? { ...item, making: newMaking, making_value: newMaking }
          : item
      )
    );
    markTableDirty();
  };

  const getDetailUom = (detail) => {
    if (!detail?.packet) return "gm";
    const pkt = packets.find((p) => p.pckt_no === detail.packet);
    return pkt?.stone_item_uom || "ct";
  };

  const calcDetailValue = (detail, rate) => {
    const r = parseFloat(rate) || 0;
    const uom = getDetailUom(detail);
    if (uom === "ct") {
      return r * (parseFloat(detail.sub_ct) || 0);
    }
    const fineWt =
      (parseFloat(detail.sub_gw) || 0) *
      ((parseFloat(detail.tunch) || 0) / 100);
    const basis = fineWt > 0 ? fineWt : (parseFloat(detail.sub_gw) || 0);
    return r * basis;
  };

  const handleDetailRateChange = (itemIdx, detailIdx, newRate) => {
    setRows((prev) =>
      prev.map((item, i) => {
        if (i !== itemIdx) return item;
        const updatedDetails = (item.purchasereturndetails_set || []).map(
          (d, j) => {
            if (j !== detailIdx) return d;
            const value = calcDetailValue(d, newRate);
            return { ...d, rate: newRate, value: Number(value.toFixed(2)) };
          }
        );
        return { ...item, purchasereturndetails_set: updatedDetails };
      })
    );
    markTableDirty();
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
    markTableDirty();
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmitForm = async () => {
    try {
      if (rs.length === 0) {
        toast({ title: "Table is empty" });
        return;
      }
      const data = { ...getValues("form"), purchasereturnitems_set: rs };
      setSaving(true);
      const response = id
        ? await updatePurchaseReturnForEdit(data, id)
        : await createPurchaseReturn(data);

      if (response.success) {
        toast({ title: id ? "Updated successfully!" : "Form submitted successfully!" });
        reset();
        setRows([]);
        setTimeout(() => navigate("/purchase/purchasereturn/list/"), 2000);
      } else {
        setSaving(false);
        toast({
          title: "Form submission failed.",
          description: renderErrorTree(response.error),
        });
      }
    } catch (error) {
      setSaving(false);
      console.error("Error submitting Purchase Return:", error);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  // ── Barcode scan ───────────────────────────────────────────────────────────
  const handleScan = async (e) => {
    e?.preventDefault();
    const code = barcodeInput.trim();
    if (!code || barcodeFetchingRef.current) return;

    if (rs.some((i) => i.barcode_txt === code)) {
      toast({ title: "Already added", description: `"${code}" is already in the list.` });
      setBarcodeInput("");
      return;
    }

    barcodeFetchingRef.current = true;
    setScanning(true);
    try {
      const res = await fetchBarcodeDetailOnly(code);
      if (!res.success || !res.data) {
        toast({ title: "Barcode not found", description: `No active stock for "${code}"`, variant: "destructive" });
        return;
      }
      const d = res.data;
      const nextSl = rs.length + 1;
      const normalizedDetails = Array.isArray(d.main_item_set)
        ? d.main_item_set.map((sd) => {
            const detail = {
              sl_no: nextSl,
              sub_item: sd.item ?? "",
              sub_pcs: sd.pcs ?? 0,
              sub_ct: sd.ct ?? 0,
              sub_gw: sd.gw ?? 0,
              metal_purity: sd.metal_purity ?? "",
              loss: sd.loss ?? 0,
              tunch: sd.tunch ?? 0,
              rate: sd.rate ?? 0,
              value: sd.amt ?? sd.value ?? 0,
              packet: sd.packet ?? "",
            };
            const computed = calcDetailValue(detail, detail.rate);
            if (computed > 0) detail.value = Number(computed.toFixed(2));
            return detail;
          })
        : [];

      const newRow = {
        sl_no: nextSl,
        barcode: d.id ?? null,
        barcode_txt: d.barcode || code,
        item: d.item ?? "",
        pcs: d.pcs ?? 1,
        gw: d.gw ?? 0,
        purity: d.purity ?? "",
        making_type: d.making_type ?? "",
        making_value: d.making ?? 0,
        making: d.making ?? 0,
        remarks: "",
        purchasereturndetails_set: normalizedDetails,
      };
      setRows((prev) => [...prev, newRow]);
      setBarcodeInput("");
      markTableDirty();
    } catch (err) {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    } finally {
      setScanning(false);
      barcodeFetchingRef.current = false;
    }
  };

  useF4Submit(handleSubmit(handleSubmitForm));
  useF2Navigate("/purchase/purchasereturn/list/add/");
  const formRef = useRef(null);
  useEnterAsTab(formRef);

  const cgstPerForLabel = parseFloat(watchedCgstPer) || 0;
  const sgstPerForLabel = parseFloat(watchedSgstPer) || 0;
  const igstPerForLabel = parseFloat(watchedIgstPer) || 0;

  const billSummaryRows = [
    { label: "Freight Charge", field: "form.freight_amt",   editable: true, step: "0.01" },
    { label: "Other Charge",   field: "form.other_charge",  editable: true, step: "0.01" },
    { isSeparator: true },
    { label: "Discount",       field: "form.discount",      editable: true, step: "0.01" },
    { label: "Taxable Value",  field: "form.taxable_value" },
    { label: cgstPerForLabel > 0 ? `CGST @ ${cgstPerForLabel}%` : "CGST", field: "form.cgst_amt" },
    { label: igstPerForLabel > 0 ? `IGST @ ${igstPerForLabel}%` : "IGST", field: "form.igst_amt" },
    { label: sgstPerForLabel > 0 ? `SGST @ ${sgstPerForLabel}%` : "SGST", field: "form.sgst_amt" },
    { label: "Total incl. GST", field: "form.total_incl_gst" },
    { label: "Round Off",      field: "form.round_off",     editable: true, step: "0.01" },
    { isSeparator: true },
    { label: "Total",          field: "form.bill_value",    isTotal: true },
  ];

  return (
    <div className="mt-5">
      <form
        ref={formRef}
        className="p-6 shadow-sm rounded-xl bg-white border border-gray-100"
        onSubmit={handleSubmit(handleSubmitForm)}
      >
        {/* Title */}
        <div className="flex items-center gap-3 my-5">
          <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">
            ↩
          </span>
          <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">
            Purchase Return
          </span>
          <div className="flex-1 h-px bg-violet-100" />
        </div>

        {/* ══ SECTION 1: Header ══════════════════════════════════════════════ */}
        <SectionHeader number="1" title="Return Details" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label>Date</Label>
            <Input type="date" {...register("form.date1", { required: true })} />
          </FieldContainer>

          <FieldContainer>
            <Label>Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                {watch("form.billno") || (
                  <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>
                )}
              </span>
              <input type="hidden" {...register("form.billno", { required: true })} />
            </div>
          </FieldContainer>

          <FieldContainer>
            <Label>Ref PV Bill No <span className="text-muted-foreground text-xs">(optional)</span></Label>
            <Input
              type="text"
              onKeyDown={handlePvBillNoKeyDown}
              {...register("form.pv_billno")}
              placeholder="Tab to auto-fill, or leave blank"
            />
          </FieldContainer>

          <FieldContainer>
            <Label>Vendor</Label>
            <SearchableComboBox
              options={vendors}
              labelKey="ac_name"
              searchKeys={["ac_name"]}
              value={watch("form.ldgr_name") || ""}
              placeholder="Search vendor…"
              onSelect={(v) => {
                setValue("form.ldgr_name", v.ac_name);
                setValue("form.ldgr", v.id);
                applyGstSplitForVendor(v);
              }}
            />
            <input type="hidden" {...register("form.ldgr_name")} required />
            <input type="hidden" {...register("form.ldgr")} />
          </FieldContainer>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label>Mode of Transport</Label>
            <Input type="text" {...register("form.mode_of_transport")} />
          </FieldContainer>

          <FieldContainer>
            <Label>Narration</Label>
            <Input type="text" {...register("form.narration")} />
          </FieldContainer>
        </div>

        {/* ══ BARCODE SCANNER ═══════════════════════════════════════════════ */}
        <div className="rounded-xl border-2 border-dashed border-primary/30 bg-primary/5 p-4 mb-4">
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1 flex-1 max-w-sm">
              <Label className="text-xs font-medium flex items-center gap-1.5">
                <ScanBarcode className="size-3.5" /> Scan Barcode / RFID
              </Label>
              <Input
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    e.stopPropagation();
                    handleScan(e);
                  }
                }}
                placeholder="Scan or type barcode…"
                className="h-10 text-base font-mono"
                disabled={scanning}
                data-enter-submit="true"
              />
            </div>
            <Button type="button" onClick={handleScan} disabled={scanning || !barcodeInput.trim()} className="h-10 gap-1.5">
              {scanning ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              {scanning ? "Loading…" : "Add"}
            </Button>
            <span className="text-xs text-muted-foreground pb-2">Press Enter after each scan</span>
          </div>
        </div>

        {/* ══ SECTION 2: Add Return Item ════════════════════════════════════ */}
        <SectionHeader number="2" title="Add Return Item (Manual)" />
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
                <TH>Pcs</TH>
                <TH>Ct</TH>
                <TH>GW</TH>
                <TH>Purity</TH>
                <TH>Loss</TH>
                <TH>Tunch</TH>
                <TH>Rate</TH>
                <TH>Amount</TH>
                <TH>Packet</TH>
              </TableRow>
              <TableRow>
                <TableCell className="w-16 px-3 py-2 border">
                  <Input type="number" placeholder="#" {...register("details.sl_no")} />
                </TableCell>
                {/* sub_item hidden — auto-filled from packet, see detailPacket watch above */}
                <input type="hidden" {...register("details.sub_item")} />
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
                <TH className="w-28">Barcode</TH>
                <TH>Packet</TH>
                <TH className="w-56">Item</TH>
                <TH>Pcs</TH>
                <TH>Ct</TH>
                <TH>GW</TH>
                <TH>Purity</TH>
                <TH className="w-20">Making</TH>
                <TH>Making Type</TH>
                <TH>Making Value</TH>
                <TH>Loss</TH>
                <TH>Tunch</TH>
                <TH>Fine Wt</TH>
                <TH className="w-20">Rate</TH>
                <TH>Amount</TH>
              </TableRow>

              {rs.map((item, idx) => (
                <React.Fragment key={idx}>
                  {/* Main item row */}
                  <TableRow className={item.barcode ? "bg-violet-50" : "bg-sky-50"}>
                    <TableCell className="px-3 py-2 border">
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-400 font-semibold mr-1">{idx + 1}</span>
                        <SquarePen
                          size={15}
                          className="cursor-pointer text-gray-500 hover:text-primary"
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
                    <TableCell className="px-3 py-2 border text-xs font-mono">{item.barcode_txt || "—"}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{mainItemData.find((m) => m.short_code === item.item)?.item_name || item.item}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.pcs}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.purity}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">
                      <Input
                        type="number"
                        step="0.01"
                        value={item.making ?? 0}
                        onChange={(e) => handleItemMakingChange(idx, e.target.value)}
                        className="h-7 text-xs"
                      />
                    </TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.making_type}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{item.making_value}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs">
                      {(
                        (parseFloat(item.making) || 0) +
                        (item.purchasereturndetails_set || []).reduce(
                          (s, d) => s + (parseFloat(d.value) || 0),
                          0
                        )
                      ).toFixed(2)}
                    </TableCell>
                  </TableRow>

                  {/* Detail rows */}
                  {Array.isArray(item.purchasereturndetails_set) &&
                    item.purchasereturndetails_set.map((detail, detailIdx) => (
                      <TableRow className="bg-gray-50" key={detailIdx}>
                        <TableCell className="px-3 py-2 border">
                          <div className="flex items-center justify-center">
                            <Trash2
                              size={14}
                              color="#d45959"
                              className="cursor-pointer"
                              onClick={() => handleDeleteDetail(idx, detailIdx)}
                            />
                          </div>
                        </TableCell>
                        {/* Detail: SL NO(↳) | BARCODE | PACKET | ITEM | PCS | CT | GW | PURITY | MAKING x3 | LOSS | TUNCH | FINE WT | AMOUNT */}
                        <TableCell className="px-3 py-2 border text-xs text-gray-400">↳</TableCell>
                        <TableCell className="px-3 py-2 border text-xs"></TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.packet}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs"></TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.sub_pcs}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.sub_gw != null ? parseFloat(detail.sub_gw).toFixed(3) : "—"}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.metal_purity}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs"></TableCell>
                        <TableCell className="px-3 py-2 border text-xs"></TableCell>
                        <TableCell className="px-3 py-2 border text-xs"></TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.loss}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{detail.tunch}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{(detail.sub_gw && detail.tunch) ? (parseFloat(detail.sub_gw) * parseFloat(detail.tunch) / 100).toFixed(3) : "—"}</TableCell>
                        <TableCell className="px-3 py-2 border text-xs">
                          <Input
                            type="number"
                            step="0.01"
                            value={detail.rate ?? 0}
                            onChange={(e) => handleDetailRateChange(idx, detailIdx, e.target.value)}
                            className="h-7 text-xs"
                          />
                        </TableCell>
                        <TableCell className="px-3 py-2 border text-xs">{Number(detail.value || 0).toFixed(2)}</TableCell>
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
          <Button type="submit" disabled={saving || !canSave} className="bg-primary hover:bg-primary text-white">
            {saveLabel(saving)}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default PurchaseReturnAdd;

import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useF2Navigate } from "@/hooks/useF2Navigate";
import { useEnterAsTab } from "@/hooks/useEnterAsTab";
import { SquarePen, Trash2, ClipboardList, CheckCircle2, AlertCircle, Gem, BadgePercent, PlusCircle, Plus, Loader2 } from "lucide-react";
import { fetchUnlinkedReceipts } from "@/services/api/accounting";
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
  TableHeader,
} from "@/components/ui/table";

import {
  getLedgers,
  fetchBarcodeDetail,
  CashTotalLedger,
  fetchCustomerCashReceived,
  fetchCustomerOrdersByLedger,
  fetchCustomerPurchasesByLedger,
  fetchB2BPricelistForLedger,
  fetchRetailDiscountPricelistForLedger,
} from "@/services/apiService";
import { Link, useParams, useSearchParams, useLocation } from "react-router-dom";

import { FieldContainer } from "@/Utils.jsx";
import {
  useSaleVoucherInitialData,
  useExhibitions,
  useTodayGoldRateMap,
  useSystemSettings,
  useBankLedgers,
  useActiveOffer,
  useSalesVoucherForEdit,
  useSaveSalesVoucherMutation,
} from "@/hooks/queries/salesVoucherQueries";
import { useEditDirty } from "@/hooks/useEditDirty";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";

// ─── Section header helper ──────────────────────────────────────────────────
// eslint-disable-next-line react/prop-types
const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 my-5">
    <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">{number}</span>
    <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</span>
    <div className="flex-1 h-px bg-accent-100" />
  </div>
);

// ─── Table header cell helper ────────────────────────────────────────────────
// eslint-disable-next-line react/prop-types
const TH = ({ children, className = "" }) => (
  <TableCell className={`px-4 py-2.5 border text-sm font-semibold text-primary uppercase tracking-wider whitespace-nowrap ${className}`}>
    {children}
  </TableCell>
);

// eslint-disable-next-line react/prop-types
const TransportSummaryChip = ({ watch }) => {
  const vehicle = watch("form.vehicle_no");
  const transporter = watch("form.transporter_name");
  const mode = watch("form.mode_of_transport");
  const distance = watch("form.trans_distance");
  const hasAny = vehicle || transporter || mode || distance;
  if (!hasAny) {
    return (
      <div className="text-xs text-muted-foreground italic px-2 py-1">
        Enter via E-Way Bill button on the voucher list
      </div>
    );
  }
  const parts = [
    mode && `${mode}`,
    vehicle && `Vehicle: ${vehicle}`,
    transporter && `Transporter: ${transporter}`,
    distance && `${distance} km`,
  ].filter(Boolean);
  return (
    <div className="text-xs px-2 py-1 rounded bg-muted/50 border" title="Edit via E-Way Bill button on voucher list">
      {parts.join("  •  ")}
    </div>
  );
};

const SalesVoucherAdd = () => {
  const { toast } = useToast();
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();

  const {
    register: originalRegister,
    handleSubmit,
    control,
    reset,
    watch,
    setValue,
    getValues,
    setFocus,
    formState: { errors, isDirty },
  } = useForm({
    defaultValues: {
      form: {
        date1: new Date().toISOString().split("T")[0],
        invoice_date: new Date().toISOString().split("T")[0],
        billno: "",
        gst_billno: "",
        ldgr: "",
        sales_person: "",
        sales_person2: "",
        place_of_supply: "WB",
        ret_status: false,
        remarks: "",
        freight_charge: 0,
        mrp: 0,
        discount: 0,
        gst_type: "gst1",
        sgst_per: 0,
        cgst_per: 0,
        igst_per: 0,
        tcs_per: 0,
        other_charge: 0,
        exhibition_profile: "",
        customer_order: "",
        advance_deducted: 0,
        old_gold_purchase: "",
        old_gold_adjusted: 0,
      },
      hsn: "711319",
      salesvouitem_set: [],
      // "mainItem" = the live input row for the main jewellery piece
      mainItem: {
        item: "", item_desc: "",
        pcs: 0, gw: 0,
        making: 0, making_type: "", discount: 0, value: 0, remarks: "",
      },
      // "details" = the live input row for manual (non-barcode) items
      details: {
        packet: "", item: "", pcs: 0, ct: 0, gw: 0,
        metal_purity: "", loss: 0, tunch: 0, fine_wt: 0, rate: 0, value: 0,
      },
    },
  });

  const bankDefaultValue = {
    amount: "", payment_mode: "NEFT", chq_no: "", bank_name: "", ledger: "", ledger_name: "", chq_date: "",
  };

  // Monkey-patching register to trigger formula recalculation on any change
  const register = (name, options = {}) => {
    const registered = originalRegister(name, options);
    return {
      ...registered,
      onChange: (e) => {
        setCalculate(prev => prev + 1);
        options?.onChange?.(e);
        registered.onChange?.(e);
      },
    };
  };

  // Bank details: add row on Tab from last field
  const handleKeyDown = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const bnk = { ...getValues("bank") };
      if (!bnk.amount || Number(bnk.amount) <= 0) { setFocus("bank.amount"); return; }
      setBankDetails(prev => [...prev, { ...bnk }]);
      reset({ form: { ...getValues('form') }, bank: { ...bankDefaultValue }, salesvouitem_set: [...getValues('salesvouitem_set')], details: { ...getValues('details') } });
      setFocus("bank.amount");
    }
  };

  // Manual item row: add on Tab from last field
  const handleKeyDownDetails = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      handleAddManualRow();
    }
  };

  const { append, remove, replace } = useFieldArray({
    control,
    name: "salesvouitem_set",
  });

  // ── State ──────────────────────────────────────────────────────────────────
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [rs, setRows] = useState([]);              // manual / raw items
  const [bankdetails, setBankDetails] = useState([]);
  const [calculate, setCalculate] = useState(0);
  const [cashledger, setCashLedger] = useState([]);
  const [retailStateCode, setRetailStateCode] = useState("");
  const [isExhibitionRetail, setIsExhibitionRetail] = useState(false);

  // ── Server-side data via React Query ───────────────────────────────────────
  // Replaces 8 useState buckets and the manual `cancelled` race-guard flag.
  // The query-key on `useSalesVoucherForEdit(id)` means switching between two
  // PV ids in quick succession is structurally race-free: the slower request
  // can never land its data over the faster one.
  const initialDataQuery = useSaleVoucherInitialData();
  const exhibitionsQuery = useExhibitions();
  const goldRateMapQuery = useTodayGoldRateMap();
  const systemSettingsQuery = useSystemSettings();
  const bankLedgersQuery = useBankLedgers();
  const activeOfferQuery = useActiveOffer();
  const editQuery = useSalesVoucherForEdit(id);
  const saveMutation = useSaveSalesVoucherMutation(id);
  const saving = saveMutation.isPending;

  // Aliases that keep the JSX downstream unchanged (~200 references). The
  // shape matches what the old useState slots held.
  const statesData = initialDataQuery.data?.states ?? [];
  const salespersonData = initialDataQuery.data?.salespersons ?? [];
  const hsns = initialDataQuery.data?.hsns ?? [];
  const mainItemData = initialDataQuery.data?.items ?? [];
  const packets = initialDataQuery.data?.packets ?? [];
  const purityData = initialDataQuery.data?.purity ?? [];
  const bankLedgers = bankLedgersQuery.data ?? [];
  const exhibitions = exhibitionsQuery.data ?? [];
  const goldRates = goldRateMapQuery.data ?? {};
  const activeOffer = activeOfferQuery.data ?? null;
  // Customers can still be locally mutated by the party-name search effect, so
  // we keep a useState — initial data flows in via a hydrate effect below.
  const [customers, setCustomers] = useState([]);
  const autoCalcEnabled = !!systemSettingsQuery.data?.bill_total_auto_calc;
  const [customerCashInfo, setCustomerCashInfo] = useState(null); // { cash_received, limit, remaining }
  const [customerOrders, setCustomerOrders] = useState([]);       // orders with available advance
  const [selectedOrder, setSelectedOrder] = useState(null);       // the linked CustomerOrder object
  const [onAccountReceipts, setOnAccountReceipts] = useState([]); // unlinked RCPT vouchers for direct advance
  const [loadingOnAccount, setLoadingOnAccount] = useState(false);
  const [selectedReceiptIds, setSelectedReceiptIds] = useState([]); // PKs chosen for direct advance
  const [customerPurchases, setCustomerPurchases] = useState([]); // old gold purchases with available balance
  const [selectedPurchase, setSelectedPurchase] = useState(null); // the linked PurchaseVoucher object
  // Inline old-gold exchange rows — these become a sale-owned Customer
  // PurchaseVoucher on submit. Each row: { item, item_name, description,
  // purity, pcs, ct, gw, loss, tunch, fine_wt, uom, rate, value }.
  // Items must be type R (Raw) or S (Stone).
  const [inlineOldGold, setInlineOldGold] = useState([]);
  const blankInlineRow = () => ({
    item: "", item_name: "", description: "", purity: "",
    pcs: "", ct: "", gw: "", loss: "", tunch: "", fine_wt: 0,
    uom: "Gm", rate: "", value: 0,
  });
  const recalcInlineRow = (row) => {
    const gw = parseFloat(row.gw || 0);
    const loss = parseFloat(row.loss || 0);
    const tunch = parseFloat(row.tunch || 0);
    const rate = parseFloat(row.rate || 0);
    const pcs = parseFloat(row.pcs || 0);
    const ct = parseFloat(row.ct || 0);
    const fine_wt = +(((gw - loss) * tunch) / 100).toFixed(3);
    const uom = row.uom || "Gm";
    let value;
    if (uom === "Pcs")      value = +(rate * pcs).toFixed(2);
    else if (uom === "Ct")  value = +(rate * ct).toFixed(2);
    else if (tunch > 0)     value = +(rate * fine_wt).toFixed(2);
    else                    value = +(rate * (gw - loss)).toFixed(2);
    return { ...row, fine_wt, value };
  };
  const updateInlineRow = (idx, patch) => {
    setInlineOldGold(prev => prev.map((r, i) => i === idx ? recalcInlineRow({ ...r, ...patch }) : r));
    markTableDirty();
    setCalculate(prev => prev + 1);
  };
  const inlineOldGoldTotal = inlineOldGold.reduce((s, r) => s + (parseFloat(r.value) || 0), 0);
  // Mirror the inline-old-gold total into a real form field so BillSummaryPanel
  // can `register()` it without blowing up (panel always calls register(row.field)).
  useEffect(() => {
    setValue("form.inline_old_gold_total", inlineOldGoldTotal);
  }, [inlineOldGoldTotal, setValue]);
  const [b2bPricelist, setB2bPricelist] = useState(null);         // null = retail mode; object = B2B pricelist data
  const [retailDiscountPricelist, setRetailDiscountPricelist] = useState(null); // retail discount pricelist for Apply Discount
  // Both flags are derived from React Query data above. `enableGstBill` honours
  // either source (the bundled initial-data payload OR the system settings) —
  // matches the legacy behaviour where the system-settings fetch could
  // override the initial-data value.
  const enableGstBill =
    !!(systemSettingsQuery.data?.enable_gst_bill ?? initialDataQuery.data?.enable_gst_bill);
  const [showManualItems, setShowManualItems] = useState(false);  // section 3 toggle
  // Resolved item for the current manual input row
  const [detailItem, setDetailItem] = useState(null);
  // Display name shown in the item text box (item_name, not short_code)
  const [detailItemDisplay, setDetailItemDisplay] = useState("");
  // Display name for the main item input
  const [mainItemDisplay, setMainItemDisplay] = useState("");
  // Ref to focus the packet field after a row is added
  const packetInputRef = useRef(null);
  const mainItemInputRef = useRef(null);
  const formRef = useRef(null);
  useEnterAsTab(formRef);

  // ── Watch bank payment mode for conditional field rendering ──────────────
  const bankPaymentMode = watch("bank.payment_mode") || "NEFT";

  // ── Watch manual detail fields ─────────────────────────────────────────────
  const detailPacket   = watch("details.packet");
  const detailPcs      = watch("details.pcs");
  const detailCt       = watch("details.ct");
  const detailGw       = watch("details.gw");
  const detailRate     = watch("details.rate");
  const detailPurity   = watch("details.metal_purity");

  // Helper: compute value from rate × qty based on UOM
  const computeValue = (rate, uom, pcs, ct, gw) => {
    const r = parseFloat(rate) || 0;
    if (uom === "Pcs") return +(r * (parseFloat(pcs) || 0)).toFixed(2);
    if (uom === "Ct")  return +(r * (parseFloat(ct)  || 0)).toFixed(2);
    // Default / "Gm"
    return +(r * (parseFloat(gw) || 0)).toFixed(2);
  };

  // Auto-load item + rate when packet changes; lock/unlock item field
  useEffect(() => {
    if (!detailPacket) {
      // Packet cleared — only reset if it was previously set by a packet
      if (detailItem) {
        setDetailItem(null);
        setDetailItemDisplay("");
        setValue("details.item", "");
        setValue("details.rate", 0);
        setValue("details.value", 0);
      }
      return;
    }
    const pkt = packets.find(p => p.pckt_no === detailPacket);
    if (pkt?.stone_item_id) {
      const item = pkt.stone_item_id;
      // B2B: use pricelist override or wholesale rate; retail: use rate_for_retail
      const b2bRate = b2bPricelist ? getB2bStoneRate(pkt.pckt_no) : null;
      const rate = b2bRate != null ? b2bRate : (pkt.rate_for_retail ?? 0);
      setValue("details.item", item.short_code);
      setValue("details.rate", rate);
      setDetailItem(item);
      setDetailItemDisplay(item.item_name);
      // Calculate initial value immediately
      const pcs = getValues("details.pcs");
      const ct  = getValues("details.ct");
      const gw  = getValues("details.gw");
      setValue("details.value", computeValue(rate, item.uom, pcs, ct, gw));
    }
    // detailItem/getValues/getB2bStoneRate read fresh inside the effect; we
    // only want it to run when packet/packets/b2bPricelist actually change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailPacket, packets, setValue, b2bPricelist]);

  // Recalculate value whenever rate or qty fields change
  useEffect(() => {
    if (!detailItem) return;
    setValue("details.value", computeValue(detailRate, detailItem.uom, detailPcs, detailCt, detailGw));
  }, [detailRate, detailPcs, detailCt, detailGw, detailItem, setValue]);

  // Handler for manual item name input (when no packet is selected)
  const handleItemDisplayChange = (e) => {
    const typed = e.target.value;
    setDetailItemDisplay(typed);
    // Resolve short_code from the typed name
    const found = mainItemData.find(m => m.item_name === typed);
    if (found) {
      setValue("details.item", found.short_code);
      setDetailItem(found);
    } else {
      setValue("details.item", "");
      setDetailItem(null);
    }
  };

  // Derived flags from the resolved item
  const detailUom  = detailItem?.uom        ?? null; // "Gm" | "Pcs" | "Ct" | null
  const detailType = detailItem?.item_type  ?? null; // "M" | "R" | "S" | "O" | "C" | null
  const isRawItem  = detailType === "R";
  const itemLockedByPacket = !!detailPacket;
  // UOM-based field disabling (pcs disabled for Raw type items)
  const pcsDisabled = isRawItem;
  const ctDisabled  = detailUom === "Gm" || detailUom === "Pcs";
  const gwDisabled  = detailUom === "Pcs" || detailUom === "Ct";

  // Clear disabled UOM fields and metal fields when item changes
  useEffect(() => {
    if (ctDisabled)  setValue("details.ct", 0);
    if (gwDisabled)  setValue("details.gw", 0);
    if (!isRawItem) {
      setValue("details.metal_purity", "");
      setValue("details.loss", 0);
      setValue("details.tunch", 0);
      setValue("details.fine_wt", 0);
    } else {
      // Auto-fill metal_purity from the parent main item's default_purity
      const lastMainItem = rs[rs.length - 1];
      const parentInfo = mainItemData.find(m => m.short_code === lastMainItem?.item);
      if (parentInfo?.default_purity) {
        setValue("details.metal_purity", parentInfo.default_purity);
      }
    }
    // ct/gw/isRawItem are derived from detailItem (already in deps); mainItemData
    // is a stable useMemo; rs/setValue read fresh on each run. Effect intentionally
    // only fires on detailItem change to avoid clobbering manual entries.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailItem]);

  // Auto-fill rate from gold rates when purity is selected on a raw/gold item
  // (must live after isRawItem declaration to avoid TDZ error)
  useEffect(() => {
    if (!isRawItem || !detailPurity) return;
    // B2B: apply tunch-adjusted rate; retail: use standard gold rate
    const b2bRate = b2bPricelist ? getB2bGoldRate(detailPurity) : null;
    const rate = b2bRate != null ? b2bRate : goldRates[detailPurity];
    if (rate !== undefined) {
      setValue("details.rate", rate);
    }
    // getB2bGoldRate is a closure over b2bPricelist (already in deps); setValue stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailPurity, isRawItem, goldRates, b2bPricelist]);

  // ── React-Query-driven hydrate effects (replaces the old mega useEffect) ────
  // The legacy effect ran ~160 lines of nested Promise.all + a manual
  // `cancelled` flag to guard against the Strict-Mode double-mount race.
  // Each React Query hook above takes care of fetching + caching; these small
  // effects just hydrate form state when their source query resolves.
  // Race-safety: switching ids cannot land stale data — React Query keys
  // responses by id, so the slower request is discarded automatically.

  // 1) Hydrate masters-derived form fields when bundled initial data lands.
  useEffect(() => {
    const d = initialDataQuery.data;
    if (!d) return;
    setCustomers(d.ledgers || []);
    if (d.billno) setValue("form.billno", d.billno);
    if (d.enable_gst_bill) setValue("form.gst_billno", d.gst_billno || "");
    if (d.retail_state_code) setRetailStateCode(d.retail_state_code);
    if (d.is_exhibition) setIsExhibitionRetail(true);
  }, [initialDataQuery.data, setValue]);

  // 2) Surface initial-data errors as a toast (matches old behaviour).
  useEffect(() => {
    if (!initialDataQuery.error) return;
    toast({
      title: "Error",
      description:
        initialDataQuery.error.message ||
        "Failed to load form data. Please ensure you are logged in and have selected a retail location.",
      variant: "destructive",
    });
  }, [initialDataQuery.error, toast]);

  // 3) Pre-select the default exhibition profile when exhibitions land.
  useEffect(() => {
    if (!exhibitionsQuery.data) return;
    const defaultExh = exhibitionsQuery.data.find((e) => e.is_active);
    if (defaultExh) setValue("form.exhibition_profile", String(defaultExh.id));
  }, [exhibitionsQuery.data, setValue]);

  // 4) Hydrate the form from the edit-record once it arrives. React Query
  //    keys by id, so the Strict-Mode double-mount race the old code guarded
  //    against with `cancelled` is now impossible.
  useEffect(() => {
    if (!id || !editQuery.data) return;
    const data = editQuery.data;
    const formData = {
      form: {
        ...data,
        salesvouitem_set: JSON.parse(JSON.stringify(data.salesvouitem_set ?? [])),
      },
    };
    Object.keys(formData.form).forEach((key) => {
      if (key === 'salesvouitem_set') {
        // Use replace() so re-running this effect cannot duplicate rows.
        replace(formData.form[key] || []);
      } else if (key !== 'salesvouitemdetails_set' && key !== 'bank_details') {
        setValue(`form.${key}`, formData.form[key]);
      }
    });
    if (data.bank_details) {
      setBankDetails(data.bank_details);
    }
    if (data.salesvouitemdetails_set?.length) {
      setRows(data.salesvouitemdetails_set);
    }
    if (data.inline_old_gold_pv?.rows?.length) {
      setInlineOldGold(data.inline_old_gold_pv.rows.map((r) => recalcInlineRow({
        item: r.item || "",
        item_name: r.item_name || r.item || "",
        description: r.item_name || "",
        purity: r.purity || "",
        pcs: r.pcs ?? "",
        ct: r.ct ?? "",
        gw: r.gw ?? "",
        loss: r.loss ?? "",
        tunch: r.tunch ?? "",
        uom: "Gm",
        rate: r.rate ?? "",
      })));
    }
    // Restore applied advance receipts AND fetch any still-unlinked receipts
    // for the loaded customer so advances can be added/removed in edit mode.
    const appliedReceipts = Array.isArray(data.applied_advance_receipts)
      ? data.applied_advance_receipts : [];
    if (appliedReceipts.length > 0) {
      setSelectedReceiptIds(appliedReceipts.map((r) => r.id));
    }
    if (data.ldgr) {
      setLoadingOnAccount(true);
      fetchUnlinkedReceipts(data.ldgr).then((res) => {
        setLoadingOnAccount(false);
        const unlinked = res.success ? res.data : [];
        const merged = [
          ...appliedReceipts,
          ...unlinked.filter((u) => !appliedReceipts.some((a) => a.id === u.id)),
        ];
        setOnAccountReceipts(merged);
      });
    } else if (appliedReceipts.length > 0) {
      setOnAccountReceipts(appliedReceipts);
    }
    // Restore old gold purchase link (still sequential — needs ldgr from voucher data)
    if (data.old_gold_purchase && data.ldgr) {
      fetchCustomerPurchasesByLedger(data.ldgr).then((res) => {
        if (res.success) {
          setCustomerPurchases(res.data);
          const pv = res.data.find((p) => p.id === data.old_gold_purchase);
          setSelectedPurchase(pv ?? null);
        }
      });
    }
    reset(getValues(), { keepValues: true, keepDirty: false });
    resetTableDirty();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, editQuery.data]);

  // ── Formulas ───────────────────────────────────────────────────────────────
  const hsn_current = watch('hsn');
  const place_of_supply = watch('form.place_of_supply');
  const watchFields = watch("salesvouitem_set");
  const party_name = watch('form.ldgr_name');

  const formulas = {
    // making_value is computed imperatively in the recalc effect (needs goldRates state)
    amount: "SUM(main_item_set.amount) + making_value",
  };
  const sub_formulas = {
    amount: "uom === 'Ct' ? ct * rate : uom === 'Pcs' ? pcs * rate : gw * rate",
    fine_wt: "gw * tunch / 100",
  };

  const mrp_formula = "SUM(salesvouitem_set.amount) + SUM(rs.value)";
  const taxable_value_formula = "SUM(salesvouitem_set.amount) + SUM(rs.value) - discount + other_charge + freight_charge";
  const total_incl_gst_formula = `(${taxable_value_formula}) * (1 + cgst_per / 100 + igst_per / 100 + sgst_per / 100)`;
  const tcs_amt_formula = `tcs_per * (${total_incl_gst_formula})`;
  const main_formulas = {
    mrp: mrp_formula,
    taxable_value: taxable_value_formula,
    cgst_amt: `(${taxable_value_formula}) * (cgst_per / 100)`,
    igst_amt: `(${taxable_value_formula}) * igst_per / 100`,
    sgst_amt: `(${taxable_value_formula}) * sgst_per / 100`,
    total_incl_gst: total_incl_gst_formula,
    tcs_amt: tcs_amt_formula,
    total_bill_value: `${tcs_amt_formula} + ${total_incl_gst_formula} + round_off`,
  };

  const evaluateFormula = (formula, data) => {
    try {
      let processedFormula = formula.replace(/SUM\(([^)]+)\)/g, (match, path) => {
        const parts = path.trim().split('.');
        let array = data[parts[0]];
        if (!Array.isArray(array)) return 0;
        return array.reduce((acc, item) => parseFloat(acc) + parseFloat(item[parts[1]] || 0), 0);
      });
      processedFormula = processedFormula.replace(/(\b[A-Za-z_][A-Za-z0-9_]*\b)|('[^']*')|(\d+)/g, (match, variable, quoted, number) => {
        if (quoted) return quoted;
        if (number) return number;
        if (data.hasOwnProperty(variable)) {
          const value = data[variable];
          return typeof value === "number" ? `(${value})` : `'${value}'`;
        }
        return "0";
      });
      return new Function(`return ${processedFormula};`)()?.toFixed(2);
    } catch (error) {
      console.error("Formula evaluation error:", error);
      return "";
    }
  };

  // Party name debounced search
  const partyNameTimerRef = useRef(null);
  useEffect(() => {
    if (partyNameTimerRef.current) clearTimeout(partyNameTimerRef.current);
    partyNameTimerRef.current = setTimeout(async () => {
      const result = await getLedgers({ type: "CO", search: party_name });
      if (result.success) setCustomers(result.data.results);
    }, 300);
    return () => clearTimeout(partyNameTimerRef.current);
  }, [party_name]);

  // Pre-fill customer when redirected back from the Add Ledger page
  useEffect(() => {
    const ldgr     = searchParams.get("ldgr");
    const ldgrName = searchParams.get("ldgr_name");
    if (ldgr && ldgrName) {
      setValue("form.ldgr", ldgr);
      setValue("form.ldgr_name", ldgrName);
      setCustomers((prev) => {
        const already = prev.some((c) => String(c.id) === String(ldgr));
        return already ? prev : [{ id: ldgr, ac_name: ldgrName, mobile1: "" }, ...prev];
      });
    }
  }, [searchParams, setValue]);

  // Recalculate formulas whenever anything changes
  useEffect(() => {
    const form = { ...getValues('form'), salesvouitem_set: getValues('salesvouitem_set'), rs };

    getValues('salesvouitem_set').forEach((row, index) => {
      // Recalculate sub-item amounts
      getValues(`salesvouitem_set.${index}.main_item_set`)?.forEach((data, sub_index) => {
        Object.keys(sub_formulas).forEach(column => {
          setValue(`salesvouitem_set.${index}.main_item_set.${sub_index}.${column}`, evaluateFormula(sub_formulas[column], data));
        });
        // When tunch is entered for gold/raw sub-items, rate must be 0 (tunch-based pricing)
        if (Number(data.tunch || 0) > 0 && (data.item_type === 'R' || (data.item || '').toUpperCase() === 'GOLD')) {
          setValue(`salesvouitem_set.${index}.main_item_set.${sub_index}.rate`, 0);
        }
      });

      // Calculate making_value based on making_type
      // - 'val'    → flat amount entered by user
      // - 'per_nw' → NW of gold × (making% / 100) × gold rate for that purity
      const making     = parseFloat(row.making) || 0;
      const makingType = row.making_type || '';
      const purity     = row.purity || '';

      // Read sub-items from getValues (picks up user-edited rates)
      const subItems = getValues(`salesvouitem_set.${index}.main_item_set`) || row.main_item_set || [];
      const goldSub  = Array.isArray(subItems)
        ? subItems.find(s => (s.item || '').toUpperCase() === 'GOLD')
        : null;

      // Gold rate: prefer the (possibly edited) gold sub-item rate; fall back to system rate
      const goldRate = parseFloat(goldSub?.rate) || parseFloat(goldRates[purity]) || 0;

      // NW of gold: prefer the barcode's nw; if null/0, derive from gold sub-item gw
      let nw = parseFloat(row.nw) || 0;
      if (!nw && goldSub) nw = parseFloat(goldSub.gw) || 0;

      let makingVal;
      if (makingType === 'val') {
        makingVal = making;
      } else if (makingType === 'per_nw') {
        // making = percentage (e.g. 30 means 30%)
        makingVal = nw * (making / 100) * goldRate;
      } else {
        makingVal = making;
      }
      makingVal = Math.floor(makingVal);
      setValue(`salesvouitem_set.${index}.making_value`, makingVal);

      // Calculate item amount using updated making_value
      const updatedRow = { ...row, making_value: makingVal };
      setValue(`salesvouitem_set.${index}.amount`, Math.floor(evaluateFormula(formulas.amount, updatedRow)));
    });

    Object.keys(main_formulas).forEach(col => {
      setValue(`form.${col}`, evaluateFormula(main_formulas[col], form));
    });
    // formulas/main_formulas/sub_formulas are stable module-scope objects;
    // getValues is a stable RHF ref. Intentionally elided to keep the hot
    // formula-recalc loop bounded to actual input changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calculate, setValue, watchFields, rs, goldRates]);

  // HSN → set GST rates based on place of supply vs retail state
  useEffect(() => {
    const hsn_ = hsns.find(e => e.hsn_no === hsn_current);
    if (!hsn_) return;
    // Use retailStateCode from initial data (same code system as place_of_supply options).
    // Fall back to sessionStorage only if initial data hasn't loaded yet.
    const retailState = retailStateCode || sessionStorage.getItem('state_code') || "";
    const isIntraState = place_of_supply === retailState;
    setValue('form.sgst_per', isIntraState ? parseFloat(hsn_.sgst) : 0.0);
    setValue('form.cgst_per', isIntraState ? parseFloat(hsn_.cgst) : 0.0);
    setValue('form.igst_per', isIntraState ? 0.0 : parseFloat(hsn_.igst));
    setCalculate(prev => prev + 1);
    // hsns is a derived array (initialDataQuery.data?.hsns); setValue stable.
    // The effect intentionally fires only when its actual triggers change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hsn_current, place_of_supply, retailStateCode]);

  // ── B2B pricelist helpers ───────────────────────────────────────────────────

  /** Find the best matching making rule from pricelist (most specific wins). */
  const findB2bMakingRule = (purity, itemCode) => {
    if (!b2bPricelist?.making_entries?.length) return null;
    const entries = b2bPricelist.making_entries;
    // Priority: purity+item > purity-only > item-only > default (both null)
    return (
      entries.find(e => e.purity === purity && e.item === itemCode) ||
      entries.find(e => e.purity === purity && !e.item) ||
      entries.find(e => !e.purity && e.item === itemCode) ||
      entries.find(e => !e.purity && !e.item) ||
      null
    );
  };

  /** Get B2B stone rate for a packet: stone_override > wholesale_packet_rates > fallback. */
  const getB2bStoneRate = (pcktNo) => {
    if (!b2bPricelist) return null;
    const override = b2bPricelist.stone_overrides?.find(s => s.packet === pcktNo);
    if (override) return override.rate;
    const wholesale = b2bPricelist.wholesale_packet_rates?.[pcktNo];
    if (wholesale != null) return wholesale;
    return null;
  };

  /** Get B2B gold rate for a purity using tunch markup.
   *  baseRate = retail rate for that purity (from goldRates state).
   *  gwPer   = purity's gold weight % (e.g. 91.67 for 22K). */
  const getB2bGoldRate = (purityName) => {
    if (!b2bPricelist) return null;
    const tunchEntry = b2bPricelist.tunch_entries?.find(t => t.purity === purityName);
    if (!tunchEntry) return null;
    const baseRate = goldRates[purityName];
    if (!baseRate) return null;
    const purityObj = purityData.find(p => p.purity === purityName);
    if (!purityObj) return null;
    const gwPer = parseFloat(purityObj.gw_per);
    const tunchPct = parseFloat(tunchEntry.tunch_percent);
    // pureRate = baseRate / (gwPer / 100), then apply (gwPer + tunch) / 100
    const pureRate = baseRate / (gwPer / 100);
    return Math.round(pureRate * ((gwPer + tunchPct) / 100));
  };

  /** Apply B2B pricelist overrides to a barcode item before appending. */
  const applyB2bOverrides = (item) => {
    if (!b2bPricelist) return item;
    const overridden = { ...item };

    // Override making charges
    const purity = item.metal_purity || item.purity;
    const itemCode = item.item;
    const makingRule = findB2bMakingRule(purity, itemCode);
    if (makingRule) {
      overridden.making_type = makingRule.making_type;
      overridden.making = parseFloat(makingRule.making_value);
    }

    // Override stone rates in main_item_set
    if (item.main_item_set?.length) {
      overridden.main_item_set = item.main_item_set.map(sub => {
        const updated = { ...sub };
        // Stone items (non-raw): override rate from pricelist
        if (sub.pckt_no) {
          const b2bRate = getB2bStoneRate(sub.pckt_no);
          if (b2bRate != null) {
            updated.rate = b2bRate;
            // Recalculate amount
            if (sub.uom === 'Ct') updated.amount = +(b2bRate * (parseFloat(sub.ct) || 0)).toFixed(2);
            else updated.amount = +(b2bRate * (parseFloat(sub.gw) || 0)).toFixed(2);
          }
        }
        // Gold/raw sub-items: override rate using tunch
        if (sub.item_type === 'R' && sub.metal_purity) {
          const b2bRate = getB2bGoldRate(sub.metal_purity);
          if (b2bRate != null) {
            updated.rate = b2bRate;
            updated.amount = +(b2bRate * (parseFloat(sub.gw) || 0)).toFixed(2);
          }
        }
        return updated;
      });
    }

    return overridden;
  };

  // ── Barcode scan handler ───────────────────────────────────────────────────
  const barcodeFetchingRef = useRef(false);
  const handleBlur = async () => {
    if (barcodeFetchingRef.current) return;          // guard against double-fire
    const { barcode, hsn } = getValues();
    if (!barcode?.trim()) return;   // blank barcode is fine — manual items don't need one

    // Prevent duplicate barcodes in the same bill
    const existing = getValues("salesvouitem_set") || [];
    if (existing.some(r => r.barcode === barcode.trim())) {
      toast({
        title: "Duplicate barcode",
        description: `Barcode ${barcode.trim()} is already in this bill.`,
        variant: "destructive",
      });
      setValue("barcode", "");
      return;
    }

    barcodeFetchingRef.current = true;
    try {
      const selectedLdgr = getValues("form.ldgr");
      const data = await fetchBarcodeDetail(barcode, hsn, selectedLdgr);
      if (data.success) {
        const item = b2bPricelist ? applyB2bOverrides(data.data) : data.data;
        append(item);
      } else {
        // Surface backend reservation/validation message verbatim when present.
        const detail = data.error?.detail || (typeof data.error === "string" ? data.error : null);
        toast({
          title: detail ? "Barcode reserved" : "Barcode not found",
          description: detail || JSON.stringify(data.error) || "Server error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      // Clear the input AFTER the fetch completes so the second blur sees an empty field
      setValue("barcode", "");
      barcodeFetchingRef.current = false;
    }
  };

  // ── Bank detail handlers ───────────────────────────────────────────────────
  const handleAddBank = () => {
    const bnk = { ...getValues("bank") };
    if (!bnk.amount || Number(bnk.amount) <= 0) return;
    setBankDetails(prev => [...prev, { ...bnk }]);
    reset({ form: { ...getValues('form') }, bank: { ...bankDefaultValue }, salesvouitem_set: [...getValues('salesvouitem_set')], details: { ...getValues('details') } });
    setFocus("bank.amount");
  };

  const handleDeleteBank = (index) => setBankDetails(prev => prev.filter((_, i) => i !== index));
  const handleEditBank = (index) => {
    const bank_details = bankdetails[index];
    Object.keys(bank_details).forEach(key => setValue(`bank.${key}`, bank_details[key]));
    reset({ form: getValues('form'), bank: bank_details, salesvouitem_set: [...getValues('salesvouitem_set')], details: { ...getValues('details') } });
    setBankDetails(prev => prev.filter((_, i) => i !== index));
  };

  // ── Manual item handlers ───────────────────────────────────────────────────

  /** Add the current mainItem form group as a new top-level row in rs. */
  const handleAddMainItem = () => {
    const newMain = getValues("mainItem");
    if (!newMain.item) { toast({ title: "Please select a main item first" }); return; }
    setRows(prev => [
      ...prev,
      { ...newMain, item_name: mainItemDisplay || newMain.item, details_set: [] },
    ]);
    markTableDirty();
    setMainItemDisplay("");
    setValue("mainItem", {
      item: "", item_desc: "", finish: false,
      pcs: 0, ct: 0, gw: 0,
      rate: 0, making: 0, making_type: "", discount: 0, value: 0, remarks: "",
    });
    setCalculate(prev => prev + 1);
    // Move focus to the sub-item packet field
    setTimeout(() => packetInputRef.current?.focus(), 0);
  };

  const handleKeyDownMainItem = (e) => {
    if (e.key === "Tab") { e.preventDefault(); handleAddMainItem(); }
  };

  const handleDeleteMainItem = (mainIdx) => {
    setRows(prev => prev.filter((_, i) => i !== mainIdx));
    markTableDirty();
    setCalculate(prev => prev + 1);
  };

  const handleDeleteSubItem = (mainIdx, subIdx) => {
    setRows(prev => {
      const updated = [...prev];
      updated[mainIdx] = {
        ...updated[mainIdx],
        details_set: updated[mainIdx].details_set.filter((_, i) => i !== subIdx),
      };
      return updated;
    });
    markTableDirty();
    setCalculate(prev => prev + 1);
  };

  /** Add the current details form group as a sub-item under the last main item. */
  const handleAddManualRow = () => {
    if (rs.length === 0) {
      toast({
        title: "Add a main item first",
        description: "Enter the jewellery piece above before adding its material details.",
      });
      return;
    }
    const newItem = getValues("details");
    if (!newItem.item) { toast({ title: "No item selected" }); return; }
    setRows(prev => {
      const updated = [...prev];
      const lastIdx = updated.length - 1;
      updated[lastIdx] = {
        ...updated[lastIdx],
        details_set: [
          ...(updated[lastIdx].details_set || []),
          { ...newItem, item_name: detailItemDisplay || newItem.item },
        ],
      };
      return updated;
    });
    markTableDirty();
    setDetailItem(null);
    setDetailItemDisplay("");
    reset({
      form: { ...getValues('form') },
      bank: { ...getValues('bank') },
      salesvouitem_set: [...getValues('salesvouitem_set')],
      hsn: getValues('hsn'),
      mainItem: { ...getValues('mainItem') },
      details: { packet: "", item: "", pcs: 0, ct: 0, gw: 0, metal_purity: "", loss: 0, tunch: 0, fine_wt: 0, rate: 0, value: 0 },
    });
    setCalculate(prev => prev + 1);
    // Return focus to packet field for the next sub-item entry
    setTimeout(() => packetInputRef.current?.focus(), 0);
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSalesVoucherSubmit = async () => {
    try {
      const data = getValues("form");
      data.salesvouitem_set = getValues("salesvouitem_set");    // barcode items
      data.salesvoumanualitems_set = rs;                        // manual items (main + nested details_set)
      // Flat list kept for backward-compat until backend is updated
      data.salesvouitemdetails_set = rs.flatMap(m => m.details_set || []);
      data.bank_details = bankdetails;

      // ── Compute due_amt ──────────────────────────────────────────────────
      const grandTotal     = parseFloat(data.total_bill_value || 0);
      const cashPaid       = parseFloat(data.cash || 0);
      const bankPaid       = bankdetails.reduce((s, b) => s + parseFloat(b.amount || 0), 0);
      const advDeducted    = parseFloat(data.advance_deducted || 0);
      const oldGoldAdj     = parseFloat(data.old_gold_adjusted || 0);
      const inlineOldGoldVal = inlineOldGold.reduce((s, r) => s + (parseFloat(r.value) || 0), 0);
      data.due_amt         = Math.max(0, grandTotal - cashPaid - bankPaid - advDeducted - oldGoldAdj - inlineOldGoldVal).toFixed(2);
      // Inline old gold rows (server creates/updates a sale-owned Customer PV)
      data.inline_old_gold_items = inlineOldGold
        .filter(r => r.item && (parseFloat(r.value) || 0) > 0)
        .map(r => ({
          item: r.item,
          description: r.description || "",
          purity: r.purity || null,
          pcs: parseInt(r.pcs || 0, 10),
          ct: parseFloat(r.ct || 0),
          gw: parseFloat(r.gw || 0),
          loss: parseFloat(r.loss || 0),
          tunch: parseFloat(r.tunch || 0),
          uom: r.uom || "Gm",
          rate: parseFloat(r.rate || 0),
        }));
      // Send null when no order/purchase linked (avoid empty-string FK)
      if (!data.customer_order) data.customer_order = null;
      if (!data.old_gold_purchase) data.old_gold_purchase = null;
      // Direct on-account advance: only send when no order is linked
      if (!data.customer_order) {
        // Always send the list (even empty) so the backend can reconcile allocations on update
        data.advance_receipt_ids = selectedReceiptIds;
      } else {
        delete data.advance_receipt_ids;
      }

      // ── Section 269ST: Cash Limit Compliance (₹2,00,000) ────────────────
      // Under Section 269ST of the Income Tax Act, no person can accept ₹2L or
      // more in cash from a single person in a day. Violation = 100% penalty.
      const cashAmt = parseFloat(data.cash || 0);
      if (cashAmt > 200000) {
        toast({
          title: "⚠️ Cash Limit Exceeded — Section 269ST",
          description: `Cash of ₹${cashAmt.toLocaleString("en-IN")} exceeds the ₹2,00,000 limit. Accepting this amount in cash is a violation of Section 269ST of the Income Tax Act and carries a 100% penalty. Please collect via cheque/bank transfer.`,
          variant: "destructive",
        });
        return;
      }

      // useMutation's `isPending` flag drives the `saving` button state; on
      // success it invalidates the list cache so the Sales list refreshes
      // without a manual reload, and seeds the per-record cache so reopening
      // the same voucher for edit is instant.
      try {
        await saveMutation.mutateAsync(data);
        toast({ title: id ? "Sales voucher updated!" : "Form submitted successfully!" });
        setTimeout(() => navigate("/sales/list/"), 500);
      } catch (mutationError) {
        const payload = mutationError?.cause ?? mutationError?.message;
        toast({
          title: "Form submission failed.",
          description: renderErrorTree(payload),
        });
      }
    } catch (error) {
      console.error("Error creating Sales Voucher:", error);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(handleSalesVoucherSubmit));
  useF2Navigate("/sales/add/");

  // ── Auto-calculate discount from entered total ─────────────────────────────
  const handleAutoCalcFromTotal = () => {
    const enteredTotal = parseFloat(getValues('form.total_bill_value') || 0);
    const mrp          = parseFloat(getValues('form.mrp')             || 0);
    const other        = parseFloat(getValues('form.other_charge')    || 0);
    const freight      = parseFloat(getValues('form.freight_charge')  || 0);
    const cgst_per     = parseFloat(getValues('form.cgst_per')        || 0);
    const igst_per     = parseFloat(getValues('form.igst_per')        || 0);
    const sgst_per     = parseFloat(getValues('form.sgst_per')        || 0);
    const tcs_per      = parseFloat(getValues('form.tcs_per')         || 0);

    const gstFactor = 1 + cgst_per / 100 + igst_per / 100 + sgst_per / 100;
    const tcsFactor = 1 + tcs_per / 100;
    // total = taxable_value * gstFactor * tcsFactor
    // taxable_value = mrp - discount + other + freight
    // => discount = mrp + other + freight - enteredTotal / (gstFactor * tcsFactor)
    const taxable  = enteredTotal / (gstFactor * tcsFactor);
    const discount = mrp + other + freight - taxable;
    setValue('form.discount', Math.max(0, parseFloat(discount.toFixed(2))));
    setCalculate(prev => prev + 1);
  };

  // ── Apply Best Discount (retail pricelist vs active offer) ───────────────
  const applyBestDiscount = () => {
    // Offers never apply to B2B customers — they have their own pricelist
    if (b2bPricelist) return;
    if (!retailDiscountPricelist && !activeOffer) return;

    const items = getValues('salesvouitem_set') || [];

    // Main items expose purity as `purity` (slug); sub-items expose it as
    // `metal_purity` (added in BarcodeDetToSaleVouDetSerializer). Packet
    // identifier on sub-items is the `packet` slug, NOT `pckt_no`.
    const purityOf = (it) => it.metal_purity || it.purity || "";
    const subHasPacket = (s) => !!(s.packet || s.pckt_no);

    // ── Retail pricelist discount ──────────────────────────────────────────
    let retailDiscount = 0;
    if (retailDiscountPricelist) {
      const ruleByPurity = Object.fromEntries(
        (retailDiscountPricelist.rules || []).map(r => [r.purity, r])
      );
      for (const item of items) {
        const rule = ruleByPurity[purityOf(item)];
        if (!rule) continue;
        retailDiscount += parseFloat(item.making_value || 0) * parseFloat(rule.making_discount_pct || 0) / 100;
        for (const sub of (item.main_item_set || [])) {
          if (subHasPacket(sub))
            retailDiscount += parseFloat(sub.amount || 0) * parseFloat(rule.diamond_discount_pct || 0) / 100;
        }
      }
    }

    // ── Active offer discount ──────────────────────────────────────────────
    let offerDiscount = 0;
    if (activeOffer) {
      const offerRuleByPurity = Object.fromEntries(
        (activeOffer.rules || []).map(r => [r.purity, r])
      );
      for (const item of items) {
        const rule = offerRuleByPurity[purityOf(item)];
        if (rule) {
          const makingVal = parseFloat(item.making_value || 0);
          if (rule.making_type === 'flat') {
            // discount = standard making - offer making (flat ₹/g × nw)
            const offerMaking = parseFloat(rule.making_value) * parseFloat(item.nw || 0);
            offerDiscount += Math.max(0, makingVal - offerMaking);
          } else if (rule.making_type === 'discount') {
            offerDiscount += makingVal * parseFloat(rule.making_value) / 100;
          }
        }
        // Diamond discount (offer-level, applies across all purities)
        for (const sub of (item.main_item_set || [])) {
          if (subHasPacket(sub))
            offerDiscount += parseFloat(sub.amount || 0) * parseFloat(activeOffer.diamond_discount_pct || 0) / 100;
        }
      }
    }

    // Apply whichever gives the customer a lower price (= higher discount)
    const bestDiscount = Math.max(retailDiscount, offerDiscount);
    if (bestDiscount > 0) {
      setValue('form.discount', parseFloat(bestDiscount.toFixed(2)));
      setCalculate(prev => prev + 1);
    }
  };

  // ── Bill Summary rows ──────────────────────────────────────────────────────
  const billSummaryRows = [
    { label: 'Freight Charge', field: 'form.freight_charge', editable: true },
    { label: 'Other Charge',   field: 'form.other_charge',   editable: true },
    { isSeparator: true },
    { label: 'MRP',            field: 'form.mrp' },
    { label: 'Discount',       field: 'form.discount',       editable: true, step: '0.01' },
    { label: 'Taxable Value',  field: 'form.taxable_value' },
    { label: 'CGST',           field: 'form.cgst_amt' },
    { label: 'IGST',           field: 'form.igst_amt' },
    { label: 'SGST',           field: 'form.sgst_amt' },
    { label: 'Total incl. GST',field: 'form.total_incl_gst' },
    { label: 'TCS',            field: 'form.tcs_amt' },
    { label: 'Round Off',      field: 'form.round_off',      editable: true, step: '0.01' },
    { isSeparator: true },
    { label: 'Total',          field: 'form.total_bill_value', isTotal: true, isEditableTotal: true },
    ...((selectedOrder || selectedReceiptIds.length > 0 || parseFloat(getValues('form.advance_deducted') || 0) > 0) ? [{ label: 'Advance Deducted', field: 'form.advance_deducted', editable: false, step: '1' }] : []),
    ...(selectedPurchase ? [{ label: 'Old Gold Adjusted', field: 'form.old_gold_adjusted', editable: true, step: '1' }] : []),
    ...(inlineOldGoldTotal > 0 ? [{ label: 'Old Gold (Inline)', field: 'form.inline_old_gold_total' }] : []),
    { isSeparator: true },
    {
      label: 'Net Due',
      isTotal: true,
      computedValue: Math.max(
        0,
        parseFloat(watch('form.total_bill_value') || 0)
        - parseFloat(watch('form.cash') || 0)
        - bankdetails.reduce((s, b) => s + parseFloat(b.amount || 0), 0)
        - parseFloat(watch('form.advance_deducted') || 0)
        - parseFloat(watch('form.old_gold_adjusted') || 0)
        - inlineOldGoldTotal
      ),
    },
  ];

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="mt-5">
      <form
        ref={formRef}
        className="p-6 shadow-sm rounded-xl bg-white border border-gray-100"
        id="orderForm"
        onSubmit={handleSubmit(handleSalesVoucherSubmit, (e) => {
          console.log("submission error", e);
          const msgs = [];
          if (e?.form?.sales_person) msgs.push("Sales Person is required");
          if (msgs.length) toast({ title: "Please fix the following", description: msgs.join(", "), variant: "destructive" });
        })}
      >

        {/* ══ 1. BILL DETAILS ══════════════════════════════════════════════════ */}
        <SectionHeader number="1" title="Bill Details" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          {/* Bill No — auto-generated, read-only */}
          <FieldContainer>
            <Label className="text-nowrap">Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-accent-50 border border-accent-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                {watch("form.billno") || <span className="text-accent-400 text-xs font-normal">Auto-generating…</span>}
              </span>
              <input type="hidden" {...register("form.billno", { required: true })} />
            </div>
          </FieldContainer>

          {/* Party Name with ledger lookup */}
          <div>
          <FieldContainer>
            <Label className="text-nowrap">Party Name</Label>
            <div className="relative">
              <div className="flex gap-1.5">
              <SearchableComboBox
                className="flex-1"
                options={customers}
                searchKeys={["mobile1", "mobile2", "mobile3", "phone1"]}
                placeholder="Search by name or mobile…"
                renderOption={(opt) => (
                  <div className="flex items-center justify-between gap-2 min-w-0">
                    <span className="truncate">{opt.ac_name}</span>
                    {(opt.mobile1 || opt.mobile2 || opt.mobile3 || opt.phone1) && (
                      <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                        {opt.mobile1 || opt.mobile2 || opt.mobile3 || opt.phone1}
                      </span>
                    )}
                  </div>
                )}
                value={watch("form.ldgr_name") ?? ""}
                onInputChange={(val) => setValue("form.ldgr_name", val)}
                onSelect={async (opt) => {
                  setValue("form.ldgr_name", opt.ac_name);
                  setValue("form.ldgr", opt.id);
                  const customerState = opt.ship_state || opt.state;
                  if (customerState && customerState !== 'none') {
                    setValue("form.place_of_supply", customerState);
                  }
                  const [ldgrcash, cashRes, ordersRes, purchasesRes, plRes, rdplRes] = await Promise.all([
                    CashTotalLedger(opt.id),
                    fetchCustomerCashReceived(opt.id),
                    fetchCustomerOrdersByLedger(opt.id),
                    fetchCustomerPurchasesByLedger(opt.id),
                    fetchB2BPricelistForLedger(opt.id),
                    fetchRetailDiscountPricelistForLedger(opt.id),
                  ]);
                  setCashLedger(ldgrcash.data.total_cash);
                  setCustomerCashInfo(cashRes.success ? cashRes.data : null);
                  setCustomerOrders(ordersRes.success ? ordersRes.data : []);
                  setSelectedOrder(null);
                  setValue("form.customer_order", "");
                  setValue("form.advance_deducted", 0);
                  setSelectedReceiptIds([]);
                  setOnAccountReceipts([]);
                  setLoadingOnAccount(true);
                  fetchUnlinkedReceipts(opt.id).then(res => {
                    setLoadingOnAccount(false);
                    setOnAccountReceipts(res.success ? res.data : []);
                  });
                  setCustomerPurchases(purchasesRes.success ? purchasesRes.data : []);
                  setSelectedPurchase(null);
                  setValue("form.old_gold_purchase", "");
                  setValue("form.old_gold_adjusted", 0);
                  setB2bPricelist(plRes.success && plRes.data ? plRes.data : null);
                  setRetailDiscountPricelist(rdplRes.success && rdplRes.data ? rdplRes.data : null);
                }}
              />
              <Link
                to={`/crm/ledger/add/?next=${encodeURIComponent(location.pathname)}`}
                tabIndex={-1}
              >
                <Button type="button" size="icon" variant="outline" title="Add new customer" className="cursor-pointer shrink-0 h-9 w-9">
                  <Plus className="size-4" />
                </Button>
              </Link>
              </div>
              <input type="hidden" {...register("form.ldgr")} />
              <div className="text-[10px] mt-1 flex flex-wrap items-center gap-1.5">
                {!Array.isArray(cashledger) && cashledger != null && (() => {
                  const bal = parseFloat(cashledger);
                  return (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border font-semibold ${
                      bal > 0 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                      bal < 0 ? 'bg-amber-50 text-amber-700 border-amber-200' :
                               'bg-gray-50 text-gray-500 border-gray-200'
                    }`}>
                      <svg className="w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/>
                      </svg>
                      ₹{bal.toLocaleString('en-IN')}
                    </span>
                  );
                })()}
                {b2bPricelist && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                    B2B: {b2bPricelist.name}
                  </span>
                )}
                {retailDiscountPricelist && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded font-semibold bg-green-50 text-green-700 border border-green-200">
                    Discount: {retailDiscountPricelist.name}
                  </span>
                )}
                {activeOffer && !b2bPricelist && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded font-semibold bg-orange-50 text-orange-700 border border-orange-200">
                    Offer: {activeOffer.name}
                  </span>
                )}
                {customerCashInfo && (() => {
                  const { cash_received, limit, remaining } = customerCashInfo;
                  const pct = limit > 0 ? Math.min(100, (cash_received / limit) * 100) : 0;
                  const isNearLimit = remaining < limit * 0.1;
                  const isAtLimit = remaining <= 0;
                  const circ = 75.4;
                  const offset = circ * (1 - pct / 100);
                  const fmt = (n) => n >= 100000 ? `₹${n % 100000 === 0 ? n / 100000 : (n / 100000).toFixed(1)}L`
                                   : n >= 1000   ? `₹${n % 1000 === 0 ? n / 1000 : (n / 1000).toFixed(1)}k`
                                   : `₹${n.toLocaleString('en-IN')}`;
                  const clr = isAtLimit
                    ? { ring: '#dc2626', track: '#fecaca', cls: 'bg-red-50 text-red-700 border-red-200' }
                    : isNearLimit
                    ? { ring: '#d97706', track: '#fde68a', cls: 'bg-amber-50 text-amber-700 border-amber-200' }
                    : { ring: 'hsl(var(--primary))', track: 'hsl(var(--accent-200))', cls: 'bg-accent-50 text-accent-700 border-accent-200' };
                  return (
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border font-semibold ${clr.cls}`}>
                      <svg width="14" height="14" viewBox="0 0 32 32" style={{ flexShrink: 0 }}>
                        <circle cx="16" cy="16" r="12" fill="none" stroke={clr.track} strokeWidth="5"/>
                        <circle cx="16" cy="16" r="12" fill="none" stroke={clr.ring} strokeWidth="5"
                          strokeDasharray={circ} strokeDashoffset={offset}
                          strokeLinecap="round" transform="rotate(-90 16 16)"/>
                      </svg>
                      {isAtLimit ? 'Cash limit reached' : `${fmt(cash_received)} / ${fmt(limit)} · ${fmt(remaining)} left`}
                    </span>
                  );
                })()}
              </div>
            </div>
          </FieldContainer>
          </div>

          {enableGstBill && (
            <FieldContainer>
              <Label className="text-nowrap">GST Bill No</Label>
              <div className="flex items-center gap-2 flex-1">
                <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-accent-50 border border-accent-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                  {watch("form.gst_billno") || <span className="text-accent-400 text-xs font-normal">Auto-generating…</span>}
                </span>
                <input type="hidden" {...register("form.gst_billno", { required: enableGstBill })} />
              </div>
            </FieldContainer>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Date</Label>
            <Input type="date" min={fyMin} max={fyMax} {...register("form.date1", { required: true })} />
          </FieldContainer>

          <FieldContainer>
            <Label className="text-nowrap">Sales Person</Label>
            <Controller name="form.sales_person" control={control} rules={{ required: "Sales person is required" }}
              render={({ field }) => (
                <>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger className={errors?.form?.sales_person ? "border-red-500" : ""}><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {salespersonData.map((sp, i) => <SelectItem key={i} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  {errors?.form?.sales_person && <p className="text-xs text-red-500 mt-1">{errors.form.sales_person.message}</p>}
                </>
              )}
            />
          </FieldContainer>

          <FieldContainer>
            <Label className="text-nowrap">Salesperson 2</Label>
            <Controller name="form.sales_person2" control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent>
                    {salespersonData.map((sp, i) => <SelectItem key={i} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Place of Supply</Label>
            <Controller name="form.place_of_supply" control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger><SelectValue placeholder="Select State" /></SelectTrigger>
                  <SelectContent>
                    {statesData.map((s, i) => <SelectItem key={i} value={`${s.code}`}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>

          <FieldContainer>
            <Label className="text-nowrap">Transport</Label>
            <TransportSummaryChip watch={watch} />
          </FieldContainer>
        </div>

        {/* Exhibition Profile row — only visible when this retail is marked as an exhibition retail */}
        {isExhibitionRetail && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
            <FieldContainer>
              <Label className="text-nowrap">Exhibition Profile</Label>
              <Controller name="form.exhibition_profile" control={control}
                render={({ field }) => (
                  <Select
                    onValueChange={(val) => field.onChange(val === "__none__" ? "" : val)}
                    value={field.value ? String(field.value) : "__none__"}
                  >
                    <SelectTrigger><SelectValue placeholder="None (regular retail)" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— None (regular retail) —</SelectItem>
                      {exhibitions.map(e => (
                        <SelectItem key={e.id} value={String(e.id)}>
                          {e.name}{e.is_active ? " ★" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FieldContainer>
          </div>
        )}

        {/* Inline Old-Gold Exchange section has moved next to the Bill Summary panel below. */}

        {/* ══ Old Gold Adjustment ════════════════════════════════════════ */}
        {customerPurchases.length > 0 && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50/60 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Gem className="size-4 text-amber-700" />
              <span className="text-sm font-semibold text-amber-900">Old Gold Adjustment</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Purchase dropdown */}
              <FieldContainer>
                <Label className="text-nowrap text-amber-800">Customer Purchase (Old Gold)</Label>
                <Controller
                  name="form.old_gold_purchase"
                  control={control}
                  render={({ field }) => (
                    <Select
                      value={field.value ? String(field.value) : "__none__"}
                      onValueChange={(val) => {
                        if (val === "__none__") {
                          field.onChange("");
                          setSelectedPurchase(null);
                          setValue("form.old_gold_adjusted", 0);
                        } else {
                          field.onChange(val);
                          const pv = customerPurchases.find(p => String(p.id) === val);
                          setSelectedPurchase(pv ?? null);
                          if (pv) {
                            setValue("form.old_gold_adjusted", parseFloat(pv.available_balance || 0));
                            setCalculate(prev => prev + 1);
                          }
                        }
                      }}
                    >
                      <SelectTrigger className="h-9 text-sm bg-white">
                        <SelectValue placeholder="Select purchase…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— No old gold linked —</SelectItem>
                        {customerPurchases.map(p => (
                          <SelectItem key={p.id} value={String(p.id)}>
                            {p.billno} · ₹{parseFloat(p.available_balance || 0).toLocaleString('en-IN')} available
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </FieldContainer>

              {/* Purchase info card */}
              {selectedPurchase && (
                <div className="rounded-md border border-amber-200 bg-white px-4 py-3 text-sm flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <CheckCircle2 className="size-3.5 text-emerald-600" />
                    <span className="font-semibold text-amber-900">{selectedPurchase.billno}</span>
                    <span className="text-muted-foreground text-xs ml-auto">{selectedPurchase.date1}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Purchase Bill Value</span>
                    <span className="font-medium">₹{parseFloat(selectedPurchase.bill_value || 0).toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Already Adjusted</span>
                    <span className="font-medium text-rose-600">
                      − ₹{parseFloat(selectedPurchase.total_adjusted || 0).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs border-t border-amber-100 pt-1 mt-0.5">
                    <span className="font-semibold text-amber-800">Available to Adjust</span>
                    <span className="font-bold text-amber-800">
                      ₹{parseFloat(selectedPurchase.available_balance || 0).toLocaleString('en-IN')}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {selectedPurchase && (
              <div className="mt-3 flex items-center gap-3">
                <AlertCircle className="size-3.5 text-amber-600 shrink-0" />
                <p className="text-xs text-amber-700">
                  Old gold adjustment reduces the <strong>due amount</strong> on this bill.
                  Adjust the "Old Gold Adjusted" field in the bill summary to apply a partial amount.
                </p>
              </div>
            )}
          </div>
        )}

        {/* HSN + Barcode scan row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">HSN Code</Label>
            {/* When items exist, Radix Select is disabled and never opens — SelectValue
                cannot resolve the label. Render a plain disabled Input instead. */}
            {watchFields?.length > 0 ? (
              <Input
                disabled
                value={(() => {
                  const match = hsns.find(h => h.hsn_no === hsn_current);
                  return match ? `${match.hsn_no} — ${match.description || ''}`.trim() : (hsn_current || '');
                })()}
              />
            ) : (
              <Controller name="hsn" control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger><SelectValue placeholder="Select HSN" /></SelectTrigger>
                    <SelectContent>
                      {hsns.map((h, i) => <SelectItem key={i} value={h.hsn_no}>{h.description || h.hsn_no}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )}
              />
            )}
          </FieldContainer>

          <FieldContainer>
            <Label className="text-nowrap">Barcode</Label>
            <Input
              type="text"
              disabled={!hsn_current}
              readOnly={!hsn_current}
              {...register("barcode", { onBlur: () => handleBlur() })}
            />
          </FieldContainer>
        </div>

        {/* ══ 2. BARCODE ITEMS ═════════════════════════════════════════════════ */}
        <SectionHeader number="2" title="Barcode Items" />

        <div className="overflow-x-auto">
          <Table>
            <TableBody>
              <TableRow className="bg-accent-50">
                <TH>Del</TH><TH>Barcode</TH><TH>Packet</TH><TH>Item</TH><TH>Pcs</TH>
                <TH>Ct</TH><TH>GW</TH><TH>Making</TH><TH>Making Type</TH>
                <TH>Making Value</TH><TH>Purity</TH><TH>Tunch</TH>
                <TH>Fine Wt</TH><TH>Rate</TH><TH>Amount</TH>
              </TableRow>

              {watchFields.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={15}
                    className="py-8 text-center text-sm text-muted-foreground"
                  >
                    No barcode items added yet. Scan a barcode above to add items.
                  </TableCell>
                </TableRow>
              )}

              {watchFields.map((field, index) => (
                <React.Fragment key={field.id || index}>
                  {/* Main item row */}
                  <TableRow className="bg-accent-50">
                    <TableCell className="px-3 py-2 border">
                      <Trash2 color="#d45959" className="size-4 cursor-pointer" onClick={() => remove(index)} />
                    </TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.barcode}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.packet}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{mainItemData.find(m => m.short_code === field?.item)?.item_name || field?.item}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.pcs}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{Number(field?.ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{Number(field?.gw || 0).toFixed(3)}</TableCell>
                    <TableCell className="w-24 px-3 py-2 border">
                      <Input type="number" className="h-7 text-sm" {...register(`salesvouitem_set.${index}.making`, { valueAsNumber: true })} />
                    </TableCell>
                    <TableCell className="w-28 px-3 py-2 border">
                      <Controller name={`salesvouitem_set.${index}.making_type`} control={control}
                        render={({ field }) => (
                          <Select onValueChange={(v) => { field.onChange(v); setCalculate(prev => prev + 1); }} value={field.value}>
                            <SelectTrigger className="h-7 text-sm"><SelectValue placeholder="Type" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="per_nw">% of wt</SelectItem>
                              <SelectItem value="val">Value</SelectItem>
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </TableCell>
                    <TableCell className="w-24 px-3 py-2 border">
                      <Input type="number" className="h-7 text-sm bg-muted/30" readOnly tabIndex={-1} {...register(`salesvouitem_set.${index}.making_value`, { valueAsNumber: true })} />
                    </TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.purity}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.tunch ? Number(field.tunch).toFixed(2) : "0.00"}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm"></TableCell>
                    <TableCell className="px-3 py-2 border text-sm"></TableCell>
                    <TableCell className="px-3 py-2 border text-sm">
                      {field?.amount}
                      <input type="hidden" {...register(`salesvouitem_set.${index}.amount`)} />
                    </TableCell>
                  </TableRow>

                  {/* Sub-item (stone / metal) rows */}
                  {field.main_item_set?.map((detail, idx) => (
                    <TableRow key={idx} className="bg-gray-50">
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.packet}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.item_name || detail?.item}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.pcs}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{Number(detail?.ct || 0).toFixed(3)}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{Number(detail?.gw || 0).toFixed(3)}</TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.metal_purity}</TableCell>
                      <TableCell className="w-20 px-3 py-2 border">
                        {(detail?.item_type === 'R' || detail?.item === "Gold") && (
                          <Input type="text" className="h-7 text-sm" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.tunch`)} placeholder="Tunch" />
                        )}
                      </TableCell>
                      <TableCell className="w-16 px-3 py-2 border text-sm">
                        {(detail?.item_type === 'R' || detail?.item === "Gold") && Number(detail?.fine_wt || 0) > 0 ? Number(detail.fine_wt).toFixed(3) : ""}
                        <input type="hidden" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.fine_wt`)} />
                      </TableCell>
                      <TableCell className="w-28 px-3 py-2 border">
                        <Input type="text" className="h-7 text-sm" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.rate`)} placeholder="Rate" disabled={Number(detail?.tunch || 0) > 0 && (detail?.item_type === 'R' || (detail?.item || '').toUpperCase() === 'GOLD')} />
                      </TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.amount}
                        <input type="hidden" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.amount`)} />
                      </TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* ══ 3. MANUAL ITEMS — hidden until checkbox is ticked ═══════════ */}
        <div className="flex items-center gap-3 mb-3">
          <SectionHeader number="3" title="Manual Items (No Barcode)" />
          <label className="flex items-center gap-2 cursor-pointer select-none ml-2">
            <input
              type="checkbox"
              checked={showManualItems}
              onChange={e => setShowManualItems(e.target.checked)}
              className="size-4 rounded border-gray-300 accent-primary"
            />
            <span className="text-sm text-muted-foreground">Add manual items</span>
          </label>
        </div>

        {showManualItems && (<>

        {/* ── 3a. Main Item Entry ─────────────────────────────────────────── */}
        <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-1.5">
          Step 1 — Main Item (Jewellery Piece)
        </p>
        <p className="text-xs text-gray-400 mb-2">
          Enter the jewellery item, then press <kbd className="px-1 py-0.5 bg-gray-100 border rounded font-mono text-gray-600">Tab</kbd> on Remarks to add it and move to sub-items.
        </p>
        <div className="overflow-x-auto mb-4">
          <Table className="w-full table-fixed border-collapse">
            <TableBody>
              <TableRow className="bg-sky-50">
                <TH className="text-sky-700">Item</TH>
                <TH className="text-sky-700">Description</TH>
                <TH className="text-sky-700 w-20">Pcs</TH>
                <TH className="text-sky-700 w-20">GW</TH>
                <TH className="text-sky-700 w-24">Making</TH>
                <TH className="text-sky-700 w-28">Making Type</TH>
                <TH className="text-sky-700 w-24">Discount</TH>
                <TH className="text-sky-700 w-24">Value</TH>
                <TH className="text-sky-700 w-32">Remarks</TH>
              </TableRow>
              <TableRow>
                {/* Item */}
                <TableCell className="w-36 px-3 py-2 border">
                  <Input
                    list="main_item_list"
                    value={mainItemDisplay}
                    ref={mainItemInputRef}
                    onChange={(e) => {
                      const typed = e.target.value;
                      setMainItemDisplay(typed);
                      const found = mainItemData.find(m => m.item_name === typed || m.short_code === typed);
                      setValue("mainItem.item", found ? found.short_code : typed);
                    }}
                    placeholder="Item code / name"
                  />
                  <datalist id="main_item_list">
                    {mainItemData.map((m, i) => <option key={i} value={m.item_name}>{m.short_code}</option>)}
                  </datalist>
                  <input type="hidden" {...register("mainItem.item")} />
                </TableCell>
                {/* Description */}
                <TableCell className="px-3 py-2 border">
                  <Input placeholder="Description" {...register("mainItem.item_desc")} />
                </TableCell>
                {/* Pcs */}
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" placeholder="0" {...register("mainItem.pcs")} />
                </TableCell>
                {/* GW */}
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" placeholder="0.000" {...register("mainItem.gw")} />
                </TableCell>
                {/* Making */}
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" placeholder="0.00" {...register("mainItem.making")} />
                </TableCell>
                {/* Making Type */}
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
                    )}
                  />
                </TableCell>
                {/* Discount */}
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" placeholder="0.00" {...register("mainItem.discount")} />
                </TableCell>
                {/* Value */}
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" placeholder="0.00" {...register("mainItem.value")} />
                </TableCell>
                {/* Remarks — Tab triggers add */}
                <TableCell className="w-32 px-3 py-2 border">
                  <Input placeholder="Remarks" {...register("mainItem.remarks")} onKeyDown={handleKeyDownMainItem} />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* ── 3b. Sub-Item / Details Entry ────────────────────────────────── */}
        <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-1.5">
          Step 2 — Sub-Items / Material Details
        </p>
        <p className="text-xs text-gray-400 mb-2">
          Sub-items are added to the <span className="font-medium">last main item</span> in the list below.
          Fill the row and press <kbd className="px-1 py-0.5 bg-gray-100 border rounded font-mono text-gray-600">Tab</kbd> on Value to add.
        </p>
        <div className="overflow-x-auto mb-5">
          <Table className="w-full table-fixed border-collapse">
            <TableBody>
              <TableRow className="bg-accent-50">
                <TH>Packet</TH><TH>Item</TH><TH>Pcs</TH><TH>Ct</TH><TH>GW</TH>
                <TH>Metal Purity</TH><TH>Loss</TH><TH>Tunch</TH><TH>Fine Wt</TH>
                <TH>Rate</TH><TH>Value</TH>
              </TableRow>
              <TableRow>
                <TableCell className="w-28 px-3 py-2 border">
                  <Input list="manual_packet_list" {...register("details.packet")} ref={(el) => { register("details.packet").ref(el); packetInputRef.current = el; }} />
                  <datalist id="manual_packet_list">
                    {packets.map((p, i) => <option key={i} value={p.pckt_no} />)}
                  </datalist>
                </TableCell>
                <TableCell className="w-40 px-3 py-2 border">
                  <Input
                    list="manual_item_list"
                    value={detailItemDisplay}
                    onChange={handleItemDisplayChange}
                    disabled={itemLockedByPacket}
                    placeholder="Item"
                    className={itemLockedByPacket ? "bg-gray-100 text-gray-500 cursor-not-allowed" : ""}
                  />
                  <datalist id="manual_item_list">
                    {mainItemData.filter(m => m.item_type !== 'S').map((m, i) => <option key={i} value={m.item_name} />)}
                  </datalist>
                  <input type="hidden" {...register("details.item")} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" {...register("details.pcs")} placeholder="Pcs"
                    disabled={pcsDisabled} className={pcsDisabled ? "bg-gray-100 text-gray-400 cursor-not-allowed" : ""} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.ct")} placeholder="Ct"
                    disabled={ctDisabled} className={ctDisabled ? "bg-gray-100 text-gray-400 cursor-not-allowed" : ""} />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.gw")} placeholder="GW"
                    disabled={gwDisabled} className={gwDisabled ? "bg-gray-100 text-gray-400 cursor-not-allowed" : ""} />
                </TableCell>
                <TableCell className="w-32 px-3 py-2 border">
                  <Controller name="details.metal_purity" control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value ?? ""}>
                        <SelectTrigger className="h-8"><SelectValue placeholder="Purity" /></SelectTrigger>
                        <SelectContent>
                          {purityData.map((p, i) => <SelectItem key={i} value={`${p.purity}`}>{p.purity}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  {detailItem?.short_code === "Gold" && (
                    <Input type="number" step="0.001" {...register("details.loss")} placeholder="Loss" />
                  )}
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  {detailItem?.short_code === "Gold" && (
                    <Input type="number" step="0.001" {...register("details.tunch")} placeholder="Tunch" />
                  )}
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.fine_wt")} placeholder="Fine Wt" />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" {...register("details.rate")} placeholder="Rate" />
                </TableCell>
                <TableCell className="w-24 px-3 py-2 border">
                  <Input type="number" step="0.01" {...register("details.value")} placeholder="Value" onKeyDown={handleKeyDownDetails} />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* ── 3c. Combined saved rows ──────────────────────────────────────── */}
        {rs.length > 0 && (
          <div className="overflow-x-auto">
            <Table className="w-full table-fixed border-collapse">
              <TableBody>
                {/* Combined header */}
                <TableRow className="bg-accent-50">
                  <TH className="w-10">#</TH>
                  <TH>Item</TH>
                  <TH>Description</TH>
                  <TH className="w-16">Pcs</TH>
                  <TH className="w-16">Ct</TH>
                  <TH className="w-16">GW</TH>
                  <TH className="w-20">Loss</TH>
                  <TH className="w-20">Tunch</TH>
                  <TH className="w-20">Fine Wt</TH>
                  <TH className="w-24">Rate</TH>
                  <TH className="w-24">Making</TH>
                  <TH className="w-20">Discount</TH>
                  <TH className="w-24">Value</TH>
                  <TH className="w-32">Remarks</TH>
                  <TH className="w-16"></TH>
                </TableRow>

                {rs.map((mainItem, mainIdx) => (
                  <React.Fragment key={mainIdx}>
                    {/* ── Main item row (blue) ── */}
                    <TableRow className="bg-sky-50 border-t-2 border-sky-200">
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainIdx + 1}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.item}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.item_desc}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.pcs}</TableCell>
                      <TableCell className="px-3 py-2 border" />{/* Ct — not on main item */}
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{Number(mainItem.gw || 0).toFixed(3)}</TableCell>
                      {/* Loss/Tunch/Fine Wt/Rate blank for main item */}
                      <TableCell className="px-3 py-2 border" />
                      <TableCell className="px-3 py-2 border" />
                      <TableCell className="px-3 py-2 border" />
                      <TableCell className="px-3 py-2 border" />{/* Rate — not on main item */}
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.making}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.discount}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.value}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs text-sky-700">{mainItem.remarks}</TableCell>
                      <TableCell className="px-3 py-2 border text-center">
                        <Trash2 color="#d45959" className="size-4 cursor-pointer mx-auto" onClick={() => handleDeleteMainItem(mainIdx)} />
                      </TableCell>
                    </TableRow>

                    {/* ── Sub-item rows (white) ── */}
                    {(mainItem.details_set || []).map((detail, subIdx) => {
                      const rowItem = mainItemData.find(m => m.short_code === detail.item);
                      const rowIsRaw = rowItem?.item_type === "R";
                      return (
                        <TableRow key={subIdx} className="bg-white">
                          <TableCell className="px-3 py-2 border text-xs text-gray-400">{mainIdx + 1}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs text-gray-500">{detail.packet || detail.item}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{detail.item_name || detail.item}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{detail.pcs || ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{Number(detail.ct || 0).toFixed(3)}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{Number(detail.gw || 0).toFixed(3)}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{rowIsRaw ? detail.loss : ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{rowIsRaw ? detail.tunch : ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{rowIsRaw ? detail.fine_wt : ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-sm">{detail.rate}</TableCell>
                          {/* Making/Discount blank for sub-items */}
                          <TableCell className="px-3 py-2 border" />
                          <TableCell className="px-3 py-2 border" />
                          <TableCell className="px-3 py-2 border text-sm">{detail.value}</TableCell>
                          <TableCell className="px-3 py-2 border" />
                          <TableCell className="px-3 py-2 border text-center">
                            <Trash2 color="#d45959" className="size-4 cursor-pointer mx-auto" onClick={() => handleDeleteSubItem(mainIdx, subIdx)} />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        </>)}  {/* end showManualItems */}

        {/* ══ 4. PAYMENT DETAILS ═══════════════════════════════════════════════ */}
        <SectionHeader number="4" title="Payment Details" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Cash</Label>
            <Input type="number" {...register("form.cash", { valueAsNumber: true, setValueAs: v => (v === "" || v === null || isNaN(v) ? 0 : Number(v)) })} />
          </FieldContainer>
        </div>

        <div className="overflow-x-auto">
          <Table className="w-full border-collapse">
            <TableBody>
              <TableRow className="bg-accent-50">
                <TH className="w-20">Action</TH>
                <TH>Mode</TH>
                <TH>Amount</TH>
                <TH>{bankPaymentMode === "CHEQUE" ? "Cheque No" : bankPaymentMode === "UPI" ? "UTR / Ref No" : "Ref No"}</TH>
                <TH>{bankPaymentMode === "CHEQUE" ? "Drawee Bank" : "Bank Name"}</TH>
                <TH>Our Bank A/C</TH>
                {bankPaymentMode === "CHEQUE" && <TH>Cheque Date</TH>}
              </TableRow>

              {/* Bank detail input row */}
              <TableRow>
                <TableCell className="w-20 px-3 py-2 border">
                  <PlusCircle size={20} className="cursor-pointer text-accent-600 mx-auto" onClick={handleAddBank} />
                </TableCell>
                <TableCell className="px-3 py-2 border">
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                    {...register("bank.payment_mode")}
                  >
                    <option value="NEFT">NEFT / IMPS</option>
                    <option value="UPI">UPI</option>
                    <option value="CHEQUE">Cheque</option>
                    <option value="CARD">Card</option>
                  </select>
                </TableCell>
                <TableCell className="px-3 py-2 border"><Input type="text" {...register("bank.amount")} /></TableCell>
                <TableCell className="px-3 py-2 border"><Input type="text" {...register("bank.chq_no")} /></TableCell>
                <TableCell className="px-3 py-2 border"><Input type="text" {...register("bank.bank_name")} /></TableCell>
                <TableCell className="px-3 py-2 border">
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm"
                    {...register("bank.ledger")}
                    onChange={(e) => {
                      const selected = bankLedgers.find(l => String(l.id) === e.target.value);
                      setValue("bank.ledger_name", selected ? selected.ac_name : "");
                      register("bank.ledger").onChange(e);
                    }}
                    onBlur={(e) => {
                      register("bank.ledger").onBlur(e);
                      // Auto-push the row on Tab-out when the entry is usable.
                      // For CHEQUE the next field (chq_date) still needs input,
                      // so skip auto-add in that mode.
                      const bnk = getValues("bank");
                      if (
                        bnk?.payment_mode !== "CHEQUE" &&
                        bnk?.ledger &&
                        Number(bnk?.amount) > 0
                      ) {
                        handleAddBank();
                      }
                    }}
                  >
                    <option value="">— Select Bank A/C —</option>
                    {bankLedgers.map(l => (
                      <option key={l.id} value={l.id}>{l.ac_name}</option>
                    ))}
                  </select>
                </TableCell>
                {bankPaymentMode === "CHEQUE" && (
                  <TableCell className="px-3 py-2 border">
                    <Input
                      type="date"
                      onKeyDown={handleKeyDown}
                      {...register("bank.chq_date")}
                      onBlur={(e) => {
                        register("bank.chq_date").onBlur(e);
                        const bnk = getValues("bank");
                        if (
                          bnk?.payment_mode === "CHEQUE" &&
                          bnk?.ledger &&
                          Number(bnk?.amount) > 0 &&
                          bnk?.chq_date
                        ) {
                          handleAddBank();
                        }
                      }}
                    />
                  </TableCell>
                )}
              </TableRow>

              {/* Saved bank entries */}
              {bankdetails.map((b, index) => (
                <TableRow key={index}>
                  <TableCell className="px-3 py-2 border">
                    <div className="flex gap-3">
                      <SquarePen className="size-4 cursor-pointer" onClick={() => handleEditBank(index)} />
                      <Trash2 color="#d45959" className="size-4 cursor-pointer" onClick={() => handleDeleteBank(index)} />
                    </div>
                  </TableCell>
                  <TableCell className="px-3 py-2 border text-sm">
                    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      b?.payment_mode === "CHEQUE" ? "bg-amber-100 text-amber-800" :
                      b?.payment_mode === "UPI"    ? "bg-green-100 text-green-800" :
                      b?.payment_mode === "CARD"   ? "bg-blue-100 text-blue-800" :
                                                      "bg-gray-100 text-gray-700"
                    }`}>{b?.payment_mode || "NEFT"}</span>
                    {b?.payment_mode === "CHEQUE" && b?.cheque_status && b.cheque_status !== "PENDING" && (
                      <span className="ml-1 text-[10px] text-green-700 font-medium">{b.cheque_status}</span>
                    )}
                  </TableCell>
                  <TableCell className="px-3 py-2 border text-sm">{b?.amount}</TableCell>
                  <TableCell className="px-3 py-2 border text-sm">{b?.chq_no}</TableCell>
                  <TableCell className="px-3 py-2 border text-sm">{b?.bank_name}</TableCell>
                  <TableCell className="px-3 py-2 border text-sm">{b?.ledger_name}</TableCell>
                  <TableCell className="px-3 py-2 border text-sm">{b?.payment_mode === "CHEQUE" ? b?.chq_date : ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* ══ 5/6. REMARKS + OLD GOLD (left)  ·  BILL SUMMARY (right) ═════════ */}
        <div className="flex flex-col lg:flex-row gap-6 items-start">
        <div className="flex-1 min-w-0">
        <SectionHeader number="5" title="Remarks" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Remarks</Label>
            <Input type="text" {...register("form.remarks")} />
          </FieldContainer>
        </div>

        {(retailDiscountPricelist || activeOffer) && !b2bPricelist && (
          <div className="flex justify-end mb-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5 text-green-700 border-green-300 hover:bg-green-50"
              onClick={applyBestDiscount}
            >
              <BadgePercent className="w-3.5 h-3.5" />
              Apply Best Discount
              {retailDiscountPricelist && activeOffer
                ? ` (${retailDiscountPricelist.name} vs ${activeOffer.name})`
                : retailDiscountPricelist
                  ? ` (${retailDiscountPricelist.name})`
                  : ` (${activeOffer.name})`
              }
            </Button>
          </div>
        )}
          {/* ── Buy Old Gold / Stones (inline) ─────────────────────────────── */}
          <div className="mb-4 rounded-lg border border-accent-200 bg-accent-50/40 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Gem className="size-4 text-primary" />
                <span className="text-sm font-semibold text-primary">Buy Old Gold / Stones in this Sale</span>
                <span className="text-[11px] text-muted-foreground">(Raw &amp; Stone items only — creates a linked customer purchase voucher)</span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => { setInlineOldGold(prev => [...prev, blankInlineRow()]); markTableDirty(); }}
              >
                <Plus className="size-3 mr-1" /> Add Row
              </Button>
            </div>
            {inlineOldGold.length > 0 && (
              <div className="overflow-x-auto rounded border border-accent-200 bg-white">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/60">
                      <TH className="px-2 py-1.5 text-[11px]">Item</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Purity</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Pcs</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Ct</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Gw</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Loss</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Tunch</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Fine Wt</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Uom</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Rate</TH>
                      <TH className="px-2 py-1.5 text-[11px]">Value</TH>
                      <TH className="px-2 py-1.5 text-[11px]"></TH>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {inlineOldGold.map((row, idx) => {
                      const itemOptions = mainItemData
                        .filter(m => m.item_type === 'R' || m.item_type === 'S');
                      return (
                      <TableRow key={idx}>
                        <TableCell className="p-1 border align-top min-w-[180px]">
                          <SearchableComboBox
                            className="w-full"
                            labelKey="item_name"
                            searchKeys={["short_code"]}
                            options={itemOptions}
                            value={row.item_name || row.item || ""}
                            onInputChange={(val) => updateInlineRow(idx, { item: val, item_name: val })}
                            onSelect={(opt) => {
                              if (opt.item_type !== 'R' && opt.item_type !== 'S') {
                                toast({ title: `Item '${opt.item_name}' is not Raw or Stone — cannot use for old gold.`, variant: "destructive" });
                                return;
                              }
                              updateInlineRow(idx, {
                                item: opt.short_code,
                                item_name: opt.item_name,
                                description: row.description || opt.item_name,
                              });
                            }}
                          />
                          {row.description && row.description !== row.item_name && (
                            <div className="mt-1 text-[10px] text-gray-500 italic px-1 truncate" title={row.description}>{row.description}</div>
                          )}
                        </TableCell>
                        <TableCell className="p-1 border align-top">
                          <select
                            className="h-7 text-sm w-full px-1 border rounded"
                            value={row.purity}
                            onChange={(e) => {
                              const newPurity = e.target.value;
                              const autoRate = parseFloat(goldRates[newPurity]) || 0;
                              updateInlineRow(idx, {
                                purity: newPurity,
                                ...(autoRate > 0 ? { rate: autoRate } : {}),
                              });
                            }}
                          >
                            <option value="">—</option>
                            {purityData.map((p) => <option key={p.id} value={p.purity}>{p.purity}</option>)}
                          </select>
                        </TableCell>
                        <TableCell className="p-1 border align-top"><Input type="number" className="h-7 text-sm w-16" value={row.pcs} onChange={(e) => updateInlineRow(idx, { pcs: e.target.value })} /></TableCell>
                        <TableCell className="p-1 border align-top"><Input type="number" step="0.001" className="h-7 text-sm w-16" value={row.ct} onChange={(e) => updateInlineRow(idx, { ct: e.target.value })} /></TableCell>
                        <TableCell className="p-1 border align-top"><Input type="number" step="0.001" className="h-7 text-sm w-20" value={row.gw} onChange={(e) => updateInlineRow(idx, { gw: e.target.value })} /></TableCell>
                        <TableCell className="p-1 border align-top"><Input type="number" step="0.001" className="h-7 text-sm w-16" value={row.loss} onChange={(e) => updateInlineRow(idx, { loss: e.target.value })} /></TableCell>
                        <TableCell className="p-1 border align-top"><Input type="number" step="0.01" className="h-7 text-sm w-16" value={row.tunch} onChange={(e) => updateInlineRow(idx, { tunch: e.target.value })} /></TableCell>
                        <TableCell className="p-1 border align-top text-right text-sm">{Number(row.fine_wt || 0).toFixed(3)}</TableCell>
                        <TableCell className="p-1 border align-top">
                          <select className="h-7 text-sm w-full px-1 border rounded" value={row.uom} onChange={(e) => updateInlineRow(idx, { uom: e.target.value })}>
                            <option value="Gm">Gm</option>
                            <option value="Pcs">Pcs</option>
                            <option value="Ct">Ct</option>
                          </select>
                        </TableCell>
                        <TableCell className="p-1 border align-top"><Input type="number" step="0.01" className="h-7 text-sm w-24" value={row.rate} onChange={(e) => updateInlineRow(idx, { rate: e.target.value })} /></TableCell>
                        <TableCell className="p-1 border align-top text-right text-sm font-medium">₹{Number(row.value || 0).toFixed(2)}</TableCell>
                        <TableCell className="p-1 border align-top text-center">
                          <button type="button" className="text-rose-500 hover:text-rose-700" onClick={() => { setInlineOldGold(prev => prev.filter((_, i) => i !== idx)); markTableDirty(); setCalculate(prev => prev + 1); }}>
                            <Trash2 className="size-3.5" />
                          </button>
                        </TableCell>
                      </TableRow>
                    );})}
                    <TableRow className="bg-accent-50">
                      <TableCell colSpan={10} className="px-2 py-1.5 border text-right text-xs font-semibold text-primary">Inline Old Gold Total</TableCell>
                      <TableCell className="px-2 py-1.5 border text-right text-sm font-bold text-primary">₹{inlineOldGoldTotal.toFixed(2)}</TableCell>
                      <TableCell className="border" />
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            )}
          </div>

        {/* ══ Order Advance Reconciliation / On-Account Advance ══ */}
        {(customerOrders.length > 0 || onAccountReceipts.length > 0 || loadingOnAccount) && (
          <div className="mb-4 rounded-lg border border-accent-200 bg-accent-50/60 p-4">
            <div className="flex items-center gap-2 mb-3">
              <ClipboardList className="size-4 text-primary" />
              <span className="text-sm font-semibold text-primary">
                {customerOrders.length > 0 ? "Link Customer Order & Apply Advance" : "Apply On-Account Advance"}
              </span>
            </div>
            {customerOrders.length > 0 && (
            <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FieldContainer>
                <Label className="text-nowrap text-primary">Customer Order</Label>
                <Controller
                  name="form.customer_order"
                  control={control}
                  render={({ field }) => (
                    <Select
                      value={field.value ? String(field.value) : "__none__"}
                      onValueChange={(val) => {
                        if (val === "__none__") {
                          field.onChange("");
                          setSelectedOrder(null);
                          setValue("form.advance_deducted", 0);
                        } else {
                          field.onChange(val);
                          const order = customerOrders.find(o => String(o.id) === val);
                          setSelectedOrder(order ?? null);
                          if (order) {
                            const avail = parseFloat(order.advance_available ?? order.advance_amt ?? 0);
                            setValue("form.advance_deducted", avail);
                            setCalculate(prev => prev + 1);
                          }
                        }
                      }}
                    >
                      <SelectTrigger className="h-9 text-sm bg-white">
                        <SelectValue placeholder="Select order…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— No order linked —</SelectItem>
                        {customerOrders.map(o => (
                          <SelectItem key={o.id} value={String(o.id)}>
                            {o.order_no} · ₹{parseFloat(o.advance_available ?? o.advance_amt ?? 0).toLocaleString('en-IN')} available
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </FieldContainer>
              {selectedOrder && (
                <div className="rounded-md border border-accent-200 bg-white px-4 py-3 text-sm flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <CheckCircle2 className="size-3.5 text-emerald-600" />
                    <span className="font-semibold text-primary">{selectedOrder.order_no}</span>
                    <span className="text-muted-foreground text-xs ml-auto">{selectedOrder.date1}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Total Advance</span>
                    <span className="font-medium">₹{parseFloat(selectedOrder.advance_amt || 0).toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Already Reconciled</span>
                    <span className="font-medium text-rose-600">
                      − ₹{parseFloat(selectedOrder.advance_reconciled || 0).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs border-t border-accent-100 pt-1 mt-0.5">
                    <span className="font-semibold text-primary">Available to Apply</span>
                    <span className="font-bold text-primary">
                      ₹{parseFloat(selectedOrder.advance_available ?? selectedOrder.advance_amt ?? 0).toLocaleString('en-IN')}
                    </span>
                  </div>
                </div>
              )}
            </div>
            {selectedOrder && (
              <div className="mt-3 flex items-center gap-3">
                <AlertCircle className="size-3.5 text-amber-600 shrink-0" />
                <p className="text-xs text-amber-700">
                  The full available advance is applied automatically. Any surplus
                  stays on the order and will roll into the next bill against it.
                </p>
              </div>
            )}
            </>
            )}
            {!selectedOrder && (loadingOnAccount || onAccountReceipts.length > 0) && (
              <div className={customerOrders.length > 0 ? "mt-3" : ""}>
                {customerOrders.length > 0 && (
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    On-account credits
                  </p>
                )}
                {loadingOnAccount ? (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="size-3 animate-spin" /> Loading…
                  </div>
                ) : (
                  <div className="rounded-md border border-border overflow-hidden bg-white">
                    {onAccountReceipts.map(r => {
                      const checked = selectedReceiptIds.includes(r.id);
                      return (
                        <label
                          key={r.id}
                          className={`flex items-center gap-3 px-3 py-2 cursor-pointer text-xs border-b last:border-0 transition-colors ${checked ? "bg-emerald-50" : "hover:bg-muted/30"}`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={e => {
                              const next = e.target.checked
                                ? [...selectedReceiptIds, r.id]
                                : selectedReceiptIds.filter(x => x !== r.id);
                              const nextSum = next.reduce((s, id) => {
                                const rec = onAccountReceipts.find(o => o.id === id);
                                return s + (rec ? parseFloat(rec.amount_remaining || 0) : 0);
                              }, 0);
                              if (e.target.checked) {
                                const grandTotal = parseFloat(getValues("form.total_bill_value") || 0);
                                const cashPaid   = parseFloat(getValues("form.cash") || 0);
                                const bankPaid   = bankdetails.reduce((s, b) => s + parseFloat(b.amount || 0), 0);
                                const oldGoldAdj = parseFloat(getValues("form.old_gold_adjusted") || 0);
                                const maxAdvance = Math.max(0, grandTotal - cashPaid - bankPaid - oldGoldAdj);
                                if (nextSum > maxAdvance + 0.01) {
                                  toast({
                                    title: "Advance exceeds bill balance",
                                    description: `Only ₹${maxAdvance.toFixed(2)} can be adjusted against this bill.`,
                                    variant: "destructive",
                                  });
                                  return;
                                }
                              }
                              setSelectedReceiptIds(next);
                              setValue("form.advance_deducted", parseFloat(nextSum.toFixed(2)));
                              setCalculate(prev => prev + 1);
                            }}
                            className="accent-primary"
                          />
                          <span className="font-mono flex-1">{r.voucher_no}</span>
                          <span className="text-muted-foreground">{r.date}</span>
                          <span className="font-medium text-emerald-700">
                            ₹{r.amount_remaining.toLocaleString("en-IN")} available
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
                {selectedReceiptIds.length > 0 && (
                  <p className="text-[10px] text-emerald-700 mt-1">
                    Selected credits will be applied as advance deduction on this bill.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        </div>{/* end left column */}

          {/* ── Bill Summary (right-side panel) ─────────────────────────────── */}
          <div className="w-full lg:w-[420px] shrink-0 mt-12">
            <BillSummaryPanel rows={billSummaryRows} register={register} watch={watch} standalone={false} autoCalcTotal={autoCalcEnabled} onAutoCalc={handleAutoCalcFromTotal} />
          </div>
        </div>{/* end outer flex row */}

        {/* Submit */}
        <div className="flex justify-center gap-3 mt-6 pt-4 border-t border-gray-100">
          <Button
            asChild
            className="bg-primary hover:bg-primary text-white px-8"
            disabled={saving || !canSave}
          >
            <button type="submit" disabled={saving || !canSave}>{saveLabel(saving)}</button>
          </Button>
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default SalesVoucherAdd;

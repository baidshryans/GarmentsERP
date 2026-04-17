import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useF2Navigate } from "@/hooks/useF2Navigate";
import { useEnterAsTab } from "@/hooks/useEnterAsTab";
import { SquarePen, Printer, Trash2, ClipboardList, CheckCircle2, AlertCircle, Gem, BadgePercent, PlusCircle } from "lucide-react";
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
  TableHead,
} from "@/components/ui/table";

import {
  getLedgers,
  createSalesVoucher,
  fetchBarcodeDetail,
  CashTotalLedger,
  fetchSaleVoucherInitialData,
  fetchSystemSettings,
  fetchMainItem,
  fetchPurity,
  fetchPackets,
  fetchExhibitions,
  fetchCustomerCashReceived,
  fetchCustomerOrdersByLedger,
  fetchCustomerPurchasesByLedger,
  fetchB2BPricelistForLedger,
  fetchRetailDiscountPricelistForLedger,
  fetchActiveOffer,
} from "@/services/apiService";
import { Link, useParams } from "react-router-dom";

import { FieldContainer } from "@/Utils.jsx";
import { fetchSalesVoucherwithID, updateSalesVoucher, getGoldRate } from "../../services/apiService";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";

// ─── Section header helper ──────────────────────────────────────────────────
const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 my-5">
    <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">{number}</span>
    <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</span>
    <div className="flex-1 h-px bg-violet-100" />
  </div>
);

// ─── Table header cell helper ────────────────────────────────────────────────
const TH = ({ children, className = "" }) => (
  <TableCell className={`px-4 py-2.5 border text-sm font-semibold text-primary uppercase tracking-wider whitespace-nowrap ${className}`}>
    {children}
  </TableCell>
);

const SalesVoucherAdd = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();

  const {
    register: originalRegister,
    handleSubmit,
    control,
    reset,
    watch,
    setValue,
    getValues,
    setFocus,
    formState: { errors },
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
        mode_of_transport: "",
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

  const { fields, append, remove } = useFieldArray({
    control,
    name: "salesvouitem_set",
  });

  // ── State ──────────────────────────────────────────────────────────────────
  const [rs, setRows] = useState([]);              // manual / raw items
  const [statesData, setstatesData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [hsns, setHsns] = useState([]);
  const [bankdetails, setBankDetails] = useState([]);
  const [bankLedgers, setBankLedgers] = useState([]);
  const [calculate, setCalculate] = useState(0);
  const [cashledger, setCashLedger] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [packets, setPackets] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [retailStateCode, setRetailStateCode] = useState("");
  const [goldRates, setGoldRates] = useState({});  // { "22KT": 4600, "24KT": 5000, … }
  const [exhibitions, setExhibitions] = useState([]);
  const [isExhibitionRetail, setIsExhibitionRetail] = useState(false);
  const [autoCalcEnabled, setAutoCalcEnabled] = useState(false);
  const [customerCashInfo, setCustomerCashInfo] = useState(null); // { cash_received, limit, remaining }
  const [customerOrders, setCustomerOrders] = useState([]);       // orders with available advance
  const [selectedOrder, setSelectedOrder] = useState(null);       // the linked CustomerOrder object
  const [customerPurchases, setCustomerPurchases] = useState([]); // old gold purchases with available balance
  const [selectedPurchase, setSelectedPurchase] = useState(null); // the linked PurchaseVoucher object
  const [b2bPricelist, setB2bPricelist] = useState(null);         // null = retail mode; object = B2B pricelist data
  const [retailDiscountPricelist, setRetailDiscountPricelist] = useState(null); // retail discount pricelist for Apply Discount
  const [activeOffer, setActiveOffer] = useState(null);           // company-wide active offer (retail only)
  const [enableGstBill, setEnableGstBill] = useState(false);      // driven by SystemSettings.enable_gst_bill
  const [showManualItems, setShowManualItems] = useState(false);  // section 3 toggle
  const [isVoucherLocked, setIsVoucherLocked] = useState(false); // true when any barcode is no longer in stock
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
  }, [detailPacket, packets, setValue, b2bPricelist]);

  // Recalculate value whenever rate or qty fields change
  useEffect(() => {
    if (!detailItem) return;
    setValue("details.value", computeValue(detailRate, detailItem.uom, detailPcs, detailCt, detailGw));
  }, [detailRate, detailPcs, detailCt, detailGw, detailItem]);

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
  }, [detailPurity, isRawItem, goldRates, b2bPricelist]);

  // ── Initial data load ──────────────────────────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      try {
        const [res, exhRes] = await Promise.all([
          fetchSaleVoucherInitialData(),
          fetchExhibitions(),
        ]);
        if (res.success) {
          const d = res.data;
          console.log("Initial data loaded:", d);
          setstatesData(d.states || []);
          setCustomers(d.ledgers || []);
          setSalespersonData(d.salespersons || []);
          setHsns(d.hsns || []);
          setMainItemData(d.items || []);
          setPurityData(d.purity || []);
          setPackets(d.packets || []);
          setValue("form.billno", d.billno);
          if (d.enable_gst_bill) {
            setEnableGstBill(true);
            setValue("form.gst_billno", d.gst_billno || "");
          }
          if (d.retail_state_code) setRetailStateCode(d.retail_state_code);
          if (d.is_exhibition) setIsExhibitionRetail(true);
        } else {
          console.error("Failed to fetch initial data:", res.error);
          toast({
            title: "Error",
            description: res.error?.error || "Failed to load form data. Please ensure you are logged in and have selected a retail location.",
            variant: "destructive",
          });
        }
        if (exhRes.success) {
          const list = Array.isArray(exhRes.data) ? exhRes.data : (exhRes.data?.results ?? []);
          setExhibitions(list);
          // Pre-select the profile marked as default (is_active = true), if any
          const defaultExh = list.find(e => e.is_active);
          if (defaultExh) setValue("form.exhibition_profile", String(defaultExh.id));
        }
      } catch (err) {
        console.error("Exception while fetching initial data:", err);
      }
      // Fetch today's gold rates for auto-filling rate on raw/gold items
      const today = new Date().toISOString().split("T")[0];
      getGoldRate(today).then(res => {
        if (res.success && Array.isArray(res.data)) {
          const rateMap = {};
          res.data.forEach(r => { if (r.purity_name) rateMap[r.purity_name] = r.selling_rate || r.rate; });
          setGoldRates(rateMap);
        }
      });

      // Fetch system settings, bank ledgers, active offer, AND the voucher being edited
      // all in parallel — the voucher fetch no longer waits for the other calls to finish.
      const [sysSettings, bankLedgersRes, offerRes, voucherResponse] = await Promise.all([
        fetchSystemSettings(),
        getLedgers({ type: "BA", page: 1 }),
        fetchActiveOffer(),
        // In create mode (no id) resolves immediately to null.
        id ? fetchSalesVoucherwithID(id) : Promise.resolve(null),
      ]);
      if (sysSettings.success) setAutoCalcEnabled(!!sysSettings.data.bill_total_auto_calc);
      if (bankLedgersRes.success) {
        const list = Array.isArray(bankLedgersRes.data) ? bankLedgersRes.data : (bankLedgersRes.data?.results ?? []);
        setBankLedgers(list);
      }
      if (offerRes.success && offerRes.data?.id) setActiveOffer(offerRes.data);

      return voucherResponse;
    }

    fetchData().then((voucherResponse) => {
      if (id) {
        if (!voucherResponse?.success) {
          console.error('Error fetching sales voucher for edit:', voucherResponse?.error);
        } else {
          const data = voucherResponse.data;
          // Lock editing if any barcode in this voucher is no longer in stock
          // (stk_status=false means it has been sold/transferred).
          const hasSoldBarcode = (data.salesvouitem_set ?? []).some(
            item => item.barcode_stk_status === false
          );
          if (hasSoldBarcode) setIsVoucherLocked(true);
          const formData = {
            form: {
              ...data,
              salesvouitem_set: JSON.parse(JSON.stringify(data.salesvouitem_set ?? [])),
            }
          };
          Object.keys(formData.form).forEach(key => {
            if (key === 'salesvouitem_set') {
              formData.form[key].forEach(item => append(item));
            } else if (key !== 'salesvouitemdetails_set' && key !== 'bank_details') {
              setValue(`form.${key}`, formData.form[key]);
            }
          });
          if (data.bank_details) {
            setBankDetails(data.bank_details);
          }
          // Restore manual items
          if (data.salesvouitemdetails_set?.length) {
            setRows(data.salesvouitemdetails_set);
          }
          // Restore old gold purchase link (still sequential — needs ldgr from voucher data)
          if (data.old_gold_purchase && data.ldgr) {
            fetchCustomerPurchasesByLedger(data.ldgr).then(res => {
              if (res.success) {
                setCustomerPurchases(res.data);
                const pv = res.data.find(p => p.id === data.old_gold_purchase);
                setSelectedPurchase(pv ?? null);
              }
            });
          }
        }
      }
    });
  }, [setValue]);

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
    total_bill_value: `${tcs_amt_formula} + ${total_incl_gst_formula}`,
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

  // Recalculate formulas whenever anything changes
  useEffect(() => {
    const form = { ...getValues('form'), salesvouitem_set: getValues('salesvouitem_set'), rs };

    getValues('salesvouitem_set').forEach((row, index) => {
      // Recalculate sub-item amounts
      getValues(`salesvouitem_set.${index}.main_item_set`)?.forEach((data, sub_index) => {
        Object.keys(sub_formulas).forEach(column => {
          setValue(`salesvouitem_set.${index}.main_item_set.${sub_index}.${column}`, evaluateFormula(sub_formulas[column], data));
        });
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
  }, [calculate, setValue, watchFields, rs, goldRates]);

  // HSN → set GST rates based on place of supply vs retail state
  useEffect(() => {
    const hsn_ = hsns.find(e => e.hsn_no === hsn_current);
    if (!hsn_) return;
    // Use retailStateCode from initial data (same code system as place_of_supply options).
    // Fall back to localStorage only if initial data hasn't loaded yet.
    const retailState = retailStateCode || localStorage.getItem('state_code') || "";
    const isIntraState = place_of_supply === retailState;
    setValue('form.sgst_per', isIntraState ? parseFloat(hsn_.sgst) : 0.0);
    setValue('form.cgst_per', isIntraState ? parseFloat(hsn_.cgst) : 0.0);
    setValue('form.igst_per', isIntraState ? 0.0 : parseFloat(hsn_.igst));
    setCalculate(prev => prev + 1);
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
      const data = await fetchBarcodeDetail(barcode, hsn);
      if (data.success) {
        const item = b2bPricelist ? applyB2bOverrides(data.data) : data.data;
        append(item);
      } else {
        toast({ title: "Barcode not found", description: JSON.stringify(data.error) || "Server error" });
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

  /** @deprecated Use handleDeleteMainItem / handleDeleteSubItem */
  const handleDeleteManualRow = (index) => {
    setRows(prev => prev.filter((_, i) => i !== index));
    setCalculate(prev => prev + 1);
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
      data.due_amt         = Math.max(0, grandTotal - cashPaid - bankPaid - advDeducted - oldGoldAdj).toFixed(2);
      // Send null when no order/purchase linked (avoid empty-string FK)
      if (!data.customer_order) data.customer_order = null;
      if (!data.old_gold_purchase) data.old_gold_purchase = null;

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

      const response = id
        ? await updateSalesVoucher(data, id)
        : await createSalesVoucher(data);

      if (response.success) {
        toast({ title: "Form submitted successfully!" });
        setTimeout(() => navigate("/sales/list/"), 500);
      } else {
        toast({ title: "Form submission failed.", description: renderErrorTree(response.error) });
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

    // ── Retail pricelist discount ──────────────────────────────────────────
    let retailDiscount = 0;
    if (retailDiscountPricelist) {
      const ruleByPurity = Object.fromEntries(
        (retailDiscountPricelist.rules || []).map(r => [r.purity, r])
      );
      for (const item of items) {
        const rule = ruleByPurity[item.metal_purity];
        if (!rule) continue;
        retailDiscount += parseFloat(item.making_value || 0) * parseFloat(rule.making_discount_pct || 0) / 100;
        for (const sub of (item.main_item_set || [])) {
          if (sub.pckt_no)
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
        const rule = offerRuleByPurity[item.metal_purity];
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
          if (sub.pckt_no)
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
    { label: 'Round Off',      field: 'form.round_off',      editable: true, step: '0.01' },
    { isSeparator: true },
    { label: 'MRP',            field: 'form.mrp' },
    { label: 'Discount',       field: 'form.discount',       editable: true, step: '0.01' },
    { label: 'Taxable Value',  field: 'form.taxable_value' },
    { label: 'CGST',           field: 'form.cgst_amt' },
    { label: 'IGST',           field: 'form.igst_amt' },
    { label: 'SGST',           field: 'form.sgst_amt' },
    { label: 'Total incl. GST',field: 'form.total_incl_gst' },
    { label: 'TCS',            field: 'form.tcs_amt' },
    { isSeparator: true },
    { label: 'Total',          field: 'form.total_bill_value', isTotal: true, isEditableTotal: true },
    ...(selectedOrder ? [{ label: 'Advance Deducted', field: 'form.advance_deducted', editable: false, step: '1' }] : []),
    ...(selectedPurchase ? [{ label: 'Old Gold Adjusted', field: 'form.old_gold_adjusted', editable: true, step: '1' }] : []),
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

        {/* ── Locked voucher banner ────────────────────────────────────────── */}
        {isVoucherLocked && (
          <div className="flex items-start gap-3 mb-5 px-4 py-3 rounded-lg bg-amber-50 border border-amber-300 text-amber-800 text-sm">
            <span className="text-lg leading-none">🔒</span>
            <div>
              <p className="font-semibold">This voucher cannot be edited.</p>
              <p className="text-xs mt-0.5 text-amber-700">
                One or more barcodes in this bill are no longer in stock (already sold or transferred).
                To make corrections, please create a <strong>Sales Return</strong> first.
              </p>
            </div>
          </div>
        )}

        {/* ══ 1. BILL DETAILS ══════════════════════════════════════════════════ */}
        <SectionHeader number="1" title="Bill Details" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          {/* Bill No — auto-generated, read-only */}
          <FieldContainer>
            <Label className="text-nowrap">Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                {watch("form.billno") || <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>}
              </span>
              <input type="hidden" {...register("form.billno", { required: true })} />
            </div>
          </FieldContainer>

          {enableGstBill && (
            <FieldContainer>
              <Label className="text-nowrap">GST Bill No</Label>
              <div className="flex items-center gap-2 flex-1">
                <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                  {watch("form.gst_billno") || <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>}
                </span>
                <input type="hidden" {...register("form.gst_billno", { required: true })} />
              </div>
            </FieldContainer>
          )}

          {/* Party Name with ledger lookup */}
          <FieldContainer>
            <Label className="text-nowrap">Party Name</Label>
            <div className="relative">
              <SearchableComboBox
                options={customers}
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
                  setCustomerPurchases(purchasesRes.success ? purchasesRes.data : []);
                  setSelectedPurchase(null);
                  setValue("form.old_gold_purchase", "");
                  setValue("form.old_gold_adjusted", 0);
                  setB2bPricelist(plRes.success && plRes.data ? plRes.data : null);
                  setRetailDiscountPricelist(rdplRes.success && rdplRes.data ? rdplRes.data : null);
                }}
                placeholder="Search customer…"
              />
              <input type="hidden" {...register("form.ldgr")} />
              <p className="text-xs mt-1 text-gray-500">
                Ledger cash: {cashledger}
                {b2bPricelist && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                    B2B: {b2bPricelist.name}
                  </span>
                )}
                {retailDiscountPricelist && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-green-50 text-green-700 border border-green-200">
                    Discount: {retailDiscountPricelist.name}
                  </span>
                )}
                {activeOffer && !b2bPricelist && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
                    Offer: {activeOffer.name}
                  </span>
                )}
              </p>
            </div>
          </FieldContainer>
        </div>
        {customerCashInfo && (() => {
          const { cash_received, limit, remaining } = customerCashInfo;
          const pct = limit > 0 ? Math.min(100, (cash_received / limit) * 100) : 0;
          const isNearLimit = remaining < limit * 0.1;
          const isAtLimit   = remaining <= 0;
          return (
            <div className={`mb-4 rounded-md border px-3 py-2 text-xs ${
              isAtLimit   ? 'bg-red-50 border-red-200 text-red-700' :
              isNearLimit ? 'bg-amber-50 border-amber-200 text-amber-700' :
                            'bg-gray-50 border-gray-200 text-gray-600'
            }`}>
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-medium">Cash received this FY</span>
                <span className="font-mono font-semibold">
                  ₹{cash_received.toLocaleString('en-IN')} / ₹{limit.toLocaleString('en-IN')}
                </span>
              </div>
              <div className="h-1 rounded-full bg-gray-200 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    isAtLimit ? 'bg-red-500' : isNearLimit ? 'bg-amber-400' : 'bg-violet-400'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {isAtLimit
                ? <p className="mt-1 font-semibold text-red-600">⚠ Cash limit reached — no further cash can be accepted from this customer this FY.</p>
                : <p className="mt-1 text-muted-foreground">Remaining: ₹{remaining.toLocaleString('en-IN')}</p>
              }
            </div>
          );
        })()}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Date</Label>
            <Input type="date" {...register("form.date1", { required: true })} />
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
            <Label className="text-nowrap">Mode of Transport</Label>
            <Input type="text" {...register("form.mode_of_transport")} />
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

        {/* ══ Order Advance Reconciliation ════════════════════════════════════ */}
        {customerOrders.length > 0 && (
          <div className="mb-4 rounded-lg border border-violet-200 bg-violet-50/60 p-4">
            <div className="flex items-center gap-2 mb-3">
              <ClipboardList className="size-4 text-primary" />
              <span className="text-sm font-semibold text-primary">Link Customer Order &amp; Apply Advance</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Order dropdown */}
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
                          // Auto-fill with available advance
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

              {/* Advance info card */}
              {selectedOrder && (
                <div className="rounded-md border border-violet-200 bg-white px-4 py-3 text-sm flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <CheckCircle2 className="size-3.5 text-emerald-600" />
                    <span className="font-semibold text-primary">{selectedOrder.order_no}</span>
                    <span className="text-muted-foreground text-xs ml-auto">{selectedOrder.date1}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Estimated Value</span>
                    <span className="font-medium">₹{parseFloat(selectedOrder.est_amount || 0).toLocaleString('en-IN')}</span>
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
                  <div className="flex justify-between text-xs border-t border-violet-100 pt-1 mt-0.5">
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
          </div>
        )}

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
              <TableRow className="bg-violet-50">
                <TH>Barcode</TH><TH>Packet</TH><TH>Item</TH><TH>Pcs</TH>
                <TH>Ct</TH><TH>GW</TH><TH>Making</TH><TH>Making Type</TH>
                <TH>Making Value</TH><TH>Purity</TH><TH>Tunch</TH>
                <TH>Fine Wt</TH><TH>Rate</TH><TH>Amount</TH><TH>Del</TH>
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
                  <TableRow className="bg-violet-50">
                    <TableCell className="px-3 py-2 border text-sm">{field?.barcode}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.packet}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.item}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.pcs}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{Number(field?.ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="px-3 py-2 border text-sm">{field?.gw}</TableCell>
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
                    <TableCell className="px-3 py-2 border">
                      <Trash2 color="#d45959" className="size-4 cursor-pointer" onClick={() => remove(index)} />
                    </TableCell>
                  </TableRow>

                  {/* Sub-item (stone / metal) rows */}
                  {field.main_item_set?.map((detail, idx) => (
                    <TableRow key={idx} className="bg-gray-50">
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.packet}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.item}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.pcs}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{Number(detail?.ct || 0).toFixed(3)}</TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.gw}</TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.purity}</TableCell>
                      <TableCell className="w-20 px-3 py-2 border">
                        {detail?.item === "Gold" && (
                          <Input type="text" className="h-7 text-sm" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.tunch`)} placeholder="Tunch" />
                        )}
                      </TableCell>
                      <TableCell className="px-3 py-2 border text-sm"></TableCell>
                      <TableCell className="w-20 px-3 py-2 border">
                        <Input type="text" className="h-7 text-sm" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.rate`)} placeholder="Rate" />
                      </TableCell>
                      <TableCell className="px-3 py-2 border text-sm">{detail?.amount}</TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
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
              <TableRow className="bg-violet-50">
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
                    {mainItemData.map((m, i) => <option key={i} value={m.item_name} />)}
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
                <TableRow className="bg-violet-50">
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
                      <TableCell className="px-3 py-2 border text-xs font-bold text-sky-800">{mainItem.gw}</TableCell>
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
                          <TableCell className="px-3 py-2 border text-sm">{detail.gw}</TableCell>
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
              <TableRow className="bg-violet-50">
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
                  <PlusCircle size={20} className="cursor-pointer text-violet-600 mx-auto" onClick={handleAddBank} />
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
                  >
                    <option value="">— Select Bank A/C —</option>
                    {bankLedgers.map(l => (
                      <option key={l.id} value={l.id}>{l.ac_name}</option>
                    ))}
                  </select>
                </TableCell>
                {bankPaymentMode === "CHEQUE" && (
                  <TableCell className="px-3 py-2 border">
                    <Input type="date" onKeyDown={handleKeyDown} {...register("bank.chq_date")} />
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

        {/* ══ 5. REMARKS ═══════════════════════════════════════════════════════ */}
        <SectionHeader number="5" title="Remarks" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Remarks</Label>
            <Input type="text" {...register("form.remarks")} />
          </FieldContainer>
        </div>

        {/* ══ 6. BILL SUMMARY ══════════════════════════════════════════════════ */}
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
        <BillSummaryPanel rows={billSummaryRows} register={register} watch={watch} autoCalcTotal={autoCalcEnabled} onAutoCalc={handleAutoCalcFromTotal} />

        {/* Submit */}
        <div className="flex justify-center gap-3 mt-6 pt-4 border-t border-gray-100">
          <Button
            asChild
            className="bg-primary hover:bg-primary text-white px-8"
            disabled={isVoucherLocked}
            title={isVoucherLocked ? "Voucher is locked — barcodes are no longer in stock" : undefined}
          >
            <button type="submit" disabled={isVoucherLocked}>Save</button>
          </Button>
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default SalesVoucherAdd;

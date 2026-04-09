import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useEnterAsTab } from "@/hooks/useEnterAsTab";
import { SquarePen, Printer, Trash2, ClipboardList, CheckCircle2, AlertCircle, Gem } from "lucide-react";
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
} from "@/services/apiService";
import { Link, useParams } from "react-router-dom";

import { FieldContainer } from "@/Utils.jsx";
import { fetchSalesVoucherwithID, updateSalesVoucher, getGoldRate } from "../../services/apiService";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../Utils";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";

// ─── Section header helper ──────────────────────────────────────────────────
const SectionHeader = ({ number, title }) => (
  <div className="flex items-center gap-3 my-5">
    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">{number}</span>
    <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</span>
    <div className="flex-1 h-px bg-violet-100" />
  </div>
);

// ─── Table header cell helper ────────────────────────────────────────────────
const TH = ({ children, className = "" }) => (
  <TableCell className={`px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap ${className}`}>
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
    amount: "", chq_no: "", bank_name: "", ledger: "", ledger_name: "", chq_date: "",
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
      const rate = pkt.rate_for_retail ?? 0;
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
  }, [detailPacket, packets, setValue]);

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
    const rate = goldRates[detailPurity];
    if (rate !== undefined) {
      setValue("details.rate", rate);
    }
  }, [detailPurity, isRawItem, goldRates]);

  // ── Initial data load ──────────────────────────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetchSaleVoucherInitialData();
        if (res.success) {
          const d = res.data;
          console.log("Initial data loaded:", d);
          setstatesData(d.states || []);
          setCustomers(d.ledgers || []);
          setSalespersonData(d.salespersons || []);
          setHsns(d.hsns || []);
          setValue("form.billno", d.billno);
          if (d.retail_state_code) setRetailStateCode(d.retail_state_code);
          if (d.is_exhibition) setIsExhibitionRetail(true);

          // Load exhibition profiles for this retail (only relevant for exhibition retails)
          const exhRes = await fetchExhibitions();
          if (exhRes.success) {
            const list = Array.isArray(exhRes.data) ? exhRes.data : (exhRes.data?.results ?? []);
            setExhibitions(list);
            // Pre-select the profile marked as default (is_active = true), if any
            const defaultExh = list.find(e => e.is_active);
            if (defaultExh) setValue("form.exhibition_profile", String(defaultExh.id));
          }
        } else {
          console.error("Failed to fetch initial data:", res.error);
          toast({
            title: "Error",
            description: res.error?.error || "Failed to load form data. Please ensure you are logged in and have selected a retail location.",
            variant: "destructive",
          });
        }
      } catch (err) {
        console.error("Exception while fetching initial data:", err);
      }
      // Fetch today's gold rates for auto-filling rate on raw/gold items
      const today = new Date().toISOString().split("T")[0];
      getGoldRate(today).then(res => {
        if (res.success && Array.isArray(res.data)) {
          const rateMap = {};
          res.data.forEach(r => { if (r.purity_name) rateMap[r.purity_name] = r.rate; });
          setGoldRates(rateMap);
        }
      });

      // Additional master data needed for manual item entry
      const [mainItem, purity, packetsRes, sysSettings, bankLedgersRes] = await Promise.all([
        fetchMainItem(),
        fetchPurity(),
        fetchPackets(),
        fetchSystemSettings(),
        getLedgers({ type: "BA", page: 1 }),
      ]);
      if (mainItem.success) setMainItemData(mainItem.data);
      if (purity.success) setPurityData(purity.data);
      if (packetsRes.success) setPackets(packetsRes.data);
      if (sysSettings.success) setAutoCalcEnabled(!!sysSettings.data.bill_total_auto_calc);
      if (bankLedgersRes.success) {
        const list = Array.isArray(bankLedgersRes.data) ? bankLedgersRes.data : (bankLedgersRes.data?.results ?? []);
        setBankLedgers(list);
      }
    }

    fetchData().then(() => {
      if (id) {
        fetchSalesVoucherwithID(id).then(data => {
          if (data.success) {
            const formData = {
              form: {
                ...data.data,
                salesvouitem_set: JSON.parse(JSON.stringify(data.data.salesvouitem_set ?? [])),
              }
            };
            Object.keys(formData.form).forEach(key => {
              if (key === 'salesvouitem_set') {
                formData.form[key].forEach(item => append(item));
              } else {
                setValue(`form.${key}`, formData.form[key]);
              }
            });
            if (data.data.bank_details) {
              setBankDetails(data.data.bank_details);
            }
            // Restore manual items
            if (data.data.salesvouitemdetails_set?.length) {
              setRows(data.data.salesvouitemdetails_set);
            }
            // Restore old gold purchase link
            if (data.data.old_gold_purchase && data.data.ldgr) {
              fetchCustomerPurchasesByLedger(data.data.ldgr).then(res => {
                if (res.success) {
                  setCustomerPurchases(res.data);
                  const pv = res.data.find(p => p.id === data.data.old_gold_purchase);
                  setSelectedPurchase(pv ?? null);
                }
              });
            }
          }
        });
      }
    });
  }, [setValue]);

  // ── Formulas ───────────────────────────────────────────────────────────────
  const hsn_current = watch('hsn');
  const place_of_supply = watch('form.place_of_supply');
  const watchFields = watch("salesvouitem_set");
  const party_name = watch('form.ldgr_name');

  const formulas = {
    making_value: "making_type === 'val' ? making : ((making / 100)*making)",
    amount: "SUM(main_item_set.amount) + making_value",
  };
  const sub_formulas = {
    amount: "uom === 'Ct' ? ct * rate : gw * rate",
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
      Object.keys(formulas).forEach(col => {
        getValues(`salesvouitem_set.${index}.main_item_set`)?.forEach((data, sub_index) => {
          Object.keys(sub_formulas).forEach(column => {
            setValue(`salesvouitem_set.${index}.main_item_set.${sub_index}.${column}`, evaluateFormula(sub_formulas[column], data));
          });
        });
        setValue(`salesvouitem_set.${index}.${col}`, Math.floor(evaluateFormula(formulas[col], row)));
      });
    });

    Object.keys(main_formulas).forEach(col => {
      setValue(`form.${col}`, evaluateFormula(main_formulas[col], form));
    });
  }, [calculate, setValue, watchFields, rs]);

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

  // ── Barcode scan handler ───────────────────────────────────────────────────
  const handleBlur = async () => {
    const { barcode, hsn } = getValues();
    if (!barcode?.trim()) return;   // blank barcode is fine — manual items don't need one
    try {
      const data = await fetchBarcodeDetail(barcode, hsn);
      if (data.success) {
        append(data.data);
      } else {
        toast({ title: "Barcode not found", description: JSON.stringify(data.error) || "Server error" });
      }
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  // ── Bank detail handlers ───────────────────────────────────────────────────
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
        onSubmit={handleSubmit(handleSalesVoucherSubmit, (e) => console.log("submission error", e))}
      >

        {/* ══ 1. BILL DETAILS ══════════════════════════════════════════════════ */}
        <SectionHeader number="1" title="Bill Details" />

        <div className="grid grid-cols-3 gap-6 mb-4">
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

          <FieldContainer>
            <Label className="text-nowrap">GST Bill No</Label>
            <Input type="text" {...register("form.gst_billno", { required: true })} />
          </FieldContainer>

          {/* Party Name with ledger lookup */}
          <FieldContainer>
            <Label className="text-nowrap">Party Name</Label>
            <div className="relative">
              <Input
                list="party_list"
                {...register("form.ldgr_name", {
                  required: true,
                  onChange: async (e) => {
                    const selected = customers.find(c => c.ac_name === e.target.value);
                    if (selected) {
                      setValue("form.ldgr", selected.id);
                      // Auto-set place of supply from customer's shipping state (fallback to billing state)
                      const customerState = selected.ship_state || selected.state;
                      if (customerState && customerState !== 'none') {
                        setValue("form.place_of_supply", customerState);
                      }
                      const ldgrcash = await CashTotalLedger(selected.id);
                      setCashLedger(ldgrcash.data.total_cash);
                      // Fetch cash-received-this-FY for the 269ST limit indicator
                      const cashRes = await fetchCustomerCashReceived(selected.id);
                      setCustomerCashInfo(cashRes.success ? cashRes.data : null);
                      // Fetch open customer orders with available advance for this customer
                      const ordersRes = await fetchCustomerOrdersByLedger(selected.id);
                      setCustomerOrders(ordersRes.success ? ordersRes.data : []);
                      setSelectedOrder(null);
                      setValue("form.customer_order", "");
                      setValue("form.advance_deducted", 0);
                      // Fetch customer purchases (old gold) with available balance
                      const purchasesRes = await fetchCustomerPurchasesByLedger(selected.id);
                      setCustomerPurchases(purchasesRes.success ? purchasesRes.data : []);
                      setSelectedPurchase(null);
                      setValue("form.old_gold_purchase", "");
                      setValue("form.old_gold_adjusted", 0);
                    } else {
                      setCustomerCashInfo(null);
                      setCustomerOrders([]);
                      setSelectedOrder(null);
                      setCustomerPurchases([]);
                      setSelectedPurchase(null);
                    }
                  },
                })}
              />
              <Input type="hidden" {...register("form.ldgr")} />
              <p className="text-xs mt-1 text-gray-500">Ledger cash: {cashledger}</p>
              {customerCashInfo && (() => {
                const { cash_received, limit, remaining } = customerCashInfo;
                const pct = limit > 0 ? Math.min(100, (cash_received / limit) * 100) : 0;
                const isNearLimit = remaining < limit * 0.1;   // < 10% remaining
                const isAtLimit   = remaining <= 0;
                return (
                  <div className={`mt-1.5 rounded-md border px-2.5 py-1.5 text-xs ${
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
            </div>
            <datalist id="party_list">
              {customers.map((c, i) => <option key={i} value={c.ac_name}>{c.id}</option>)}
            </datalist>
          </FieldContainer>
        </div>

        <div className="grid grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Date</Label>
            <Input type="date" {...register("form.date1", { required: true })} />
          </FieldContainer>

          <FieldContainer>
            <Label className="text-nowrap">Sales Person</Label>
            <Controller name="form.sales_person" control={control} rules={{ required: true }}
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

          <FieldContainer>
            <Label className="text-nowrap">Salesperson 2</Label>
            <Controller name="form.sales_person2" control={control} rules={{ required: true }}
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

        <div className="grid grid-cols-3 gap-6 mb-4">
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
          <div className="grid grid-cols-3 gap-6 mb-4">
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
        <div className="grid grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">HSN Code</Label>
            <Controller name="hsn" control={control}
              render={({ field }) => (
                <Select disabled={getValues("salesvouitem_set").length > 0} onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger><SelectValue placeholder="Select HSN" /></SelectTrigger>
                  <SelectContent>
                    {hsns.map((h, i) => <SelectItem key={i} value={h.hsn_no}>{h.description || h.hsn_no}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
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

              {watchFields.map((field, index) => (
                <React.Fragment key={field.id || index}>
                  {/* Main item row */}
                  <TableRow className="bg-violet-50">
                    <TableCell className="px-3 py-2 border text-xs">{field?.barcode}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{field?.packet}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{field?.item}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{field?.pcs}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{Number(field?.ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{field?.gw}</TableCell>
                    <TableCell className="w-24 px-3 py-2 border">
                      <Input type="number" className="h-7 text-xs" {...register(`salesvouitem_set.${index}.making`, { valueAsNumber: true })} />
                    </TableCell>
                    <TableCell className="w-28 px-3 py-2 border">
                      <Controller name={`salesvouitem_set.${index}.making_type`} control={control}
                        render={({ field }) => (
                          <Select onValueChange={field.onChange} value={field.value}>
                            <SelectTrigger className="h-7 text-xs"><SelectValue placeholder="Type" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="per_nw">% of wt</SelectItem>
                              <SelectItem value="val">Value</SelectItem>
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </TableCell>
                    <TableCell className="w-24 px-3 py-2 border">
                      <Input type="number" className="h-7 text-xs" {...register(`salesvouitem_set.${index}.making_value`, { valueAsNumber: true })} />
                    </TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{field?.purity}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs">{field?.tunch ? Number(field.tunch).toFixed(2) : "0.00"}</TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs"></TableCell>
                    <TableCell className="px-3 py-2 border text-xs">
                      {field?.amount}
                      <input type="hidden" {...register(`salesvouitem_set.${index}.amount`)} />
                    </TableCell>
                    <TableCell className="px-3 py-2 border">
                      <Trash2 size={16} color="#d45959" className="cursor-pointer" onClick={() => remove(index)} />
                    </TableCell>
                  </TableRow>

                  {/* Sub-item (stone / metal) rows */}
                  {field.main_item_set?.map((detail, idx) => (
                    <TableRow key={idx} className="bg-gray-50">
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{detail?.packet}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{detail?.item}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{detail?.pcs}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{Number(detail?.ct || 0).toFixed(3)}</TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{detail?.gw}</TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{detail?.purity}</TableCell>
                      <TableCell className="w-20 px-3 py-2 border">
                        <Input type="text" className="h-7 text-xs" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.tunch`)} placeholder="Tunch" />
                      </TableCell>
                      <TableCell className="px-3 py-2 border text-xs"></TableCell>
                      <TableCell className="w-20 px-3 py-2 border">
                        <Input type="text" className="h-7 text-xs" {...register(`salesvouitem_set.${index}.main_item_set.${idx}.rate`)} placeholder="Rate" />
                      </TableCell>
                      <TableCell className="px-3 py-2 border text-xs">{detail?.amount}</TableCell>
                      <TableCell className="px-3 py-2 border"></TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* ══ 3. MANUAL / RAW ITEMS ════════════════════════════════════════════ */}
        <SectionHeader number="3" title="Manual Items (No Barcode)" />

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
                  <Input type="number" step="0.001" {...register("details.loss")} placeholder="Loss" />
                </TableCell>
                <TableCell className="w-20 px-3 py-2 border">
                  <Input type="number" step="0.001" {...register("details.tunch")} placeholder="Tunch" />
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
                        <Trash2 size={14} color="#d45959" className="cursor-pointer mx-auto" onClick={() => handleDeleteMainItem(mainIdx)} />
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
                          <TableCell className="px-3 py-2 border text-xs">{detail.item_name || detail.item}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{detail.pcs || ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{Number(detail.ct || 0).toFixed(3)}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{detail.gw}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{rowIsRaw ? detail.loss : ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{rowIsRaw ? detail.tunch : ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{rowIsRaw ? detail.fine_wt : ""}</TableCell>
                          <TableCell className="px-3 py-2 border text-xs">{detail.rate}</TableCell>
                          {/* Making/Discount blank for sub-items */}
                          <TableCell className="px-3 py-2 border" />
                          <TableCell className="px-3 py-2 border" />
                          <TableCell className="px-3 py-2 border text-xs">{detail.value}</TableCell>
                          <TableCell className="px-3 py-2 border" />
                          <TableCell className="px-3 py-2 border text-center">
                            <Trash2 size={14} color="#d45959" className="cursor-pointer mx-auto" onClick={() => handleDeleteSubItem(mainIdx, subIdx)} />
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

        {/* ══ 4. PAYMENT DETAILS ═══════════════════════════════════════════════ */}
        <SectionHeader number="4" title="Payment Details" />

        <div className="grid grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Cash</Label>
            <Input type="number" {...register("form.cash")} />
          </FieldContainer>
        </div>

        <div className="overflow-x-auto">
          <Table className="w-full border-collapse">
            <TableBody>
              <TableRow className="bg-violet-50">
                <TH className="w-20">Action</TH>
                <TH>Amount</TH><TH>Chq / Card No</TH>
                <TH>Bank Name</TH><TH>Our Bank A/C</TH><TH>Date</TH>
              </TableRow>

              {/* Bank detail input row */}
              <TableRow>
                <TableCell className="w-20 px-3 py-2 border"></TableCell>
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
                <TableCell className="px-3 py-2 border">
                  <Input type="date" onKeyDown={handleKeyDown} {...register("bank.chq_date")} />
                </TableCell>
              </TableRow>

              {/* Saved bank entries */}
              {bankdetails.map((b, index) => (
                <TableRow key={index}>
                  <TableCell className="px-3 py-2 border">
                    <div className="flex gap-3">
                      <SquarePen size={16} className="cursor-pointer" onClick={() => handleEditBank(index)} />
                      <Trash2 size={16} color="#d45959" className="cursor-pointer" onClick={() => handleDeleteBank(index)} />
                    </div>
                  </TableCell>
                  <TableCell className="px-3 py-2 border text-xs">{b?.amount}</TableCell>
                  <TableCell className="px-3 py-2 border text-xs">{b?.chq_no}</TableCell>
                  <TableCell className="px-3 py-2 border text-xs">{b?.bank_name}</TableCell>
                  <TableCell className="px-3 py-2 border text-xs">{b?.ledger_name}</TableCell>
                  <TableCell className="px-3 py-2 border text-xs">{b?.chq_date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* ══ 5. REMARKS ═══════════════════════════════════════════════════════ */}
        <SectionHeader number="5" title="Remarks" />

        <div className="grid grid-cols-3 gap-6 mb-4">
          <FieldContainer>
            <Label className="text-nowrap">Remarks</Label>
            <Input type="text" {...register("form.remarks", { required: true })} />
          </FieldContainer>
        </div>

        {/* ══ 6. BILL SUMMARY ══════════════════════════════════════════════════ */}
        <BillSummaryPanel rows={billSummaryRows} register={register} watch={watch} autoCalcTotal={autoCalcEnabled} onAutoCalc={handleAutoCalcFromTotal} />

        {/* Submit */}
        <div className="flex justify-center gap-3 mt-6 pt-4 border-t border-gray-100">
          <Button asChild className="bg-primary hover:bg-primary text-white px-8">
            <button type="submit">Save</button>
          </Button>
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default SalesVoucherAdd;

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";
import { ShoppingCart } from "lucide-react";
import {
  getLedgers,
  createSalesVoucher,
  fetchBarcodeDetail,
  fetchSaleVoucherInitialData,
  fetchExhibitions,
  fetchCustomerCashReceived,
  fetchCustomerPurchasesByLedger,
  fetchB2BPricelistForLedger,
  fetchRetailDiscountPricelistForLedger,
  fetchActiveOffer,
  getGoldRate,
} from "@/services/apiService";
import { renderErrorTree } from "@/Utils";
import POSBillHeader from "./POSBillHeader";
import POSItemsTable from "./POSItemsTable";
import POSPaymentPanel from "./POSPaymentPanel";
import CustomerSelectModal from "./CustomerSelectModal";

// ── helpers ──────────────────────────────────────────────────────────────────
const TODAY = new Date().toISOString().split("T")[0];

const emptyForm = () => ({
  date1: TODAY,
  invoice_date: TODAY,
  billno: "",
  ldgr: "",
  place_of_supply: "",
  hsn: "",
  exhibition_profile: "",
  customer_order: null,
  old_gold_purchase: null,
  old_gold_adjusted: 0,
  discount: 0,
  mrp: 0,
  sgst_per: 0,
  cgst_per: 0,
  igst_per: 0,
  tcs_per: 0,
  other_charge: 0,
  freight_charge: 0,
  round_off: 0,
  remarks: "",
  gst_type: "gst1",
  ret_status: false,
  sales_person: "",
});

export default function POSView() {
  const { toast } = useToast();
  const navigate  = useNavigate();

  // ── Master data ────────────────────────────────────────────────────────────
  const [statesData,      setStatesData]      = useState([]);
  const [customers,       setCustomers]       = useState([]);
  const [hsns,            setHsns]            = useState([]);
  const [bankLedgers,     setBankLedgers]     = useState([]);
  const [goldRates,       setGoldRates]       = useState({});
  const [retailStateCode, setRetailStateCode] = useState("");

  // ── Bill header form ───────────────────────────────────────────────────────
  const [form,            setForm]            = useState(emptyForm());

  // ── Items ──────────────────────────────────────────────────────────────────
  const [barcodeItems,    setBarcodeItems]    = useState([]);   // barcode-scanned rows
  const [manualItems,     setManualItems]     = useState([]);   // manual rows (future)

  // ── Payment ───────────────────────────────────────────────────────────────
  const [cash,            setCash]            = useState(0);
  const [bankDetails,     setBankDetails]     = useState([]);
  const [advanceDeducted, setAdvanceDeducted] = useState(0);

  // ── Customer context ──────────────────────────────────────────────────────
  const [customerCashInfo,    setCustomerCashInfo]    = useState(null);
  const [customerPurchases,   setCustomerPurchases]   = useState([]);
  const [selectedPurchase,    setSelectedPurchase]    = useState(null);
  const [b2bPricelist,        setB2bPricelist]        = useState(null);

  // ── UI ─────────────────────────────────────────────────────────────────────
  const [saving,           setSaving]           = useState(false);
  const [showCustomerModal, setShowCustomerModal] = useState(true);
  const [ldgrName,         setLdgrName]          = useState(""); // display value for customer combobox

  // ── Refs ───────────────────────────────────────────────────────────────────
  const barcodeFetchingRef = useRef(false);
  const itemsTableRef      = useRef(null);

  // ── Derived bill figures ───────────────────────────────────────────────────
  const mrp          = barcodeItems.reduce((s, i) => s + parseFloat(i.amount || 0), 0);
  const discount     = parseFloat(form.discount) || 0;
  const taxableValue = Math.max(0, mrp - discount);
  const cgst_amt     = (taxableValue * (parseFloat(form.cgst_per) || 0)) / 100;
  const sgst_amt     = (taxableValue * (parseFloat(form.sgst_per) || 0)) / 100;
  const igst_amt     = (taxableValue * (parseFloat(form.igst_per) || 0)) / 100;
  const roundOff     = parseFloat(form.round_off) || 0;
  const billTotal    = taxableValue + cgst_amt + sgst_amt + igst_amt + roundOff;
  const oldGoldAdj   = parseFloat(form.old_gold_adjusted) || 0;
  const bankPaid     = bankDetails.reduce((s, b) => s + parseFloat(b.amount || 0), 0);
  const collected    = parseFloat(cash) + bankPaid + oldGoldAdj + advanceDeducted;
  const dueAmt       = Math.max(0, billTotal - collected);

  // ── HSN → GST rates ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!form.hsn || !hsns.length) return;
    const hsn_ = hsns.find(h => String(h.id) === String(form.hsn) || h.hsn_no === form.hsn);
    if (!hsn_) return;
    const isIntra = form.place_of_supply === retailStateCode;
    setForm(prev => ({
      ...prev,
      sgst_per: isIntra ? parseFloat(hsn_.sgst) : 0,
      cgst_per: isIntra ? parseFloat(hsn_.cgst) : 0,
      igst_per: isIntra ? 0 : parseFloat(hsn_.igst),
    }));
  }, [form.hsn, form.place_of_supply, hsns, retailStateCode]);

  // ── Initial data load ──────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [initRes, exhRes, bankRes, offerRes, goldRes] = await Promise.all([
          fetchSaleVoucherInitialData(),
          fetchExhibitions(),
          getLedgers({ type: "BA", page: 1 }),
          fetchActiveOffer(),
          getGoldRate(TODAY),
        ]);

        if (cancelled) return;

        if (initRes.success) {
          const d = initRes.data;
          setStatesData(d.states || []);
          setCustomers(d.ledgers || []);
          setHsns(d.hsns || []);
          setForm(prev => ({
            ...prev,
            billno: d.billno || "",
            place_of_supply: d.retail_state_code || prev.place_of_supply,
          }));
          if (d.retail_state_code) setRetailStateCode(d.retail_state_code);
          // default HSN to first entry
          if (d.hsns?.length) {
            const defaultHsn = d.hsns.find(h => h.hsn_no === "711319") || d.hsns[0];
            setForm(prev => ({ ...prev, hsn: defaultHsn.hsn_no }));
          }
        } else {
          toast({
            title: "Error loading form data",
            description: initRes.error?.error || "Please ensure you are logged in and have selected a retail location.",
            variant: "destructive",
          });
        }

        if (exhRes.success) {
          const list = Array.isArray(exhRes.data) ? exhRes.data : (exhRes.data?.results ?? []);
          const defaultExh = list.find(e => e.is_active);
          if (defaultExh) setForm(prev => ({ ...prev, exhibition_profile: String(defaultExh.id) }));
        }

        if (bankRes.success) {
          const list = Array.isArray(bankRes.data) ? bankRes.data : (bankRes.data?.results ?? []);
          setBankLedgers(list);
        }

        if (goldRes.success && Array.isArray(goldRes.data)) {
          const rateMap = {};
          goldRes.data.forEach(r => { if (r.purity_name) rateMap[r.purity_name] = r.selling_rate || r.rate; });
          setGoldRates(rateMap);
        }
      } catch (err) {
        console.error("POS initial load error:", err);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // ── Customer selection ─────────────────────────────────────────────────────
  const handleCustomerChange = useCallback(async (ldgrId, { fromModal = false } = {}) => {
    setForm(prev => ({ ...prev, ldgr: ldgrId, old_gold_purchase: null, old_gold_adjusted: 0 }));
    setSelectedPurchase(null);
    setCustomerPurchases([]);
    setAdvanceDeducted(0);
    if (!ldgrId) { setCustomerCashInfo(null); setB2bPricelist(null); setLdgrName(""); return; }
    if (fromModal) {
      setShowCustomerModal(false);
      setTimeout(() => itemsTableRef.current?.focusBarcode(), 80);
    }

    const [cashRes, purchasesRes, b2bRes] = await Promise.all([
      fetchCustomerCashReceived(ldgrId),
      fetchCustomerPurchasesByLedger(ldgrId),
      fetchB2BPricelistForLedger(ldgrId),
    ]);
    if (cashRes.success) setCustomerCashInfo(cashRes.data);
    if (purchasesRes.success) setCustomerPurchases(purchasesRes.data || []);
    if (b2bRes.success && b2bRes.data?.id) setB2bPricelist(b2bRes.data);
    else setB2bPricelist(null);
  }, []);

  // ── Barcode scan ───────────────────────────────────────────────────────────
  const handleBarcodeSubmit = useCallback(async (barcode) => {
    if (!barcode?.trim()) return;
    if (barcodeFetchingRef.current) return;

    if (barcodeItems.some(r => r.barcode === barcode.trim())) {
      toast({ title: "Duplicate barcode", description: `${barcode.trim()} is already in this bill.`, variant: "destructive" });
      return;
    }

    barcodeFetchingRef.current = true;
    try {
      const data = await fetchBarcodeDetail(barcode, form.hsn, form.ldgr);
      if (data.success) {
        setBarcodeItems(prev => [...prev, data.data]);
      } else {
        const detail = data.error?.detail || (typeof data.error === "string" ? data.error : null);
        toast({ title: detail ? "Barcode reserved" : "Barcode not found", description: detail || JSON.stringify(data.error), variant: "destructive" });
      }
    } catch (err) {
      console.error("Barcode fetch error:", err);
    } finally {
      barcodeFetchingRef.current = false;
    }
  }, [barcodeItems, form.hsn, form.ldgr, toast]);

  const handleDeleteBarcodeItem = useCallback((index) => {
    setBarcodeItems(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ── Bank detail handlers ───────────────────────────────────────────────────
  const handleAddBank = useCallback((row) => {
    if (!row.amount || Number(row.amount) <= 0) return;
    setBankDetails(prev => [...prev, row]);
  }, []);

  const handleDeleteBank = useCallback((index) => {
    setBankDetails(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleEditBank = useCallback((index) => {
    setBankDetails(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ── Old gold link ──────────────────────────────────────────────────────────
  const handleSelectPurchase = useCallback((purchase) => {
    setSelectedPurchase(purchase);
    setForm(prev => ({
      ...prev,
      old_gold_purchase: purchase?.id ?? null,
      old_gold_adjusted: 0,
    }));
  }, []);

  // ── Clear form ─────────────────────────────────────────────────────────────
  const handleClear = () => {
    setForm(emptyForm());
    setBarcodeItems([]);
    setManualItems([]);
    setCash(0);
    setBankDetails([]);
    setAdvanceDeducted(0);
    setSelectedPurchase(null);
    setCustomerCashInfo(null);
    setLdgrName("");
    setShowCustomerModal(true);
    // Re-fetch bill number
    fetchSaleVoucherInitialData().then(res => {
      if (res.success) setForm(prev => ({ ...prev, billno: res.data.billno || "" }));
    });
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (opts = {}) => {
    if (!form.ldgr) { toast({ title: "Please select a customer", variant: "destructive" }); return; }
    if (!barcodeItems.length && !manualItems.length) { toast({ title: "No items added to this bill", variant: "destructive" }); return; }

    // 269ST cash limit check
    const cashAmt = parseFloat(cash) || 0;
    if (cashAmt > 200000) {
      toast({
        title: "⚠️ Cash Limit Exceeded — Section 269ST",
        description: `Cash of ₹${cashAmt.toLocaleString("en-IN")} exceeds the ₹2,00,000 limit under Section 269ST.`,
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...form,
        mrp,
        salesvouitem_set: barcodeItems,
        salesvoumanualitems_set: manualItems,
        salesvouitemdetails_set: manualItems.flatMap(m => m.details_set || []),
        bank_details: bankDetails,
        cash: cashAmt,
        due_amt: parseFloat(dueAmt.toFixed(2)),
        old_gold_purchase:  form.old_gold_purchase  || null,
        customer_order:     form.customer_order     || null,
        exhibition_profile: form.exhibition_profile || null,
        advance_deducted:   advanceDeducted,
      };

      const res = await createSalesVoucher(payload);
      if (res.success) {
        toast({ title: "Bill saved successfully!" });
        if (opts.print) {
          // open print in new tab then go to list
          window.open(`/sales/${res.data.id}/print/`, "_blank");
        }
        setTimeout(() => navigate("/sales/list/"), 500);
      } else {
        toast({ title: "Save failed", description: renderErrorTree(res.error), variant: "destructive" });
      }
    } catch (err) {
      console.error("POS submit error:", err);
      toast({ title: "An error occurred. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  // ── Customer display name ──────────────────────────────────────────────────
  const customerObj = customers.find(c => String(c.id) === String(form.ldgr));

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-muted/40 font-[Assistant]">

      {/* ── Customer select modal ── */}
      {showCustomerModal && customers.length > 0 && (
        <CustomerSelectModal
          customers={customers}
          onSelect={opt => {
            setLdgrName(opt.ac_name || "");
            handleCustomerChange(opt.id, { fromModal: true });
          }}
          onSkip={() => {
            setShowCustomerModal(false);
            setTimeout(() => itemsTableRef.current?.focusBarcode(), 80);
          }}
        />
      )}

      {/* Top bar */}
      <div className="h-12 bg-background border-b border-border flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="size-6 rounded bg-primary flex items-center justify-center">
            <ShoppingCart className="size-3.5 text-white" />
          </div>
          <span className="font-bold text-sm text-foreground">POS Counter</span>
          <span className="text-muted-foreground text-xs">·</span>
          <span className="text-xs text-muted-foreground">
            Bill <strong className="text-foreground">{form.billno || "—"}</strong>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/sales/list/")}
            className="text-xs text-muted-foreground border border-border px-3 py-1.5 rounded-md hover:bg-muted transition-colors"
          >
            Sales List
          </button>
          <button
            onClick={handleClear}
            className="text-xs text-destructive border border-transparent px-3 py-1.5 rounded-md hover:bg-red-50 hover:border-red-200 transition-colors"
          >
            Discard
          </button>
        </div>
      </div>

      {/* Two-panel body */}
      <div className="flex flex-1 overflow-hidden gap-px bg-border">

        {/* ── LEFT PANEL ── */}
        <div className="flex flex-col bg-background overflow-hidden" style={{ flex: "0 0 61%" }}>
          <POSBillHeader
            form={form}
            setForm={setForm}
            statesData={statesData}
            customers={customers}
            hsns={hsns}
            customerCashInfo={customerCashInfo}
            b2bPricelist={b2bPricelist}
            customerPurchases={customerPurchases}
            selectedPurchase={selectedPurchase}
            onCustomerChange={handleCustomerChange}
            onSelectPurchase={handleSelectPurchase}
            ldgrName={ldgrName}
            setLdgrName={setLdgrName}
          />
          <POSItemsTable
            ref={itemsTableRef}
            barcodeItems={barcodeItems}
            onBarcodeSubmit={handleBarcodeSubmit}
            onDeleteBarcodeItem={handleDeleteBarcodeItem}
          />
        </div>

        {/* ── RIGHT PANEL ── */}
        <div className="flex flex-col bg-background overflow-hidden" style={{ flex: "0 0 39%" }}>
          <POSPaymentPanel
            customerObj={customerObj}
            form={form}
            setForm={setForm}
            mrp={mrp}
            discount={discount}
            taxableValue={taxableValue}
            cgst_amt={cgst_amt}
            sgst_amt={sgst_amt}
            igst_amt={igst_amt}
            billTotal={billTotal}
            oldGoldAdj={oldGoldAdj}
            advanceDeducted={advanceDeducted}
            cash={cash}
            setCash={setCash}
            bankDetails={bankDetails}
            bankLedgers={bankLedgers}
            collected={collected}
            dueAmt={dueAmt}
            customerCashInfo={customerCashInfo}
            selectedPurchase={selectedPurchase}
            saving={saving}
            onAddBank={handleAddBank}
            onDeleteBank={handleDeleteBank}
            onEditBank={handleEditBank}
            onClear={handleClear}
            onSave={() => handleSubmit()}
            onSaveAndPrint={() => handleSubmit({ print: true })}
          />
        </div>

      </div>
    </div>
  );
}

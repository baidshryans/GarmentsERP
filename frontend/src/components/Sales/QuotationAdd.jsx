import React, { useRef, useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Printer, Plus, Trash2, Search, Save, ScanBarcode } from "lucide-react";
import {
  fetchBarcodeDetailOnly,
  fetchQuotationInitialData,
  createQuotation,
  updateQuotation,
  fetchQuotationById,
  getGoldRate,
  fetchB2BPricelistForLedger,
} from "@/services/apiService";
import { openAndPrint } from "@/services/print/utils";
import QuotationPrint from "./QuotationPrint";

const fmt = (v, d = 3) => {
  const n = parseFloat(v);
  return isNaN(n) ? "0" : n.toFixed(d);
};
const fmtI = (v) => {
  const n = parseInt(v);
  return isNaN(n) ? 0 : n;
};
const today = () => new Date().toISOString().split("T")[0];
const addDays = (dateStr, days) => {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
};

// Derive gold rate per gram for a purity string like "22" from the 3 rates
const goldRateForPurity = (purity, r18, r22, r24, r14) => {
  const p = parseInt(purity);
  if (p === 24 || p === 995) return r24;
  if (p === 22 || p === 916) return r22;
  if (p === 18 || p === 750) return r18;
  if (p === 14 || p === 585) return r14;
  // Fallback: interpolate based on 24K
  if (r24 && p) return Math.round((r24 * p) / 24);
  return 0;
};

// Compute fine weight from B2B tunch pricelist entry.
// Returns { fine_wt, gold_amount } when tunch applies, null otherwise.
// Same formula as sale voucher: fine_wt = nw * (gw_per + tunch_markup) / 100
//                               gold_amount = fine_wt * rate_24kt
const computeB2BFineWt = (pricelist, purities, purityVal, nw, rate24kt) => {
  const entries = pricelist?.tunch_entries || [];
  if (!entries.length) return null;
  const match = entries.find((e) => String(e.purity) === String(purityVal));
  if (!match) return null;
  const purityObj = purities.find((p) => String(p.purity) === String(purityVal));
  const gwPer = parseFloat(purityObj?.gw_per || 0);
  const tunchMarkup = parseFloat(match.tunch_percent) || 0;
  const fullTunch = gwPer + tunchMarkup;
  const fineWt = (parseFloat(nw) * fullTunch) / 100;
  const goldAmount = fineWt * parseFloat(rate24kt || 0);
  return { fine_wt: fineWt, gold_amount: Math.round(goldAmount) };
};

// Compute making charge from B2B pricelist for a scanned item
const computeB2BMaking = (pricelist, nw, purityVal, goldAmount) => {
  const entries = pricelist?.making_entries || [];
  if (!entries.length) return null;
  let best = null;
  let bestScore = -1;
  for (const e of entries) {
    const matchPurity = e.purity ? String(e.purity) === String(purityVal) : true;
    if (!matchPurity) continue;
    const score = e.purity ? 1 : 0;
    if (score > bestScore) { best = e; bestScore = score; }
  }
  if (!best) return null;
  const val = parseFloat(best.making_value) || 0;
  if (best.making_type === "val") return val;
  if (best.making_type === "per_nw") return (goldAmount * val) / 100;
  return null;
};

// Compute stone amount for a detail entry using B2B pricelist overrides
const computeB2BStoneAmount = (pricelist, packetName, wt) => {
  const overrides = pricelist?.stone_overrides || [];
  const wholesale = pricelist?.wholesale_packet_rates || {};
  const override = overrides.find((o) => o.packet === packetName);
  const rate = override ? override.rate : (wholesale[packetName] ?? null);
  if (rate === null) return null;
  return parseFloat(rate) * parseFloat(wt);
};

export default function QuotationAdd() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const inputRef = useRef(null);

  // ── Header state ────────────────────────────────────────────────────────
  const [date1, setDate1] = useState(today());
  const [quotationNo, setQuotationNo] = useState("");
  const [partyType, setPartyType] = useState("ledger"); // "ledger" or "walkin"
  const [ldgr, setLdgr] = useState("");
  const [partyName, setPartyName] = useState("");
  const [salesPerson, setSalesPerson] = useState("");
  const [sellerInfo, setSellerInfo] = useState("");
  const [validUntil, setValidUntil] = useState(addDays(today(), 7));
  const [remarks, setRemarks] = useState("");
  const [taxPercent, setTaxPercent] = useState(3);

  // Gold rates
  const [goldRateDate, setGoldRateDate] = useState(today());
  const [rate14kt, setRate14kt] = useState(0);
  const [rate18kt, setRate18kt] = useState(0);
  const [rate22kt, setRate22kt] = useState(0);
  const [rate24kt, setRate24kt] = useState(0);

  // Initial data
  const [ledgers, setLedgers] = useState([]);
  const [salespersons, setSalespersons] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [partySearch, setPartySearch] = useState("");

  // B2B pricelist (set when a B2B ledger is selected)
  const [b2bPricelist, setB2bPricelist] = useState(null);
  const [purities, setPurities] = useState([]);

  // Scanner
  const [barcodeInput, setBarcodeInput] = useState("");
  const [scanning, setScanning] = useState(false);

  // Items
  const [items, setItems] = useState([]);
  const [saving, setSaving] = useState(false);

  // ── Load initial data ──────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      const res = await fetchQuotationInitialData();
      if (res.success) {
        setLedgers(res.data.ledgers || []);
        setSalespersons(res.data.salespersons || []);
        setPurities(res.data.purities || []);
        if (!id) setQuotationNo(res.data.billno || "");
      }
      setInitialLoading(false);
    })();
  }, []);

  // Load existing quotation for edit
  useEffect(() => {
    if (!id) return;
    (async () => {
      const res = await fetchQuotationById(id);
      if (res.success) {
        const q = res.data;
        setDate1(q.date1);
        setQuotationNo(q.quotation_no);
        setLdgr(q.ldgr ? String(q.ldgr) : "");
        setPartyName(q.party_name || "");
        setPartyType(q.ldgr ? "ledger" : "walkin");
        setSalesPerson(q.sales_person ? String(q.sales_person) : "");
        setSellerInfo(q.seller_info || "");
        setValidUntil(q.valid_until || "");
        setRemarks(q.remarks || "");
        setTaxPercent(parseFloat(q.tax_percent) || 3);
        setGoldRateDate(q.gold_rate_date || today());
        setRate18kt(q.rate_18kt || 0);
        setRate22kt(q.rate_22kt || 0);
        setRate24kt(q.rate_24kt || 0);
        setItems(
          (q.items || []).map((item, idx) => ({
            ...item,
            _key: Date.now() + idx,
          }))
        );
        // Restore B2B pricelist so any newly scanned items are priced correctly
        if (q.ldgr) {
          const plRes = await fetchB2BPricelistForLedger(q.ldgr);
          if (plRes.success && plRes.data) setB2bPricelist(plRes.data);
        }
      }
    })();
  }, [id]);

  // ── Gold rates ─────────────────────────────────────────────────────────
  const fetchRates = useCallback(async (dateVal) => {
    const res = await getGoldRate(dateVal);
    if (!res.success || !res.data) return;
    const rates = Array.isArray(res.data) ? res.data : res.data.results || [];
    for (const r of rates) {
      const p = String(r.purity_name || "");
      const val = Number(r.selling_rate ?? r.rate) || 0;
      if (p.includes("14")) setRate14kt(val);
      else if (p.includes("18")) setRate18kt(val);
      else if (p.includes("22")) setRate22kt(val);
      else if (p.includes("24")) setRate24kt(val);
    }
  }, []);

  useEffect(() => {
    if (!id) fetchRates(goldRateDate);
  }, [goldRateDate, fetchRates, id]);

  // ── Barcode scan ───────────────────────────────────────────────────────
  const handleScan = async (e) => {
    e?.preventDefault();
    const code = barcodeInput.trim();
    if (!code) return;

    if (items.some((i) => i.barcode_text === code)) {
      toast({ title: "Already added", description: `"${code}" is already in the list.` });
      setBarcodeInput("");
      return;
    }

    setScanning(true);
    try {
      const res = await fetchBarcodeDetailOnly(code);
      if (!res.success || !res.data) {
        toast({ title: "Barcode not found", description: `No active stock for "${code}"`, variant: "destructive" });
        setScanning(false);
        return;
      }

      const d = res.data;
      const stoneItems = (d.main_item_set || []).filter((i) => i.item !== "GOLD");
      const metalItem = (d.main_item_set || []).find((i) => i.item === "GOLD");

      const purityVal = d.purity ? String(d.purity).replace("K", "") : "";
      const gRate = goldRateForPurity(purityVal, rate18kt, rate22kt, rate24kt, rate14kt);

      // B2B tunch: compute fine weight; gold_amount derives from fine_wt � 24K rate
      const tunchResult = b2bPricelist
        ? computeB2BFineWt(b2bPricelist, purities, purityVal, parseFloat(d.nw) || 0, rate24kt)
        : null;

      const goldAmount = tunchResult
        ? tunchResult.gold_amount
        : (metalItem ? parseFloat(metalItem.amt) || (parseFloat(d.nw) * gRate) : 0);
      const fineWt = tunchResult ? tunchResult.fine_wt : 0;

      const makingAmt = parseFloat(d.making) || 0;

      // Separate diamonds from other stones (diamonds are items whose short_code suggests diamond)
      const details = stoneItems.map((si) => {
        const isDiamond = (si.item || "").toUpperCase().includes("DIA") ||
                          (si.item || "").toUpperCase().includes("DMND") ||
                          (si.item || "").toUpperCase() === "DIAMOND";
        return {
          packet: si.packet_id || null,
          packet_name: si.packet || "",
          item_name: si.item || "",
          is_diamond: isDiamond,
          pcs: fmtI(si.pcs),
          wt: parseFloat(si.ct || si.gw || 0),
          rate: fmtI(si.rate),
          amount: parseFloat(si.amt) || 0,
        };
      });

      const diamondDetails = details.filter((d) => d.is_diamond);
      const stoneDetails = details.filter((d) => !d.is_diamond);

      const totalDiamondPcs = diamondDetails.reduce((s, d) => s + d.pcs, 0);
      const totalDiamondWt = diamondDetails.reduce((s, d) => s + d.wt, 0);
      const totalDiamondAmt = diamondDetails.reduce((s, d) => s + d.amount, 0);

      // Apply B2B stone overrides if pricelist is set
      const finalStoneDetails = b2bPricelist
        ? stoneDetails.map((sd) => {
            const b2bAmt = computeB2BStoneAmount(b2bPricelist, sd.packet_name, sd.wt);
            if (b2bAmt !== null) {
              const b2bRate = sd.wt > 0 ? Math.round(b2bAmt / sd.wt) : sd.rate;
              return { ...sd, rate: b2bRate, amount: Math.round(b2bAmt) };
            }
            return sd;
          })
        : stoneDetails;

      const totalStonePcs = finalStoneDetails.reduce((s, d) => s + d.pcs, 0);
      const totalStoneWt = finalStoneDetails.reduce((s, d) => s + d.wt, 0);
      const totalStoneAmt = finalStoneDetails.reduce((s, d) => s + d.amount, 0);

      // Apply B2B making override if pricelist is set
      const finalMakingAmt = b2bPricelist
        ? (computeB2BMaking(b2bPricelist, parseFloat(d.nw) || 0, purityVal, goldAmount) ?? makingAmt)
        : makingAmt;

      const totalAmount = goldAmount + totalDiamondAmt + totalStoneAmt + finalMakingAmt;

      // Try to get image URL
      let imageUrl = "";
      if (d.id) {
        try {
          const imgRes = await fetch(`/inventory/api/barcode-images/${d.id}/`, {
            headers: { "Authorization": `Token ${sessionStorage.getItem("token")}` },
          });
          if (imgRes.ok) {
            const imgData = await imgRes.json();
            const imgs = Array.isArray(imgData) ? imgData : imgData.results || [];
            if (imgs.length > 0) imageUrl = imgs[0].image || "";
          }
        } catch { /* ignore */ }
      }

      const newItem = {
        _key: Date.now(),
        sl_no: items.length + 1,
        barcode: d.id || null,
        barcode_text: d.barcode || code,
        item: null,
        item_name: `${d.item_desc || d.item || ""}`,
        design_code: d.design_code || "",
        purity_text: d.purity ? `${d.purity} K` : "",
        pcs: fmtI(d.pcs) || 1,
        gw: parseFloat(d.gw) || 0,
        nw: parseFloat(d.nw) || 0,
        gold_rate: tunchResult ? 0 : gRate,
        gold_amount: Math.round(goldAmount),
        fine_wt: tunchResult ? parseFloat(fineWt.toFixed(3)) : 0,
        making_rate: finalMakingAmt > 0 && parseFloat(d.nw) > 0 ? Math.round(finalMakingAmt / parseFloat(d.nw)) : 0,
        making_amount: Math.round(finalMakingAmt),
        total_diamond_pcs: totalDiamondPcs,
        total_diamond_wt: totalDiamondWt,
        total_diamond_amt: Math.round(totalDiamondAmt),
        total_stone_pcs: totalStonePcs,
        total_stone_wt: totalStoneWt,
        total_stone_amt: Math.round(totalStoneAmt),
        total_amount: Math.round(totalAmount),
        image_url: imageUrl,
        details: [...diamondDetails, ...finalStoneDetails],
      };

      setItems((prev) => [...prev, newItem]);
      setBarcodeInput("");
      setTimeout(() => inputRef.current?.focus(), 50);
    } catch {
      toast({ title: "Error scanning barcode", variant: "destructive" });
    }
    setScanning(false);
  };

  const handleRemove = (key) => {
    setItems((prev) => {
      const filtered = prev.filter((i) => i._key !== key);
      return filtered.map((item, idx) => ({ ...item, sl_no: idx + 1 }));
    });
  };

  // ── Grand totals ───────────────────────────────────────────────────────
  const grand = items.reduce(
    (acc, item) => ({
      pcs: acc.pcs + fmtI(item.pcs),
      gw: acc.gw + parseFloat(item.gw || 0),
      nw: acc.nw + parseFloat(item.nw || 0),
      goldAmt: acc.goldAmt + parseFloat(item.gold_amount || 0),
      diamondPcs: acc.diamondPcs + fmtI(item.total_diamond_pcs),
      diamondWt: acc.diamondWt + parseFloat(item.total_diamond_wt || 0),
      diamondAmt: acc.diamondAmt + parseFloat(item.total_diamond_amt || 0),
      stonePcs: acc.stonePcs + fmtI(item.total_stone_pcs),
      stoneWt: acc.stoneWt + parseFloat(item.total_stone_wt || 0),
      stoneAmt: acc.stoneAmt + parseFloat(item.total_stone_amt || 0),
      makingAmt: acc.makingAmt + parseFloat(item.making_amount || 0),
      totalAmt: acc.totalAmt + parseFloat(item.total_amount || 0),
    }),
    { pcs: 0, gw: 0, nw: 0, goldAmt: 0, diamondPcs: 0, diamondWt: 0, diamondAmt: 0, stonePcs: 0, stoneWt: 0, stoneAmt: 0, makingAmt: 0, totalAmt: 0 }
  );

  const taxAmount = Math.round(grand.totalAmt * (taxPercent / 100));
  const netTotal = grand.totalAmt + taxAmount;

  // ── Save ────────────────────────────────────────────────────────────────
  const handleSave = async (andPrint = false) => {
    if (items.length === 0) {
      toast({ title: "No items", description: "Scan at least one barcode.", variant: "destructive" });
      return;
    }

    setSaving(true);
    const payload = {
      date1,
      ldgr: partyType === "ledger" && ldgr ? parseInt(ldgr) : null,
      party_name: partyType === "walkin" ? partyName : "",
      gold_rate_date: goldRateDate,
      rate_18kt: rate18kt,
      rate_22kt: rate22kt,
      rate_24kt: rate24kt,
      total_items: items.length,
      grand_total: grand.totalAmt,
      tax_percent: taxPercent,
      tax_amount: taxAmount,
      net_total: netTotal,
      valid_until: validUntil || null,
      remarks,
      seller_info: sellerInfo,
      sales_person: salesPerson ? parseInt(salesPerson) : null,
      items: items.map((item) => ({
        sl_no: item.sl_no,
        barcode: item.barcode || null,
        barcode_text: item.barcode_text,
        item: item.item || null,
        item_name: item.item_name,
        design_code: item.design_code,
        purity_text: item.purity_text,
        pcs: item.pcs,
        gw: item.gw,
        nw: item.nw,
        gold_rate: item.gold_rate,
        gold_amount: item.gold_amount,
        fine_wt: item.fine_wt || 0,
        making_rate: item.making_rate,
        making_amount: item.making_amount,
        total_diamond_pcs: item.total_diamond_pcs,
        total_diamond_wt: item.total_diamond_wt,
        total_diamond_amt: item.total_diamond_amt,
        total_stone_pcs: item.total_stone_pcs,
        total_stone_wt: item.total_stone_wt,
        total_stone_amt: item.total_stone_amt,
        total_amount: item.total_amount,
        image_url: item.image_url,
        details: (item.details || []).map((d) => ({
          packet: d.packet || null,
          packet_name: d.packet_name,
          item_name: d.item_name,
          is_diamond: d.is_diamond,
          pcs: d.pcs,
          wt: d.wt,
          rate: d.rate,
          amount: d.amount,
        })),
      })),
    };

    const res = id ? await updateQuotation(id, payload) : await createQuotation(payload);
    if (res.success) {
      toast({ title: "Quotation saved" });
      if (andPrint) {
        openAndPrint(
          <QuotationPrint
            data={{
              ...payload,
              quotation_no: res.data?.quotation_no || quotationNo,
              ldgr_name: partyType === "ledger" ? ledgers.find((l) => String(l.id) === ldgr)?.ac_name || "" : partyName,
            }}
          />
        );
      }
      setTimeout(() => navigate("/sales/quotation/list/"), 800);
    } else {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setSaving(false);
  };

  // F4 keyboard shortcut
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "F4") { e.preventDefault(); handleSave(false); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [items, date1, ldgr, partyName]);

  // ── Filtered ledgers ───────────────────────────────────────────────────
  const filteredLedgers = partySearch
    ? ledgers.filter((l) => l.ac_name?.toLowerCase().includes(partySearch.toLowerCase())).slice(0, 50)
    : ledgers.slice(0, 50);

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 max-w-[1400px] mx-auto">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{id ? "Edit" : "New"} Quotation</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {quotationNo && <span className="font-mono bg-muted px-1.5 py-0.5 rounded mr-2">{quotationNo}</span>}
            Scan barcodes / RFIDs to build the quotation
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/sales/quotation/list/")} className="h-9">
            Cancel
          </Button>
          <Button onClick={() => handleSave(false)} disabled={saving} className="h-9 gap-1.5">
            <Save className="size-4" /> {saving ? (id ? "Updating�" : "Saving�") : (id ? "Update Draft" : "Save Draft")}
          </Button>
          <Button onClick={() => handleSave(true)} disabled={saving} className="h-9 gap-1.5 bg-primary">
            <Printer className="size-4" /> {id ? "Update & Print" : "Save & Print"}
          </Button>
        </div>
      </div>

      {/* ── Form header ────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-card shadow-sm p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Date</Label>
            <Input type="date" value={date1} onChange={(e) => setDate1(e.target.value)} className="h-9" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Gold Rate Date</Label>
            <Input type="date" value={goldRateDate} onChange={(e) => { setGoldRateDate(e.target.value); fetchRates(e.target.value); }} className="h-9" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Valid Until</Label>
            <Input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className="h-9" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Tax %</Label>
            <Input type="number" value={taxPercent} onChange={(e) => setTaxPercent(parseFloat(e.target.value) || 0)} className="h-9" step="0.5" />
          </div>
          <div className="flex flex-col gap-1 col-span-2">
            <Label className="text-xs">Salesperson</Label>
            <Select value={salesPerson} onValueChange={setSalesPerson}>
              <SelectTrigger className="h-9"><SelectValue placeholder="Select�" /></SelectTrigger>
              <SelectContent>
                {salespersons.map((sp) => (
                  <SelectItem key={sp.id} value={String(sp.id)}>{sp.salesperson_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Gold rates display */}
        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
          <span>Gold Rates:</span>
          <span className="font-mono bg-muted px-1.5 py-0.5 rounded">14K: {rate14kt || "�"}</span>
          <span className="font-mono bg-muted px-1.5 py-0.5 rounded">18K: {rate18kt || "�"}</span>
          <span className="font-mono bg-muted px-1.5 py-0.5 rounded">22K: {rate22kt || "�"}</span>
          {b2bPricelist && (
            <span className="font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
              B2B Pricelist: {b2bPricelist.name}
            </span>
          )}
        </div>

        {/* Party row */}
        <div className="flex items-end gap-3 mt-4">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Party Type</Label>
            <Select value={partyType} onValueChange={(v) => { setPartyType(v); setLdgr(""); setPartyName(""); setB2bPricelist(null); }}>
              <SelectTrigger className="h-9 w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ledger">Customer</SelectItem>
                <SelectItem value="walkin">Walk-in</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {partyType === "ledger" ? (
            <div className="flex flex-col gap-1 flex-1 max-w-md">
              <Label className="text-xs">Customer</Label>
              <Select value={ldgr} onValueChange={async (v) => {
                setLdgr(v);
                setB2bPricelist(null);
                if (v) {
                  const res = await fetchB2BPricelistForLedger(v);
                  if (res.success && res.data) setB2bPricelist(res.data);
                }
              }}>
                <SelectTrigger className="h-9"><SelectValue placeholder="Select customer�" /></SelectTrigger>
                <SelectContent>
                  <div className="px-2 pb-2">
                    <Input
                      placeholder="Search�"
                      value={partySearch}
                      onChange={(e) => setPartySearch(e.target.value)}
                      className="h-8"
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                  {filteredLedgers.map((l) => (
                    <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="flex flex-col gap-1 flex-1 max-w-md">
              <Label className="text-xs">Party Name</Label>
              <Input value={partyName} onChange={(e) => setPartyName(e.target.value)} placeholder="Walk-in party name�" className="h-9" />
            </div>
          )}

          <div className="flex flex-col gap-1 flex-1 max-w-sm">
            <Label className="text-xs">Seller Info / Tag</Label>
            <Input value={sellerInfo} onChange={(e) => setSellerInfo(e.target.value)} placeholder="e.g. Rishiji baid kolkata #IIJS" className="h-9" />
          </div>
        </div>
      </div>

      {/* ── Barcode Scanner ────────────────────────────────────────────── */}
      <div className="rounded-xl border-2 border-dashed border-primary/30 bg-primary/5 p-4">
        <form onSubmit={handleScan} className="flex items-end gap-3">
          <div className="flex flex-col gap-1 flex-1 max-w-sm">
            <Label className="text-xs font-medium flex items-center gap-1.5">
              <ScanBarcode className="size-3.5" /> Scan Barcode / RFID
            </Label>
            <Input
              ref={inputRef}
              value={barcodeInput}
              onChange={(e) => setBarcodeInput(e.target.value)}
              placeholder="Scan or type barcode�"
              autoFocus
              className="h-10 text-base font-mono"
              disabled={scanning}
            />
          </div>
          <Button type="submit" disabled={scanning || !barcodeInput.trim()} className="h-10 gap-1.5">
            {scanning ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {scanning ? "Loading�" : "Add"}
          </Button>
          <span className="text-xs text-muted-foreground pb-2">Press Enter after each scan</span>
        </form>
      </div>

      {/* ── Items Table ────────────────────────────────────────────────── */}
      {items.length > 0 && (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
            <span className="text-sm font-semibold">{items.length} Item{items.length !== 1 ? "s" : ""}</span>
            <Button variant="ghost" size="sm" className="text-xs text-muted-foreground hover:text-destructive" onClick={() => setItems([])}>
              Clear all
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/50 border-b border-border">
                <tr>
                  <th className="px-2 py-2 text-center font-semibold text-muted-foreground w-8">Sr</th>
                  <th className="px-2 py-2 text-center font-semibold text-muted-foreground w-16">Image</th>
                  <th className="px-2 py-2 text-left font-semibold text-muted-foreground">Design / Barcode</th>
                  <th className="px-2 py-2 text-left font-semibold text-muted-foreground">Product</th>
                  <th className="px-2 py-2 text-center font-semibold text-muted-foreground" colSpan={5}>
                    <span className="text-primary">Gold</span>
                  </th>
                  <th className="px-2 py-2 text-center font-semibold text-muted-foreground" colSpan={4}>
                    <span className="text-blue-600">Diamond</span>
                  </th>
                  <th className="px-2 py-2 text-center font-semibold text-muted-foreground" colSpan={4}>
                    <span className="text-emerald-600">Stone</span>
                  </th>
                  <th className="px-2 py-2 text-center font-semibold text-muted-foreground" colSpan={2}>Labour</th>
                  <th className="px-2 py-2 text-right font-semibold text-muted-foreground">Total</th>
                  <th className="px-2 py-2 w-8"></th>
                </tr>
                <tr className="text-[10px] text-muted-foreground bg-muted/30 border-b border-border">
                  <th></th><th></th><th></th><th></th>
                  {/* Gold sub-headers */}
                  <th className="px-1 py-1 text-center">Qly</th>
                  <th className="px-1 py-1 text-right">Gwt</th>
                  <th className="px-1 py-1 text-right">Nwt</th>
                  <th className="px-1 py-1 text-right">Rate/FW</th>
                  <th className="px-1 py-1 text-right">Amt</th>
                  {/* Diamond sub-headers */}
                  <th className="px-1 py-1 text-right">Pcs</th>
                  <th className="px-1 py-1 text-right">Wt</th>
                  <th className="px-1 py-1 text-right">Rate</th>
                  <th className="px-1 py-1 text-right">Amt</th>
                  {/* Stone sub-headers */}
                  <th className="px-1 py-1 text-right">Pcs</th>
                  <th className="px-1 py-1 text-right">Wt</th>
                  <th className="px-1 py-1 text-right">Rate</th>
                  <th className="px-1 py-1 text-right">Amt</th>
                  {/* Labour */}
                  <th className="px-1 py-1 text-right">Rate</th>
                  <th className="px-1 py-1 text-right">Amt</th>
                  <th></th><th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const baseUrl = window.location.origin.replace(":5173", ":8000");
                  return (
                    <React.Fragment key={item._key}>
                      {/* Main row */}
                      <tr className="border-b border-border hover:bg-muted/20">
                        <td className="px-2 py-2 text-center text-muted-foreground">{item.sl_no}</td>
                        <td className="px-2 py-2 text-center">
                          {item.image_url ? (
                            <img
                              src={item.image_url.startsWith("http") ? item.image_url : `${baseUrl}${item.image_url}`}
                              alt=""
                              className="size-12 object-cover rounded border"
                              onError={(e) => { e.target.style.display = "none"; }}
                            />
                          ) : (
                            <div className="size-12 bg-muted/50 rounded border flex items-center justify-center text-muted-foreground text-[8px]">
                              No img
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-2">
                          <div className="font-semibold">{item.design_code || "�"}</div>
                          <div className="font-mono text-muted-foreground text-[10px]">{item.barcode_text}</div>
                        </td>
                        <td className="px-2 py-2">{item.item_name}</td>
                        {/* Gold */}
                        <td className="px-1 py-2 text-center font-medium">{item.purity_text}</td>
                        <td className="px-1 py-2 text-right tabular-nums">{fmt(item.gw)}</td>
                        <td className="px-1 py-2 text-right tabular-nums">{fmt(item.nw)}</td>
                        <td className="px-1 py-2 text-right tabular-nums">
                          {item.fine_wt > 0
                            ? <span className="text-blue-600">{fmt(item.fine_wt, 3)}<span className="text-[10px] text-muted-foreground ml-0.5">fw</span></span>
                            : fmtI(item.gold_rate)}
                        </td>
                        <td className="px-1 py-2 text-right tabular-nums font-medium">{fmtI(item.gold_amount)}</td>
                        {/* Diamond */}
                        <td className="px-1 py-2 text-right tabular-nums">{item.total_diamond_pcs || ""}</td>
                        <td className="px-1 py-2 text-right tabular-nums">{item.total_diamond_wt ? fmt(item.total_diamond_wt) : ""}</td>
                        <td className="px-1 py-2 text-right tabular-nums"></td>
                        <td className="px-1 py-2 text-right tabular-nums font-medium">{item.total_diamond_amt || ""}</td>
                        {/* Stone */}
                        <td className="px-1 py-2 text-right tabular-nums">{item.total_stone_pcs || ""}</td>
                        <td className="px-1 py-2 text-right tabular-nums">{item.total_stone_wt ? fmt(item.total_stone_wt) : ""}</td>
                        <td className="px-1 py-2 text-right tabular-nums"></td>
                        <td className="px-1 py-2 text-right tabular-nums font-medium">{item.total_stone_amt || ""}</td>
                        {/* Labour */}
                        <td className="px-1 py-2 text-right tabular-nums">{fmtI(item.making_rate) || ""}</td>
                        <td className="px-1 py-2 text-right tabular-nums font-medium">{fmtI(item.making_amount)}</td>
                        {/* Total */}
                        <td className="px-2 py-2 text-right tabular-nums font-bold text-primary">{fmtI(item.total_amount)}</td>
                        <td className="px-2 py-2 text-center">
                          <button onClick={() => handleRemove(item._key)} className="text-muted-foreground hover:text-destructive">
                            <Trash2 className="size-3.5" />
                          </button>
                        </td>
                      </tr>
                      {/* Sub-rows for stone/diamond detail breakdown */}
                      {(item.details || []).map((det, di) => (
                        <tr key={`${item._key}-d${di}`} className="bg-muted/10 text-[10px] text-muted-foreground">
                          <td></td><td></td><td></td><td></td>
                          <td></td><td></td><td></td><td></td><td></td>
                          {det.is_diamond ? (
                            <>
                              <td className="px-1 py-0.5 text-right">{det.pcs}</td>
                              <td className="px-1 py-0.5 text-right">{fmt(det.wt)}</td>
                              <td className="px-1 py-0.5 text-right">{det.rate}</td>
                              <td className="px-1 py-0.5 text-right">{fmtI(det.amount)}</td>
                              <td colSpan={4} className="px-1 py-0.5 text-left italic pl-2">{det.packet_name}</td>
                            </>
                          ) : (
                            <>
                              <td colSpan={4}></td>
                              <td className="px-1 py-0.5 text-right">{det.pcs}</td>
                              <td className="px-1 py-0.5 text-right">{fmt(det.wt)}</td>
                              <td className="px-1 py-0.5 text-right">{det.rate}</td>
                              <td className="px-1 py-0.5 text-right">{fmtI(det.amount)}</td>
                            </>
                          )}
                          <td colSpan={2} className="px-1 py-0.5 text-left italic">
                            {!det.is_diamond && det.packet_name}
                          </td>
                          <td></td>
                        </tr>
                      ))}
                    </React.Fragment>
                  );
                })}
              </tbody>
              {/* Totals footer */}
              <tfoot className="bg-muted/50 border-t-2 border-border font-semibold text-xs">
                <tr>
                  <td colSpan={4} className="px-2 py-2 text-right text-muted-foreground">TOTAL ({items.length} items)</td>
                  <td></td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmt(grand.gw)}</td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmt(grand.nw)}</td>
                  <td></td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmtI(grand.goldAmt)}</td>
                  <td className="px-1 py-2 text-right tabular-nums">{grand.diamondPcs}</td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmt(grand.diamondWt)}</td>
                  <td></td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmtI(grand.diamondAmt)}</td>
                  <td className="px-1 py-2 text-right tabular-nums">{grand.stonePcs}</td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmt(grand.stoneWt)}</td>
                  <td></td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmtI(grand.stoneAmt)}</td>
                  <td></td>
                  <td className="px-1 py-2 text-right tabular-nums">{fmtI(grand.makingAmt)}</td>
                  <td className="px-2 py-2 text-right tabular-nums font-bold">{fmtI(grand.totalAmt)}</td>
                  <td></td>
                </tr>
                <tr>
                  <td colSpan={19} className="px-2 py-2 text-right font-medium">GST {taxPercent}%</td>
                  <td className="px-2 py-2 text-right tabular-nums font-bold">{fmtI(taxAmount)}</td>
                  <td></td>
                </tr>
                <tr className="text-sm">
                  <td colSpan={19} className="px-2 py-2 text-right font-bold">Net Total</td>
                  <td className="px-2 py-2 text-right tabular-nums font-bold text-primary text-sm">
                    ₹ {netTotal.toLocaleString("en-IN")}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Remarks */}
          <div className="px-5 py-3 border-t border-border flex items-center gap-4">
            <Label className="text-xs text-muted-foreground whitespace-nowrap">Remarks</Label>
            <Input value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Any notes�" className="h-8 max-w-md" />
          </div>
        </div>
      )}

      {/* Empty state */}
      {items.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-muted/10 flex flex-col items-center justify-center py-20 text-center gap-3">
          <Search className="size-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No items scanned yet. Use the barcode scanner above.</p>
        </div>
      )}
    </div>
  );
}

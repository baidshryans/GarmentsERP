import React, { useEffect, useState, useRef, useCallback } from "react";
import { formatNumber } from "@/lib/format";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableHeader, TableBody } from "@/components/ui/table";
import {
  fetchMainItem, fetchKarigarIssues, fetchPurity,
  fetchNextBarcode, fetchReceiveItemsForBarcode, createBarcode,
  fetchBarcodeForEdit, fetchPurhcaseItemsForBarcode, updateBarcodeForEdit,
  fetchPackets, uploadBarcodeImages,
} from "@/services/apiService";
import { useLocation, useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { Plus, Trash2, ImageIcon } from "lucide-react";
import { renderErrorTree } from "../../../Utils";
import BarcodeImages from "./BarcodeImages";

// Format a value to exactly 3 decimal places (returns "" for blank/null)
const fmt3 = (v) => {
  const n = parseFloat(v);
  return isNaN(n) ? "" : n.toFixed(3);
};

const BarcodeManagementList = () => {
  const location = useLocation();
  const { id } = useParams();
  const searchParams = new URLSearchParams(location.search);
  const sl_no = searchParams.get("sl_no");
  const rec_slip_no = decodeURIComponent(searchParams.get("rec_sl_no"));
  const bill_no = decodeURIComponent(searchParams.get("bill_no"));

  const { toast } = useToast();
  const navigate = useNavigate();
  const packetInputRef = useRef(null);

  const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {
      form: {
        barcode: "", item: "", purity: "", pcs: "", gw: "", nw: "",
        huid: "", rfid_tag: "", value: "", making_val: "", making_type: "", other_chg: 0,
        design_code: "", kr_code: "", voucher_no: "", size: "", metal_color: "",
        total_amount: 0, order_no: "", add_to_design: false,
        created_date: new Date().toISOString().split("T")[0],
        barcodedetails_set: [],
      },
      // Sub-item entry fields (not submitted — used for inline entry)
      detail: { packet: "", item: "", pcs: "", ct: "", gw: "", rate: "", amt: "" },
    },
  });

  const [mainItemData, setMainItemData] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [packetData, setPacketData] = useState([]);
  // Photos: in edit mode they upload live (id present); in create mode they are
  // staged here and flushed in onSubmit once the new barcode id is known.
  const [photoOpen, setPhotoOpen] = useState(false);
  const [stagedPhotos, setStagedPhotos] = useState([]);
  const [detailItemDisplay, setDetailItemDisplay] = useState("");
  const [detailUom, setDetailUom] = useState("");          // UOM of inline entry item
  const [pvPrefilled, setPvPrefilled] = useState(false);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const pvPurityRef   = useRef(null); // holds purity from PV until purityData is ready
  const pvGoldItemRef = useRef(null); // holds the gold sub-item info captured from PV

  const { fields, append, remove } = useFieldArray({ control, name: "form.barcodedetails_set" });

  const item_name = watch("form.item_name");
  const formGw = watch("form.gw");
  const detailPacket = watch("detail.packet");

  // ── Auto-calculate Net Weight ──────────────────────
  const recalcNetWeight = useCallback(() => {
    const gw = parseFloat(getValues("form.gw")) || 0;
    const details = getValues("form.barcodedetails_set") || [];
    const subGw = details.reduce((sum, d) => sum + (parseFloat(d.gw) || 0), 0);
    setValue("form.nw", fmt3(gw - subGw));
  }, [getValues, setValue]);

  useEffect(() => { recalcNetWeight(); }, [formGw, fields.length]);

  // ── Auto-calculate Value + Total Amount ────────────
  // value = sum(sub-item amounts) + making_val (only when making_type === "val")
  // total_amount = value + other_chg
  const recalcTotal = useCallback(() => {
    const details = getValues("form.barcodedetails_set") || [];
    const subTotal = details.reduce((sum, d) => sum + (parseFloat(d.amt) || 0), 0);
    const making = parseFloat(getValues("form.making_val")) || 0;
    const makingType = getValues("form.making_type") || "";
    const value = subTotal + (makingType === "val" ? making : 0);
    setValue("form.value", value);
    const otherChg = parseFloat(getValues("form.other_chg")) || 0;
    setValue("form.total_amount", Math.round(value + otherChg));
  }, [getValues, setValue]);

  // ── Packet → Item auto-load ────────────────────────
  useEffect(() => {
    if (!detailPacket) {
      setDetailItemDisplay("");
      setDetailUom("");
      setValue("detail.item", "");
      setValue("detail.rate", "");
      return;
    }
    const pkt = packetData.find((p) => p.pckt_no === detailPacket);
    if (pkt) {
      const shortCode =
        (pkt.stone_item_id && typeof pkt.stone_item_id === "object"
          ? pkt.stone_item_id.short_code
          : pkt.stone_item_short_code) || "";
      const itemName =
        (pkt.stone_item_id && typeof pkt.stone_item_id === "object"
          ? pkt.stone_item_id.item_name
          : pkt.stone_item_name) || "";
      const uom =
        (pkt.stone_item_id && typeof pkt.stone_item_id === "object"
          ? pkt.stone_item_id.uom
          : pkt.stone_item_uom) || "";
      setValue("detail.item", shortCode);
      setValue("detail.rate", pkt.rate_for_retail ?? pkt.rate ?? "");
      setDetailItemDisplay(itemName);
      setDetailUom(uom);
    }
  }, [detailPacket, packetData, setValue]);

  // ── CT → GW auto-calc helpers (1 ct = 0.2 gm) ────
  // Inline entry row
  const handleEntryCtChange = () => {
    if (detailUom.toLowerCase() === "ct") {
      const ct = parseFloat(getValues("detail.ct")) || 0;
      setValue("detail.gw", fmt3(ct * 0.2));
    }
    recalcEntryAmt();
  };

  // Saved rows
  const handleDetailCtChange = (index) => {
    const uom = (getValues(`form.barcodedetails_set.${index}.uom`) || "").toLowerCase();
    if (uom === "ct") {
      const ct = parseFloat(getValues(`form.barcodedetails_set.${index}.ct`)) || 0;
      setValue(`form.barcodedetails_set.${index}.gw`, fmt3(ct * 0.2));
    }
    recalcDetailAmt(index);
  };

  // ── Prefill from Receive / Purchase ────────────────
  useEffect(() => {
    // Helper: format all weight fields in a barcodedetails row to 3 dp strings
    const fmtDetailWeights = (d) => ({ ...d, ct: fmt3(d.ct), gw: fmt3(d.gw) });

    if (sl_no && rec_slip_no && rec_slip_no !== "null") {
      fetchReceiveItemsForBarcode(sl_no, rec_slip_no)
        .then((r) => {
          if (r.success) {
            // Purity Select races with purityData load — stash for re-apply effect
            pvPurityRef.current = r.data.purity || null;
            const formData = {
              ...r.data,
              gw: fmt3(r.data.gw),
              nw: fmt3(r.data.nw),
              barcodedetails_set: (r.data.barcodedetails_set || []).map(fmtDetailWeights),
            };
            reset({ form: formData, detail: getValues("detail") });
          }
        })
        .catch(() => toast({ title: "Error", description: "Failed to load barcode details" }));
    } else if (sl_no && bill_no) {
      fetchPurhcaseItemsForBarcode(sl_no, bill_no)
        .then((r) => {
          if (r.success) {
            pvPurityRef.current = r.data.purity || null;
            // If purityData already loaded by the time prefill returns, the re-apply
            // useEffect won't re-fire (it depends on purityData, not the ref). Apply now.
            if (pvPurityRef.current) {
              setValue("form.purity", pvPurityRef.current);
            }
            // Capture the gold/metal entry (no packet) before filtering it out.
            // It will be re-injected on submit with the actual NW as its weight.
            pvGoldItemRef.current =
              (r.data.barcodedetails_set || []).find((d) => !d.packet) || null;
            const formData = {
              ...r.data,
              gw: fmt3(r.data.gw),
              nw: fmt3(r.data.nw),
              barcodedetails_set: (r.data.barcodedetails_set || [])
                .filter(d => d.packet)
                .map(fmtDetailWeights),
            };
            reset({ form: formData, detail: getValues("detail") });
            setPvPrefilled(true);
          }
        })
        .catch(() => toast({ title: "Error", description: "Failed to load barcode details" }));
    }
  }, [sl_no, rec_slip_no, reset]);

  // ── Load master data + edit mode ───────────────────
  useEffect(() => {
    async function fetchData() {
      const [karigarR, mainItemR, purityR, nextBarcodeR, packetR] = await Promise.all([
        fetchKarigarIssues(),
        fetchMainItem(),
        fetchPurity(),
        fetchNextBarcode(),
        fetchPackets(),
      ]);
      if (karigarR.success) setKarigars(Array.isArray(karigarR.data) ? karigarR.data : karigarR.data.results || []);
      if (mainItemR.success) setMainItemData(Array.isArray(mainItemR.data) ? mainItemR.data : mainItemR.data.results || []);
      if (purityR.success) setPurityData(Array.isArray(purityR.data) ? purityR.data : purityR.data.results || []);
      if (packetR.success) setPacketData(Array.isArray(packetR.data) ? packetR.data : packetR.data.results || []);
      if (!id && nextBarcodeR.success) setValue("form.barcode", nextBarcodeR.data.barcode);

      if (id) {
        try {
          const response = await fetchBarcodeForEdit(id);
          if (response.success || response.data) {
            const d = response.data;
            if (d.stk_status === false) setIsReadOnly(true);
            // Capture gold/metal sub-item (no packet) into the ref so it can be
            // re-injected on submit — and filter it out of the editable list
            // (its weight lives in NW and its purity mirrors the main item).
            const allDetails = d.barcodedetails_set || [];
            const goldRow = allDetails.find((r) => !r.packet && r.item === "Gold") || null;
            pvGoldItemRef.current = goldRow;
            // Stash the loaded purity so the submit's effectivePurity fallback
            // works in edit mode too (mirrors what we do for PV prefill above).
            pvPurityRef.current = d.purity || null;
            // Format weight fields to 3 dp strings before setting
            const formData = {
              ...d,
              // Prefill ORDER NO textbox with the readable CO number
              order_no: d.customer_order_no || "",
              gw: fmt3(d.gw),
              nw: fmt3(d.nw),
              barcodedetails_set: allDetails
                .filter((row) => row !== goldRow)
                .map((row) => ({ ...row, ct: fmt3(row.ct), gw: fmt3(row.gw) })),
            };
            Object.keys(formData).forEach((key) => setValue(`form.${key}`, formData[key]));
          }
        } catch (error) {
          console.error("Error fetching barcode for edit:", error);
        }
      }
    }
    fetchData();
  }, []);

  // ── Submit ─────────────────────────────────────────
  // Resolve an item reference (short_code / item_name) to its numeric id using
  // the in-memory item master. Leaves numeric ids untouched; falls back to the
  // original value if no match (backend accepts both id and short_code).
  const resolveItemId = (val) => {
    if (val === null || val === undefined || val === "") return val;
    if (typeof val === "number") return val;
    if (typeof val === "string" && /^\d+$/.test(val.trim())) return val;
    const found = mainItemData.find((i) => i.short_code === val || i.item_name === val);
    return found?.id ?? val;
  };

  const onSubmit = () => {
    const form_data = { ...getValues("form") };
    // Submit-time transform: send the main item as its numeric id, not short_code.
    form_data.item = resolveItemId(form_data.item);

    // Resolve the effective main-item purity. The Radix Select races with purityData
    // load — if purityData arrives BEFORE the PV prefill, the re-apply useEffect
    // (line ~363) never fires after the ref is set, leaving form.purity blank at
    // submit. Fall back to pvPurityRef.current so the gold sub-item still gets a
    // purity_id even in that race.
    const effectivePurity = form_data.purity || pvPurityRef.current || null;

    // Sub-items inherit purity strictly by item type — overrides any stale value
    // that may have been left on the row:
    //   Raw (R)   → main-item purity (e.g. 22K)  — gold scrap, accessory metal, etc.
    //                (if the user explicitly set d.purity, that wins)
    //   Stone (S) → always null (stones never carry a metal purity)
    //   anything else → null
    const stoneDetails = (form_data.barcodedetails_set || []).map((d) => {
      const itemMaster = mainItemData.find((m) => m.short_code === d.item);
      const t = (itemMaster?.item_type || "").toUpperCase();
      let purity;
      if (t === "S") {
        purity = null;
      } else if (t === "R") {
        purity = d.purity || effectivePurity;
      } else {
        purity = null;
      }
      return {
        ...d,
        item: resolveItemId(d.item),   // submit item as numeric id, not short_code
        barcode_text: form_data.barcode,
        purity,
      };
    });

    // Gold sub-item — re-inject with NW as weight and main-item purity
    // (rate is fetched live at sale time). The item must always be the
    // raw "Gold" item, not the main finished-product item.
    const nw = parseFloat(form_data.nw) || 0;
    const goldRef = pvGoldItemRef.current || {
      item:      "Gold",
      item_name: "Gold",
      uom:       "Gm",
    };
    const goldEntry = nw > 0
      ? {
          packet:       null,
          item:         goldRef.item,
          item_name:    goldRef.item_name,
          uom:          goldRef.uom,
          pcs:          0,
          ct:           0,
          gw:           nw,
          purity:       effectivePurity,   // main-item purity (e.g. "22K") — race-safe
          rate:         0,
          amt:          0,
          barcode_text: form_data.barcode,
        }
      : null;

    form_data.barcodedetails_set = [
      ...stoneDetails,
      ...(goldEntry ? [goldEntry] : []),
    ];

    // Remove transient fields
    delete form_data.item_name;

    (id ? updateBarcodeForEdit(form_data, id) : createBarcode(form_data))
      .then(async (response) => {
        if (response.success) {
          // Create mode: flush the photos staged while filling the form, now that
          // the new barcode id exists. (Edit mode uploads live, so nothing staged.)
          let photoMsg = "";
          const newId = id || response.data?.id;
          if (!id && stagedPhotos.length && newId) {
            const up = await uploadBarcodeImages(newId, stagedPhotos);
            photoMsg = up.success
              ? ` + ${stagedPhotos.length} photo${stagedPhotos.length > 1 ? "s" : ""}`
              : "";
            if (!up.success) {
              toast({ title: "Barcode saved, but photos failed to upload.", variant: "destructive" });
            }
          }
          toast({ title: `Barcode saved successfully!${photoMsg}` });
          setStagedPhotos([]);
          setTimeout(() => navigate("/inventory/barcodemanagement/list/"), 1500);
        } else {
          toast({ title: "Save failed", description: renderErrorTree(response.error), variant: "destructive" });
        }
      })
      .catch(() => toast({ title: "An error occurred. Please try again.", variant: "destructive" }));
  };

  useF4Submit(handleSubmit(onSubmit));

  // ── Add sub-item row from entry fields ─────────────
  const handleAddSubItem = () => {
    const d = getValues("detail");
    if (!d.item) {
      toast({ title: "Select an item", description: "Enter the item code for the sub-item." });
      return;
    }
    const itemObj = mainItemData.find((i) => i.short_code === d.item);
    append({
      packet: d.packet || "",
      item: d.item,
      item_name: detailItemDisplay || itemObj?.item_name || d.item,
      uom: itemObj?.uom || "",
      pcs: d.pcs || "",
      ct: d.ct || "",
      gw: d.gw || "",
      rate: d.rate || "",
      amt: d.amt || "",
    });
    // Reset entry fields
    setValue("detail", { packet: "", item: "", pcs: "", ct: "", gw: "", rate: "", amt: "" });
    setDetailItemDisplay("");
    recalcNetWeight();
    recalcTotal();
    setTimeout(() => packetInputRef.current?.focus(), 50);
  };

  // Tab on last field → add sub-item
  const handleSubItemKeyDown = (e) => {
    if (e.key === "Tab" && !e.shiftKey) {
      const d = getValues("detail");
      if (d.item) {
        e.preventDefault();
        handleAddSubItem();
      }
    }
  };

  // ── Detail amount recalc (for saved rows) ──────────
  const recalcDetailAmt = (index) => {
    const rate = parseFloat(getValues(`form.barcodedetails_set.${index}.rate`)) || 0;
    const uom = (getValues(`form.barcodedetails_set.${index}.uom`) || "").toLowerCase();
    let qty = 0;
    if (uom === "ct") qty = parseFloat(getValues(`form.barcodedetails_set.${index}.ct`)) || 0;
    else if (uom === "gm") qty = parseFloat(getValues(`form.barcodedetails_set.${index}.gw`)) || 0;
    else qty = parseFloat(getValues(`form.barcodedetails_set.${index}.pcs`)) || 0;
    setValue(`form.barcodedetails_set.${index}.amt`, Math.round(rate * qty));
    recalcNetWeight();
    recalcTotal();
  };

  // ── Inline entry amount recalc ─────────────────────
  const recalcEntryAmt = () => {
    const rate = parseFloat(getValues("detail.rate")) || 0;
    const itemObj = mainItemData.find((i) => i.short_code === getValues("detail.item"));
    const uom = (itemObj?.uom || "").toLowerCase();
    let qty = 0;
    if (uom === "ct") qty = parseFloat(getValues("detail.ct")) || 0;
    else if (uom === "gm") qty = parseFloat(getValues("detail.gw")) || 0;
    else qty = parseFloat(getValues("detail.pcs")) || 0;
    setValue("detail.amt", Math.round(rate * qty));
  };

  // ── Re-apply purity once purityData is available (fixes Radix Select race) ──
  useEffect(() => {
    if (purityData.length === 0 || !pvPurityRef.current) return;
    setValue("form.purity", pvPurityRef.current);
  }, [purityData]);

  // ── Apply packet-master rates + calculate sub-item amounts ─────────────────
  // Items WITH a packet → rate comes from packet_master.rate_for_retail
  // Items WITHOUT a packet (e.g. Gold) → rate stays from PV; skip (realtime at sale)
  useEffect(() => {
    if (!pvPrefilled || packetData.length === 0) return;
    const details = getValues("form.barcodedetails_set") || [];
    details.forEach((detail, index) => {
      if (!detail.packet) return; // Gold / no-packet items: skip, handled at sale time
      const pkt = packetData.find((p) => p.pckt_no === detail.packet);
      const rate = pkt ? (pkt.rate_for_retail ?? 0) : (parseFloat(detail.rate) || 0);
      setValue(`form.barcodedetails_set.${index}.rate`, rate);
      const uom = (detail.uom || "").toLowerCase();
      let qty = 0;
      if (uom === "ct") qty = parseFloat(detail.ct) || 0;
      else if (uom === "gm") qty = parseFloat(detail.gw) || 0;
      else qty = parseFloat(detail.pcs) || 0;
      setValue(`form.barcodedetails_set.${index}.amt`, Math.round(rate * qty));
    });
    recalcTotal();
  }, [packetData, pvPrefilled]);

  const handleDeleteDetail = (index) => {
    remove(index);
    setTimeout(() => { recalcNetWeight(); recalcTotal(); }, 0);
  };

  // ── Compute sub-item totals ────────────────────────
  const detailsArr = watch("form.barcodedetails_set") || [];
  const subTotalAmt = detailsArr.reduce((s, d) => s + (parseFloat(d.amt) || 0), 0);

  // ────────────────────────────────────────────────────
  // RENDER
  // ────────────────────────────────────────────────────
  return (
    <div className="mt-4">
      {isReadOnly && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive font-medium">
          This barcode is no longer in stock and cannot be edited.
        </div>
      )}
      <form className="space-y-8" id="orderForm" onSubmit={isReadOnly ? (e) => e.preventDefault() : handleSubmit(onSubmit)}>
      <div className={isReadOnly ? "pointer-events-none select-none opacity-60 space-y-8" : "space-y-8"}>

        {/* ════════════════════════════════════════════════
            SECTION 1: Header Info
            ════════════════════════════════════════════════ */}
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-muted-foreground">Item Details</h3>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setPhotoOpen(true)}
            >
              <ImageIcon className="size-4" />
              Photos
              {!id && stagedPhotos.length > 0 && (
                <span className="ml-1 rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">
                  {stagedPhotos.length}
                </span>
              )}
            </Button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-4 gap-y-3">
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">BARCODE</Label>
              <Input type="text" className="font-mono bg-accent/40" {...register("form.barcode")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">DESIGN NO</Label>
              <Input type="text" {...register("form.design_code")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">DATE</Label>
              <Input type="date" {...register("form.created_date")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">KARIGAR CODE</Label>
              <Controller
                name="form.kr_code"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value ? String(field.value) : ""}>
                    <SelectTrigger className="h-9"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {karigars.map((k) => (
                        <SelectItem key={k.id} value={String(k.id)}>{k.ledger_name || k.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">VOUCHER NO</Label>
              <Input type="text" {...register("form.voucher_no")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">ORDER NO</Label>
              <Input type="text" {...register("form.order_no")} />
            </FieldContainer>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-4 gap-y-3 mt-5">
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">HUID</Label>
              <Input type="text" {...register("form.huid")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">RFID TAG</Label>
              <Input type="text" className="font-mono" placeholder="Scan or type EPC" {...register("form.rfid_tag")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">SIZE</Label>
              <Input type="text" {...register("form.size")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">METAL COLOR</Label>
              <Input type="text" {...register("form.metal_color")} />
            </FieldContainer>
            <div className="flex items-end gap-2 pb-0.5">
              <Controller
                control={control}
                name="form.add_to_design"
                render={({ field }) => (
                  <Checkbox id="add_to_design" checked={field.value} onCheckedChange={(v) => field.onChange(Boolean(v))} />
                )}
              />
              <Label htmlFor="add_to_design" className="text-xs cursor-pointer">Add to Design Master</Label>
            </div>
          </div>
        </div>

        {/* ════════════════════════════════════════════════
            SECTION 2: Main Item (inline table entry row)
            ════════════════════════════════════════════════ */}
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="bg-primary/5 px-4 py-3 border-b">
            <span className="text-sm font-semibold text-primary">Main Item</span>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 text-xs">
                  <TableHead className="w-[130px]">Item *</TableHead>
                  <TableHead className="w-[140px]">Description</TableHead>
                  <TableHead className="w-[120px]">Purity *</TableHead>
                  <TableHead className="w-[70px] text-right">Pcs</TableHead>
                  <TableHead className="w-[90px] text-right">GW</TableHead>
                  <TableHead className="w-[90px] text-right">NW</TableHead>
                  <TableHead className="w-[90px] text-right">Value</TableHead>
                  <TableHead className="w-[90px] text-right">Making</TableHead>
                  <TableHead className="w-[110px]">Making Type</TableHead>
                  <TableHead className="w-[90px] text-right">Other Chg</TableHead>
                  <TableHead className="w-[100px] text-right font-bold">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow className="bg-accent/30">
                  <TableCell className="p-1.5">
                    <Input
                      type="text"
                      list="main_item_list"
                      className="h-8 text-sm"
                      {...register("form.item", {
                        onChange: (e) => {
                          const found = mainItemData.find((i) => i.short_code === e.target.value);
                          if (found) setValue("form.item_name", found.item_name);
                        },
                      })}
                    />
                    <datalist id="main_item_list">
                      {mainItemData.map((item, i) => (
                        <option key={i} value={item.short_code}>{item.item_name}</option>
                      ))}
                    </datalist>
                  </TableCell>
                  <TableCell className="p-1.5">
                    <span className="text-xs text-muted-foreground truncate block">{item_name || "—"}</span>
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Controller
                      name="form.purity"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value || ""}>
                          <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="Select" /></SelectTrigger>
                          <SelectContent>
                            {purityData.map((p) => (
                              <SelectItem key={p.id || p.purity} value={p.purity}>{p.purity}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" className="h-8 text-sm text-right" {...register("form.pcs")} />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="text" inputMode="decimal" placeholder="0.000" className="h-8 text-sm text-right"
                      {...register("form.gw", {
                        onChange: () => { recalcNetWeight(); recalcTotal(); },
                        onBlur: (e) => { setValue("form.gw", fmt3(e.target.value)); recalcNetWeight(); },
                      })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="text" inputMode="decimal" placeholder="0.000" className="h-8 text-sm text-right bg-muted/30"
                      readOnly tabIndex={-1}
                      {...register("form.nw")}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" step="1" placeholder="0" className="h-8 text-sm text-right bg-muted/30"
                      readOnly tabIndex={-1}
                      {...register("form.value")}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" step="1" placeholder="0" className="h-8 text-sm text-right"
                      {...register("form.making_val", { onChange: recalcTotal })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Controller
                      name="form.making_type"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={(v) => { field.onChange(v); recalcTotal(); }} value={field.value || ""}>
                          <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="Type" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="per_nw">% of NW</SelectItem>
                            <SelectItem value="val">Value</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" step="1" placeholder="0" className="h-8 text-sm text-right"
                      {...register("form.other_chg", { onChange: recalcTotal })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" step="1" placeholder="0" className="h-8 text-sm text-right font-semibold bg-muted/30"
                      readOnly tabIndex={-1}
                      {...register("form.total_amount")}
                    />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </div>

        {/* ════════════════════════════════════════════════
            SECTION 3: Sub-item Entry Row + Saved Items
            ════════════════════════════════════════════════ */}
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="bg-primary/5 px-4 py-3 border-b flex items-center justify-between">
            <span className="text-sm font-semibold text-primary">Sub-Items (Stones / Accessories)</span>
            <Button type="button" size="sm" variant="outline" className="h-7 text-xs" onClick={handleAddSubItem}>
              <Plus className="size-4 mr-1" /> Add
            </Button>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 text-xs">
                  <TableHead className="w-[40px]"></TableHead>
                  <TableHead className="w-[120px]">Packet</TableHead>
                  <TableHead className="w-[130px]">Item *</TableHead>
                  <TableHead className="w-[110px]">Description</TableHead>
                  <TableHead className="w-[70px] text-right">Pcs</TableHead>
                  <TableHead className="w-[80px] text-right">Ct</TableHead>
                  <TableHead className="w-[80px] text-right">GW</TableHead>
                  <TableHead className="w-[80px] text-right">Rate</TableHead>
                  <TableHead className="w-[90px] text-right">Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* ── Inline entry row (orange tint) ── */}
                <TableRow className="bg-orange-50/70 border-b-2 border-orange-200">
                  <TableCell className="p-1.5">
                    {/* + action lives in the leading action column so this row
                         aligns with the saved-row layout (delete in col 1). */}
                    <Button type="button" variant="ghost" size="icon" className="size-7 text-primary" onClick={handleAddSubItem}>
                      <Plus className="size-4" />
                    </Button>
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="text" list="detail_packet_list" className="h-8 text-sm"
                      placeholder="Packet"
                      ref={(el) => {
                        packetInputRef.current = el;
                        register("detail.packet").ref(el);
                      }}
                      {...(() => { const { ref, ...rest } = register("detail.packet"); return rest; })()}
                    />
                    <datalist id="detail_packet_list">
                      {packetData.map((p, i) => (
                        <option key={i} value={p.pckt_no}>{p.pckt_no}</option>
                      ))}
                    </datalist>
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="text" list="detail_item_list"
                      placeholder="Item code"
                      disabled={!!detailPacket}
                      className={`h-8 text-sm${detailPacket ? " bg-muted text-muted-foreground cursor-not-allowed" : ""}`}
                      {...register("detail.item", {
                        onChange: (e) => {
                          const found = mainItemData.find((i) => i.short_code === e.target.value);
                          if (found) {
                            setDetailItemDisplay(found.item_name);
                            setDetailUom(found.uom || "");
                          } else {
                            setDetailItemDisplay("");
                            setDetailUom("");
                          }
                        },
                      })}
                    />
                    <datalist id="detail_item_list">
                      {mainItemData.map((item, i) => (
                        <option key={i} value={item.short_code}>{item.item_name}</option>
                      ))}
                    </datalist>
                  </TableCell>
                  <TableCell className="p-1.5">
                    <span className="text-xs text-muted-foreground truncate block">{detailItemDisplay || "—"}</span>
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" className="h-8 text-sm text-right"
                      {...register("detail.pcs", { onChange: recalcEntryAmt })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="text" inputMode="decimal" placeholder="0.000" className="h-8 text-sm text-right"
                      disabled={detailUom.toLowerCase() === "gm"}
                      {...register("detail.ct", {
                        onChange: handleEntryCtChange,
                        onBlur: (e) => setValue("detail.ct", fmt3(e.target.value)),
                      })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="text" inputMode="decimal" placeholder="0.000" className="h-8 text-sm text-right"
                      readOnly={detailUom.toLowerCase() === "ct"}
                      disabled={detailUom.toLowerCase() === "ct"}
                      {...register("detail.gw", {
                        onChange: recalcEntryAmt,
                        onBlur: (e) => { if (detailUom.toLowerCase() !== "ct") setValue("detail.gw", fmt3(e.target.value)); },
                      })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" step="1" placeholder="0" className="h-8 text-sm text-right"
                      {...register("detail.rate", { onChange: recalcEntryAmt })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" step="1" placeholder="0" className="h-8 text-sm text-right"
                      onKeyDown={handleSubItemKeyDown}
                      {...register("detail.amt")}
                    />
                  </TableCell>
                </TableRow>

                {/* ── Saved sub-item rows ── */}
                {fields.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center py-6 text-muted-foreground text-sm">
                      Enter sub-item details above and press <kbd className="mx-1 px-1.5 py-0.5 rounded bg-muted text-xs font-mono">Tab</kbd> on Value to add, or click <strong>+ Add</strong>.
                    </TableCell>
                  </TableRow>
                )}
                {fields.map((field, index) => (
                  <TableRow key={field.id} className="hover:bg-muted/20">
                    <TableCell className="p-1.5">
                      <Button type="button" variant="ghost" size="icon" className="size-7 text-destructive hover:text-destructive"
                        onClick={() => handleDeleteDetail(index)}>
                        <Trash2 className="size-4" />
                      </Button>
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="text" list={`saved_pckt_${index}`} className="h-8 text-sm"
                        {...register(`form.barcodedetails_set.${index}.packet`, {
                          onChange: (e) => {
                            const pkt = packetData.find((p) => p.pckt_no === e.target.value);
                            if (pkt) {
                              const itemObj = pkt.stone_item_id;
                              if (itemObj && typeof itemObj === "object") {
                                setValue(`form.barcodedetails_set.${index}.item`, itemObj.short_code || "");
                                setValue(`form.barcodedetails_set.${index}.item_name`, itemObj.item_name || "");
                                setValue(`form.barcodedetails_set.${index}.uom`, itemObj.uom || "");
                              } else if (pkt.stone_item_short_code) {
                                setValue(`form.barcodedetails_set.${index}.item`, pkt.stone_item_short_code);
                                setValue(`form.barcodedetails_set.${index}.item_name`, pkt.stone_item_name || "");
                                setValue(`form.barcodedetails_set.${index}.uom`, pkt.stone_item_uom || "");
                              }
                              setValue(`form.barcodedetails_set.${index}.rate`, pkt.rate_for_retail ?? 0);
                              recalcDetailAmt(index);
                            }
                          },
                        })}
                      />
                      <datalist id={`saved_pckt_${index}`}>
                        {packetData.map((p, i) => <option key={i} value={p.pckt_no} />)}
                      </datalist>
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input
                        list={`saved_item_${index}`}
                        disabled={!!field.packet}
                        className={`h-8 text-sm${field.packet ? " bg-muted text-muted-foreground cursor-not-allowed" : ""}`}
                        {...register(`form.barcodedetails_set.${index}.item`, {
                          onChange: (e) => {
                            const found = mainItemData.find((i) => i.short_code === e.target.value);
                            if (found) {
                              setValue(`form.barcodedetails_set.${index}.item_name`, found.item_name);
                              setValue(`form.barcodedetails_set.${index}.uom`, found.uom || "");
                            }
                          },
                        })}
                      />
                      <datalist id={`saved_item_${index}`}>
                        {mainItemData.map((item, i) => <option key={i} value={item.short_code}>{item.item_name}</option>)}
                      </datalist>
                    </TableCell>
                    <TableCell className="p-1.5">
                      <span className="text-xs text-muted-foreground truncate block">
                        {field.item_name || ""}
                      </span>
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="number" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.pcs`, { onChange: () => recalcDetailAmt(index) })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="text" inputMode="decimal" placeholder="0.000" className="h-8 text-sm text-right"
                        disabled={(field.uom || "").toLowerCase() === "gm"}
                        {...register(`form.barcodedetails_set.${index}.ct`, {
                          onChange: () => handleDetailCtChange(index),
                          onBlur: (e) => setValue(`form.barcodedetails_set.${index}.ct`, fmt3(e.target.value)),
                        })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="text" inputMode="decimal" placeholder="0.000" className="h-8 text-sm text-right"
                        readOnly={(field.uom || "").toLowerCase() === "ct"}
                        disabled={(field.uom || "").toLowerCase() === "ct"}
                        {...register(`form.barcodedetails_set.${index}.gw`, {
                          onChange: () => recalcDetailAmt(index),
                          onBlur: (e) => { if ((field.uom || "").toLowerCase() !== "ct") setValue(`form.barcodedetails_set.${index}.gw`, fmt3(e.target.value)); },
                        })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="number" step="1" placeholder="0" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.rate`, { onChange: () => recalcDetailAmt(index) })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="number" step="1" placeholder="0" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.amt`)}
                      />
                    </TableCell>
                  </TableRow>
                ))}

                {/* ── Total row ── */}
                {fields.length > 0 && (
                  <TableRow className="bg-muted/30 font-semibold border-t-2">
                    <TableCell colSpan={7} className="text-right p-2 text-sm">TOTAL</TableCell>
                    <TableCell className="text-right p-2 text-sm font-bold">{formatNumber(subTotalAmt)}</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* ════════════════════════════════════════════════
            SECTION 4: Actions
            ════════════════════════════════════════════════ */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">Press <kbd className="mx-1 px-1.5 py-0.5 rounded bg-muted text-xs font-mono">F4</kbd> to Save</span>
          <div className="flex-1" />
          {!isReadOnly && <Button type="submit" className="px-6">Save</Button>}
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
        </div>
      </form>

      <BarcodeImages
        barcodeId={id || undefined}
        barcodeText={watch("form.barcode") || "New Barcode"}
        open={photoOpen}
        onOpenChange={setPhotoOpen}
        staged={!id}
        stagedFiles={stagedPhotos}
        onStagedChange={setStagedPhotos}
      />
    </div>
  );
};

export default BarcodeManagementList;

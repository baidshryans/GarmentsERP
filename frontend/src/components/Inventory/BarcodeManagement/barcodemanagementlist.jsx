import React, { useEffect, useState, useRef, useCallback } from "react";
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
  fetchPackets,
} from "@/services/apiService";
import { useLocation, useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { Plus, Trash2 } from "lucide-react";
import { renderErrorTree } from "../../../Utils";

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
        huid: "", value: "", making_val: "", making_type: "", other_chg: 0,
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
  const [detailItemDisplay, setDetailItemDisplay] = useState("");

  const { fields, append, remove } = useFieldArray({ control, name: "form.barcodedetails_set" });

  const item_name = watch("form.item_name");
  const formGw = watch("form.gw");
  const detailPacket = watch("detail.packet");

  // ── Auto-calculate Net Weight ──────────────────────
  const recalcNetWeight = useCallback(() => {
    const gw = parseFloat(getValues("form.gw")) || 0;
    const details = getValues("form.barcodedetails_set") || [];
    const subGw = details.reduce((sum, d) => sum + (parseFloat(d.gw) || 0), 0);
    setValue("form.nw", parseFloat((gw - subGw).toFixed(3)));
  }, [getValues, setValue]);

  useEffect(() => { recalcNetWeight(); }, [formGw, fields.length]);

  // ── Auto-calculate Total Amount ────────────────────
  const recalcTotal = useCallback(() => {
    const value = parseFloat(getValues("form.value")) || 0;
    const making = parseFloat(getValues("form.making_val")) || 0;
    const otherChg = parseFloat(getValues("form.other_chg")) || 0;
    const details = getValues("form.barcodedetails_set") || [];
    const subTotal = details.reduce((sum, d) => sum + (parseFloat(d.amt) || 0), 0);
    setValue("form.total_amount", Math.round(value + making + otherChg + subTotal));
  }, [getValues, setValue]);

  // ── Packet → Item auto-load ────────────────────────
  useEffect(() => {
    if (!detailPacket) {
      setDetailItemDisplay("");
      setValue("detail.item", "");
      setValue("detail.rate", "");
      return;
    }
    const pkt = packetData.find((p) => p.pckt_no === detailPacket);
    if (pkt?.stone_item_id) {
      const item = pkt.stone_item_id;
      setValue("detail.item", item.short_code || "");
      setValue("detail.rate", pkt.rate_for_retail ?? pkt.rate ?? "");
      setDetailItemDisplay(item.item_name || "");
    }
  }, [detailPacket, packetData, setValue]);

  // ── Prefill from Receive / Purchase ────────────────
  useEffect(() => {
    if (sl_no && rec_slip_no && rec_slip_no !== "null") {
      fetchReceiveItemsForBarcode(sl_no, rec_slip_no)
        .then((r) => r.success && reset({ form: { ...r.data }, detail: getValues("detail") }))
        .catch(() => toast({ title: "Error", description: "Failed to load barcode details" }));
    } else if (sl_no && bill_no) {
      fetchPurhcaseItemsForBarcode(sl_no, bill_no)
        .then((r) => {
          if (r.success) reset({ form: r.data, detail: getValues("detail") });
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
            Object.keys(response.data).forEach((key) => setValue(`form.${key}`, response.data[key]));
          }
        } catch (error) {
          console.error("Error fetching barcode for edit:", error);
        }
      }
    }
    fetchData();
  }, []);

  // ── Submit ─────────────────────────────────────────
  const onSubmit = () => {
    const form_data = { ...getValues("form") };
    form_data.barcodedetails_set = (form_data.barcodedetails_set || []).map((d) => ({
      ...d, barcode_text: form_data.barcode,
    }));
    // Remove transient fields
    delete form_data.item_name;

    (id ? updateBarcodeForEdit(form_data, id) : createBarcode(form_data))
      .then((response) => {
        if (response.success) {
          toast({ title: "Barcode saved successfully!" });
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
      <form className="space-y-5" id="orderForm" onSubmit={handleSubmit(onSubmit)}>

        {/* ════════════════════════════════════════════════
            SECTION 1: Header Info
            ════════════════════════════════════════════════ */}
        <div className="rounded-lg border bg-card p-4 shadow-sm">
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
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-4 gap-y-3 mt-3">
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">HUID</Label>
              <Input type="text" {...register("form.huid")} />
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
          <div className="bg-primary/5 px-4 py-2 border-b">
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
                      type="number" step="0.001" className="h-8 text-sm text-right"
                      {...register("form.gw", { onChange: () => { recalcNetWeight(); recalcTotal(); } })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" step="0.001" className="h-8 text-sm text-right bg-muted/30"
                      readOnly tabIndex={-1}
                      {...register("form.nw")}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" className="h-8 text-sm text-right"
                      {...register("form.value", { onChange: recalcTotal })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" className="h-8 text-sm text-right"
                      {...register("form.making_val", { onChange: recalcTotal })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Controller
                      name="form.making_type"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value || ""}>
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
                      type="number" className="h-8 text-sm text-right"
                      {...register("form.other_chg", { onChange: recalcTotal })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input
                      type="number" className="h-8 text-sm text-right font-semibold bg-muted/30"
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
          <div className="bg-primary/5 px-4 py-2 border-b flex items-center justify-between">
            <span className="text-sm font-semibold text-primary">Sub-Items (Stones / Accessories)</span>
            <Button type="button" size="sm" variant="outline" className="h-7 text-xs" onClick={handleAddSubItem}>
              <Plus className="h-3.5 w-3.5 mr-1" /> Add
            </Button>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 text-xs">
                  <TableHead className="w-[120px]">Packet</TableHead>
                  <TableHead className="w-[130px]">Item *</TableHead>
                  <TableHead className="w-[110px]">Description</TableHead>
                  <TableHead className="w-[70px] text-right">Pcs</TableHead>
                  <TableHead className="w-[80px] text-right">Ct</TableHead>
                  <TableHead className="w-[80px] text-right">GW</TableHead>
                  <TableHead className="w-[80px] text-right">Rate</TableHead>
                  <TableHead className="w-[90px] text-right">Value</TableHead>
                  <TableHead className="w-[40px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* ── Inline entry row (orange tint) ── */}
                <TableRow className="bg-orange-50/70 border-b-2 border-orange-200">
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
                      type="text" list="detail_item_list" className="h-8 text-sm"
                      placeholder="Item code"
                      {...register("detail.item", {
                        onChange: (e) => {
                          const found = mainItemData.find((i) => i.short_code === e.target.value);
                          if (found) setDetailItemDisplay(found.item_name);
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
                    <Input type="number" step="0.001" className="h-8 text-sm text-right"
                      {...register("detail.ct", { onChange: recalcEntryAmt })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" step="0.001" className="h-8 text-sm text-right"
                      {...register("detail.gw", { onChange: recalcEntryAmt })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" className="h-8 text-sm text-right"
                      {...register("detail.rate", { onChange: recalcEntryAmt })}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Input type="number" className="h-8 text-sm text-right"
                      onKeyDown={handleSubItemKeyDown}
                      {...register("detail.amt")}
                    />
                  </TableCell>
                  <TableCell className="p-1.5">
                    <Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-primary" onClick={handleAddSubItem}>
                      <Plus className="h-4 w-4" />
                    </Button>
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
                      <Input type="text" list={`saved_pckt_${index}`} className="h-8 text-sm"
                        {...register(`form.barcodedetails_set.${index}.packet`)}
                      />
                      <datalist id={`saved_pckt_${index}`}>
                        {packetData.map((p, i) => <option key={i} value={p.pckt_no} />)}
                      </datalist>
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="text" list={`saved_item_${index}`} className="h-8 text-sm"
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
                      <Input type="number" step="0.001" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.ct`, { onChange: () => recalcDetailAmt(index) })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="number" step="0.001" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.gw`, { onChange: () => recalcDetailAmt(index) })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="number" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.rate`, { onChange: () => recalcDetailAmt(index) })}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Input type="number" className="h-8 text-sm text-right"
                        {...register(`form.barcodedetails_set.${index}.amt`)}
                      />
                    </TableCell>
                    <TableCell className="p-1.5">
                      <Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                        onClick={() => handleDeleteDetail(index)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}

                {/* ── Total row ── */}
                {fields.length > 0 && (
                  <TableRow className="bg-muted/30 font-semibold border-t-2">
                    <TableCell colSpan={7} className="text-right p-2 text-sm">TOTAL</TableCell>
                    <TableCell className="text-right p-2 text-sm font-bold">{subTotalAmt.toLocaleString("en-IN")}</TableCell>
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
          <Button type="submit" className="px-6">Save</Button>
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default BarcodeManagementList;

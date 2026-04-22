import React, { useEffect, useState, useCallback } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import {
  fetchMainItem, fetchBarcodeByText, fetchBarcodeForEdit,
  mergeBarcode, fetchNextBarcode,
} from "@/services/apiService";
import { Link } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../../Utils";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt3 = (v) => (v != null && v !== "" ? parseFloat(v).toFixed(3) : "—");
const sumField = (rows, field) =>
  rows.reduce((acc, r) => acc + (parseFloat(r[field]) || 0), 0);

/**
 * Build the merged subitems preview:
 * All barcodedetails_set from all rows, grouped by packet key (fallback: item).
 * Common packets have their pcs / ct / gw / amt summed.
 */
function buildMergedSubitems(rows) {
  const map = new Map();
  for (const row of rows) {
    for (const d of row.barcodedetails_set || []) {
      const key = d.packet || `__item__${d.item}`;
      if (map.has(key)) {
        const e = map.get(key);
        e.pcs = (e.pcs || 0) + (d.pcs || 0);
        e.ct  = (parseFloat(e.ct  || 0) + parseFloat(d.ct  || 0)) || null;
        e.gw  = (parseFloat(e.gw  || 0) + parseFloat(d.gw  || 0)) || null;
        e.amt = (parseFloat(e.amt || 0) + parseFloat(d.amt || 0)) || null;
      } else {
        map.set(key, { ...d });
      }
    }
  }
  return Array.from(map.values());
}

// ─── Component ───────────────────────────────────────────────────────────────

const MergeBarcode = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { register, handleSubmit, control, watch, setValue, getValues } = useForm({
    defaultValues: {
      form: {
        date1: new Date().toISOString().split("T")[0],
        barcode: "",
        item: "",
        purity: "",
        pcs: "",
        gw: "",
        nw: "",
        making_val: "",
        making_type: "",
        other_chg: "",
        design_code: "",
        loss_wt: "",
        loss_value: "",
        old_barcode: "",
      },
    },
  });

  const [rs, setRows]                     = useState([]);
  const [expandedRows, setExpandedRows]   = useState(new Set());
  const [mergedSubitems, setMergedSubitems] = useState([]);
  const [showPreview, setShowPreview]     = useState(false);
  const [mainItemData, setMainItemData]   = useState([]);
  const [barcodeLoading, setBarcodeLoading] = useState(false);

  // ── On mount: load lookups + auto-barcode ──────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      const [nextBarcode, mainItem] = await Promise.all([
        fetchNextBarcode(),
        fetchMainItem({ type: "M" }),
      ]);
      if (nextBarcode.success) setValue("form.barcode", nextBarcode.data.barcode);
      if (mainItem.success)    setMainItemData(mainItem.data.results ?? mainItem.data);
    }
    fetchData();
  }, []);

  // ── Re-calculate merged totals whenever rs changes ─────────────────────────
  useEffect(() => {
    if (rs.length === 0) {
      setValue("form.purity", "");
      setValue("form.pcs",    "");
      setValue("form.gw",     "");
      setValue("form.nw",     "");
      setMergedSubitems([]);
      return;
    }

    // Purity — taken from first barcode (all are guaranteed same purity)
    // BarcodeMainSerializer uses SlugRelatedField(slug_field="purity"), so purity is the string value (e.g. "22KT")
    const puritySlug = rs[0].purity ?? "";
    setValue("form.purity", puritySlug);

    // Aggregate weights
    const totalPcs = rs.reduce((acc, r) => acc + (parseInt(r.pcs) || 0), 0);
    const totalGw  = sumField(rs, "gw").toFixed(3);
    const totalNw  = sumField(rs, "nw").toFixed(3);
    setValue("form.pcs", totalPcs);
    setValue("form.gw",  totalGw);
    setValue("form.nw",  totalNw);

    // Build merged subitems preview
    setMergedSubitems(buildMergedSubitems(rs));
  }, [rs]);

  // ── Toggle row expansion ───────────────────────────────────────────────────
  const toggleExpand = (index) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(index) ? next.delete(index) : next.add(index);
      return next;
    });
  };

  // ── Add barcode to merge list ──────────────────────────────────────────────
  const handleKeyDownBarcode = useCallback(async (e) => {
    if (e.key !== "Tab" && e.key !== "Enter") return;
    const barcode = getValues("form.old_barcode").trim();
    if (!barcode) return;
    e.preventDefault();

    // Prevent duplicate
    if (rs.some((r) => r.barcode === barcode)) {
      toast({ title: "This barcode is already added.", variant: "destructive" });
      setValue("form.old_barcode", "");
      return;
    }

    setBarcodeLoading(true);
    try {
      // Look up barcode in the list to verify it exists and get its ID
      const lookup = await fetchBarcodeByText(barcode);
      if (!lookup.success || !lookup.data) {
        toast({ title: "Barcode not found.", variant: "destructive" });
        return;
      }
      if (!lookup.data.stk_status) {
        toast({ title: "Barcode is not in stock.", variant: "destructive" });
        return;
      }

      // Fetch full details (barcodedetails_set + purity)
      const res = await fetchBarcodeForEdit(lookup.data.id);
      if (!res.success) {
        toast({ title: "Failed to load barcode details.", variant: "destructive" });
        return;
      }
      const detail = res.data;

      // Purity validation — all merged barcodes must share the same purity
      if (rs.length > 0) {
        const existingPurity = String(rs[0].purity ?? "");
        const newPurity      = String(detail.purity ?? "");
        if (existingPurity !== newPurity) {
          toast({
            title: "Purity mismatch",
            description: `Cannot merge barcodes of different purities. Expected: ${rs[0].purity}, got: ${detail.purity}.`,
            variant: "destructive",
          });
          return;
        }
      }

      setRows((prev) => [...prev, detail]);
      setValue("form.old_barcode", "");
    } finally {
      setBarcodeLoading(false);
    }
  }, [rs]);

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.delete(index);
      return next;
    });
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const onSubmit = (data) => {
    if (rs.length < 2) {
      toast({ title: "Add at least 2 barcodes to merge.", variant: "destructive" });
      return;
    }

    const sub_data = { ...data.form };
    delete sub_data.old_barcode;

    // Send original (unaggregated) details so backend can read barcode_text
    // for deactivating old barcodes
    sub_data.barcodedetails_set = rs
      .flatMap((r) => r.barcodedetails_set || [])
      .map(({ id, ...rest }) => rest);

    mergeBarcode(sub_data)
      .then((response) => {
        if (response.success) {
          toast({ title: "Barcodes merged successfully!" });
          setTimeout(() => navigate(""), 2000);
        } else if (response.status < 500) {
          toast({
            title: "Merge failed. Please check the details.",
            description: renderErrorTree(response.error),
          });
        } else {
          toast({ title: "An error occurred. Please try again later." });
        }
      })
      .catch(() => toast({ title: "An error occurred. Please try again later." }));
  };

  useF4Submit(handleSubmit(onSubmit));

  // ── Derived display helpers ────────────────────────────────────────────────
  // purity is already the slug string (e.g. "22KT") from the serializer
  const purityLabel = (slug) => slug || "—";

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="container mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white space-y-6"
        onSubmit={handleSubmit(onSubmit)}
      >

        {/* ── Section 1: Barcodes to Merge ─────────────────────────────── */}
        <div>
          <h6 className="font-semibold text-sm text-foreground mb-3 border-b pb-2">
            Barcodes to Merge
          </h6>

          <div className="flex items-end gap-3 mb-3">
            <FieldContainer>
              <Label className="text-nowrap text-xs">Enter Barcode</Label>
              <Input
                onKeyDown={handleKeyDownBarcode}
                type="text"
                {...register("form.old_barcode")}
                placeholder={barcodeLoading ? "Looking up…" : "Scan / type barcode, press Enter"}
                className="w-72"
                autoComplete="off"
                disabled={barcodeLoading}
              />
            </FieldContainer>
          </div>

          {rs.length > 0 && (
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/50 text-muted-foreground uppercase tracking-wider">
                    <th className="px-3 py-2 w-6"></th>
                    <th className="px-3 py-2 text-left">Barcode</th>
                    <th className="px-3 py-2 text-left">Item</th>
                    <th className="px-3 py-2 text-left">Purity</th>
                    <th className="px-3 py-2 text-right">Pcs</th>
                    <th className="px-3 py-2 text-right">Gw (g)</th>
                    <th className="px-3 py-2 text-right">Nw (g)</th>
                    <th className="px-3 py-2 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {rs.map((row, index) => (
                    <React.Fragment key={index}>
                      {/* Main row */}
                      <tr className={`border-t border-border/50 ${index % 2 === 1 ? "bg-muted/10" : ""}`}>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => toggleExpand(index)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            {expandedRows.has(index)
                              ? <ChevronDown className="w-3.5 h-3.5" />
                              : <ChevronRight className="w-3.5 h-3.5" />}
                          </button>
                        </td>
                        <td className="px-3 py-2 font-mono">{row.barcode}</td>
                        <td className="px-3 py-2">{row.item}</td>
                        <td className="px-3 py-2">{purityLabel(row.purity)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{row.pcs}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{fmt3(row.gw)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{fmt3(row.nw)}</td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => handleDelete(index)}
                            className="p-1 rounded text-red-500 hover:bg-red-50 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>

                      {/* Expandable subitems */}
                      {expandedRows.has(index) && (row.barcodedetails_set?.length > 0) && (
                        <tr className="border-t border-dashed border-border/30 bg-primary/5">
                          <td colSpan={8} className="px-8 py-2">
                            <table className="w-full text-[11px]">
                              <thead>
                                <tr className="text-muted-foreground uppercase tracking-wider">
                                  <th className="px-2 py-1 text-left">Item</th>
                                  <th className="px-2 py-1 text-left">Packet</th>
                                  <th className="px-2 py-1 text-left">Purity</th>
                                  <th className="px-2 py-1 text-right">Pcs</th>
                                  <th className="px-2 py-1 text-right">Ct / Gw</th>
                                  <th className="px-2 py-1 text-left">UOM</th>
                                  <th className="px-2 py-1 text-right">Rate</th>
                                  <th className="px-2 py-1 text-right">Amt</th>
                                </tr>
                              </thead>
                              <tbody>
                                {row.barcodedetails_set.map((d, di) => (
                                  <tr key={di} className="border-t border-border/20">
                                    <td className="px-2 py-1">{d.item || "—"}</td>
                                    <td className="px-2 py-1">{d.packet || "—"}</td>
                                    <td className="px-2 py-1">{d.purity || "—"}</td>
                                    <td className="px-2 py-1 text-right tabular-nums">{d.pcs ?? "—"}</td>
                                    <td className="px-2 py-1 text-right tabular-nums">
                                      {d.ct != null ? parseFloat(d.ct).toFixed(3)
                                        : d.gw != null ? parseFloat(d.gw).toFixed(3)
                                        : "—"}
                                    </td>
                                    <td className="px-2 py-1">{d.uom || "—"}</td>
                                    <td className="px-2 py-1 text-right tabular-nums">{d.rate ?? "—"}</td>
                                    <td className="px-2 py-1 text-right tabular-nums">{d.amt ?? "—"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}

                  {/* Totals row */}
                  {rs.length >= 2 && (
                    <tr className="border-t-2 border-border bg-muted/30 font-semibold">
                      <td colSpan={4} className="px-3 py-2 text-xs text-muted-foreground text-right">
                        Total
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {rs.reduce((a, r) => a + (parseInt(r.pcs) || 0), 0)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {sumField(rs, "gw").toFixed(3)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {sumField(rs, "nw").toFixed(3)}
                      </td>
                      <td />
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Section 2: New Barcode Subitems Preview ──────────────────── */}
        {mergedSubitems.length > 0 && (
          <div>
            <button
              type="button"
              className="flex items-center gap-1.5 text-sm font-semibold text-foreground border-b pb-2 w-full text-left mb-3"
              onClick={() => setShowPreview((v) => !v)}
            >
              {showPreview ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              New Barcode Subitems Preview
              <span className="text-xs font-normal text-muted-foreground ml-1">
                ({mergedSubitems.length} items)
              </span>
            </button>

            {showPreview && (
              <div className="rounded-lg border border-primary/20 overflow-hidden bg-primary/5">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-primary/10 text-primary uppercase tracking-wider">
                      <th className="px-3 py-2 text-left">Item</th>
                      <th className="px-3 py-2 text-left">Packet</th>
                      <th className="px-3 py-2 text-left">Purity</th>
                      <th className="px-3 py-2 text-right">Pcs</th>
                      <th className="px-3 py-2 text-right">Ct / Gw</th>
                      <th className="px-3 py-2 text-left">UOM</th>
                      <th className="px-3 py-2 text-right">Rate</th>
                      <th className="px-3 py-2 text-right">Amt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mergedSubitems.map((d, i) => (
                      <tr key={i} className={`border-t border-primary/10 ${i % 2 === 1 ? "bg-primary/5" : ""}`}>
                        <td className="px-3 py-2">{d.item || "—"}</td>
                        <td className="px-3 py-2">{d.packet || "—"}</td>
                        <td className="px-3 py-2">{d.purity || "—"}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{d.pcs ?? "—"}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {d.ct != null ? parseFloat(d.ct).toFixed(3)
                            : d.gw != null ? parseFloat(d.gw).toFixed(3)
                            : "—"}
                        </td>
                        <td className="px-3 py-2">{d.uom || "—"}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{d.rate ?? "—"}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {d.amt != null ? parseFloat(d.amt).toFixed(2) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── Section 3: New Merged Barcode Details ────────────────────── */}
        <div>
          <h6 className="font-semibold text-sm text-foreground mb-3 border-b pb-2">
            New Merged Barcode Details
          </h6>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {/* New barcode — read-only, auto-generated */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">New Barcode</Label>
              <Input
                type="text"
                value={watch("form.barcode") || "Auto-generating…"}
                readOnly
                className="bg-muted cursor-not-allowed font-mono text-sm"
              />
              <input type="hidden" {...register("form.barcode")} />
            </FieldContainer>

            {/* Purity — auto-set from merged barcodes */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Purity</Label>
              <Input
                type="text"
                value={purityLabel(watch("form.purity"))}
                readOnly
                className="bg-muted cursor-not-allowed text-sm"
                placeholder="Auto from barcodes"
              />
              <input type="hidden" {...register("form.purity")} />
            </FieldContainer>

            {/* Pcs — auto-summed */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Pcs</Label>
              <Input
                type="number"
                value={watch("form.pcs") || ""}
                readOnly
                className="bg-muted cursor-not-allowed text-sm text-right"
                placeholder="Auto"
              />
              <input type="hidden" {...register("form.pcs")} />
            </FieldContainer>

            {/* Gross Wt — auto-summed */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Gross Wt (g)</Label>
              <Input
                type="number"
                value={watch("form.gw") || ""}
                readOnly
                className="bg-muted cursor-not-allowed text-sm text-right"
                placeholder="Auto"
              />
              <input type="hidden" {...register("form.gw")} />
            </FieldContainer>

            {/* Net Wt — auto-summed */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Net Wt (g)</Label>
              <Input
                type="number"
                value={watch("form.nw") || ""}
                readOnly
                className="bg-muted cursor-not-allowed text-sm text-right"
                placeholder="Auto"
              />
              <input type="hidden" {...register("form.nw")} />
            </FieldContainer>

            {/* Item — M type only */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Item</Label>
              <Input list="item_list" {...register("form.item")} placeholder="Item code" className="text-sm" />
              <datalist id="item_list">
                {mainItemData.map((item, i) => (
                  <option key={i} value={item.short_code}>{item.item_name}</option>
                ))}
              </datalist>
            </FieldContainer>

            {/* Design Code */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Design Code</Label>
              <Input type="text" {...register("form.design_code")} className="text-sm" />
            </FieldContainer>

            {/* Making Value */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Making Value</Label>
              <Input type="number" {...register("form.making_val")} className="text-sm text-right" />
            </FieldContainer>

            {/* Making Type — Select */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Making Type</Label>
              <Controller
                name="form.making_type"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value || ""}>
                    <SelectTrigger className="text-sm h-9">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="per_nw">% of NW</SelectItem>
                      <SelectItem value="val">Value</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </FieldContainer>

            {/* Other Charges */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Other Charges</Label>
              <Input type="number" {...register("form.other_chg")} className="text-sm text-right" />
            </FieldContainer>

            {/* Gold Loss Wt */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Gold Loss Wt (g)</Label>
              <Input type="number" step="0.001" {...register("form.loss_wt")} className="text-sm text-right" />
            </FieldContainer>

            {/* Gold Loss Value */}
            <FieldContainer>
              <Label className="text-xs text-nowrap">Gold Loss Value</Label>
              <Input type="number" {...register("form.loss_value")} className="text-sm text-right" />
            </FieldContainer>
          </div>
        </div>

        {/* ── Submit ───────────────────────────────────────────────────── */}
        <div className="flex justify-end gap-3 pt-2">
          <Link to="">
            <Button variant="outline" type="button">Cancel</Button>
          </Link>
          <Button type="submit" disabled={rs.length < 2}>
            Save Merge
          </Button>
        </div>

      </form>
    </div>
  );
};

export default MergeBarcode;

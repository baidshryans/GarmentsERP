import React, { useEffect, useState, useRef, useCallback } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { Trash2, Search } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import Select from "react-select";
import {
  getLedgers,
  createSampleIssue,
  updateSampleIssue,
  fetchSampleIssueForEdit,
  fetchSampleIssueNextBillno,
  fetchKarigarReceiveSlipForSample,
  fetchBarcodeForSample,
} from "@/services/apiService";

const SLIP_TYPES = ["Job Work", "Repair", "Finishing", "Polishing", "Other"].map((v) => ({ value: v, label: v }));
const SOURCE_TYPES = [
  { value: "KR", label: "Karigar Receive" },
  { value: "BC", label: "Barcode" },
  { value: "MAN", label: "Manual" },
];

const blankItem = {
  id: undefined,
  sl_no: 0,
  piece: null,
  barcode: null,
  instructions: "",
  due_date: "",
  remarks: "",
  // display-only (not sent to backend)
  _item_name: "",
  _purity: "",
  _gw: "",
  _pcs: "",
  _design_code: "",
  _barcode_no: "",
  _details: [],
};

function SubItemsTable({ details }) {
  if (!details?.length) return null;
  return (
    <Table className="mt-1 text-xs border">
      <TableHeader>
        <TableRow className="bg-muted/40">
          <TableHead className="py-1 px-2">Packet</TableHead>
          <TableHead className="py-1 px-2">Sub Item</TableHead>
          <TableHead className="py-1 px-2">Description</TableHead>
          <TableHead className="py-1 px-2 text-right">Pcs</TableHead>
          <TableHead className="py-1 px-2 text-right">Ct</TableHead>
          <TableHead className="py-1 px-2 text-right">GW</TableHead>
          <TableHead className="py-1 px-2 text-right">Rate</TableHead>
          <TableHead className="py-1 px-2 text-right">Value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {details.map((d, i) => (
          <TableRow key={i}>
            <TableCell className="py-0.5 px-2">{d.packet}</TableCell>
            <TableCell className="py-0.5 px-2">{d.sub_item}</TableCell>
            <TableCell className="py-0.5 px-2">{d.description}</TableCell>
            <TableCell className="py-0.5 px-2 text-right">{d.pcs}</TableCell>
            <TableCell className="py-0.5 px-2 text-right">{d.ct}</TableCell>
            <TableCell className="py-0.5 px-2 text-right">{d.gw}</TableCell>
            <TableCell className="py-0.5 px-2 text-right">{d.rate}</TableCell>
            <TableCell className="py-0.5 px-2 text-right">{d.amt}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function SampleIssue() {
  const { id } = useParams();
  const { toast } = useToast();
  const navigate = useNavigate();

  // ── header state ──────────────────────────────────────────────────────────
  const [billno, setBillno] = useState("");
  const [date1, setDate1] = useState(new Date().toISOString().split("T")[0]);
  const [karigarId, setKarigarId] = useState(null);
  const [slipType, setSlipType] = useState(null);
  const [remarks, setRemarks] = useState("");
  const [retailId, setRetailId] = useState(null);
  const [fiscalYearId, setFiscalYearId] = useState(null);

  // source reference (header-level)
  const [sourceType, setSourceType] = useState("KR");
  const [sourceBillNo, setSourceBillNo] = useState("");
  const [slipData, setSlipData] = useState(null); // full KR slip data
  const [slipLoading, setSlipLoading] = useState(false);

  // barcode lookup (used when sourceType === "BC")
  const [barcodeInput, setBarcodeInput] = useState("");
  const [barcodeLoading, setBarcodeLoading] = useState(false);

  // karigars dropdown
  const [karigars, setKarigars] = useState([]);

  // items being issued
  const [items, setItems] = useState([{ ...blankItem, sl_no: 1 }]);

  // ── load karigars ─────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      const res = await getLedgers("manufacturer");
      if (res.success) setKarigars(res.data.map((k) => ({ value: k.id, label: k.ac_name })));
    })();
  }, []);

  // ── auto bill-no ──────────────────────────────────────────────────────────
  const fetchBillno = useCallback(async () => {
    if (!retailId || !fiscalYearId) return;
    const res = await fetchSampleIssueNextBillno({ retail: retailId, fiscal_year: fiscalYearId });
    if (res.success && res.data?.next_billno) setBillno(res.data.next_billno);
  }, [retailId, fiscalYearId]);

  useEffect(() => {
    if (!id) fetchBillno();
  }, [id, fetchBillno]);

  // ── load for edit ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return;
    (async () => {
      const res = await fetchSampleIssueForEdit(id);
      if (!res.success) return;
      const d = res.data;
      setBillno(d.billno);
      setDate1(d.date1);
      setKarigarId(d.karigar_ldgr);
      setSlipType(d.slip_type ? { value: d.slip_type, label: d.slip_type } : null);
      setRemarks(d.remarks || "");
      setRetailId(d.retail);
      setFiscalYearId(d.fiscal_year);
      setItems(
        (d.items || []).map((it, i) => ({
          ...blankItem,
          id: it.id,
          sl_no: it.sl_no || i + 1,
          piece: it.piece,
          barcode: it.barcode,
          instructions: it.instructions || "",
          due_date: it.due_date || "",
          remarks: it.remarks || "",
          _item_name: it.item_name || "",
          _purity: it.purity_name || "",
          _gw: it.gw || "",
          _pcs: it.pcs || "",
          _design_code: it.design_code || "",
          _barcode_no: it.barcode_no || "",
        }))
      );
    })();
  }, [id]);

  // ── lookup KR slip ────────────────────────────────────────────────────────
  const lookupSlip = async () => {
    if (!sourceBillNo.trim()) return;
    setSlipLoading(true);
    const res = await fetchKarigarReceiveSlipForSample(sourceBillNo.trim());
    setSlipLoading(false);
    if (!res.success) {
      toast({ title: "Slip not found", description: res.error?.error || "", variant: "destructive" });
      setSlipData(null);
      return;
    }
    setSlipData(res.data);
    // auto-set karigar from slip if not already set
    if (!karigarId && res.data.karigar_ldgr) setKarigarId(res.data.karigar_ldgr);
  };

  const addItemFromSlip = (krItem) => {
    setItems((prev) => [
      ...prev,
      {
        ...blankItem,
        sl_no: prev.length + 1,
        piece: krItem.unbarcoded_item_id,
        _item_name: krItem.item,
        _purity: krItem.purity,
        _gw: krItem.gw,
        _pcs: krItem.pcs,
        _design_code: krItem.design_code,
        _details: krItem.details || [],
      },
    ]);
  };

  // ── lookup barcode ────────────────────────────────────────────────────────
  const lookupBarcode = async () => {
    if (!barcodeInput.trim()) return;
    setBarcodeLoading(true);
    const res = await fetchBarcodeForSample(barcodeInput.trim());
    setBarcodeLoading(false);
    if (!res.success) {
      toast({ title: "Barcode not found", description: res.error?.error || "", variant: "destructive" });
      return;
    }
    const bc = res.data;
    setItems((prev) => [
      ...prev,
      {
        ...blankItem,
        sl_no: prev.length + 1,
        barcode: bc.barcode_id,
        _barcode_no: bc.barcode,
        _item_name: bc.item,
        _purity: bc.purity,
        _gw: bc.gw,
        _pcs: bc.pcs,
        _design_code: bc.design_code,
        _details: bc.details || [],
      },
    ]);
    setBarcodeInput("");
  };

  const addManualItem = () => {
    setItems((prev) => [...prev, { ...blankItem, sl_no: prev.length + 1 }]);
  };

  const removeItem = (idx) => setItems((prev) => prev.filter((_, i) => i !== idx));

  const updateItemField = (idx, field, value) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  };

  // ── submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!karigarId) { toast({ title: "Karigar required", variant: "destructive" }); return; }
    const validItems = items.filter((it) => it.piece || it.barcode || it._item_name);
    if (!validItems.length) { toast({ title: "Add at least one item", variant: "destructive" }); return; }
    const payload = {
      billno,
      date1,
      karigar_ldgr: karigarId,
      retail: retailId,
      fiscal_year: fiscalYearId,
      slip_type: slipType?.value || "",
      remarks,
      items: validItems.map((it, idx) => ({
        id: it.id,
        sl_no: idx + 1,
        piece: it.piece || null,
        barcode: it.barcode || null,
        instructions: it.instructions || "",
        due_date: it.due_date || null,
        remarks: it.remarks || "",
        retail: retailId,
      })),
    };
    const res = id ? await updateSampleIssue(id, payload) : await createSampleIssue(payload);
    if (res.success) {
      toast({ title: id ? "Updated" : "Created" });
      navigate("/manufacturing/issue/sample-issue");
    } else {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 space-y-4 text-sm">
      <h2 className="text-xl font-semibold">Sample Issue to Karigar</h2>

      {/* ── Header ── */}
      <div className="border rounded p-3 grid grid-cols-4 gap-3 bg-muted/20">
        <div>
          <Label>Date</Label>
          <Input type="date" value={date1} onChange={(e) => setDate1(e.target.value)} />
        </div>
        <div>
          <Label>Karigar</Label>
          <Select
            options={karigars}
            value={karigars.find((k) => k.value === karigarId) || null}
            onChange={(opt) => setKarigarId(opt?.value || null)}
            placeholder="Select karigar…"
          />
        </div>
        <div>
          <Label>Issue Slip No</Label>
          <Input value={billno} onChange={(e) => setBillno(e.target.value)} />
        </div>
        <div>
          <Label>Slip Type</Label>
          <Select
            isClearable
            options={SLIP_TYPES}
            value={slipType}
            onChange={setSlipType}
            placeholder="Select type…"
          />
        </div>
        <div className="col-span-2">
          <Label>Remarks</Label>
          <Input value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>
      </div>

      {/* ── Source Reference ── */}
      <div className="border rounded p-3 bg-muted/20 space-y-3">
        <div className="flex items-center gap-3">
          <Label className="w-28 shrink-0">Source</Label>
          <Select
            options={SOURCE_TYPES}
            value={SOURCE_TYPES.find((s) => s.value === sourceType)}
            onChange={(opt) => { setSourceType(opt?.value || "KR"); setSlipData(null); setBarcodeInput(""); }}
            className="w-40"
          />
          {sourceType === "KR" && (
            <>
              <Input
                className="w-64"
                placeholder="Enter Karigar Receive slip no…"
                value={sourceBillNo}
                onChange={(e) => setSourceBillNo(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), lookupSlip())}
              />
              <Button type="button" variant="secondary" onClick={lookupSlip} disabled={slipLoading}>
                <Search size={14} className="mr-1" />
                {slipLoading ? "Loading…" : "Fetch"}
              </Button>
            </>
          )}
          {sourceType === "BC" && (
            <>
              <Input
                className="w-48"
                placeholder="Scan / enter barcode…"
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), lookupBarcode())}
              />
              <Button type="button" variant="secondary" onClick={lookupBarcode} disabled={barcodeLoading}>
                {barcodeLoading ? "Loading…" : "Add"}
              </Button>
            </>
          )}
          {sourceType === "MAN" && (
            <Button type="button" variant="secondary" onClick={addManualItem}>
              + Add Row
            </Button>
          )}
        </div>

        {/* KR slip items list */}
        {sourceType === "KR" && slipData && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium">
              Slip: {slipData.receive_slip_no} &nbsp;·&nbsp; Karigar: {slipData.karigar_name}
            </p>
            <Table className="border text-xs">
              <TableHeader>
                <TableRow className="bg-muted/40">
                  <TableHead className="py-1 px-2">Sl</TableHead>
                  <TableHead className="py-1 px-2">Item</TableHead>
                  <TableHead className="py-1 px-2">Purity</TableHead>
                  <TableHead className="py-1 px-2 text-right">Pcs</TableHead>
                  <TableHead className="py-1 px-2 text-right">GW</TableHead>
                  <TableHead className="py-1 px-2">Design</TableHead>
                  <TableHead className="py-1 px-2"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {slipData.items.map((krItem) => (
                  <TableRow key={krItem.sl_no}>
                    <TableCell className="py-0.5 px-2">{krItem.sl_no}</TableCell>
                    <TableCell className="py-0.5 px-2">{krItem.item}</TableCell>
                    <TableCell className="py-0.5 px-2">{krItem.purity}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{krItem.pcs}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{krItem.gw}</TableCell>
                    <TableCell className="py-0.5 px-2">{krItem.design_code}</TableCell>
                    <TableCell className="py-0.5 px-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => addItemFromSlip(krItem)}
                        disabled={!krItem.unbarcoded_item_id}
                        title={!krItem.unbarcoded_item_id ? "No unbarcoded piece linked to this receive item" : ""}
                      >
                        + Issue
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* ── Items to Issue ── */}
      {items.length > 0 && (
        <div className="border rounded p-3 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Items Being Issued</p>
          {items.map((item, idx) => (
            <div key={idx} className="border rounded p-2 space-y-2 bg-white">
              {/* Item summary row */}
              <div className="grid grid-cols-7 gap-2 items-end">
                <div>
                  <Label className="text-xs">Sl. No.</Label>
                  <Input className="h-7 text-xs" value={item.sl_no} readOnly />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">Item</Label>
                  <Input
                    className="h-7 text-xs"
                    value={item._item_name}
                    onChange={(e) => updateItemField(idx, "_item_name", e.target.value)}
                    placeholder="Item name"
                  />
                </div>
                <div>
                  <Label className="text-xs">Purity</Label>
                  <Input className="h-7 text-xs" value={item._purity} onChange={(e) => updateItemField(idx, "_purity", e.target.value)} />
                </div>
                <div>
                  <Label className="text-xs">Pcs</Label>
                  <Input className="h-7 text-xs" value={item._pcs} onChange={(e) => updateItemField(idx, "_pcs", e.target.value)} />
                </div>
                <div>
                  <Label className="text-xs">GW</Label>
                  <Input className="h-7 text-xs" value={item._gw} onChange={(e) => updateItemField(idx, "_gw", e.target.value)} />
                </div>
                <div className="flex items-end gap-1">
                  {item._barcode_no && (
                    <span className="text-xs text-muted-foreground">{item._barcode_no}</span>
                  )}
                  <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeItem(idx)}>
                    <Trash2 size={13} />
                  </Button>
                </div>
              </div>

              {/* Instructions + Due Date */}
              <div className="grid grid-cols-4 gap-2">
                <div className="col-span-2">
                  <Label className="text-xs">Instructions / Entry Nature</Label>
                  <Input
                    className="h-7 text-xs"
                    value={item.instructions}
                    onChange={(e) => updateItemField(idx, "instructions", e.target.value)}
                    placeholder="Instructions for karigar…"
                  />
                </div>
                <div>
                  <Label className="text-xs">Due Date</Label>
                  <Input
                    type="date"
                    className="h-7 text-xs"
                    value={item.due_date}
                    onChange={(e) => updateItemField(idx, "due_date", e.target.value)}
                  />
                </div>
                <div>
                  <Label className="text-xs">Remarks</Label>
                  <Input
                    className="h-7 text-xs"
                    value={item.remarks}
                    onChange={(e) => updateItemField(idx, "remarks", e.target.value)}
                  />
                </div>
              </div>

              {/* Sub-items breakdown */}
              <SubItemsTable details={item._details} />
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <Button type="submit">{id ? "Update" : "Save"}</Button>
        <Button type="button" variant="ghost" onClick={() => navigate("/manufacturing/issue/sample-issue")}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

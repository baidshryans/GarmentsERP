import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { Trash2, Search, ChevronDown, ChevronRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import Select from "react-select";
import {
  getLedgers,
  createSampleIssue,
  updateSampleIssue,
  fetchSampleIssueForEdit,
  fetchSampleIssueInitialData,
  fetchKarigarReceiveSlipForSample,
  fetchBarcodeForSample,
  fetchPurchaseVoucherForSample,
} from "@/services/apiService";

const SOURCE_TYPES = [
  { value: "KR", label: "Karigar Receive" },
  { value: "PV", label: "Purchase Voucher" },
  { value: "BC", label: "Barcode" },
];

const blankItem = {
  id: undefined,
  sl_no: 1,
  source_type: null,
  piece: null,
  barcode: null,
  kr_receive_item: null,
  pv_item: null,
  item: null,
  purity: null,
  pcs: "",
  gw: "",
  design_code: "",
  size: "",
  huid: "",
  barcode_no: "",
  item_name: "",
  purity_name: "",
  instructions: "",
  due_date: "",
  remarks: "",
  details: [],
  _expanded: false,
};

export default function SampleIssue() {
  const { id } = useParams();
  const { toast } = useToast();
  const navigate = useNavigate();

  // ── header ────────────────────────────────────────────────────────────────
  const [billno, setBillno] = useState("");
  const [date1, setDate1] = useState(new Date().toISOString().split("T")[0]);
  const [karigarOpt, setKarigarOpt] = useState(null);
  const [remarks, setRemarks] = useState("");
  const [retailId, setRetailId] = useState(null);
  const [fiscalYearId, setFiscalYearId] = useState(null);

  // ── source lookup ─────────────────────────────────────────────────────────
  const [sourceType, setSourceType] = useState("KR");
  const [sourceInput, setSourceInput] = useState("");
  const [sourceData, setSourceData] = useState(null);
  const [sourceLoading, setSourceLoading] = useState(false);

  // ── dropdown data ─────────────────────────────────────────────────────────
  const [karigars, setKarigars] = useState([]);

  // ── items table ───────────────────────────────────────────────────────────
  const [items, setItems] = useState([]);

  // ── load karigars (role=KR) ───────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      const res = await getLedgers({ type: "KR", page_size: 500 });
      if (res.success) {
        const list = res.data?.results ?? res.data ?? [];
        setKarigars(list.map((k) => ({ value: k.id, label: k.ac_name })));
      }
    })();
  }, []);

  // ── initial data on mount (new form) ─────────────────────────────────────
  useEffect(() => {
    if (id) return;
    (async () => {
      const res = await fetchSampleIssueInitialData();
      if (res.success) {
        setBillno(res.data.billno);
        setRetailId(res.data.retail);
        setFiscalYearId(res.data.fiscal_year);
      }
    })();
  }, [id]);

  // ── load for edit ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return;
    (async () => {
      const res = await fetchSampleIssueForEdit(id);
      if (!res.success) return;
      const d = res.data;
      setBillno(d.billno);
      setDate1(d.date1);
      setRetailId(d.retail);
      setFiscalYearId(d.fiscal_year);
      setRemarks(d.remarks || "");
      setKarigarOpt(d.karigar_ldgr ? { value: d.karigar_ldgr, label: d.karigar_ldgr_name || "" } : null);
      setItems(
        (d.items || []).map((it) => ({
          ...blankItem,
          id: it.id,
          sl_no: it.sl_no,
          source_type: it.source_type || null,
          piece: it.piece,
          barcode: it.barcode,
          kr_receive_item: it.kr_receive_item,
          pv_item: it.pv_item,
          item: it.item,
          purity: it.purity,
          pcs: it.pcs ?? "",
          gw: it.gw ?? "",
          design_code: it.design_code || "",
          size: it.size || "",
          huid: it.huid || "",
          barcode_no: it.barcode_no || "",
          item_name: it.item_name || "",
          purity_name: it.purity_name || "",
          instructions: it.instructions || "",
          due_date: it.due_date || "",
          remarks: it.remarks || "",
          details: it.details || [],
          _expanded: false,
        }))
      );
    })();
  }, [id]);

  // Resolve karigar label once list loads
  useEffect(() => {
    if (!karigarOpt || karigarOpt.label || !karigars.length) return;
    const match = karigars.find((k) => k.value === karigarOpt.value);
    if (match) setKarigarOpt(match);
  }, [karigars]);

  // ── source fetch ──────────────────────────────────────────────────────────
  const handleFetch = async () => {
    if (!sourceInput.trim()) return;
    setSourceLoading(true);
    setSourceData(null);
    let res;
    if (sourceType === "KR") res = await fetchKarigarReceiveSlipForSample(sourceInput.trim());
    else if (sourceType === "PV") res = await fetchPurchaseVoucherForSample(sourceInput.trim());
    else if (sourceType === "BC") res = await fetchBarcodeForSample(sourceInput.trim());
    setSourceLoading(false);
    if (!res.success) {
      toast({ title: "Not found", description: res.error?.error || "", variant: "destructive" });
      return;
    }
    setSourceData({ type: sourceType, ...res.data });

    // For barcode: add directly
    if (sourceType === "BC") {
      const bc = res.data;
      addItem({
        source_type: "BC",
        barcode: bc.barcode_id,
        barcode_no: bc.barcode,
        item: bc.item_id,
        item_name: bc.item,
        purity: bc.purity_id,
        purity_name: bc.purity,
        pcs: bc.pcs,
        gw: bc.gw,
        design_code: bc.design_code || "",
        size: bc.size || "",
        huid: bc.huid || "",
        details: (bc.details || []).map((d, i) => ({ ...d, sl_no: i + 1 })),
      });
      setSourceInput("");
      setSourceData(null);
    }

    // Auto-set karigar from KR slip
    if (sourceType === "KR" && res.data.karigar_ldgr && !karigarOpt) {
      const match = karigars.find((k) => k.value === res.data.karigar_ldgr);
      if (match) setKarigarOpt(match);
    }
  };

  const addItem = (fields) => {
    setItems((prev) => [
      ...prev,
      { ...blankItem, ...fields, sl_no: prev.length + 1 },
    ]);
  };

  const addFromKR = (krItem) => {
    addItem({
      source_type: "KR",
      piece: krItem.unbarcoded_item_id,
      kr_receive_item: krItem.receive_item_id,
      item: krItem.item_id,
      item_name: krItem.item,
      purity: krItem.purity_id,
      purity_name: krItem.purity,
      pcs: krItem.pcs,
      gw: krItem.gw,
      design_code: krItem.design_code || "",
      size: krItem.size || "",
      huid: krItem.huid || "",
      details: (krItem.details || []).map((d, i) => ({ ...d, sl_no: i + 1 })),
    });
  };

  const addFromPV = (pvItem) => {
    addItem({
      source_type: "PV",
      barcode: pvItem.barcode_id || null,
      pv_item: pvItem.pv_item_id,
      barcode_no: pvItem.barcode_no || "",
      item: pvItem.item_id,
      item_name: pvItem.item,
      purity: pvItem.purity_id,
      purity_name: pvItem.purity,
      pcs: pvItem.pcs,
      gw: pvItem.gw,
      size: pvItem.size || "",
      details: (pvItem.details || []).map((d, i) => ({ ...d, sl_no: i + 1 })),
    });
  };

  const removeItem = (idx) => setItems((prev) => prev.filter((_, i) => i !== idx).map((it, i) => ({ ...it, sl_no: i + 1 })));

  const updateField = (idx, field, value) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  };

  const toggleExpand = (idx) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, _expanded: !it._expanded } : it)));
  };

  // ── submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!karigarOpt) { toast({ title: "Karigar required", variant: "destructive" }); return; }
    if (!items.length) { toast({ title: "Add at least one item", variant: "destructive" }); return; }
    const payload = {
      billno, date1,
      karigar_ldgr: karigarOpt.value,
      retail: retailId,
      fiscal_year: fiscalYearId,
      remarks,
      items: items.map((it, idx) => ({
        id: it.id,
        sl_no: idx + 1,
        source_type: it.source_type || null,
        piece: it.piece || null,
        barcode: it.barcode || null,
        kr_receive_item: it.kr_receive_item || null,
        pv_item: it.pv_item || null,
        item: it.item || null,
        purity: it.purity || null,
        pcs: it.pcs !== "" ? Number(it.pcs) : null,
        gw: it.gw !== "" ? Number(it.gw) : null,
        design_code: it.design_code || "",
        size: it.size || "",
        huid: it.huid || "",
        instructions: it.instructions || "",
        due_date: it.due_date || null,
        remarks: it.remarks || "",
        retail: retailId,
        details: (it.details || []).map((d, di) => ({
          id: d.id,
          sl_no: di + 1,
          sub_item: d.sub_item || null,
          packet: d.packet || null,
          pcs: d.pcs || 0,
          ct: d.ct || 0,
          gw: d.gw || 0,
          rate: d.rate || 0,
          value: d.value || 0,
        })),
      })),
    };
    const res = id ? await updateSampleIssue(id, payload) : await createSampleIssue(payload);
    if (res.success) {
      toast({ title: id ? "Updated" : "Saved" });
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
            value={karigarOpt}
            onChange={setKarigarOpt}
            isSearchable
            placeholder="Select karigar…"
          />
        </div>
        <div>
          <Label>Issue Slip No</Label>
          <Input value={billno} onChange={(e) => setBillno(e.target.value)} />
        </div>
        <div className="col-span-1">
          <Label>Remarks</Label>
          <Input value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>
      </div>

      {/* ── Source Lookup ── */}
      <div className="border rounded p-3 bg-muted/20 space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Label className="w-16 shrink-0">Source</Label>
          <Select
            options={SOURCE_TYPES}
            value={SOURCE_TYPES.find((s) => s.value === sourceType)}
            onChange={(opt) => { setSourceType(opt.value); setSourceData(null); setSourceInput(""); }}
            isSearchable={false}
            className="w-48"
          />
          <Input
            className="w-64"
            placeholder={
              sourceType === "KR" ? "Karigar Receive slip no…"
              : sourceType === "PV" ? "Purchase Voucher bill no…"
              : "Scan / enter barcode…"
            }
            value={sourceInput}
            onChange={(e) => setSourceInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleFetch())}
          />
          <Button type="button" variant="secondary" onClick={handleFetch} disabled={sourceLoading}>
            <Search size={14} className="mr-1" />
            {sourceLoading ? "Loading…" : sourceType === "BC" ? "Add" : "Fetch"}
          </Button>
        </div>

        {/* KR items */}
        {sourceData?.type === "KR" && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">
              Slip: <strong>{sourceData.receive_slip_no}</strong> · Karigar: {sourceData.karigar_name}
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
                {sourceData.items.map((kr) => (
                  <TableRow key={kr.sl_no}>
                    <TableCell className="py-0.5 px-2">{kr.sl_no}</TableCell>
                    <TableCell className="py-0.5 px-2">{kr.item}</TableCell>
                    <TableCell className="py-0.5 px-2">{kr.purity}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{kr.pcs}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{kr.gw}</TableCell>
                    <TableCell className="py-0.5 px-2">{kr.design_code}</TableCell>
                    <TableCell className="py-0.5 px-2">
                      <Button
                        type="button" size="sm" variant="outline"
                        onClick={() => addFromKR(kr)}
                        disabled={!kr.unbarcoded_item_id}
                        title={!kr.unbarcoded_item_id ? "No unbarcoded piece linked" : ""}
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

        {/* PV items */}
        {sourceData?.type === "PV" && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">
              Voucher: <strong>{sourceData.billno}</strong> · Party: {sourceData.ldgr_name}
            </p>
            <Table className="border text-xs">
              <TableHeader>
                <TableRow className="bg-muted/40">
                  <TableHead className="py-1 px-2">Sl</TableHead>
                  <TableHead className="py-1 px-2">Item</TableHead>
                  <TableHead className="py-1 px-2">Purity</TableHead>
                  <TableHead className="py-1 px-2 text-right">Pcs</TableHead>
                  <TableHead className="py-1 px-2 text-right">GW</TableHead>
                  <TableHead className="py-1 px-2">Barcode</TableHead>
                  <TableHead className="py-1 px-2"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sourceData.items.map((pv) => (
                  <TableRow key={pv.sl_no}>
                    <TableCell className="py-0.5 px-2">{pv.sl_no}</TableCell>
                    <TableCell className="py-0.5 px-2">{pv.item}</TableCell>
                    <TableCell className="py-0.5 px-2">{pv.purity}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{pv.pcs}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{pv.gw}</TableCell>
                    <TableCell className="py-0.5 px-2">{pv.barcode_no}</TableCell>
                    <TableCell className="py-0.5 px-2">
                      <Button type="button" size="sm" variant="outline" onClick={() => addFromPV(pv)}>
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

      {/* ── Items Being Issued ── */}
      {items.length > 0 && (
        <div className="border rounded overflow-hidden">
          <Table className="text-xs">
            <TableHeader>
              <TableRow className="bg-muted/40">
                <TableHead className="py-1 px-2 w-6"></TableHead>
                <TableHead className="py-1 px-2">Sl</TableHead>
                <TableHead className="py-1 px-2">Src</TableHead>
                <TableHead className="py-1 px-2">Item</TableHead>
                <TableHead className="py-1 px-2">Purity</TableHead>
                <TableHead className="py-1 px-2 text-right">Pcs</TableHead>
                <TableHead className="py-1 px-2 text-right">GW</TableHead>
                <TableHead className="py-1 px-2">Design</TableHead>
                <TableHead className="py-1 px-2">Instructions</TableHead>
                <TableHead className="py-1 px-2">Due Date</TableHead>
                <TableHead className="py-1 px-2">Remarks</TableHead>
                <TableHead className="py-1 px-2 w-8"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item, idx) => (
                <React.Fragment key={idx}>
                  <TableRow className={idx % 2 === 0 ? "bg-white" : "bg-muted/10"}>
                    {/* expand toggle */}
                    <TableCell className="py-0.5 px-1">
                      {item.details?.length > 0 && (
                        <button type="button" onClick={() => toggleExpand(idx)} className="text-muted-foreground hover:text-foreground">
                          {item._expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        </button>
                      )}
                    </TableCell>
                    <TableCell className="py-0.5 px-2">{item.sl_no}</TableCell>
                    <TableCell className="py-0.5 px-2 text-muted-foreground">{item.source_type}</TableCell>
                    <TableCell className="py-0.5 px-2">{item.item_name}</TableCell>
                    <TableCell className="py-0.5 px-2">{item.purity_name}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">
                      <Input className="h-6 w-16 text-xs text-right p-1" value={item.pcs} onChange={(e) => updateField(idx, "pcs", e.target.value)} />
                    </TableCell>
                    <TableCell className="py-0.5 px-2 text-right">
                      <Input className="h-6 w-20 text-xs text-right p-1" value={item.gw} onChange={(e) => updateField(idx, "gw", e.target.value)} />
                    </TableCell>
                    <TableCell className="py-0.5 px-2">{item.design_code || item.barcode_no}</TableCell>
                    <TableCell className="py-0.5 px-2">
                      <Input className="h-6 text-xs p-1" value={item.instructions} onChange={(e) => updateField(idx, "instructions", e.target.value)} placeholder="Instructions…" />
                    </TableCell>
                    <TableCell className="py-0.5 px-2">
                      <Input type="date" className="h-6 text-xs p-1 w-32" value={item.due_date} onChange={(e) => updateField(idx, "due_date", e.target.value)} />
                    </TableCell>
                    <TableCell className="py-0.5 px-2">
                      <Input className="h-6 text-xs p-1" value={item.remarks} onChange={(e) => updateField(idx, "remarks", e.target.value)} />
                    </TableCell>
                    <TableCell className="py-0.5 px-1">
                      <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={() => removeItem(idx)}>
                        <Trash2 size={12} />
                      </Button>
                    </TableCell>
                  </TableRow>

                  {/* Sub-item details */}
                  {item._expanded && item.details?.length > 0 && (
                    <TableRow>
                      <TableCell colSpan={12} className="py-1 px-4 bg-blue-50/50">
                        <Table className="text-xs border">
                          <TableHeader>
                            <TableRow className="bg-blue-100/40">
                              <TableHead className="py-0.5 px-2">Packet</TableHead>
                              <TableHead className="py-0.5 px-2">Sub Item</TableHead>
                              <TableHead className="py-0.5 px-2 text-right">Pcs</TableHead>
                              <TableHead className="py-0.5 px-2 text-right">Ct</TableHead>
                              <TableHead className="py-0.5 px-2 text-right">GW</TableHead>
                              <TableHead className="py-0.5 px-2 text-right">Rate</TableHead>
                              <TableHead className="py-0.5 px-2 text-right">Value</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {item.details.map((d, di) => (
                              <TableRow key={di}>
                                <TableCell className="py-0.5 px-2">{d.packet_code || d.packet}</TableCell>
                                <TableCell className="py-0.5 px-2">{d.sub_item_name || d.sub_item}</TableCell>
                                <TableCell className="py-0.5 px-2 text-right">{d.pcs}</TableCell>
                                <TableCell className="py-0.5 px-2 text-right">{d.ct}</TableCell>
                                <TableCell className="py-0.5 px-2 text-right">{d.gw}</TableCell>
                                <TableCell className="py-0.5 px-2 text-right">{d.rate}</TableCell>
                                <TableCell className="py-0.5 px-2 text-right">{d.value ?? d.amt}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {items.length === 0 && (
        <p className="text-xs text-muted-foreground border rounded p-4 text-center">
          Fetch a Karigar Receive slip, Purchase Voucher, or scan a barcode above to add items.
        </p>
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

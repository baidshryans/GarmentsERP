import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { Label } from "@/components/ui/label";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { Trash2, Download, PackageSearch, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import {
  getLedgers,
  createSampleIssue,
  updateSampleIssue,
  fetchSampleIssueForEdit,
  fetchSampleIssueInitialData,
  fetchKarigarReceiveSlipForSample,
  fetchKarigarReceiveSlipsForSample,
  fetchBarcodeForSample,
  fetchPurchaseVoucherForSample,
  fetchPurchaseVouchersForSample,
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
  remarks: "",
  details: [],
  _expanded: false,
};

export default function SampleIssue() {
  const { id } = useParams();
  const { toast } = useToast();
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();
  const navigate = useNavigate();

  // ── header ────────────────────────────────────────────────────────────────
  const [billno, setBillno] = useState("");
  const [date1, setDate1] = useState(new Date().toISOString().split("T")[0]);
  const [karigarId, setKarigarId] = useState(null);
  const [karigarName, setKarigarName] = useState("");
  const [remarks, setRemarks] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [retailId, setRetailId] = useState(null);
  const [fiscalYearId, setFiscalYearId] = useState(null);

  // ── source lookup ─────────────────────────────────────────────────────────
  const [sourceType, setSourceType] = useState("KR");
  const [sourceInput, setSourceInput] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [pendingSelection, setPendingSelection] = useState(null); // { type, label, candidates: [{checked, payload}] }

  // ── dropdown data ─────────────────────────────────────────────────────────
  const [karigars, setKarigars] = useState([]);
  const [krSlips, setKrSlips] = useState([]);
  const [pvBills, setPvBills] = useState([]);

  // ── items table ───────────────────────────────────────────────────────────
  const [items, setItems] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  // ── totals (memo-lite) ────────────────────────────────────────────────────
  const totals = items.reduce(
    (acc, it) => {
      acc.pcs += Number(it.pcs) || 0;
      acc.gw += Number(it.gw) || 0;
      (it.details || []).forEach((d) => {
        acc.subPcs += Number(d.pcs) || 0;
        acc.subCt += Number(d.ct) || 0;
        acc.subGw += Number(d.gw) || 0;
        acc.subValue += Number(d.value ?? d.amt) || 0;
      });
      return acc;
    },
    { pcs: 0, gw: 0, subPcs: 0, subCt: 0, subGw: 0, subValue: 0 }
  );

  // ── load karigars (role=KR) ───────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      const res = await getLedgers({ type: "KR,VD", page_size: 10000 });
      if (res.success) setKarigars(res.data?.results ?? res.data ?? []);
    })();
  }, []);

  // ── pre-load recent KR slips & PV bills for combo-box pickers ────────────
  useEffect(() => {
    (async () => {
      const [kr, pv] = await Promise.all([
        fetchKarigarReceiveSlipsForSample(""),
        fetchPurchaseVouchersForSample(""),
      ]);
      if (kr.success) setKrSlips(kr.data || []);
      if (pv.success) setPvBills(pv.data || []);
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
      setDueDate(d.due_date || "");
      setKarigarId(d.karigar_ldgr || null);
      setKarigarName(d.karigar_ldgr_name || "");
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
          remarks: it.remarks || "",
          details: it.details || [],
          _expanded: false,
        }))
      );
    })();
  }, [id]);

  // Resolve karigar name once list loads (edit mode)
  useEffect(() => {
    if (!karigarId || karigarName || !karigars.length) return;
    const match = karigars.find((k) => k.id === karigarId);
    if (match) setKarigarName(match.ac_name);
  }, [karigars, karigarId, karigarName]);

  // ── source fetch ──────────────────────────────────────────────────────────
  const handleFetch = async () => {
    if (!sourceInput.trim()) return;
    setSourceLoading(true);
    let res;
    if (sourceType === "KR") res = await fetchKarigarReceiveSlipForSample(sourceInput.trim());
    else if (sourceType === "PV") res = await fetchPurchaseVoucherForSample(sourceInput.trim());
    else if (sourceType === "BC") res = await fetchBarcodeForSample(sourceInput.trim());
    setSourceLoading(false);
    if (!res.success) {
      toast({ title: "Not found", description: res.error?.error || "", variant: "destructive" });
      return;
    }

    if (sourceType === "BC") {
      const bc = res.data;
      if (items.some((it) => it.barcode && it.barcode === bc.barcode_id)) {
        toast({ title: "Already added", description: `Barcode ${bc.barcode} is already in the list`, variant: "destructive" });
        setSourceInput("");
        return;
      }
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
      return;
    }

    if (sourceType === "KR") {
      const slipNo = res.data.receive_slip_no;
      const candidates = (res.data.items || []).map((kr) => {
        const alreadyAdded = items.some((it) => it.kr_receive_item === kr.receive_item_id);
        const noPiece = !kr.unbarcoded_item_id;
        return {
          key: `kr-${kr.receive_item_id || kr.sl_no}`,
          checked: !alreadyAdded && !noPiece,
          disabled: alreadyAdded || noPiece,
          disabledReason: alreadyAdded ? "Already added" : noPiece ? "No unbarcoded piece" : "",
          display: { sl_no: kr.sl_no, item: kr.item, purity: kr.purity, pcs: kr.pcs, gw: kr.gw, design_code: kr.design_code || "" },
          payload: {
            source_type: "KR",
            piece: kr.unbarcoded_item_id,
            kr_receive_item: kr.receive_item_id,
            item: kr.item_id,
            item_name: kr.item,
            purity: kr.purity_id,
            purity_name: kr.purity,
            pcs: kr.pcs,
            gw: kr.gw,
            design_code: kr.design_code || "",
            size: kr.size || "",
            huid: kr.huid || "",
            _slip_no: slipNo,
            details: (kr.details || []).map((d, i) => ({ ...d, sl_no: i + 1 })),
          },
        };
      });
      if (res.data.karigar_ldgr && !karigarId) {
        const match = karigars.find((k) => k.id === res.data.karigar_ldgr);
        if (match) { setKarigarId(match.id); setKarigarName(match.ac_name); }
      }
      handleCandidates({ type: "KR", label: `Karigar Receive ${slipNo}`, candidates });
      return;
    }

    if (sourceType === "PV") {
      const billno = res.data.billno;
      const candidates = (res.data.items || []).map((pv) => {
        const alreadyAdded = items.some((it) => it.pv_item === pv.pv_item_id);
        return {
          key: `pv-${pv.pv_item_id || pv.sl_no}`,
          checked: !alreadyAdded,
          disabled: alreadyAdded,
          disabledReason: alreadyAdded ? "Already added" : "",
          display: { sl_no: pv.sl_no, item: pv.item, purity: pv.purity, pcs: pv.pcs, gw: pv.gw, design_code: pv.barcode_no || "" },
          payload: {
            source_type: "PV",
            barcode: pv.barcode_id || null,
            pv_item: pv.pv_item_id,
            barcode_no: pv.barcode_no || "",
            item: pv.item_id,
            item_name: pv.item,
            purity: pv.purity_id,
            purity_name: pv.purity,
            pcs: pv.pcs,
            gw: pv.gw,
            size: pv.size || "",
            _billno: billno,
            details: (pv.details || []).map((d, i) => ({ ...d, sl_no: i + 1 })),
          },
        };
      });
      handleCandidates({ type: "PV", label: `Purchase Voucher ${billno}`, candidates });
    }
  };

  const handleCandidates = ({ type, label, candidates }) => {
    const selectable = candidates.filter((c) => !c.disabled);
    if (!selectable.length) {
      toast({ title: "Nothing to add", description: `All items from ${label} are already added or unavailable.`, variant: "destructive" });
      setSourceInput("");
      return;
    }
    if (selectable.length === 1 && candidates.length === 1) {
      addItems([selectable[0].payload]);
      setSourceInput("");
      return;
    }
    setPendingSelection({ type, label, candidates });
  };

  const togglePendingCandidate = (key) => {
    setPendingSelection((prev) => prev && {
      ...prev,
      candidates: prev.candidates.map((c) => c.key === key && !c.disabled ? { ...c, checked: !c.checked } : c),
    });
  };

  const confirmPendingSelection = () => {
    if (!pendingSelection) return;
    const picked = pendingSelection.candidates.filter((c) => c.checked && !c.disabled).map((c) => c.payload);
    if (!picked.length) {
      toast({ title: "Select at least one item", variant: "destructive" });
      return;
    }
    addItems(picked);
    setPendingSelection(null);
    setSourceInput("");
  };

  const addItem = (fields) => {
    setItems((prev) => [
      ...prev,
      { ...blankItem, ...fields, sl_no: prev.length + 1 },
    ]);
  };

  const addItems = (newFieldsList) => {
    setItems((prev) => [
      ...prev,
      ...newFieldsList.map((fields, i) => ({
        ...blankItem,
        ...fields,
        sl_no: prev.length + i + 1,
      })),
    ]);
  };

  const removeItem = (idx) => setItems((prev) => prev.filter((_, i) => i !== idx).map((it, i) => ({ ...it, sl_no: i + 1 })));

  const updateField = (idx, field, value) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  };

  // ── submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!karigarId) { toast({ title: "Karigar required", variant: "destructive" }); return; }
    if (!items.length) { toast({ title: "Add at least one item", variant: "destructive" }); return; }
    const payload = {
      billno, date1,
      karigar_ldgr: karigarId,
      retail: retailId,
      fiscal_year: fiscalYearId,
      remarks,
      due_date: dueDate || null,
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
        remarks: it.remarks || "",
        retail: retailId,
        details: (it.details || []).map((d, di) => ({
          id: d.id,
          sl_no: di + 1,
          // sub_item: PK from picker (sub_item_id); packet: pckt_no slug
          sub_item: d.sub_item_id ?? null,
          packet: d.packet || null,
          pcs: d.pcs || 0,
          ct: d.ct || 0,
          gw: d.gw || 0,
          rate: d.rate || 0,
          value: d.value || 0,
        })),
      })),
    };
    setSubmitting(true);
    try {
      const res = id ? await updateSampleIssue(id, payload) : await createSampleIssue(payload);
      if (res.success) {
        toast({ title: id ? "Updated" : "Saved" });
        navigate("/manufacturing/issue/sample-issue");
      } else {
        toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 space-y-4 text-sm">
      <h2 className="text-xl font-semibold">Sample Issue to Karigar</h2>

      {/* ── Header ── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-4 py-2 bg-accent-50 border-b border-accent-100 rounded-t-lg text-sm font-medium text-primary">
          Issue Details
        </div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="si-date">Date</Label>
            <Input id="si-date" type="date" min={fyMin} max={fyMax} value={date1} onChange={(e) => setDate1(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="si-slipno">Issue Slip No</Label>
            <div id="si-slipno" className="flex items-center gap-2">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-accent-50 border border-accent-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                {billno || <span className="text-accent-400 text-xs font-normal">Auto-generating…</span>}
              </span>
            </div>
          </div>
          <div>
            <Label htmlFor="si-due">Due Date</Label>
            <Input id="si-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="si-karigar">Karigar <span className="text-red-500">*</span></Label>
            <SearchableComboBox
              options={karigars}
              value={karigarName}
              onSelect={(opt) => { setKarigarId(opt.id); setKarigarName(opt.ac_name); }}
              placeholder="Search vendor / karigar…"
            />
          </div>
          <div>
            <Label htmlFor="si-remarks">Remarks</Label>
            <Input id="si-remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Optional notes…" />
          </div>
        </div>
      </div>

      {/* ── Source Lookup ── */}
      <div className="rounded-lg border bg-card shadow-sm p-4 space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Label htmlFor="si-source" className="w-16 shrink-0">Source</Label>
          <Select value={sourceType} onValueChange={(v) => { setSourceType(v); setSourceInput(""); }}>
            <SelectTrigger id="si-source" className="w-48">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              {SOURCE_TYPES.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {sourceType === "KR" ? (
            <div className="w-72">
              <SearchableComboBox
                options={krSlips.map((s) => ({
                  ...s,
                  _label: `${s.receive_slip_no} · ${s.karigar_ldgr_name}${s.date1 ? ` · ${s.date1}` : ""}`,
                }))}
                labelKey="_label"
                value={sourceInput}
                onSelect={(opt) => setSourceInput(opt.receive_slip_no)}
                onInputChange={(v) => setSourceInput(v)}
                placeholder="Pick or type slip no… (suffix ok)"
              />
            </div>
          ) : sourceType === "PV" ? (
            <div className="w-72">
              <SearchableComboBox
                options={pvBills.map((p) => ({
                  ...p,
                  _label: `${p.billno} · ${p.ldgr_name}${p.date1 ? ` · ${p.date1}` : ""}`,
                }))}
                labelKey="_label"
                value={sourceInput}
                onSelect={(opt) => setSourceInput(opt.billno)}
                onInputChange={(v) => setSourceInput(v)}
                placeholder="Pick or type bill no… (suffix ok)"
              />
            </div>
          ) : (
            <Input
              className="w-64"
              placeholder="Scan / enter barcode…"
              value={sourceInput}
              onChange={(e) => setSourceInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleFetch())}
            />
          )}
          <Button type="button" variant="secondary" onClick={handleFetch} disabled={sourceLoading}>
            <Download size={14} className="mr-1" />
            {sourceLoading ? "Loading…" : "Fetch"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Items from the slip/voucher/barcode are added directly to the table below. Use the trash icon to remove any you don't want to issue.
        </p>

        {pendingSelection && (
          <div className="border rounded p-3 bg-accent-50/40">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium">
                Select items from <span className="text-primary">{pendingSelection.label}</span>
              </p>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="ghost" onClick={() => setPendingSelection(null)}>Cancel</Button>
                <Button type="button" size="sm" onClick={confirmPendingSelection}>Add Selected</Button>
              </div>
            </div>
            <Table className="border text-xs bg-white">
              <TableHeader>
                <TableRow className="bg-accent-100/60">
                  <TableHead className="py-1 px-2 w-8"></TableHead>
                  <TableHead className="py-1 px-2">Sl</TableHead>
                  <TableHead className="py-1 px-2">Item</TableHead>
                  <TableHead className="py-1 px-2">Purity</TableHead>
                  <TableHead className="py-1 px-2 text-right">Pcs</TableHead>
                  <TableHead className="py-1 px-2 text-right">GW</TableHead>
                  <TableHead className="py-1 px-2">{pendingSelection.type === "PV" ? "Barcode" : "Design"}</TableHead>
                  <TableHead className="py-1 px-2"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingSelection.candidates.map((c) => (
                  <TableRow key={c.key} className={c.disabled ? "opacity-50" : ""}>
                    <TableCell className="py-0.5 px-2">
                      <input
                        type="checkbox"
                        checked={c.checked}
                        disabled={c.disabled}
                        onChange={() => togglePendingCandidate(c.key)}
                      />
                    </TableCell>
                    <TableCell className="py-0.5 px-2">{c.display.sl_no}</TableCell>
                    <TableCell className="py-0.5 px-2">{c.display.item}</TableCell>
                    <TableCell className="py-0.5 px-2">{c.display.purity}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">{c.display.pcs}</TableCell>
                    <TableCell className="py-0.5 px-2 text-right">
                      {c.display.gw != null && c.display.gw !== "" ? Number(c.display.gw).toFixed(3) : ""}
                    </TableCell>
                    <TableCell className="py-0.5 px-2">{c.display.design_code}</TableCell>
                    <TableCell className="py-0.5 px-2 text-xs text-muted-foreground">{c.disabledReason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* ── Items Being Issued ── */}
      {items.length > 0 && (
        <div className="rounded-lg border bg-card shadow-sm overflow-hidden">
          <div className="px-4 py-2 bg-accent-50 border-b border-accent-100 text-sm font-medium text-primary flex items-center justify-between">
            <span>Items to Issue</span>
            <span className="text-xs text-muted-foreground font-normal">{items.length} item{items.length === 1 ? "" : "s"}</span>
          </div>
          <div className="overflow-auto max-h-[60vh]">
            <Table className="text-sm tabular-nums">
              <TableHeader className="sticky top-0 z-10">
                <TableRow className="bg-accent-100/80">
                  <TableHead className="py-2 px-3 w-10"></TableHead>
                  <TableHead className="py-2 px-3">Sl</TableHead>
                  <TableHead className="py-2 px-3">Src</TableHead>
                  <TableHead className="py-2 px-3">Packet</TableHead>
                  <TableHead className="py-2 px-3">Sub Item</TableHead>
                  <TableHead className="py-2 px-3">Item</TableHead>
                  <TableHead className="py-2 px-3">Purity</TableHead>
                  <TableHead className="py-2 px-3">Design / Barcode</TableHead>
                  <TableHead className="py-2 px-3 text-right">Pcs</TableHead>
                  <TableHead className="py-2 px-3 text-right">Ct</TableHead>
                  <TableHead className="py-2 px-3 text-right">GW</TableHead>
                  <TableHead className="py-2 px-3 text-right">Rate</TableHead>
                  <TableHead className="py-2 px-3 text-right">Value</TableHead>
                  <TableHead className="py-2 px-3">Remarks</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item, idx) => (
                  <React.Fragment key={idx}>
                    <TableRow className="bg-white border-t-2 border-accent-200/70 hover:bg-accent-50/30 font-semibold">
                      <TableCell className="py-1.5 px-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Remove item"
                          className="h-6 w-6 text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={() => removeItem(idx)}
                        >
                          <Trash2 size={12} />
                        </Button>
                      </TableCell>
                      <TableCell className="py-1.5 px-3">{item.sl_no}</TableCell>
                      <TableCell className="py-1.5 px-3 text-muted-foreground font-normal">{item.source_type}</TableCell>
                      <TableCell className="py-1.5 px-3"></TableCell>
                      <TableCell className="py-1.5 px-3"></TableCell>
                      <TableCell className="py-1.5 px-3">{item.item_name}</TableCell>
                      <TableCell className="py-1.5 px-3">{item.purity_name}</TableCell>
                      <TableCell className="py-1.5 px-3 font-mono text-sm">{item.design_code || item.barcode_no}</TableCell>
                      <TableCell className="py-1.5 px-3 text-right tabular-nums">{item.pcs}</TableCell>
                      <TableCell className="py-1.5 px-3"></TableCell>
                      <TableCell className="py-1.5 px-3 text-right tabular-nums">
                        {item.gw != null && item.gw !== "" ? Number(item.gw).toFixed(3) : ""}
                      </TableCell>
                      <TableCell className="py-1.5 px-3"></TableCell>
                      <TableCell className="py-1.5 px-3"></TableCell>
                      <TableCell className="py-1.5 px-3 font-normal">
                        <Input className="h-7 text-sm p-1" value={item.remarks} onChange={(e) => updateField(idx, "remarks", e.target.value)} />
                      </TableCell>
                    </TableRow>
                    {(item.details || []).map((d, di) => (
                      <TableRow key={`${idx}-d-${di}`} className="bg-accent-50/20 text-muted-foreground border-l-4 border-accent-300">
                        <TableCell className="py-1.5 px-2"></TableCell>
                        <TableCell className="py-1.5 px-3"></TableCell>
                        <TableCell className="py-1.5 px-3"></TableCell>
                        <TableCell className="py-1.5 px-3">{d.packet_code || d.packet}</TableCell>
                        <TableCell className="py-1.5 px-3">{d.sub_item_name || d.sub_item}</TableCell>
                        <TableCell className="py-1.5 px-3"></TableCell>
                        <TableCell className="py-1.5 px-3"></TableCell>
                        <TableCell className="py-1.5 px-3"></TableCell>
                        <TableCell className="py-1.5 px-3 text-right">{d.pcs}</TableCell>
                        <TableCell className="py-1.5 px-3 text-right">{d.ct != null && d.ct !== "" ? Number(d.ct).toFixed(3) : ""}</TableCell>
                        <TableCell className="py-1.5 px-3 text-right">{d.gw != null && d.gw !== "" ? Number(d.gw).toFixed(3) : ""}</TableCell>
                        <TableCell className="py-1.5 px-3 text-right">{d.rate}</TableCell>
                        <TableCell className="py-1.5 px-3 text-right">{d.value ?? d.amt}</TableCell>
                        <TableCell className="py-1.5 px-3"></TableCell>
                      </TableRow>
                    ))}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
          {/* Totals strip */}
          <div className="px-4 py-2 bg-accent-50/60 border-t border-accent-100 text-xs flex flex-wrap items-center gap-x-6 gap-y-1 tabular-nums">
            <span className="text-muted-foreground">Totals:</span>
            <span><span className="text-muted-foreground">Pcs</span> <strong>{totals.pcs}</strong></span>
            <span><span className="text-muted-foreground">GW</span> <strong>{totals.gw.toFixed(3)}</strong></span>
            {totals.subPcs > 0 && (
              <>
                <span className="text-muted-foreground">·</span>
                <span><span className="text-muted-foreground">Sub Pcs</span> <strong>{totals.subPcs}</strong></span>
                <span><span className="text-muted-foreground">Sub Ct</span> <strong>{totals.subCt.toFixed(3)}</strong></span>
                <span><span className="text-muted-foreground">Sub GW</span> <strong>{totals.subGw.toFixed(3)}</strong></span>
                <span><span className="text-muted-foreground">Value</span> <strong>{totals.subValue.toFixed(2)}</strong></span>
              </>
            )}
          </div>
        </div>
      )}

      {items.length === 0 && (
        <div className="rounded-lg border border-dashed bg-muted/10 p-10 text-center text-muted-foreground space-y-2">
          <PackageSearch className="mx-auto opacity-50" size={36} />
          <p className="text-sm font-medium">No items added yet</p>
          <p className="text-xs">Fetch a Karigar Receive slip, Purchase Voucher, or scan a barcode above to add items.</p>
        </div>
      )}

      <div className="flex justify-end gap-2 pt-4 border-t">
        <Button type="submit" disabled={submitting}>
          {submitting && <Loader2 size={14} className="mr-1 animate-spin" />}
          {id ? "Update" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => navigate("/manufacturing/issue/sample-issue")}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

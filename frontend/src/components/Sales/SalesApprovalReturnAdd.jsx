// frontend/src/components/Sales/SalesApprovalReturnAdd.jsx
import React, { useEffect, useState, useRef } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { renderErrorTree } from "../../Utils";
import { useParams, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Trash2, Plus } from "lucide-react";
import {
  Table,
  TableRow,
  TableCell,
  TableBody,
  TableHead,
  TableHeader,
} from "@/components/ui/table";
import {
  fetchNextSARNo,
  fetchSalesApprovalReturnById,
  createSalesApprovalReturn,
  updateSalesApprovalReturn,
  fetchSalesApproval,
  fetchSalesApprovalById,
  fetchBarcodeForReturn,
  fetchPackets,
  fetchMainItem,
} from "@/services/apiService";

const SalesApprovalReturnAdd = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const { register, handleSubmit, control, setValue, getValues, watch } = useForm({
    defaultValues: {
      date1: new Date().toISOString().split("T")[0],
      billno: "",
      ref_approval: null,
      narration: "",
      items: [],
      _barcode: "",
      _refSearch: "",
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "items" });

  const [saving, setSaving] = useState(false);
  const [packets, setPackets] = useState([]);
  const [mainItems, setMainItems] = useState([]);
  const [approvalResults, setApprovalResults] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [expandedRows, setExpandedRows] = useState({});
  const refSearchDebounce = useRef(null);

  /* ── Initial data load ── */
  useEffect(() => {
    async function init() {
      const [packetsRes, mainItemRes, billNoRes] = await Promise.all([
        fetchPackets(),
        fetchMainItem(),
        id ? Promise.resolve({ success: false }) : fetchNextSARNo(),
      ]);
      if (packetsRes.success) setPackets(packetsRes.data.results ?? packetsRes.data);
      if (mainItemRes.success) setMainItems(mainItemRes.data.results ?? mainItemRes.data);
      if (billNoRes.success) setValue("billno", billNoRes.data.billno);

      if (id) {
        const res = await fetchSalesApprovalReturnById(id);
        if (res.success) {
          const d = res.data;
          setValue("date1", d.date1);
          setValue("billno", d.billno);
          setValue("ref_approval", d.ref_approval ?? null);
          setValue("narration", d.narration ?? "");
          (d.items || []).forEach((item) =>
            append({
              ...item,
              main_item_set: (item.main_item_set || []).map((sub) => ({
                ...sub,
                _sid: sub.id ?? crypto.randomUUID(),
              })),
            })
          );
          // Restore approval preview if ref is set
          if (d.ref_approval) {
            const aRes = await fetchSalesApprovalById(d.ref_approval);
            if (aRes.success) setSelectedApproval(aRes.data);
          }
        }
      }
    }
    init();
    // id is stable for the component lifetime (route param); append/setValue are stable RHF refs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  /* ── Ref approval search (debounced 300 ms) ── */
  const refSearch = watch("_refSearch");
  useEffect(() => {
    clearTimeout(refSearchDebounce.current);
    if (!refSearch || refSearch.length < 2) {
      setApprovalResults([]);
      return;
    }
    // If an approval is already selected and the search field still holds its
    // billno (i.e. the user hasn't typed something new), don't re-search.
    if (selectedApproval && refSearch === selectedApproval.billno) {
      setApprovalResults([]);
      return;
    }
    refSearchDebounce.current = setTimeout(async () => {
      const res = await fetchSalesApproval({ search: refSearch, page: 1, pendingOnly: true });
      if (res.success) setApprovalResults(res.data.results || []);
    }, 300);
    return () => clearTimeout(refSearchDebounce.current);
  }, [refSearch, selectedApproval]);

  const handleSelectApproval = async (approval) => {
    setApprovalResults([]);
    setValue("_refSearch", approval.billno);
    setValue("ref_approval", approval.id);
    const res = await fetchSalesApprovalById(approval.id);
    if (res.success) setSelectedApproval(res.data);
  };

  const clearApproval = () => {
    setSelectedApproval(null);
    setValue("_refSearch", "");
    setValue("ref_approval", null);
    // Remove all items that came from this approval
    const toRemove = fields
      .map((f, i) => (f.approval_item ? i : null))
      .filter((i) => i !== null)
      .reverse();
    toRemove.forEach((i) => remove(i));
  };

  /* ── Toggle approval item checkbox ── */
  const isApprovalItemChecked = (approvalItemId) =>
    fields.some((f) => f.approval_item === approvalItemId);

  const toggleApprovalItem = (approvalItem) => {
    const idx = fields.findIndex((f) => f.approval_item === approvalItem.id);
    if (idx >= 0) {
      remove(idx);
    } else {
      append({
        barcode: approvalItem.barcode ?? null,
        approval_item: approvalItem.id,
        item: approvalItem.item,
        pcs: approvalItem.pcs,
        gw: approvalItem.gw,
        purity: approvalItem.purity ?? "",
        amount: approvalItem.amount ?? 0,
        main_item_set: (approvalItem.main_item_set || []).map((d) => ({
          _sid: d.id ?? crypto.randomUUID(),
          item: d.item,
          pcs: d.pcs,
          ct: d.ct ?? null,
          gw: d.gw ?? null,
          metal_purity: d.metal_purity ?? "",
          rate: d.rate,
          amount: d.amount ?? d.amt ?? 0,
          packet: d.packet ?? null,
        })),
      });
    }
  };

  /* ── Barcode scan ── */
  const handleBarcodeBlur = async () => {
    const bc = getValues("_barcode");
    if (!bc) return;
    const res = await fetchBarcodeForReturn(bc);
    if (res.success) {
      const d = res.data;
      append({
        barcode: d.barcode,
        approval_item: null,
        item: d.item,
        pcs: d.pcs ?? 1,
        gw: d.gw ?? 0,
        purity: d.purity ?? "",
        amount: d.amount ?? 0,
        main_item_set: (d.main_item_set || []).map((sub) => ({
          _sid: sub.id ?? crypto.randomUUID(),
          item: sub.item,
          pcs: sub.pcs ?? 1,
          ct: sub.ct ?? null,
          gw: sub.gw ?? null,
          metal_purity: sub.metal_purity ?? "",
          rate: sub.rate ?? 0,
          amount: sub.amount ?? sub.amt ?? 0,
          packet: sub.packet ?? null,
        })),
      });
      setValue("_barcode", "");
    } else {
      toast({
        title: "Barcode not found",
        description: res.error?.detail ?? String(bc),
        variant: "destructive",
      });
    }
  };

  /* ── Manual add row ── */
  const addManualRow = () => {
    append({
      barcode: null,
      approval_item: null,
      item: "",
      pcs: 1,
      gw: 0,
      purity: "",
      amount: 0,
      main_item_set: [],
    });
  };

  /* ── Add sub-item row to a main item ── */
  const addSubRow = (mainIdx) => {
    const current = getValues(`items.${mainIdx}.main_item_set`) || [];
    setValue(`items.${mainIdx}.main_item_set`, [
      ...current,
      { _sid: crypto.randomUUID(), item: "", pcs: 1, ct: null, gw: null, metal_purity: "", rate: 0, amount: 0, packet: null },
    ]);
  };

  const removeSubRow = (mainIdx, subIdx) => {
    const current = getValues(`items.${mainIdx}.main_item_set`) || [];
    setValue(
      `items.${mainIdx}.main_item_set`,
      current.filter((_, i) => i !== subIdx),
    );
  };

  /* ── Submit ── */
  const onSubmit = async (formData) => {
    if (fields.length === 0) {
      toast({ title: "No items", description: "Add at least one return item.", variant: "destructive" });
      return;
    }
    const payload = {
      date1: formData.date1,
      ref_approval: formData.ref_approval ?? null,
      narration: formData.narration ?? "",
      items: (formData.items || []).map((item) => ({
        ...(item.id ? { id: item.id } : {}),
        barcode: item.barcode ?? null,
        approval_item: item.approval_item ?? null,
        item: item.item,
        pcs: Number(item.pcs),
        gw: item.gw,
        purity: item.purity ?? "",
        amount: item.amount ?? 0,
        main_item_set: (item.main_item_set || []).map((d) => ({
          ...(d.id ? { id: d.id } : {}),
          item: d.item,
          pcs: Number(d.pcs),
          ct: d.ct ?? null,
          gw: d.gw ?? null,
          metal_purity: d.metal_purity ?? null,
          rate: d.rate,
          amount: d.amount,
          packet: d.packet ?? null,
        })),
      })),
    };

    setSaving(true);
    const result = id
      ? await updateSalesApprovalReturn(payload, id)
      : await createSalesApprovalReturn(payload);
    setSaving(false);

    if (result.success) {
      toast({ title: id ? "Updated" : "Saved", description: `Return ${result.data.billno} recorded.` });
      navigate("/sales/salesapprovalreturn/list/");
    } else {
      toast({
        title: "Error saving",
        description: renderErrorTree(result.error),
        variant: "destructive",
      });
    }
  };

  useF4Submit(handleSubmit(onSubmit));

  const toggleExpand = (idx) =>
    setExpandedRows((prev) => ({ ...prev, [idx]: !prev[idx] }));

  return (
    <div className="px-8 py-7 max-w-7xl mx-auto space-y-7">
      {/* ── Header section ── */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="grid grid-cols-2 gap-6 mb-8">
          <div>
            <Label>Bill No</Label>
            <Input {...register("billno")} readOnly className="bg-muted" />
          </div>
          <div>
            <Label>Date</Label>
            <Input type="date" {...register("date1")} />
          </div>
          <div className="col-span-2 relative">
            <Label>Reference Approval (optional)</Label>
            <div className="flex gap-2">
              <Input
                {...register("_refSearch")}
                placeholder="Search by approval bill no…"
                autoComplete="off"
              />
              {selectedApproval && (
                <Button type="button" variant="outline" size="sm" onClick={clearApproval}>
                  Clear
                </Button>
              )}
            </div>
            {approvalResults.length > 0 && (
              <div className="absolute z-10 mt-1 bg-white border rounded-lg shadow-lg w-full max-h-52 overflow-y-auto">
                {approvalResults.map((a) => (
                  <div
                    key={a.id}
                    className="px-4 py-2.5 hover:bg-slate-50 cursor-pointer text-sm"
                    onClick={() => handleSelectApproval(a)}
                  >
                    {a.billno} — {a.ldgr_name}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="col-span-2">
            <Label>Narration</Label>
            <Input {...register("narration")} placeholder="Optional notes" />
          </div>
        </div>

        {/* ── From linked approval: checkbox list ── */}
        {selectedApproval && (
          <div className="border rounded-xl p-5 mb-6 bg-slate-50/70 shadow-sm">
            <p className="text-sm font-semibold mb-3 text-slate-700">
              Items from {selectedApproval.billno} — tick to include in return:
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">✓</TableHead>
                  <TableHead>Barcode</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>GW</TableHead>
                  <TableHead>Purity</TableHead>
                  <TableHead>Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(selectedApproval.items || []).map((ai) => (
                  <TableRow
                    key={ai.id}
                    className={ai.ret_status ? "opacity-40" : ""}
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={isApprovalItemChecked(ai.id)}
                        disabled={ai.ret_status}
                        onChange={() => toggleApprovalItem(ai)}
                      />
                    </TableCell>
                    <TableCell className="text-sm font-mono">{ai.barcode}</TableCell>
                    <TableCell className="text-sm">{ai.item_name || ai.item}</TableCell>
                    <TableCell className="text-sm tabular-nums">{ai.gw}</TableCell>
                    <TableCell className="text-sm">{ai.purity}</TableCell>
                    <TableCell className="text-sm tabular-nums">
                      {Number(ai.amount || 0).toLocaleString("en-IN", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* ── Barcode scan ── */}
        <div className="flex gap-3 mb-6 items-end">
          <div className="flex-1">
            <Label>Scan Barcode</Label>
            <Input
              {...register("_barcode")}
              placeholder="Scan or type barcode then Tab/click away…"
              onBlur={handleBarcodeBlur}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleBarcodeBlur(); } }}
            />
          </div>
          <Button type="button" variant="outline" onClick={addManualRow}>
            <Plus className="size-4 mr-1" /> Add Row
          </Button>
        </div>

        {/* ── Items table ── */}
        {fields.length > 0 && (
          <div className="border rounded-xl mb-6 overflow-x-auto shadow-sm">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-10" />
                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500">Barcode</TableHead>
                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500">Item</TableHead>
                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">Pcs</TableHead>
                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">GW</TableHead>
                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500">Purity</TableHead>
                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">Amount</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {fields.map((field, idx) => {
                  /* Barcode items are returned in their entirety and must not
                     be edited. Manual rows (no barcode) remain fully editable. */
                  const isBarcodeItem = !!field.barcode;
                  const resolvedName = mainItems.find(
                    (m) => m.short_code === field.item
                  )?.item_name;
                  const subItems = watch(`items.${idx}.main_item_set`) || [];

                  return (
                    <React.Fragment key={field.id}>
                      <TableRow className="hover:bg-slate-50/60">
                        {/* Expand toggle — only show when there are sub-items */}
                        <TableCell className="py-3.5 pl-4">
                          {subItems.length > 0 ? (
                            <button
                              type="button"
                              onClick={() => toggleExpand(idx)}
                              className="text-slate-400 hover:text-slate-700"
                            >
                              {expandedRows[idx] ? (
                                <ChevronDown className="size-4" />
                              ) : (
                                <ChevronRight className="size-4" />
                              )}
                            </button>
                          ) : (
                            <span className="size-4 inline-block" />
                          )}
                        </TableCell>

                        {/* Barcode — monospace badge */}
                        <TableCell className="py-3.5">
                          <span className="font-mono text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded tracking-wide">
                            {field.barcode ?? "—"}
                          </span>
                        </TableCell>

                        {/* Item */}
                        <TableCell className="py-3.5">
                          {isBarcodeItem ? (
                            /* read-only: show resolved name or short code */
                            <div>
                              <span className="text-sm font-medium">{field.item}</span>
                              {resolvedName && (
                                <p className="text-xs text-slate-500 mt-0.5">{resolvedName}</p>
                              )}
                            </div>
                          ) : (
                            <>
                              <Input
                                {...register(`items.${idx}.item`)}
                                list={`items-datalist-${idx}`}
                                className="h-8 text-sm w-32"
                              />
                              <datalist id={`items-datalist-${idx}`}>
                                {mainItems.map((m) => (
                                  <option key={m.id} value={m.short_code}>{m.item_name}</option>
                                ))}
                              </datalist>
                              {resolvedName && (
                                <p className="text-xs text-slate-500 mt-0.5 truncate max-w-[8rem]">
                                  {resolvedName}
                                </p>
                              )}
                            </>
                          )}
                        </TableCell>

                        {/* Pcs */}
                        <TableCell className="py-3.5 text-right">
                          {isBarcodeItem ? (
                            <span className="text-sm tabular-nums">{field.pcs}</span>
                          ) : (
                            <Input
                              type="number"
                              {...register(`items.${idx}.pcs`)}
                              className="h-8 text-sm w-16 text-right"
                            />
                          )}
                        </TableCell>

                        {/* GW */}
                        <TableCell className="py-3.5 text-right">
                          {isBarcodeItem ? (
                            <span className="text-sm tabular-nums">
                              {Number(field.gw || 0).toFixed(3)}
                            </span>
                          ) : (
                            <Input
                              type="number"
                              step="0.001"
                              {...register(`items.${idx}.gw`)}
                              className="h-8 text-sm w-22 text-right"
                            />
                          )}
                        </TableCell>

                        {/* Purity */}
                        <TableCell className="py-3.5">
                          {isBarcodeItem ? (
                            <span className="text-sm">{field.purity || "—"}</span>
                          ) : (
                            <Input
                              {...register(`items.${idx}.purity`)}
                              className="h-8 text-sm w-18"
                              placeholder="18K"
                            />
                          )}
                        </TableCell>

                        {/* Amount */}
                        <TableCell className="py-3.5 text-right">
                          {isBarcodeItem ? (
                            <span className="text-sm tabular-nums font-medium">
                              {Number(field.amount || 0).toLocaleString("en-IN", {
                                minimumFractionDigits: 2, maximumFractionDigits: 2,
                              })}
                            </span>
                          ) : (
                            <Input
                              type="number"
                              step="0.01"
                              {...register(`items.${idx}.amount`)}
                              className="h-8 text-sm w-28 text-right"
                            />
                          )}
                        </TableCell>

                        {/* Delete — always shown on main row so user can de-select */}
                        <TableCell className="py-3.5 pr-4">
                          <button
                            type="button"
                            onClick={() => remove(idx)}
                            className="text-red-400 hover:text-red-600"
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </TableCell>
                      </TableRow>

                      {/* ── Sub-items (expanded) ── */}
                      {expandedRows[idx] && subItems.length > 0 && (
                        <TableRow>
                          <TableCell colSpan={8} className="bg-slate-50/80 px-6 py-4">
                            <Table>
                              <TableHeader>
                                <TableRow className="bg-slate-100/80">
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500">Item</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500">Packet</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">Pcs</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">Ct</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">GW</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500">Metal Purity</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">Rate</TableHead>
                                  <TableHead className="text-xs font-semibold tracking-wide uppercase text-slate-500 text-right">Amount</TableHead>
                                  {/* No action column for barcode items */}
                                  {!isBarcodeItem && <TableHead className="w-8" />}
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {subItems.map((sub, si) => {
                                  const subName = mainItems.find(
                                    (m) => m.short_code === sub.item
                                  )?.item_name;
                                  return (
                                    <TableRow key={sub._sid ?? si} className="hover:bg-slate-50">
                                      {/* Item */}
                                      <TableCell className="py-2.5">
                                        {isBarcodeItem ? (
                                          <div>
                                            <span className="text-xs font-medium">{sub.item}</span>
                                            {subName && (
                                              <p className="text-[10px] text-slate-500 mt-0.5">
                                                {subName}
                                              </p>
                                            )}
                                          </div>
                                        ) : (
                                          <>
                                            <Input
                                              {...register(`items.${idx}.main_item_set.${si}.item`)}
                                              list={`sub-items-datalist-${idx}-${si}`}
                                              className="h-7 text-xs w-24"
                                            />
                                            <datalist id={`sub-items-datalist-${idx}-${si}`}>
                                              {mainItems.map((m) => (
                                                <option key={m.id} value={m.short_code}>{m.item_name}</option>
                                              ))}
                                            </datalist>
                                            {subName && (
                                              <p className="text-[10px] text-slate-500 mt-0.5 truncate max-w-[6rem]">
                                                {subName}
                                              </p>
                                            )}
                                          </>
                                        )}
                                      </TableCell>

                                      {/* Packet */}
                                      <TableCell className="py-2.5">
                                        {isBarcodeItem ? (
                                          <span className="text-xs">{sub.packet || "—"}</span>
                                        ) : (
                                          <select
                                            {...register(`items.${idx}.main_item_set.${si}.packet`)}
                                            className="h-7 text-xs border rounded px-1 w-28"
                                          >
                                            <option value="">—</option>
                                            {packets.map((p) => (
                                              <option key={p.id} value={p.pckt_no}>{p.pckt_no}</option>
                                            ))}
                                          </select>
                                        )}
                                      </TableCell>

                                      {/* Pcs */}
                                      <TableCell className="py-1.5 text-right">
                                        {isBarcodeItem ? (
                                          <span className="text-xs tabular-nums">{sub.pcs}</span>
                                        ) : (
                                          <Input
                                            type="number"
                                            {...register(`items.${idx}.main_item_set.${si}.pcs`)}
                                            className="h-7 text-xs w-14 text-right"
                                          />
                                        )}
                                      </TableCell>

                                      {/* Ct */}
                                      <TableCell className="py-1.5 text-right">
                                        {isBarcodeItem ? (
                                          <span className="text-xs tabular-nums">
                                            {sub.ct && Number(sub.ct) !== 0
                                              ? Number(sub.ct).toFixed(3)
                                              : "—"}
                                          </span>
                                        ) : (
                                          <Input
                                            type="number"
                                            step="0.001"
                                            {...register(`items.${idx}.main_item_set.${si}.ct`)}
                                            className="h-7 text-xs w-16 text-right"
                                          />
                                        )}
                                      </TableCell>

                                      {/* GW */}
                                      <TableCell className="py-1.5 text-right">
                                        {isBarcodeItem ? (
                                          <span className="text-xs tabular-nums">
                                            {Number(sub.gw || 0).toFixed(3)}
                                          </span>
                                        ) : (
                                          <Input
                                            type="number"
                                            step="0.001"
                                            {...register(`items.${idx}.main_item_set.${si}.gw`)}
                                            className="h-7 text-xs w-16 text-right"
                                          />
                                        )}
                                      </TableCell>

                                      {/* Metal Purity */}
                                      <TableCell className="py-2.5">
                                        {isBarcodeItem ? (
                                          <span className="text-xs">{sub.metal_purity || "—"}</span>
                                        ) : (
                                          <Input
                                            {...register(`items.${idx}.main_item_set.${si}.metal_purity`)}
                                            className="h-7 text-xs w-16"
                                          />
                                        )}
                                      </TableCell>

                                      {/* Rate */}
                                      <TableCell className="py-1.5 text-right">
                                        {isBarcodeItem ? (
                                          <span className="text-xs tabular-nums">
                                            {Number(sub.rate || 0).toLocaleString("en-IN")}
                                          </span>
                                        ) : (
                                          <Input
                                            type="number"
                                            step="0.001"
                                            {...register(`items.${idx}.main_item_set.${si}.rate`)}
                                            className="h-7 text-xs w-20 text-right"
                                          />
                                        )}
                                      </TableCell>

                                      {/* Amount */}
                                      <TableCell className="py-1.5 text-right">
                                        {isBarcodeItem ? (
                                          <span className="text-xs tabular-nums">
                                            {Number(sub.amount || 0).toLocaleString("en-IN", {
                                              minimumFractionDigits: 2, maximumFractionDigits: 2,
                                            })}
                                          </span>
                                        ) : (
                                          <Input
                                            type="number"
                                            step="0.01"
                                            {...register(`items.${idx}.main_item_set.${si}.amount`)}
                                            className="h-7 text-xs w-20 text-right"
                                          />
                                        )}
                                      </TableCell>

                                      {/* Delete — hidden for barcode sub-items */}
                                      {!isBarcodeItem && (
                                        <TableCell className="py-2.5">
                                          <button
                                            type="button"
                                            onClick={() => removeSubRow(idx, si)}
                                            className="text-red-400 hover:text-red-600"
                                          >
                                            <Trash2 className="size-3" />
                                          </button>
                                        </TableCell>
                                      )}
                                    </TableRow>
                                  );
                                })}
                              </TableBody>
                            </Table>
                            {/* Add Sub-item only for manual rows */}
                            {!isBarcodeItem && (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="mt-1 text-xs"
                                onClick={() => addSubRow(idx)}
                              >
                                <Plus className="size-3 mr-1" /> Add Sub-item
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}

        {/* ── Footer ── */}
        <div className="flex justify-end gap-3 mt-8 pt-4 border-t">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/sales/salesapprovalreturn/list/")}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : id ? "Update (F4)" : "Save (F4)"}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default SalesApprovalReturnAdd;

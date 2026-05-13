import React, { useEffect, useMemo, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Table, TableRow, TableCell, TableBody } from "@/components/ui/table";
import { Trash2, ChevronDown, ChevronRight, Search } from "lucide-react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { renderErrorTree } from "../../../Utils";
import {
  createHallmarkIssue,
  fetchRCVs,
  fetchHallmarkIssueForEdit,
  fetchNextHallMarkIssueNo,
  getLedgers,
  updateHallmarkIssue,
} from "@/services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";

function SectionCard({ title, subtitle, action, children, className = "" }) {
  return (
    <div className={`bg-white border border-border rounded-xl shadow-sm ${className}`}>
      <div className="px-5 py-3 border-b border-border bg-muted/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-0.5 h-4 rounded-full bg-primary inline-block" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">{title}</h3>
          {subtitle ? <span className="text-xs text-muted-foreground">� {subtitle}</span> : null}
        </div>
        {action ? <div>{action}</div> : null}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

const fmt3 = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n.toFixed(3) : "�";
};
const fmt0 = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? String(Math.round(n)) : "0";
};

const HallmarkIssue = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();

  const { register, handleSubmit, control, setValue, getValues, watch, reset, formState: { isDirty } } = useForm({
    defaultValues: {
      form: {
        date1: new Date().toISOString().split("T")[0],
        issue_slip_no: "",
        hallmark_center: "",
        hallmark_center_name: "",
      },
      table: [],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "table" });
  const { canSave, saveLabel, resetTableDirty } = useEditDirty({ id, isDirty });
  const [saving, setSaving] = useState(false);

  const [karigars, setKarigars] = useState([]); // available karigar receives with items
  const [centres, setCentres] = useState([]); // hallmarking centres (Ledger HM)
  const [expandedReceives, setExpandedReceives] = useState(new Set());
  const [pickedKeys, setPickedKeys] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState("");

  // ── Initial load + edit mode ─────────────────────────────────────────────
  useEffect(() => {
    async function fetchData() {
      const [rcvR, ldgrR, billR] = await Promise.all([
        fetchRCVs(),
        getLedgers({ type: "HM" }),
        fetchNextHallMarkIssueNo(),
      ]);
      if (rcvR.success) setKarigars(rcvR.data || []);
      if (ldgrR.success) setCentres(ldgrR.data.results || ldgrR.data || []);
      if (billR.success && !id) setValue("form.issue_slip_no", billR.data.bill_no);
    }
    fetchData().then(() => {
      if (!id) return;
      fetchHallmarkIssueForEdit(id)
        .then((r) => {
          if (!r.success) return;
          const d = r.data;
          setValue("form.date1", d.date1 || "");
          setValue("form.issue_slip_no", d.issue_slip_no || "");
          setValue("form.hallmark_center", d.hallmark_center || "");
          setValue("form.hallmark_center_name", d.hallmark_center_name || "");
          (d.hallmarkissueitem_set || []).forEach((it) => {
            append({
              ...it,
              _receive_slip_no: it.source_receive_slip || "",
              _karigar_name: it.source_karigar || "",
              _date: it.source_date || "",
              _source_sl_no: it.source_sl_no ?? null,
            });
          });
          reset(getValues(), { keepValues: true, keepDirty: false });
          resetTableDirty();
        })
        .catch((err) => console.error("Error fetching hallmark issue:", err));
    });
  }, [id]);

  // ── Receives picker logic ────────────────────────────────────────────────
  const tableSnapshot = watch("table") || [];
  const addedReceiveSls = useMemo(
    () => new Set(tableSnapshot.map((it) => it.receive_sl).filter(Boolean)),
    [tableSnapshot]
  );

  const filteredReceives = useMemo(() => {
    const t = searchTerm.trim().toLowerCase();
    if (!t) return karigars;
    return karigars.filter((r) => {
      if ((r.receive_slip_no || "").toLowerCase().includes(t)) return true;
      if ((r.karigar_ldgr_name || "").toLowerCase().includes(t)) return true;
      return (r.karigarreceiveitem_set || []).some((i) =>
        (i.item || "").toLowerCase().includes(t) || String(i.sl_no || "").includes(t)
      );
    });
  }, [karigars, searchTerm]);

  const toggleExpand = (slip) => {
    setExpandedReceives((prev) => {
      const next = new Set(prev);
      next.has(slip) ? next.delete(slip) : next.add(slip);
      return next;
    });
  };

  const togglePick = (slip, slNo) => {
    const key = `${slip}::${slNo}`;
    setPickedKeys((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const toggleReceiveAll = (slip, items) => {
    const itemKeys = items
      .filter((i) => !addedReceiveSls.has(i.receive_sl))
      .map((i) => `${slip}::${i.sl_no}`);
    const allPicked = itemKeys.every((k) => pickedKeys.has(k));
    setPickedKeys((prev) => {
      const next = new Set(prev);
      itemKeys.forEach((k) => (allPicked ? next.delete(k) : next.add(k)));
      return next;
    });
  };

  const addSelected = () => {
    if (pickedKeys.size === 0) return;
    let added = 0;
    pickedKeys.forEach((key) => {
      const [slip, slNoStr] = key.split("::");
      const recv = karigars.find((r) => r.receive_slip_no === slip);
      if (!recv) return;
      const ri = (recv.karigarreceiveitem_set || []).find(
        (i) => String(i.sl_no) === String(slNoStr)
      );
      if (!ri || addedReceiveSls.has(ri.receive_sl)) return;
      append({
        sl_no: getValues("table").length + 1,
        receive_sl: ri.receive_sl,
        item: ri.item,
        item_name: ri.item_name || "",
        purity: ri.purity,
        pcs: ri.pcs,
        gw: ri.gw,
        nw: ri.nw,
        remarks: "",
        hallmarkissuedetails_set: (ri.details || ri.karigarreceiveitemdetails_set || []).map((d) => ({
          packet: d.packet || null,
          metal_purity: d.metal_purity || null,
          pcs: d.pcs || 0,
          ct: d.ct || 0,
          gw: d.gw || 0,
        })),
        _receive_slip_no: recv.receive_slip_no,
        _karigar_name: recv.karigar_ldgr_name || "",
        _date: recv.date1 || "",
        _source_sl_no: ri.sl_no,
      });
      added += 1;
    });
    setPickedKeys(new Set());
    if (added > 0) toast({ title: `Added ${added} item${added === 1 ? "" : "s"} to slip` });
  };

  // ── Submit ───────────────────────────────────────────────────────────────
  const onSubmit = async () => {
    const formData = getValues("form");
    const tableData = getValues("table");
    if (!formData.hallmark_center) {
      toast({ title: "Please select a Hallmarking centre.", variant: "destructive" });
      return;
    }
    if (tableData.length === 0) {
      toast({ title: "Add at least one item to the slip.", variant: "destructive" });
      return;
    }
    // Strip the metadata fields the backend doesn't know about.
    const cleaned = tableData.map((it, idx) => {
      const { _receive_slip_no, _karigar_name, _date, _source_sl_no, source_receive_slip, source_karigar, source_date, source_sl_no, ...rest } = it;
      return { ...rest, sl_no: idx + 1 };
    });
    const payload = { ...formData, hallmarkissueitem_set: cleaned };
    setSaving(true);
    const fn = id ? updateHallmarkIssue(id, payload) : createHallmarkIssue(payload);
    fn.then((r) => {
      if (r.success) {
        toast({ title: id ? "Hallmark issue updated" : "Hallmark issue saved" });
        setTimeout(() => navigate("/manufacturing/issue/hallmarkissue/"), 1200);
      } else {
        setSaving(false);
        toast({
          title: "Save failed",
          description: renderErrorTree(r.error),
          variant: "destructive",
        });
      }
    }).catch(() => setSaving(false));
  };

  useF4Submit(handleSubmit(onSubmit));

  // ── Totals on slip ───────────────────────────────────────────────────────
  const slipTotals = useMemo(() => {
    const t = { pcs: 0, gw: 0, nw: 0 };
    tableSnapshot.forEach((it) => {
      t.pcs += parseFloat(it.pcs) || 0;
      t.gw += parseFloat(it.gw) || 0;
      t.nw += parseFloat(it.nw) || 0;
    });
    return t;
  }, [tableSnapshot]);

  // Group added items by source receive for table render
  const groupedItems = useMemo(() => {
    const map = new Map();
    tableSnapshot.forEach((it, idx) => {
      const key = it._receive_slip_no || "�";
      if (!map.has(key)) {
        map.set(key, {
          slip: key,
          karigar: it._karigar_name || "",
          date: it._date || "",
          rows: [],
        });
      }
      map.get(key).rows.push({ ...it, _idx: idx });
    });
    return Array.from(map.values());
  }, [tableSnapshot]);

  return (
    <div className="w-[96%] max-w-[1500px] mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <button type="button" onClick={() => navigate("/")} className="hover:text-foreground">Home</button>
        <span>/</span>
        <button type="button" onClick={() => navigate("/manufacturing/issue/hallmarkissue/")} className="hover:text-foreground">Hallmark Issue</button>
        <span>/</span>
        <span className="text-foreground">{id ? "Edit" : "New"}</span>
      </div>

      <div className="flex items-center justify-between sticky top-0 z-20 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70 -mx-4 px-4 py-2 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold">{id ? "Edit Hallmark Issue" : "New Hallmark Issue"}</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Bundle items from karigar receives and send them to a hallmarking centre.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.history.back()}>Cancel</Button>
          <Button type="submit" form="hmIssueForm" size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground" disabled={saving || !canSave}>{saveLabel(saving)}</Button>
        </div>
      </div>

      <form id="hmIssueForm" onSubmit={handleSubmit(onSubmit)} className="space-y-4">

        {/* Slip header */}
        <SectionCard title="Slip header">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-4">
            <FieldContainer>
              <Label htmlFor="date1">Date</Label>
              <Input type="date" {...register("form.date1")} required />
            </FieldContainer>
            <FieldContainer>
              <Label htmlFor="issue_slip_no" className="text-nowrap">Issue Slip No</Label>
              <Input type="text" {...register("form.issue_slip_no")} readOnly disabled className="bg-muted/40" />
            </FieldContainer>
            <FieldContainer className="col-span-2">
              <Label htmlFor="hallmark_center_name">Hallmarking centre <span className="text-red-500">*</span></Label>
              <Input
                list="hm_centre_list"
                {...register("form.hallmark_center_name", {
                  onChange: (e) => {
                    const c = centres.find((x) => x.ac_name === e.target.value);
                    setValue("form.hallmark_center", c ? c.id : "");
                  },
                })}
                required
              />
              <datalist id="hm_centre_list">
                {centres.map((c) => <option key={c.id} value={c.ac_name}>{c.id}</option>)}
              </datalist>
              <Input type="hidden" {...register("form.hallmark_center")} />
            </FieldContainer>
          </div>
        </SectionCard>

        {/* Step 1: Add items from karigar receives */}
        <SectionCard
          title="Step 1 � Add items from karigar receives"
          subtitle={`${filteredReceives.length} receive${filteredReceives.length === 1 ? "" : "s"} available`}
          action={
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="size-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-8 w-56 pl-7 text-xs"
                  placeholder="Search karigar / slip / item�"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <Button
                type="button"
                size="sm"
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={pickedKeys.size === 0}
                onClick={addSelected}
              >
                Add {pickedKeys.size || ""} selected
              </Button>
            </div>
          }
        >
          <div className="space-y-2">
            {filteredReceives.length === 0 ? (
              <div className="text-sm text-muted-foreground py-6 text-center">No karigar receives match.</div>
            ) : null}
            {filteredReceives.map((recv) => {
              const slip = recv.receive_slip_no;
              const items = recv.karigarreceiveitem_set || [];
              const expanded = expandedReceives.has(slip);
              const availableItems = items.filter((i) => !addedReceiveSls.has(i.receive_sl));
              const allItemKeys = availableItems.map((i) => `${slip}::${i.sl_no}`);
              const pickedHere = allItemKeys.filter((k) => pickedKeys.has(k)).length;
              const pcsTotal = items.reduce((s, i) => s + (parseFloat(i.pcs) || 0), 0);
              const gwTotal = items.reduce((s, i) => s + (parseFloat(i.gw) || 0), 0);
              return (
                <div key={slip} className="border border-border rounded-lg bg-white">
                  <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                    <div className="flex items-center gap-2.5 text-sm">
                      <button type="button" onClick={() => toggleExpand(slip)} className="text-muted-foreground hover:text-foreground">
                        {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                      </button>
                      <span className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground">Receive</span>
                      <span className="font-medium">{slip}</span>
                      <span className="text-xs text-muted-foreground">�</span>
                      <span className="text-xs text-muted-foreground">{recv.date1}</span>
                      <span className="text-xs text-muted-foreground">�</span>
                      <span className="inline-flex px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{recv.karigar_ldgr_name || "�"}</span>
                    </div>
                    <div className="text-xs text-muted-foreground tabular-nums">
                      {items.length} item{items.length === 1 ? "" : "s"} � {fmt0(pcsTotal)} pc � {fmt3(gwTotal)} g
                      {pickedHere > 0 ? <span className="ml-2 text-primary font-medium">� {pickedHere} selected</span> : null}
                    </div>
                  </div>
                  {expanded ? (
                    <Table className="w-full text-[12.5px] border-collapse">
                      <TableBody>
                        <TableRow className="hover:bg-transparent bg-slate-50">
                          <TableCell className="px-3 py-2 border w-10 text-center">
                            <input
                              type="checkbox"
                              className="h-3.5 w-3.5"
                              checked={availableItems.length > 0 && allItemKeys.every((k) => pickedKeys.has(k))}
                              onChange={() => toggleReceiveAll(slip, items)}
                              disabled={availableItems.length === 0}
                            />
                          </TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Sl</TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Item</TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Purity</TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">Pcs</TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">GW</TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">NW</TableCell>
                          <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-center">Status</TableCell>
                        </TableRow>
                        {items.map((it) => {
                          const key = `${slip}::${it.sl_no}`;
                          const alreadyAdded = addedReceiveSls.has(it.receive_sl);
                          const picked = pickedKeys.has(key);
                          const displayName = it.item_name || it.item || "�";
                          return (
                            <TableRow key={it.receive_sl ?? `${slip}-${it.sl_no}`} className={alreadyAdded ? "opacity-50" : "hover:bg-slate-50/60"}>
                              <TableCell className="px-3 py-2 border text-center">
                                <input
                                  type="checkbox"
                                  className="h-3.5 w-3.5"
                                  checked={picked}
                                  onChange={() => togglePick(slip, it.sl_no)}
                                  disabled={alreadyAdded}
                                />
                              </TableCell>
                              <TableCell className="px-3 py-2 border text-center font-semibold">{it.sl_no}</TableCell>
                              <TableCell className="px-3 py-2 border">
                                <div className="font-medium">{displayName}</div>
                                {it.item_name && it.item ? <div className="text-[11px] text-muted-foreground font-mono">{it.item}</div> : null}
                              </TableCell>
                              <TableCell className="px-3 py-2 border">
                                {it.purity ? <span className="inline-flex px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{it.purity}</span> : "�"}
                              </TableCell>
                              <TableCell className="px-3 py-2 border text-right tabular-nums">{fmt0(it.pcs)}</TableCell>
                              <TableCell className="px-3 py-2 border text-right tabular-nums">{fmt3(it.gw)}</TableCell>
                              <TableCell className="px-3 py-2 border text-right tabular-nums font-medium">{fmt3(it.nw)}</TableCell>
                              <TableCell className="px-3 py-2 border text-center text-[11px]">
                                {alreadyAdded ? (
                                  <span className="text-slate-400">On this slip</span>
                                ) : (
                                  <span className="text-emerald-600">● Available</span>
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  ) : null}
                </div>
              );
            })}
          </div>
        </SectionCard>

        {/* Step 2: Items on this slip */}
        <SectionCard
          title="Step 2 � Items on this slip"
          subtitle={
            tableSnapshot.length > 0
              ? `${tableSnapshot.length} item${tableSnapshot.length === 1 ? "" : "s"} from ${groupedItems.length} receive${groupedItems.length === 1 ? "" : "s"}`
              : "Pick items above to begin"
          }
        >
          {tableSnapshot.length === 0 ? (
            <div className="text-sm text-muted-foreground py-8 text-center">No items added yet.</div>
          ) : (
            <Table className="w-full text-[12.5px] border-collapse">
              <TableBody>
                <TableRow className="hover:bg-transparent bg-slate-50">
                  <TableCell className="px-3 py-2 border w-10 text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-center"></TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-center">Sl</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Item</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Purity</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Sub-item</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Packet</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">Pcs</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">Ct</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">GW</TableCell>
                  <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">NW</TableCell>
                </TableRow>

                {groupedItems.map((group) => (
                  <React.Fragment key={group.slip}>
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={10} className="px-4 py-2.5 border-y-2 border-y-[hsl(242_30%_86%)] bg-[hsl(242_40%_96%)] text-[hsl(242_64%_38%)] text-[12.5px]">
                        <span className="text-[11px] uppercase tracking-wider font-semibold mr-2">▸ Receive</span>
                        <span className="font-semibold">{group.slip}</span>
                        {group.karigar ? <span className="mx-1.5 text-slate-400">�</span> : null}
                        {group.karigar ? <span>{group.karigar}</span> : null}
                        {group.date ? <span className="mx-1.5 text-slate-400">�</span> : null}
                        {group.date ? <span>{group.date}</span> : null}
                      </TableCell>
                    </TableRow>
                    {group.rows.map((row) => {
                      const subItems = row.hallmarkissuedetails_set || [];
                      const span = Math.max(subItems.length, 1);
                      return subItems.length > 0 ? (
                        subItems.map((sub, sIdx) => (
                          <TableRow key={`${row._idx}-${sIdx}`} className="hover:bg-slate-50/60">
                            {sIdx === 0 ? (
                              <>
                                <TableCell rowSpan={span} className="px-3 py-2.5 border text-center align-middle">
                                  <button type="button" onClick={() => remove(row._idx)} className="text-slate-400 hover:text-rose-600 p-1 rounded hover:bg-rose-50 transition-colors" title="Remove from slip">
                                    <Trash2 className="size-4" />
                                  </button>
                                </TableCell>
                                <TableCell rowSpan={span} className="px-3 py-2.5 border text-center font-semibold align-middle">{row.sl_no || row._idx + 1}</TableCell>
                                <TableCell rowSpan={span} className="px-3 py-2.5 border align-middle font-medium">{row.item_name || row.item || "�"}</TableCell>
                                <TableCell rowSpan={span} className="px-3 py-2.5 border align-middle">
                                  {row.purity ? <span className="inline-flex px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{row.purity}</span> : "�"}
                                </TableCell>
                              </>
                            ) : null}
                            <TableCell className="px-3 py-2.5 border">{sub.item || sub.metal_purity || "�"}</TableCell>
                            <TableCell className="px-3 py-2.5 border">{sub.packet || "�"}</TableCell>
                            <TableCell className="px-3 py-2.5 border text-right tabular-nums bg-[hsl(220_30%_97.5%)]">{fmt0(sub.pcs)}</TableCell>
                            <TableCell className="px-3 py-2.5 border text-right tabular-nums bg-[hsl(220_30%_97.5%)]">{fmt3(sub.ct)}</TableCell>
                            <TableCell className="px-3 py-2.5 border text-right tabular-nums bg-[hsl(220_30%_97.5%)]">{fmt3(sub.gw)}</TableCell>
                            {sIdx === 0 ? (
                              <TableCell rowSpan={span} className="px-3 py-2.5 border text-right tabular-nums font-medium align-middle">{fmt3(row.nw)}</TableCell>
                            ) : null}
                          </TableRow>
                        ))
                      ) : (
                        <TableRow key={row._idx} className="hover:bg-slate-50/60">
                          <TableCell className="px-3 py-2.5 border text-center align-middle">
                            <button type="button" onClick={() => remove(row._idx)} className="text-slate-400 hover:text-rose-600 p-1 rounded hover:bg-rose-50 transition-colors" title="Remove from slip">
                              <Trash2 className="size-4" />
                            </button>
                          </TableCell>
                          <TableCell className="px-3 py-2.5 border text-center font-semibold">{row.sl_no || row._idx + 1}</TableCell>
                          <TableCell className="px-3 py-2.5 border font-medium">{row.item_name || row.item || "�"}</TableCell>
                          <TableCell className="px-3 py-2.5 border">
                            {row.purity ? <span className="inline-flex px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{row.purity}</span> : "�"}
                          </TableCell>
                          <TableCell className="px-3 py-2.5 border text-slate-400">�</TableCell>
                          <TableCell className="px-3 py-2.5 border text-slate-400">�</TableCell>
                          <TableCell className="px-3 py-2.5 border text-right tabular-nums">{fmt0(row.pcs)}</TableCell>
                          <TableCell className="px-3 py-2.5 border text-slate-400">�</TableCell>
                          <TableCell className="px-3 py-2.5 border text-right tabular-nums">{fmt3(row.gw)}</TableCell>
                          <TableCell className="px-3 py-2.5 border text-right tabular-nums font-medium">{fmt3(row.nw)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </React.Fragment>
                ))}

                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={6} className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-center font-semibold">
                    Total � {tableSnapshot.length} item{tableSnapshot.length === 1 ? "" : "s"} from {groupedItems.length} receive{groupedItems.length === 1 ? "" : "s"}
                  </TableCell>
                  <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt0(slipTotals.pcs)}</TableCell>
                  <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)]"></TableCell>
                  <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt3(slipTotals.gw)}</TableCell>
                  <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt3(slipTotals.nw)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          )}
        </SectionCard>
      </form>
    </div>
  );
};

export default HallmarkIssue;

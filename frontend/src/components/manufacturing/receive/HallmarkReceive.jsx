import React, { useEffect, useMemo, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableBody } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { useParams, useNavigate } from "react-router-dom";
import { FieldContainer, renderErrorTree } from "@/Utils";
import {
  createHallmarkReceive,
  fetchHallmarkIssuewithslno,
  getLedgers,
  fetchNextHallMarkReceiveNo,
  fetchHallMarkRecForEdit,
  updateHallMarkRecForEdit,
} from "@/services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";

function SectionCard({ title, subtitle, action, children, className = "" }) {
  return (
    <div className={`bg-white border border-border rounded-xl shadow-sm ${className}`}>
      <div className="px-5 py-3 border-b border-border bg-muted/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-0.5 h-4 rounded-full bg-primary inline-block" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">{title}</h3>
          {subtitle ? <span className="text-xs text-muted-foreground">· {subtitle}</span> : null}
        </div>
        {action ? <div>{action}</div> : null}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

const fmt3 = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n.toFixed(3) : "—";
};
const fmt0 = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? String(Math.round(n)) : "0";
};

const HallmarkReceive = () => {
  const { toast } = useToast();
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();
  const { id } = useParams();
  const navigate = useNavigate();

  const { register, handleSubmit, control, watch, setValue, getValues, reset, formState: { isDirty } } = useForm({
    defaultValues: {
      form: {
        date1: new Date().toISOString().split("T")[0],
        receive_slip_no: "",
        issue_slip_no: "",
        hallmark_center: "",
        hallmark_center_name: "",
      },
      table: [],
    },
  });
  const { fields, replace } = useFieldArray({ control, name: "table" });
  const { canSave, saveLabel, resetTableDirty } = useEditDirty({ id, isDirty });
  const [saving, setSaving] = useState(false);

  const [centres, setCentres] = useState([]);
  const [openIssues, setOpenIssues] = useState([]);

  // Initial load: next bill no, centres, available hallmark issues, and edit data
  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      const [billR, centresR, issuesR] = await Promise.all([
        fetchNextHallMarkReceiveNo(),
        getLedgers({ type: "HM" }),
        fetchHallmarkIssuewithslno(),
      ]);
      if (cancelled) return;
      if (billR.success && !id) setValue("form.receive_slip_no", billR.data.bill_no);
      if (centresR.success) setCentres(centresR.data.results || centresR.data || []);
      if (issuesR.success) {
        const list = issuesR.data.results || issuesR.data || [];
        setOpenIssues(Array.isArray(list) ? list : []);
      }
    }
    fetchData().then(() => {
      if (!id) return;
      fetchHallMarkRecForEdit(id).then((data) => {
        if (cancelled || !data.success) return;
        const d = data.data;
        setValue("form.date1", d.date1 || "");
        setValue("form.receive_slip_no", d.receive_slip_no || "");
        setValue("form.issue_slip_no", d.issue_slip_no || "");
        setValue("form.hallmark_center", d.hallmark_center || "");
        setValue("form.hallmark_center_name", d.hallmark_center_name || "");
        replace((d.hallmarkreceiveitem_set || []).map((it) => ({
          ...it,
          // normalize the children key to the receive shape
          hallmarkreceivedetails_set:
            it.hallmarkreceivedetails_set || it.hallmarkissuedetails_set || [],
        })));
        reset(getValues(), { keepValues: true, keepDirty: false });
        resetTableDirty();
      });
    });
    return () => { cancelled = true; };
  }, [id, replace, setValue]);

  // Issue picker — choose a hallmark issue, then load its items into the table
  const pickIssue = (iss) => {
    setValue("form.issue_slip_no", iss.issue_slip_no || iss.id);
    setValue("form.hallmark_center", iss.hallmark_center || "");
    setValue("form.hallmark_center_name", iss.hallmark_center_name || "");
    const rows = (iss.hallmarkissueitem_set || []).map((item) => ({
      ...item,
      issue_slip_no: iss.id,
      huid: item.huid || "",
      loss_wt: item.loss_wt || "",
      rejection_status: false,
      hallmarkreceivedetails_set: item.hallmarkissuedetails_set || [],
    }));
    replace(rows);
  };

  const clearIssue = () => {
    setValue("form.issue_slip_no", "");
    setValue("form.hallmark_center", "");
    setValue("form.hallmark_center_name", "");
    replace([]);
  };

  const onSubmit = async () => {
    const formData = getValues("form");
    const tableData = getValues("table");
    if (!formData.issue_slip_no) {
      toast({ title: "Pick an Issue Slip first.", variant: "destructive" });
      return;
    }
    if (tableData.length === 0) {
      toast({ title: "No items to receive.", variant: "destructive" });
      return;
    }
    const payload = { ...formData, hallmarkreceiveitem_set: tableData };
    setSaving(true);
    const fn = id ? updateHallMarkRecForEdit(payload, id) : createHallmarkReceive(payload);
    fn.then((r) => {
      if (r.success) {
        toast({ title: id ? "Hallmark receive updated" : "Hallmark receive saved" });
        setTimeout(() => navigate("/manufacturing/receive/hallmarkreceive/"), 1200);
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

  // Group items by source receive for display
  const tableSnapshot = watch("table") || [];
  const groupedItems = useMemo(() => {
    const map = new Map();
    tableSnapshot.forEach((it, idx) => {
      const key = it.source_receive_slip || it._receive_slip_no || "—";
      if (!map.has(key)) {
        map.set(key, {
          slip: key,
          karigar: it.source_karigar || it._karigar_name || "",
          date: it.source_date || it._date || "",
          rows: [],
        });
      }
      map.get(key).rows.push({ ...it, _idx: idx });
    });
    return Array.from(map.values());
  }, [tableSnapshot]);

  const totals = useMemo(() => {
    const t = { pcs: 0, gw: 0, nw: 0 };
    tableSnapshot.forEach((it) => {
      t.pcs += parseFloat(it.pcs) || 0;
      t.gw += parseFloat(it.gw) || 0;
      t.nw += parseFloat(it.nw) || 0;
    });
    return t;
  }, [tableSnapshot]);

  const issueSlipDisplay = watch("form.issue_slip_no");
  const centreDisplay = watch("form.hallmark_center_name");
  const receiveSlipNo = watch("form.receive_slip_no");

  return (
    <div className="w-[96%] max-w-[1500px] mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <button type="button" onClick={() => navigate("/")} className="hover:text-foreground">Home</button>
        <span>/</span>
        <button type="button" onClick={() => navigate("/manufacturing/receive/hallmarkreceive/")} className="hover:text-foreground">Hallmark Receive</button>
        <span>/</span>
        <span className="text-foreground">{id ? "Edit" : "New"}</span>
      </div>

      <div className="flex items-center justify-between sticky top-0 z-20 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70 -mx-4 px-4 py-2 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold">{id ? "Edit Hallmark Receive" : "New Hallmark Receive"}</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Receive items back from a hallmarking centre, record HUIDs, and flag any rejections.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.history.back()}>Cancel</Button>
          <Button type="submit" form="hmReceiveForm" size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground" disabled={saving || !canSave}>{saveLabel(saving)}</Button>
        </div>
      </div>

      <form id="hmReceiveForm" onSubmit={handleSubmit(onSubmit)} className="space-y-4">

        {/* Slip header */}
        <SectionCard title="Slip header">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4 gap-y-4">
            <FieldContainer>
              <Label htmlFor="date1">Date</Label>
              <Input type="date" min={fyMin} max={fyMax} {...register("form.date1")} required />
            </FieldContainer>

            {/* Receive Slip No — auto-generated, read-only, violet pill (matches Sales Voucher billno) */}
            <FieldContainer>
              <Label className="text-nowrap">Receive Slip No</Label>
              <div className="flex items-center gap-2 flex-1">
                <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-accent-50 border border-accent-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate h-9">
                  {receiveSlipNo || <span className="text-accent-400 text-xs font-normal">Auto-generating…</span>}
                </span>
                <input type="hidden" {...register("form.receive_slip_no", { required: true })} />
              </div>
            </FieldContainer>

            {/* Issue Slip No — searchable combo box (dropdown is fixed-positioned, capped at max-h-60) */}
            <FieldContainer>
              <Label htmlFor="issue_slip_no" className="text-nowrap">Issue Slip No <span className="text-red-500">*</span></Label>
              <div className="flex items-center gap-1.5">
                <div className="flex-1">
                  <SearchableComboBox
                    options={openIssues}
                    labelKey="issue_slip_no"
                    searchKeys={["hallmark_center_name"]}
                    value={issueSlipDisplay ?? ""}
                    onSelect={(opt) => pickIssue(opt)}
                    placeholder="Search hallmark issue slip…"
                  />
                </div>
                {issueSlipDisplay ? (
                  <button
                    type="button"
                    onClick={clearIssue}
                    className="text-xs text-muted-foreground hover:text-rose-600 px-1"
                    title="Clear selection"
                  >
                    clear
                  </button>
                ) : null}
              </div>
              <input type="hidden" {...register("form.issue_slip_no", { required: true })} />
            </FieldContainer>

            <FieldContainer>
              <Label className="text-nowrap">Hallmarking centre</Label>
              <Input
                value={centreDisplay || ""}
                readOnly
                disabled
                className="bg-muted/40"
                placeholder="auto-fills from issue slip"
              />
              <input type="hidden" {...register("form.hallmark_center")} />
              <input type="hidden" {...register("form.hallmark_center_name")} />
            </FieldContainer>
          </div>
        </SectionCard>

        {/* Items table */}
        <SectionCard
          title="Issued items"
          subtitle={
            tableSnapshot.length > 0
              ? `${tableSnapshot.length} item${tableSnapshot.length === 1 ? "" : "s"} from ${groupedItems.length} receive${groupedItems.length === 1 ? "" : "s"} · enter HUID per piece`
              : "Pick an issue slip above to load items"
          }
        >
          {tableSnapshot.length === 0 ? (
            <div className="text-sm text-muted-foreground py-10 text-center">
              No items loaded. Choose a hallmark issue slip in the header to populate the table.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="w-full text-[12.5px] border-collapse">
                <TableBody>
                  {/* Header — grouped */}
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={5} className="px-3 py-2.5 border bg-slate-100 text-slate-600 text-[11px] font-semibold uppercase tracking-wider text-center">Issued piece</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-slate-100 text-slate-600 text-[11px] font-semibold uppercase tracking-wider text-center">Stone / sub-item</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-[hsl(242_64%_95%)] text-[hsl(242_64%_38%)] text-[11px] font-semibold uppercase tracking-wider text-center">Hallmark result</TableCell>
                  </TableRow>
                  <TableRow className="hover:bg-transparent bg-slate-50">
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-center">Sl</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Item</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Purity</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">Pcs</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">NW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Sub-item</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Packet</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">Pcs / Ct / GW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">HUID</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-right">Loss wt</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] uppercase tracking-wider text-muted-foreground font-semibold text-center">Rejected</TableCell>
                  </TableRow>

                  {groupedItems.map((group) => (
                    <React.Fragment key={group.slip}>
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={11} className="px-4 py-2.5 border-y-2 border-y-[hsl(242_30%_86%)] bg-[hsl(242_40%_96%)] text-[hsl(242_64%_38%)] text-[12.5px]">
                          <span className="text-[11px] uppercase tracking-wider font-semibold mr-2">▸ Receive</span>
                          <span className="font-semibold">{group.slip}</span>
                          {group.karigar ? <span className="mx-1.5 text-slate-400">·</span> : null}
                          {group.karigar ? <span>{group.karigar}</span> : null}
                          {group.date ? <span className="mx-1.5 text-slate-400">·</span> : null}
                          {group.date ? <span>{group.date}</span> : null}
                        </TableCell>
                      </TableRow>

                      {group.rows.map((row) => {
                        const idx = row._idx;
                        const subItems = row.hallmarkreceivedetails_set || [];
                        const span = Math.max(subItems.length, 1);
                        const isRejected = !!watch(`table.${idx}.rejection_status`);
                        const renderMain = (sIdx) => sIdx === 0 && (
                          <>
                            <TableCell rowSpan={span} className="px-3 py-2.5 border text-center font-semibold align-middle">{row.sl_no || idx + 1}</TableCell>
                            <TableCell rowSpan={span} className="px-3 py-2.5 border align-middle">
                              <div className="font-medium">{row.item_name || row.item || "—"}</div>
                              {row.item_name && row.item ? <div className="text-[11px] text-muted-foreground font-mono">{row.item}</div> : null}
                            </TableCell>
                            <TableCell rowSpan={span} className="px-3 py-2.5 border align-middle">
                              {row.purity ? <span className="inline-flex px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{row.purity}</span> : "—"}
                            </TableCell>
                            <TableCell rowSpan={span} className="px-3 py-2.5 border text-right tabular-nums align-middle">{fmt0(row.pcs)}</TableCell>
                            <TableCell rowSpan={span} className="px-3 py-2.5 border text-right tabular-nums align-middle font-medium">{fmt3(row.nw)}</TableCell>
                          </>
                        );
                        const renderResult = (sIdx) => sIdx === 0 && (
                          <>
                            <TableCell rowSpan={span} className="px-3 py-2 border align-middle">
                              <Input
                                {...register(`table.${idx}.huid`)}
                                placeholder="6-digit HUID"
                                className="h-8 font-mono uppercase text-xs tracking-wider"
                                disabled={isRejected}
                              />
                            </TableCell>
                            <TableCell rowSpan={span} className="px-3 py-2 border align-middle">
                              <Input
                                type="number"
                                step="0.001"
                                {...register(`table.${idx}.loss_wt`)}
                                placeholder="0.000"
                                className="h-8 text-right tabular-nums text-xs"
                                disabled={isRejected}
                              />
                            </TableCell>
                            <TableCell rowSpan={span} className="px-3 py-2 border text-center align-middle">
                              <Controller
                                name={`table.${idx}.rejection_status`}
                                control={control}
                                render={({ field }) => (
                                  <Checkbox checked={!!field.value} onCheckedChange={field.onChange} />
                                )}
                              />
                            </TableCell>
                          </>
                        );

                        return subItems.length > 0
                          ? subItems.map((sub, sIdx) => (
                              <TableRow key={`${idx}-${sIdx}`} className={`hover:bg-slate-50/60 ${isRejected ? "bg-rose-50/40" : ""}`}>
                                {renderMain(sIdx)}
                                <TableCell className="px-3 py-2 border">{sub.item || sub.metal_purity || "—"}</TableCell>
                                <TableCell className="px-3 py-2 border">{sub.packet || "—"}</TableCell>
                                <TableCell className="px-3 py-2 border text-right tabular-nums bg-[hsl(220_30%_97.5%)] whitespace-nowrap">
                                  {fmt0(sub.pcs)} / {fmt3(sub.ct)} / {fmt3(sub.gw)}
                                </TableCell>
                                {renderResult(sIdx)}
                              </TableRow>
                            ))
                          : (
                            <TableRow key={idx} className={`hover:bg-slate-50/60 ${isRejected ? "bg-rose-50/40" : ""}`}>
                              {renderMain(0)}
                              <TableCell className="px-3 py-2 border text-slate-400">—</TableCell>
                              <TableCell className="px-3 py-2 border text-slate-400">—</TableCell>
                              <TableCell className="px-3 py-2 border text-slate-400">—</TableCell>
                              {renderResult(0)}
                            </TableRow>
                          );
                      })}
                    </React.Fragment>
                  ))}

                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={3} className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-center font-semibold">
                      Total · {tableSnapshot.length} item{tableSnapshot.length === 1 ? "" : "s"}
                    </TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt0(totals.pcs)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt3(totals.nw)}</TableCell>
                    <TableCell colSpan={6} className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)]"></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          )}
        </SectionCard>
      </form>
    </div>
  );
};

export default HallmarkReceive;

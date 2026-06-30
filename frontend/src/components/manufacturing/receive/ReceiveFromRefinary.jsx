import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { getLedgers, fetchPurity, fetchRefinaryIssuewithslno } from "@/services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import {
    createRefinaryReceive,
    fetchNextRefinaryReceiveNo,
    fetchRefinaryReceiveForEdit,
    updateRefinaryReceiveForEdit,
} from "../../../services/apiService";
import { renderErrorTree } from "../../../Utils";
import { Trash2, Flame, Save, ArrowLeft, ArrowUpRight, ArrowDownLeft, TrendingDown } from "lucide-react";
import { useEditDirty } from "@/hooks/useEditDirty";

/* Vertical label + input stacking */
const Field = ({ label, children, className = "" }) => (
    <div className={`flex flex-col gap-1.5 ${className}`}>
        <Label className="text-xs font-medium text-gray-500">{label}</Label>
        {children}
    </div>
);

const fmt = (v, dp = 3) =>
    v != null && v !== "" && !Number.isNaN(parseFloat(v)) ? parseFloat(v).toFixed(dp) : "—";

const ReceiveFromRefinary = () => {
    const { toast } = useToast();
    const { min: fyMin, max: fyMax } = useActiveFiscalYear();
    const { id } = useParams();
    const navigate = useNavigate();

    const { register, handleSubmit, control, reset, watch, setValue, getValues, formState: { isDirty } } = useForm({
        defaultValues: {
            form: {
                date1: new Date().toISOString().split("T")[0],
                billno: "",
                ldgr: "",
                ldgr_name: "",
                issue_slip_no: "",
            },
        },
    });

    const { fields, remove, replace } = useFieldArray({ control, name: "table" });

    const [saving, setSaving] = useState(false);
    const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
    const [refineries, setRefineries] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [issueNumbers, setIssueNumbers] = useState([]);

    useEffect(() => {
        async function fetchData() {
            const [refRes, purityRes, orderNoRes, issueRes] = await Promise.all([
                getLedgers({ type: "REF" }),
                fetchPurity(),
                fetchNextRefinaryReceiveNo(),
                fetchRefinaryIssuewithslno(),
            ]);
            if (refRes.success) setRefineries(refRes.data.results);
            if (purityRes.success) setPurityData(purityRes.data);
            if (orderNoRes.success) setValue("form.billno", orderNoRes.data.bill_no);
            if (issueRes.success) setIssueNumbers(issueRes.data.results);
        }

        fetchData().then(() => {
            if (id) {
                fetchRefinaryReceiveForEdit(id).then((data) => {
                    if (data.success) {
                        const d = data.data;
                        setValue("form.date1", d.date1);
                        setValue("form.billno", d.billno);
                        setValue("form.ldgr", d.ldgr);
                        setValue("form.ldgr_name", d.ldgr_name || "");
                        replace(d.refinaryreceivedetail_set || []);
                        reset(getValues(), { keepValues: true, keepDirty: false });
                        resetTableDirty();
                    }
                });
            }
        });
    }, []);

    /* Auto-fill table rows from fetched issue */
    const handleIssueFetch = async () => {
        const issue_slip_no = getValues("form.issue_slip_no");
        if (!issue_slip_no) return;
        const data = await fetchRefinaryIssuewithslno(issue_slip_no);
        if (!data.success) return;

        const rows = data.data.results
            .filter((r) => r.billno === issue_slip_no)
            .flatMap((r) =>
                r.refinaryissuedetail_set.map((item) => ({
                    ...item,
                    issue_no: r.billno,
                    conv_purity: "",
                    conv_nw: "",
                    loss_wt: "",
                    loss_per: "",
                    remarks: "",
                }))
            );
        replace(rows);
        markTableDirty();
    };

    /* ── Loss auto-calculation ──
       Loss Wt = Gross − Conv. Wt ; Loss % = Loss Wt ÷ Gross × 100.
       Conv. Wt drives both loss fields; either can still be edited as an override. */
    const grossOf = (index) => parseFloat(getValues(`table.${index}.gw`)) || 0;

    const handleConvChange = (index, value) => {
        const gross = grossOf(index);
        const conv = parseFloat(value);
        if (Number.isNaN(conv)) {
            setValue(`table.${index}.loss_wt`, "", { shouldDirty: true });
            setValue(`table.${index}.loss_per`, "", { shouldDirty: true });
        } else {
            const lossWt = +(gross - conv).toFixed(3);
            const lossPct = gross > 0 ? +((lossWt / gross) * 100).toFixed(2) : 0;
            setValue(`table.${index}.loss_wt`, lossWt, { shouldDirty: true });
            setValue(`table.${index}.loss_per`, lossPct, { shouldDirty: true });
        }
        markTableDirty();
    };

    const handleLossWtChange = (index, value) => {
        const gross = grossOf(index);
        const lossWt = parseFloat(value);
        if (!Number.isNaN(lossWt) && gross > 0) {
            setValue(`table.${index}.loss_per`, +((lossWt / gross) * 100).toFixed(2), { shouldDirty: true });
        }
        markTableDirty();
    };

    const handleLossPerChange = (index, value) => {
        const gross = grossOf(index);
        const pct = parseFloat(value);
        if (!Number.isNaN(pct) && gross > 0) {
            setValue(`table.${index}.loss_wt`, +((gross * pct) / 100).toFixed(3), { shouldDirty: true });
        }
        markTableDirty();
    };

    /* Live totals for footer + summary strip */
    const rows = watch("table") || [];
    const totals = rows.reduce(
        (a, r) => {
            a.gross += parseFloat(r?.gw) || 0;
            a.conv += parseFloat(r?.conv_nw) || 0;
            a.loss += parseFloat(r?.loss_wt) || 0;
            return a;
        },
        { gross: 0, conv: 0, loss: 0 }
    );
    const totalLossPct = totals.gross > 0 ? (totals.loss / totals.gross) * 100 : 0;

    const onSubmit = () => {
        const form = { ...getValues("form") };
        const tableRows = getValues("table");
        delete form.issue_slip_no;
        delete form.ldgr_name;
        form.refinaryreceivedetail_set = tableRows;

        setSaving(true);
        (id ? updateRefinaryReceiveForEdit(form, id) : createRefinaryReceive(form))
            .then((response) => {
                if (response.success) {
                    toast({ title: "Saved successfully!" });
                    setTimeout(() => navigate("/manufacturing/receive/refinary/"), 1500);
                } else {
                    setSaving(false);
                    toast({
                        title: "Submission failed.",
                        description: renderErrorTree(response.error),
                    });
                }
            })
            .catch(() => { setSaving(false); toast({ title: "An error occurred. Please try again." }); });
    };

    useF4Submit(handleSubmit(onSubmit));

    return (
        <div className="mt-4 px-4 pb-16 max-w-6xl mx-auto">
            <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
                {/* ── Title row ── */}
                <div className="flex items-center gap-3">
                    <button
                        type="button"
                        onClick={() => window.history.back()}
                        className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 transition-colors"
                        title="Back"
                    >
                        <ArrowLeft className="size-5" />
                    </button>
                    <Flame className="size-5 text-primary" />
                    <h2 className="font-bold text-primary text-lg tracking-wide">
                        {id ? "Edit" : "Add"} receive from refinery
                    </h2>
                    <span className="ml-auto font-mono text-xs text-gray-600 bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-md">
                        {watch("form.billno") || <span className="text-gray-400">Auto-generating…</span>}
                    </span>
                </div>

                {/* ── Receipt details card ── */}
                <div className="bg-white shadow-sm rounded-xl border border-gray-200 p-5">
                    <div className="text-sm font-medium text-gray-500 mb-4">Receipt details</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <Field label="Date">
                            <Input type="date" min={fyMin} max={fyMax} {...register("form.date1")} required />
                        </Field>

                        <Field label="Refinery house">
                            <Input
                                list="refinery_list"
                                {...register("form.ldgr_name")}
                                onChange={(e) => {
                                    const match = refineries.find((r) => r.ac_name === e.target.value);
                                    if (match) setValue("form.ldgr", match.id);
                                }}
                                placeholder="Select refinery…"
                                required
                            />
                            <Input type="hidden" {...register("form.ldgr")} />
                            <datalist id="refinery_list">
                                {refineries.map((r) => (
                                    <option key={r.id} value={r.ac_name} />
                                ))}
                            </datalist>
                        </Field>

                        <Field label="Issue no" className="sm:col-span-2">
                            <div className="flex gap-2">
                                <Input
                                    list="issue_list"
                                    {...register("form.issue_slip_no")}
                                    placeholder="Enter issue no…"
                                    onBlur={handleIssueFetch}
                                />
                                <Button
                                    type="button"
                                    onClick={handleIssueFetch}
                                    className="shrink-0 bg-primary hover:bg-primary text-white"
                                >
                                    Fetch
                                </Button>
                            </div>
                            <datalist id="issue_list">
                                {issueNumbers.map((iss) => (
                                    <option key={iss.id} value={iss.billno} />
                                ))}
                            </datalist>
                        </Field>
                    </div>
                </div>

                {/* ── Items card ── */}
                <div className="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
                    <div className="overflow-x-auto">
                        <Table className="w-full text-sm">
                            <TableHeader>
                                {/* Group header */}
                                <TableRow className="border-b border-gray-200 hover:bg-transparent">
                                    <TableHead className="w-10 px-3 py-2" />
                                    <TableHead colSpan={4} className="px-3 py-2 text-gray-500 font-medium whitespace-nowrap">
                                        <span className="inline-flex items-center gap-1.5"><ArrowUpRight className="size-3.5" /> Issued</span>
                                    </TableHead>
                                    <TableHead colSpan={2} className="px-3 py-2 font-medium whitespace-nowrap bg-emerald-50 text-emerald-700">
                                        <span className="inline-flex items-center gap-1.5"><ArrowDownLeft className="size-3.5" /> Converted</span>
                                    </TableHead>
                                    <TableHead colSpan={2} className="px-3 py-2 font-medium whitespace-nowrap bg-rose-50 text-rose-700">
                                        <span className="inline-flex items-center gap-1.5"><TrendingDown className="size-3.5" /> Loss</span>
                                    </TableHead>
                                    <TableHead className="px-3 py-2" />
                                    <TableHead className="w-10 px-3 py-2" />
                                </TableRow>
                                {/* Column header */}
                                <TableRow className="bg-gray-50 text-gray-500 hover:bg-gray-50">
                                    <TableHead className="w-10 px-3 py-2">#</TableHead>
                                    <TableHead className="px-3 py-2 whitespace-nowrap">Voucher</TableHead>
                                    <TableHead className="px-3 py-2">Item</TableHead>
                                    <TableHead className="px-3 py-2">Purity</TableHead>
                                    <TableHead className="px-3 py-2 whitespace-nowrap text-right">Gross (g)</TableHead>
                                    <TableHead className="px-3 py-2 whitespace-nowrap bg-emerald-50/50">Conv. purity</TableHead>
                                    <TableHead className="px-3 py-2 whitespace-nowrap text-right bg-emerald-50/50">Conv. wt (g)</TableHead>
                                    <TableHead className="px-3 py-2 whitespace-nowrap text-right bg-rose-50/50">Loss wt (g)</TableHead>
                                    <TableHead className="px-3 py-2 whitespace-nowrap text-right bg-rose-50/50">Loss %</TableHead>
                                    <TableHead className="px-3 py-2">Remarks</TableHead>
                                    <TableHead className="w-10 px-3 py-2" />
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {fields.length === 0 ? (
                                    <TableRow className="hover:bg-transparent">
                                        <TableCell colSpan={11} className="text-center text-gray-400 py-12">
                                            <Flame className="size-6 mx-auto mb-2 opacity-40" />
                                            Fetch an issue number above to load items.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    fields.map((item, index) => (
                                        <TableRow key={item.id} className="border-b border-gray-100">
                                            <TableCell className="px-3 py-1.5 text-gray-400 text-xs">{index + 1}</TableCell>

                                            {/* Issued — read-only from issue */}
                                            <TableCell className="px-3 py-1.5 font-mono text-xs text-gray-500">{item.issue_no}</TableCell>
                                            <TableCell className="px-3 py-1.5">{item.item}</TableCell>
                                            <TableCell className="px-3 py-1.5">{item.metal_purity}</TableCell>
                                            <TableCell className="px-3 py-1.5 text-right font-mono">{fmt(item.gw)}</TableCell>

                                            {/* Converted — editable */}
                                            <TableCell className="px-2 py-1 bg-emerald-50/30">
                                                <Controller
                                                    name={`table.${index}.conv_purity`}
                                                    control={control}
                                                    render={({ field }) => (
                                                        <Select onValueChange={field.onChange} value={field.value || ""}>
                                                            <SelectTrigger className="h-8 text-sm min-w-[110px]">
                                                                <SelectValue placeholder="Purity" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {purityData.map((p) => (
                                                                    <SelectItem key={p.id} value={`${p.purity}`}>
                                                                        {p.purity}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    )}
                                                />
                                            </TableCell>

                                            <TableCell className="px-2 py-1 bg-emerald-50/30">
                                                {(() => {
                                                    const conv = register(`table.${index}.conv_nw`);
                                                    return (
                                                        <Input
                                                            type="number"
                                                            step="0.001"
                                                            {...conv}
                                                            onChange={(e) => { conv.onChange(e); handleConvChange(index, e.target.value); }}
                                                            className="h-8 text-sm w-24 text-right font-mono"
                                                            placeholder="0.000"
                                                        />
                                                    );
                                                })()}
                                            </TableCell>

                                            {/* Loss — auto-filled, editable override */}
                                            <TableCell className="px-2 py-1 bg-rose-50/30">
                                                {(() => {
                                                    const lw = register(`table.${index}.loss_wt`);
                                                    return (
                                                        <Input
                                                            type="number"
                                                            step="0.001"
                                                            {...lw}
                                                            onChange={(e) => { lw.onChange(e); handleLossWtChange(index, e.target.value); }}
                                                            className="h-8 text-sm w-24 text-right font-mono text-rose-700"
                                                            placeholder="0.000"
                                                        />
                                                    );
                                                })()}
                                            </TableCell>

                                            <TableCell className="px-2 py-1 bg-rose-50/30">
                                                {(() => {
                                                    const lp = register(`table.${index}.loss_per`);
                                                    return (
                                                        <Input
                                                            type="number"
                                                            step="0.01"
                                                            {...lp}
                                                            onChange={(e) => { lp.onChange(e); handleLossPerChange(index, e.target.value); }}
                                                            className="h-8 text-sm w-20 text-right font-mono text-rose-700"
                                                            placeholder="0.00"
                                                        />
                                                    );
                                                })()}
                                            </TableCell>

                                            <TableCell className="px-2 py-1">
                                                <Input
                                                    type="text"
                                                    {...register(`table.${index}.remarks`)}
                                                    className="h-8 text-sm w-32"
                                                    placeholder="Remarks"
                                                />
                                            </TableCell>

                                            <TableCell className="px-2 py-1">
                                                <button
                                                    type="button"
                                                    onClick={() => remove(index)}
                                                    className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
                                                    title="Remove row"
                                                >
                                                    <Trash2 className="size-4" />
                                                </button>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                            {fields.length > 0 && (
                                <tfoot>
                                    <TableRow className="bg-gray-50 font-medium border-t border-gray-200 hover:bg-gray-50">
                                        <TableCell colSpan={4} className="px-3 py-2 text-gray-500">Totals</TableCell>
                                        <TableCell className="px-3 py-2 text-right font-mono">{fmt(totals.gross)}</TableCell>
                                        <TableCell className="bg-emerald-50/30" />
                                        <TableCell className="px-3 py-2 text-right font-mono bg-emerald-50/30">{fmt(totals.conv)}</TableCell>
                                        <TableCell className="px-3 py-2 text-right font-mono text-rose-700 bg-rose-50/30">{fmt(totals.loss)}</TableCell>
                                        <TableCell className="px-3 py-2 text-right font-mono text-rose-700 bg-rose-50/30">{fmt(totalLossPct, 2)}%</TableCell>
                                        <TableCell colSpan={2} />
                                    </TableRow>
                                </tfoot>
                            )}
                        </Table>
                    </div>
                </div>

                {/* ── Summary strip ── */}
                {fields.length > 0 && (
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                        <div className="bg-gray-50 rounded-lg px-4 py-3">
                            <div className="text-xs text-gray-500">Items</div>
                            <div className="text-2xl font-medium">{fields.length}</div>
                        </div>
                        <div className="bg-gray-50 rounded-lg px-4 py-3">
                            <div className="text-xs text-gray-500">Gross issued</div>
                            <div className="text-2xl font-medium">{fmt(totals.gross)}<span className="text-sm text-gray-400 ml-0.5">g</span></div>
                        </div>
                        <div className="bg-gray-50 rounded-lg px-4 py-3">
                            <div className="text-xs text-gray-500">Converted</div>
                            <div className="text-2xl font-medium">{fmt(totals.conv)}<span className="text-sm text-gray-400 ml-0.5">g</span></div>
                        </div>
                        <div className="bg-rose-50 rounded-lg px-4 py-3">
                            <div className="text-xs text-rose-700">Total loss</div>
                            <div className="text-2xl font-medium text-rose-700">{fmt(totalLossPct, 2)}%</div>
                        </div>
                    </div>
                )}

                {/* ── Actions ── */}
                <div className="flex justify-end items-center gap-3 pt-2">
                    <Button type="button" variant="outline" onClick={() => window.history.back()}>
                        Cancel
                    </Button>
                    <Button type="submit" className="bg-primary hover:bg-primary text-white gap-1.5" disabled={saving || !canSave}>
                        <Save className="size-4" />
                        {saveLabel(saving)}
                    </Button>
                </div>
            </form>
        </div>
    );
};

export default ReceiveFromRefinary;

import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { getLedgers, fetchPurity, fetchAssayIssueWithBillno } from "@/services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import {
    createAssayReceive,
    fetchNextAssayReceiveNo,
    fetchAssayReceiveForEdit,
    updateAssayReceiveForEdit,
} from "../../../services/apiService";
import { renderErrorTree } from "../../../Utils";
import { Trash2, Plus } from "lucide-react";
import { useEditDirty } from "@/hooks/useEditDirty";

const Field = ({ label, children }) => (
    <div className="flex flex-col gap-1.5">
        <Label className="text-xs font-medium text-gray-600">{label}</Label>
        {children}
    </div>
);

const ReceiveFromAssay = () => {
    const { toast } = useToast();
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

    const { fields, append, remove, replace } = useFieldArray({ control, name: "table" });

    const [saving, setSaving] = useState(false);
    const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
    const [meltingHouses, setMeltingHouses] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [issueNumbers, setIssueNumbers] = useState([]);

    useEffect(() => {
        async function fetchData() {
            const [mltRes, purityRes, billNoRes, issueRes] = await Promise.all([
                getLedgers({ type: "MLT" }),
                fetchPurity(),
                fetchNextAssayReceiveNo(),
                fetchAssayIssueWithBillno(""),
            ]);
            if (mltRes.success) setMeltingHouses(mltRes.data.results);
            if (purityRes.success) setPurityData(purityRes.data);
            if (billNoRes.success) setValue("form.billno", billNoRes.data.bill_no);
            if (issueRes.success) setIssueNumbers(issueRes.data.results);
        }

        fetchData().then(() => {
            if (id) {
                fetchAssayReceiveForEdit(id).then((data) => {
                    if (data.success) {
                        const d = data.data;
                        setValue("form.date1", d.date1);
                        setValue("form.billno", d.billno);
                        setValue("form.ldgr", d.ldgr);
                        setValue("form.ldgr_name", d.ldgr_name || "");
                        replace(d.assayreceivedetail_set || []);
                        reset(getValues(), { keepValues: true, keepDirty: false });
                        resetTableDirty();
                    }
                });
            }
        });
    }, []);

    const handleIssueFetch = async () => {
        const issue_slip_no = getValues("form.issue_slip_no");
        if (!issue_slip_no) return;
        const data = await fetchAssayIssueWithBillno(issue_slip_no);
        if (!data.success) return;

        const rows = data.data.results
            .filter((r) => r.billno === issue_slip_no)
            .flatMap((r) =>
                r.assayissuedetail_set.map((item) => ({
                    ...item,
                    issue_no: r.billno,
                    conv_purity: "",
                    conv_nw: "",
                    loss_wt: "",
                    loss_per: "",
                    remarks: "",
                    is_cornet: false,
                }))
            );
        replace(rows);
        markTableDirty();
    };

    const handleAddCornetRow = () => {
        // Add an extra row representing the cornet output, defaulting to 99.5 purity
        const firstRow = fields[0];
        const cornetRow = {
            issue_no: firstRow?.issue_no || getValues("form.issue_slip_no"),
            item: firstRow?.item || "",
            packet: firstRow?.packet || "",
            metal_purity: firstRow?.metal_purity || "",
            pcs: 0,
            ct: 0,
            gw: 0,
            conv_purity: "99.5",
            conv_nw: "",
            loss_wt: "",
            loss_per: "",
            remarks: "Cornet",
            is_cornet: true,
        };
        append(cornetRow);
        markTableDirty();
    };

    const onSubmit = () => {
        const form = { ...getValues("form") };
        const tableRows = getValues("table");
        delete form.issue_slip_no;
        delete form.ldgr_name;
        form.assayreceivedetail_set = tableRows;

        setSaving(true);
        (id ? updateAssayReceiveForEdit(form, id) : createAssayReceive(form))
            .then((response) => {
                if (response.success) {
                    toast({ title: "Saved successfully!" });
                    setTimeout(() => navigate("/manufacturing/receive/assay/"), 1500);
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
        <div className="mt-4 px-4">
            <form
                className="p-6 shadow-lg rounded-lg bg-white space-y-6"
                onSubmit={handleSubmit(onSubmit)}
            >
                <h2 className="text-center font-bold text-primary text-lg tracking-wide">
                    {id ? "EDIT" : "ADD"} RECEIVE FROM ASSAY
                </h2>
                <p className="text-center text-xs text-gray-500 -mt-4">
                    Mark refined cornet rows with the <span className="font-semibold">Cornet</span> checkbox. Cornet gold goes directly to fine-gold stock and bypasses the refinery.
                </p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Field label="Date">
                        <Input type="date" {...register("form.date1")} required className="max-w-[170px]" />
                    </Field>

                    <Field label="Bill No">
                        <div className="text-sm font-mono px-3 py-2 bg-gray-50 rounded border border-gray-200 h-9 flex items-center max-w-[170px]">
                            {watch("form.billno") || <span className="text-accent-400 text-xs">Auto-generating…</span>}
                        </div>
                    </Field>

                    <Field label="Melting House">
                        <Input
                            list="melting_list"
                            {...register("form.ldgr_name")}
                            onChange={(e) => {
                                const match = meltingHouses.find((r) => r.ac_name === e.target.value);
                                if (match) setValue("form.ldgr", match.id);
                            }}
                            placeholder="Select melting house..."
                            required
                        />
                        <Input type="hidden" {...register("form.ldgr")} />
                        <datalist id="melting_list">
                            {meltingHouses.map((r) => (
                                <option key={r.id} value={r.ac_name} />
                            ))}
                        </datalist>
                    </Field>

                    <Field label="Assay Issue No">
                        <div className="flex gap-2">
                            <Input
                                list="issue_list"
                                {...register("form.issue_slip_no")}
                                placeholder="Enter assay issue no..."
                                onBlur={handleIssueFetch}
                            />
                            <Button type="button" variant="outline" onClick={handleIssueFetch} className="shrink-0">
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

                <div className="overflow-x-auto rounded border border-gray-200">
                    <Table className="w-full text-sm">
                        <TableHeader>
                            <TableRow className="bg-accent-100 text-primary">
                                <TableHead className="w-10 px-3 py-2">#</TableHead>
                                <TableHead className="w-16 px-3 py-2 text-center">Cornet</TableHead>
                                <TableHead className="px-3 py-2 whitespace-nowrap">Issue Voucher</TableHead>
                                <TableHead className="px-3 py-2">Item</TableHead>
                                <TableHead className="px-3 py-2">Purity</TableHead>
                                <TableHead className="px-3 py-2 whitespace-nowrap">Gross Wt (g)</TableHead>
                                <TableHead className="px-3 py-2 whitespace-nowrap">Conv. Purity</TableHead>
                                <TableHead className="px-3 py-2 whitespace-nowrap">Conv. Wt (g)</TableHead>
                                <TableHead className="px-3 py-2 whitespace-nowrap">Loss Wt (g)</TableHead>
                                <TableHead className="px-3 py-2 whitespace-nowrap">Loss %</TableHead>
                                <TableHead className="px-3 py-2">Remarks</TableHead>
                                <TableHead className="w-10 px-3 py-2"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {fields.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={12} className="text-center text-gray-400 py-8">
                                        Fetch an assay issue number above to load items.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                fields.map((item, index) => {
                                    const isCornet = watch(`table.${index}.is_cornet`);
                                    return (
                                        <TableRow
                                            key={item.id}
                                            className={isCornet ? "bg-amber-50" : (index % 2 === 0 ? "bg-white" : "bg-gray-50")}
                                        >
                                            <TableCell className="px-3 py-1.5 text-gray-500 text-xs">{index + 1}</TableCell>

                                            <TableCell className="px-2 py-1 text-center">
                                                <input
                                                    type="checkbox"
                                                    {...register(`table.${index}.is_cornet`)}
                                                    onChange={(e) => {
                                                        setValue(`table.${index}.is_cornet`, e.target.checked);
                                                        if (e.target.checked) {
                                                            setValue(`table.${index}.conv_purity`, "99.5");
                                                        }
                                                    }}
                                                    className="size-4"
                                                    title="Mark as cornet (goes to fine-gold stock)"
                                                />
                                            </TableCell>

                                            <TableCell className="px-3 py-1.5 font-mono text-xs">{item.issue_no}</TableCell>
                                            <TableCell className="px-3 py-1.5">{item.item}</TableCell>
                                            <TableCell className="px-3 py-1.5">{item.metal_purity}</TableCell>
                                            <TableCell className="px-3 py-1.5 text-right">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</TableCell>

                                            <TableCell className="px-2 py-1">
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

                                            <TableCell className="px-2 py-1">
                                                <Input
                                                    type="number"
                                                    step="0.001"
                                                    {...register(`table.${index}.conv_nw`)}
                                                    className="h-8 text-sm w-24"
                                                    placeholder="0.000"
                                                />
                                            </TableCell>

                                            <TableCell className="px-2 py-1">
                                                <Input
                                                    type="number"
                                                    step="0.001"
                                                    {...register(`table.${index}.loss_wt`)}
                                                    className="h-8 text-sm w-24"
                                                    placeholder="0.000"
                                                />
                                            </TableCell>

                                            <TableCell className="px-2 py-1">
                                                <Input
                                                    type="number"
                                                    step="0.001"
                                                    {...register(`table.${index}.loss_per`)}
                                                    className="h-8 text-sm w-20"
                                                    placeholder="0.000"
                                                />
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
                                    );
                                })
                            )}
                        </TableBody>
                    </Table>
                </div>

                {fields.length > 0 && (
                    <div className="flex justify-start">
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={handleAddCornetRow}
                            className="text-amber-600 border-amber-300 hover:bg-amber-50"
                        >
                            <Plus className="size-4 mr-1" /> Add Cornet Row
                        </Button>
                    </div>
                )}

                <div className="flex justify-end items-center gap-3 pt-2 border-t border-gray-100">
                    <Button type="button" variant="outline" onClick={() => window.history.back()}>
                        Cancel
                    </Button>
                    <Button type="submit" className="bg-primary hover:bg-primary text-white" disabled={saving || !canSave}>
                        {saveLabel(saving)}
                    </Button>
                </div>
            </form>
        </div>
    );
};

export default ReceiveFromAssay;

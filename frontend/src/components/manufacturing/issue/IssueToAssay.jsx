import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableBody, TableHeader, TableHead } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { fetchMainItem, fetchPurity, getLedgers, fetchPackets, fetchAvailableMeltingReceives } from "@/services/apiService";
import { createAssayIssue, fetchNextAssayIssueNo, fetchAssayIssueForEdit, updateAssayIssueForEdit } from "../../../services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";
import { useParams, useNavigate } from "react-router-dom";
import { SquarePen, Trash2 } from "lucide-react";
import { renderErrorTree } from "../../../Utils";

const Field = ({ label, children }) => (
    <div className="flex flex-col gap-1.5">
        <Label className="text-xs font-medium text-gray-600">{label}</Label>
        {children}
    </div>
);

const tableDefault = {
    packet: "",
    item: "",
    metal_purity: "",
    remarks: "",
    pcs: "",
    ct: "",
    gw: "",
};

const IssueToAssay = () => {
    const { toast } = useToast();
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();
    const { id } = useParams();
    const navigate = useNavigate();

    const { register, handleSubmit, control, reset, watch, setValue, getValues, setFocus, formState: { isDirty } } = useForm({
        defaultValues: {
            form: {
                date1: new Date().toISOString().split("T")[0],
                billno: "",
                ldgr: "",
                ldgr_name: "",
                melt_recv: "",
            },
            table: { ...tableDefault },
        },
    });

    const [rs, setRows] = useState([]);
    const [saving, setSaving] = useState(false);
    const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
    const [meltingHouses, setMeltingHouses] = useState([]);
    const [mainItemData, setMainItemData] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [packets, setPackets] = useState([]);
    const [availableReceives, setAvailableReceives] = useState([]);

    useEffect(() => {
        async function fetchData() {
            const [mltRes, itemRes, purityRes, packetRes, billNoRes, recvRes] = await Promise.all([
                getLedgers({ type: "MLT" }),
                fetchMainItem(),
                fetchPurity(),
                fetchPackets(),
                fetchNextAssayIssueNo(),
                fetchAvailableMeltingReceives(id || null),
            ]);
            if (mltRes.success) setMeltingHouses(mltRes.data.results);
            if (itemRes.success) setMainItemData(itemRes.data.results ?? itemRes.data);
            if (purityRes.success) setPurityData(purityRes.data.results ?? purityRes.data);
            if (packetRes.success) setPackets(packetRes.data.results ?? packetRes.data);
            if (billNoRes.success) setValue("form.billno", billNoRes.data.bill_no);
            if (recvRes.success) setAvailableReceives(recvRes.data.results ?? []);
        }

        fetchData().then(() => {
            if (id) {
                fetchAssayIssueForEdit(id)
                    .then((response) => {
                        if (response.success) {
                            Object.keys(response.data).forEach((key) => {
                                setValue(`form.${key}`, response.data[key]);
                            });
                            if (response.data.assayissuedetail_set) {
                                setRows(response.data.assayissuedetail_set);
                            }
                            reset(getValues(), { keepValues: true, keepDirty: false });
                            resetTableDirty();
                        }
                    })
                    .catch(console.error);
            }
        });
    }, []);

    // Auto-fill table rows when a melting receive is selected
    const handleReceiveLoad = (billno) => {
        if (!billno) return;
        const recv = availableReceives.find((r) => r.billno === billno);
        if (!recv) return;

        const details = recv.meltingreceivedetail_set || [];
        if (details.length === 0) {
            toast({ title: "Selected receive has no detail rows." });
            return;
        }

        // Map melting receive detail rows → assay issue rows
        // Use conv_purity (the purity AFTER melting) as the issue purity for the assay sample
        const newRows = details.map((d) => ({
            packet: d.packet,
            item: d.item,
            metal_purity: d.conv_purity || d.metal_purity,
            pcs: d.pcs,
            ct: d.ct,
            gw: "",          // operator sets the sample weight manually
            remarks: `Sample from melting recv ${recv.billno}`,
        }));

        setRows(newRows);
        markTableDirty();
        toast({ title: `Loaded ${newRows.length} row(s) from ${recv.billno}. Set the sample GW for each row.` });
    };

    const handleAddRow = () => {
        const row = getValues("table");
        // Validate required fields: item, purity, and gw
        if (!row.item || !row.metal_purity || !row.gw) {
            toast({ title: "Item, Purity, and Gross Weight are required before adding row." });
            return;
        }
        setRows((prev) => [...prev, { ...row }]);
        markTableDirty();
        reset({ form: { ...getValues("form") }, table: { ...tableDefault } });
        setFocus("table.packet");
    };

    const handleEdit = (index) => {
        reset({ form: { ...getValues("form") }, table: { ...rs[index] } });
        setRows((prev) => prev.filter((_, i) => i !== index));
        markTableDirty();
    };

    const handleDelete = (index) => {
        setRows((prev) => prev.filter((_, i) => i !== index));
        markTableDirty();
    };

    const handleKeyDown = (e) => {
        if (e.key === "Tab") {
            e.preventDefault();
            handleAddRow();
        }
    };

    const onSubmit = () => {
        if (rs.length === 0) {
            toast({ title: "Please add at least one item." });
            return;
        }
        const form = { ...getValues("form") };
        delete form.ldgr_name;
        if (!form.melt_recv) delete form.melt_recv;
        form.assayissuedetail_set = rs;

        setSaving(true);
        (id ? updateAssayIssueForEdit(form, id) : createAssayIssue(form))
            .then((response) => {
                if (response.success) {
                    toast({ title: id ? "Updated successfully!" : "Saved successfully!" });
                    setTimeout(() => navigate("/manufacturing/issue/assay/"), 1500);
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

    const selectedRecv = watch("form.melt_recv");

    return (
        <div className="mt-4 px-4">
            <form
                className="p-6 shadow-lg rounded-lg bg-white space-y-6"
                onSubmit={handleSubmit(onSubmit)}
            >
                <h2 className="text-center font-bold text-primary text-lg tracking-wide">
                    {id ? "EDIT" : "ADD"} FIRE ASSAY ISSUE
                </h2>
                <p className="text-center text-xs text-gray-500 -mt-4">
                    Issue a small sample to the melting house for fire assay testing.
                </p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Field label="Date">
                        <Input type="date" min={fyMin} max={fyMax} {...register("form.date1")} required className="max-w-[170px]" />
                    </Field>

                    <Field label="Bill No">
                        <div className="text-sm font-mono px-3 py-2 bg-gray-50 rounded border border-gray-200 h-9 flex items-center">
                            {watch("form.billno") || <span className="text-accent-400 text-xs">Auto-generating…</span>}
                        </div>
                    </Field>

                    <Field label="Melting House">
                        <SearchableComboBox
                            options={meltingHouses}
                            value={watch("form.ldgr_name") ?? ""}
                            onSelect={(opt) => {
                                setValue("form.ldgr_name", opt.ac_name)
                                setValue("form.ldgr", opt.id)
                            }}
                            placeholder="Search melting house…"
                            autoFocus
                        />
                        <input type="hidden" {...register("form.ldgr")} />
                    </Field>
                </div>

                {/* ── Melting Receive Reference ── */}
                <div className="rounded border border-amber-200 bg-amber-50/40 p-3">
                    <div className="flex flex-wrap items-end gap-3">
                        <div className="flex flex-col gap-1 flex-1 min-w-[220px]">
                            <Label className="text-xs font-medium text-gray-600">
                                Source Melting Receive <span className="text-gray-400 font-normal">(optional — auto-fills rows)</span>
                            </Label>
                            <Controller
                                name="form.melt_recv"
                                control={control}
                                render={({ field }) => (
                                    <Select
                                        value={field.value || ""}
                                        onValueChange={(val) => {
                                            field.onChange(val);
                                        }}
                                    >
                                        <SelectTrigger className="h-9 text-sm">
                                            <SelectValue placeholder={
                                                availableReceives.length === 0
                                                    ? "No available melting receives"
                                                    : "Select a melting receive to reference…"
                                            } />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {availableReceives.map((r) => (
                                                <SelectItem key={r.billno} value={r.billno}>
                                                    {r.billno} — {r.ldgr_name} — {r.date1}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )}
                            />
                        </div>
                        <Button
                            type="button"
                            variant="outline"
                            disabled={!selectedRecv}
                            onClick={() => handleReceiveLoad(selectedRecv)}
                            className="text-amber-700 border-amber-300 hover:bg-amber-100"
                        >
                            Load Rows
                        </Button>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-2">
                        Each melting receive can only be referenced by one assay issue. Already-referenced receives are hidden from this list.
                        Set the GW (sample weight) for each loaded row before saving.
                    </p>
                </div>

                <div className="overflow-x-auto rounded border border-gray-200">
                    <Table className="w-full text-sm">
                        <colgroup>
                            <col style={{width:"52px"}} />
                            <col style={{width:"110px"}} />
                            <col style={{width:"110px"}} />
                            <col style={{width:"120px"}} />
                            <col style={{width:"72px"}} />
                            <col style={{width:"90px"}} />
                            <col style={{width:"90px"}} />
                            <col />
                        </colgroup>
                        <TableHeader>
                            <TableRow className="bg-accent-100 text-primary">
                                <TableHead className="px-3 py-2"></TableHead>
                                <TableHead className="px-3 py-2">Packet</TableHead>
                                <TableHead className="px-3 py-2">Item</TableHead>
                                <TableHead className="px-3 py-2">Purity</TableHead>
                                <TableHead className="px-3 py-2 text-right">Pcs</TableHead>
                                <TableHead className="px-3 py-2 text-right">Ct</TableHead>
                                <TableHead className="px-3 py-2 text-right">GW (g)</TableHead>
                                <TableHead className="px-3 py-2">Remarks</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            <TableRow className="bg-accent-50">
                                <TableCell className="px-2 py-1 text-center text-gray-400 text-xs">new</TableCell>

                                <TableCell className="px-2 py-1">
                                    <Input
                                        list="packet_list"
                                        {...register("table.packet")}
                                        className="h-8 text-sm w-full"
                                        placeholder="Packet"
                                    />
                                    <datalist id="packet_list">
                                        {packets.map((p) => (
                                            <option key={p.id} value={p.pckt_no} />
                                        ))}
                                    </datalist>
                                </TableCell>

                                <TableCell className="px-2 py-1">
                                    <Input
                                        list="item_list"
                                        {...register("table.item")}
                                        className="h-8 text-sm w-full"
                                        placeholder="Item"
                                    />
                                    <datalist id="item_list">
                                        {mainItemData.map((item) => (
                                            <option key={item.id} value={item.short_code}>
                                                {item.item_name}
                                            </option>
                                        ))}
                                    </datalist>
                                </TableCell>

                                <TableCell className="px-2 py-1">
                                    <Controller
                                        name="table.metal_purity"
                                        control={control}
                                        render={({ field }) => (
                                            <Select onValueChange={field.onChange} value={field.value || ""}>
                                                <SelectTrigger className="h-8 text-sm w-full">
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
                                        {...register("table.pcs")}
                                        className="h-8 text-sm w-full text-right"
                                        placeholder="0"
                                    />
                                </TableCell>

                                <TableCell className="px-2 py-1">
                                    <Input
                                        type="number"
                                        step="0.001"
                                        min="0"
                                        {...register("table.ct")}
                                        className="h-8 text-sm w-full text-right"
                                        placeholder="0.000"
                                        onBlur={(e) => {
                                            if (e.target.value) {
                                                const val = parseFloat(e.target.value);
                                                if (!isNaN(val)) e.target.value = val.toFixed(3);
                                            }
                                        }}
                                    />
                                </TableCell>

                                <TableCell className="px-2 py-1">
                                    <Input
                                        type="number"
                                        step="0.001"
                                        min="0"
                                        {...register("table.gw")}
                                        className="h-8 text-sm w-full text-right"
                                        placeholder="0.000"
                                        onBlur={(e) => {
                                            if (e.target.value) {
                                                const val = parseFloat(e.target.value);
                                                if (!isNaN(val)) e.target.value = val.toFixed(3);
                                            }
                                        }}
                                    />
                                </TableCell>

                                <TableCell className="px-2 py-1">
                                    <Input
                                        type="text"
                                        onKeyDown={handleKeyDown}
                                        {...register("table.remarks")}
                                        className="h-8 text-sm w-full"
                                        placeholder="Remarks"
                                    />
                                </TableCell>
                            </TableRow>

                            {rs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="text-center text-gray-400 py-6 text-xs">
                                        No items added yet. Select a melting receive above to auto-fill, or fill the row manually and press Tab or click Add.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                rs.map((item, index) => (
                                    <TableRow
                                        key={index}
                                        className={index % 2 === 0 ? "bg-white" : "bg-gray-50"}
                                    >
                                        <TableCell className="px-2 py-1.5">
                                            <div className="flex gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => handleEdit(index)}
                                                    className="text-accent-400 hover:text-primary"
                                                    title="Edit"
                                                >
                                                    <SquarePen className="size-4" />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDelete(index)}
                                                    className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="size-4" />
                                                </button>
                                            </div>
                                        </TableCell>
                                        <TableCell className="px-3 py-1.5 font-mono text-xs">{item.packet}</TableCell>
                                        <TableCell className="px-3 py-1.5">{item.item}</TableCell>
                                        <TableCell className="px-3 py-1.5">{item.metal_purity}</TableCell>
                                        <TableCell className="px-3 py-1.5 text-right">{item.pcs}</TableCell>
                                        <TableCell className="px-3 py-1.5 text-right">{typeof item.ct === 'number' ? item.ct.toFixed(3) : item.ct}</TableCell>
                                        <TableCell className="px-3 py-1.5 text-right font-medium">{typeof item.gw === 'number' ? item.gw.toFixed(3) : (item.gw || <span className="text-amber-500">set GW</span>)}</TableCell>
                                        <TableCell className="px-3 py-1.5 text-gray-500">{item.remarks}</TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

                <div className="flex justify-start">
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleAddRow}
                        className="text-primary border-accent-300 hover:bg-accent-50"
                    >
                        + Add Row
                    </Button>
                </div>

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

export default IssueToAssay;

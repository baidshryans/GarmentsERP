import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableBody, TableHeader, TableHead } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { fetchMainItem, fetchPurity, getLedgers, fetchPackets, fetchMeltingReceive, fetchAssayReceive } from "@/services/apiService";
import { createRefinaryIssue, fetchNextRefinaryIssueNo, fetchRefinaryIssueForEdit, updateRefinaryIssueForEdit } from "../../../services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import { SquarePen, Trash2 } from "lucide-react";
import { renderErrorTree } from "../../../Utils";

/* Vertical label + input stacking */
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

const IssueToRefinary = () => {
    const { toast } = useToast();
    const { id } = useParams();
    const navigate = useNavigate();

    const { register, handleSubmit, control, reset, watch, setValue, getValues, setFocus } = useForm({
        defaultValues: {
            form: {
                date1: new Date().toISOString().split("T")[0],
                billno: "",
                ldgr: "",
                ldgr_name: "",
            },
            table: { ...tableDefault },
        },
    });

    const [rs, setRows] = useState([]);
    const [saving, setSaving] = useState(false);
    const [refineries, setRefineries] = useState([]);
    const [mainItemData, setMainItemData] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [packets, setPackets] = useState([]);

    // Source-receive picker state
    const [sourceType, setSourceType] = useState("");          // "melting" | "assay" | ""
    const [sourceOptions, setSourceOptions] = useState([]);     // list of receives for the picked type
    const [selectedSourceId, setSelectedSourceId] = useState(""); // chosen receive id

    useEffect(() => {
        async function fetchData() {
            const [refRes, itemRes, purityRes, packetRes, orderNoRes] = await Promise.all([
                getLedgers({ type: "REF" }),
                fetchMainItem(),
                fetchPurity(),
                fetchPackets(),
                fetchNextRefinaryIssueNo(),
            ]);
            if (refRes.success) setRefineries(refRes.data.results);
            if (itemRes.success) setMainItemData(itemRes.data.results ?? itemRes.data);
            if (purityRes.success) setPurityData(purityRes.data.results ?? purityRes.data);
            if (packetRes.success) setPackets(packetRes.data.results ?? packetRes.data);
            if (orderNoRes.success) setValue("form.billno", orderNoRes.data.bill_no);
        }

        fetchData().then(() => {
            if (id) {
                fetchRefinaryIssueForEdit(id)
                    .then((response) => {
                        if (response.success) {
                            Object.keys(response.data).forEach((key) => {
                                setValue(`form.${key}`, response.data[key]);
                            });
                            if (response.data.refinaryissuedetail_set) {
                                setRows(response.data.refinaryissuedetail_set);
                            }
                        }
                    })
                    .catch(console.error);
            }
        });
    }, []);

    // Load source options whenever the picker type changes
    useEffect(() => {
        async function loadSourceOptions() {
            if (sourceType === "melting") {
                const res = await fetchMeltingReceive({ page: 1 });
                setSourceOptions(res.success ? (res.data.results || []) : []);
            } else if (sourceType === "assay") {
                const res = await fetchAssayReceive({ page: 1 });
                setSourceOptions(res.success ? (res.data.results || []) : []);
            } else {
                setSourceOptions([]);
            }
            setSelectedSourceId("");
        }
        loadSourceOptions();
    }, [sourceType]);

    const handleLoadSourceItems = () => {
        if (!sourceType || !selectedSourceId) {
            toast({ title: "Select a source type and receive voucher first." });
            return;
        }
        const receive = sourceOptions.find((o) => String(o.id) === String(selectedSourceId));
        if (!receive) return;

        const detailKey = sourceType === "melting" ? "meltingreceivedetail_set" : "assayreceivedetail_set";
        const details = receive[detailKey] || [];
        // Skip cornet rows — cornet is already fine gold, bypasses the refinery.
        const newRows = details
            .filter((d) => !d.is_cornet)
            .map((d) => ({
                packet: d.packet,
                item: d.item,
                metal_purity: d.conv_purity,   // refinery input uses the converted purity from melting
                pcs: d.pcs,
                ct: d.ct,
                gw: d.conv_nw,                 // use the converted weight (actually received back)
                remarks: `From ${sourceType} receive ${receive.billno}`,
            }));
        if (newRows.length === 0) {
            toast({ title: "No loadable items in this receive (all rows may be cornet)." });
            return;
        }
        setRows((prev) => [...prev, ...newRows]);
        toast({ title: `Loaded ${newRows.length} row(s) from ${receive.billno}.` });
    };

    const handleAddRow = () => {
        const row = getValues("table");
        // Validate required fields: item, purity, and gw
        if (!row.item || !row.metal_purity || !row.gw) {
            toast({ title: "Item, Purity, and Gross Weight are required before adding row." });
            return;
        }
        setRows((prev) => [...prev, { ...row }]);
        reset({ form: { ...getValues("form") }, table: { ...tableDefault } });
        setFocus("table.packet");
    };

    const handleEdit = (index) => {
        reset({ form: { ...getValues("form") }, table: { ...rs[index] } });
        setRows((prev) => prev.filter((_, i) => i !== index));
    };

    const handleDelete = (index) => {
        setRows((prev) => prev.filter((_, i) => i !== index));
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
        form.refinaryissuedetail_set = rs;

        setSaving(true);
        (id ? updateRefinaryIssueForEdit(form, id) : createRefinaryIssue(form))
            .then((response) => {
                if (response.success) {
                    toast({ title: "Saved successfully!" });
                    setTimeout(() => navigate("/manufacturing/issue/refinary/"), 1500);
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
                    {id ? "EDIT" : "ADD"} ISSUE TO REFINERY
                </h2>

                {/* ── Header fields ── */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Field label="Date">
                        <Input type="date" {...register("form.date1")} required className="max-w-[170px]" />
                    </Field>

                    <Field label="Bill No">
                        <div className="text-sm font-mono px-3 py-2 bg-gray-50 rounded border border-gray-200 h-9 flex items-center">
                            {watch("form.billno") || <span className="text-violet-400 text-xs">Auto-generating…</span>}
                        </div>
                    </Field>

                    <Field label="Refinery House">
                        <SearchableComboBox
                            options={refineries}
                            value={watch("form.ldgr_name") ?? ""}
                            onSelect={(opt) => {
                                setValue("form.ldgr_name", opt.ac_name)
                                setValue("form.ldgr", opt.id)
                            }}
                            placeholder="Search refinery…"
                            autoFocus
                        />
                        <input type="hidden" {...register("form.ldgr")} />
                    </Field>
                </div>

                {/* ── Source Receive Picker (optional) ── */}
                <div className="rounded border border-amber-200 bg-amber-50/40 p-3">
                    <div className="flex flex-wrap items-end gap-3">
                        <div className="flex flex-col gap-1 min-w-[160px]">
                            <Label className="text-xs font-medium text-gray-600">Source Receive (optional)</Label>
                            <Select value={sourceType} onValueChange={setSourceType}>
                                <SelectTrigger className="h-9 text-sm">
                                    <SelectValue placeholder="— None —" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="melting">Melting Receive</SelectItem>
                                    <SelectItem value="assay">Assay Receive</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex flex-col gap-1 min-w-[220px] flex-1">
                            <Label className="text-xs font-medium text-gray-600">Bill No</Label>
                            <Select
                                value={selectedSourceId}
                                onValueChange={setSelectedSourceId}
                                disabled={!sourceType}
                            >
                                <SelectTrigger className="h-9 text-sm">
                                    <SelectValue placeholder={sourceType ? "Select a receive voucher..." : "Pick a source type first"} />
                                </SelectTrigger>
                                <SelectContent>
                                    {sourceOptions.map((o) => (
                                        <SelectItem key={o.id} value={String(o.id)}>
                                            {o.billno} — {o.ldgr_name} — {o.date1}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <Button
                            type="button"
                            variant="outline"
                            onClick={handleLoadSourceItems}
                            disabled={!sourceType || !selectedSourceId}
                            className="text-amber-700 border-amber-300 hover:bg-amber-100"
                        >
                            Load Items
                        </Button>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-2">
                        Loads rows from the selected melting or assay receive (cornet rows are skipped — cornet bypasses the refinery).
                    </p>
                </div>

                {/* ── Items table ── */}
                <div className="overflow-x-auto rounded border border-gray-200">
                    <Table className="w-full text-sm">
                        <colgroup>
                            <col style={{width:"52px"}} />   {/* actions */}
                            <col style={{width:"110px"}} />  {/* packet */}
                            <col style={{width:"110px"}} />  {/* item */}
                            <col style={{width:"120px"}} />  {/* purity */}
                            <col style={{width:"72px"}} />   {/* pcs */}
                            <col style={{width:"90px"}} />   {/* ct */}
                            <col style={{width:"90px"}} />   {/* gw */}
                            <col />                          {/* remarks — fills remaining */}
                        </colgroup>
                        <TableHeader>
                            <TableRow className="bg-violet-100 text-primary">
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
                            {/* Input row */}
                            <TableRow className="bg-violet-50">
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
                                                if (!isNaN(val)) {
                                                    e.target.value = val.toFixed(3);
                                                }
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
                                                if (!isNaN(val)) {
                                                    e.target.value = val.toFixed(3);
                                                }
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

                            {/* Saved rows */}
                            {rs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} className="text-center text-gray-400 py-6 text-xs">
                                        No items added yet. Fill the row above and press Tab or click Add.
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
                                                    className="text-violet-400 hover:text-primary"
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
                                        <TableCell className="px-3 py-1.5 text-right">{typeof item.gw === 'number' ? item.gw.toFixed(3) : item.gw}</TableCell>
                                        <TableCell className="px-3 py-1.5 text-gray-500">{item.remarks}</TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Add row button */}
                <div className="flex justify-start">
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleAddRow}
                        className="text-primary border-violet-300 hover:bg-violet-50"
                    >
                        + Add Row
                    </Button>
                </div>

                {/* ── Actions ── */}
                <div className="flex justify-end items-center gap-3 pt-2 border-t border-gray-100">
                    <Button type="button" variant="outline" onClick={() => window.history.back()}>
                        Cancel
                    </Button>
                    <Button type="submit" className="bg-primary hover:bg-primary text-white" disabled={saving}>
                        Save
                    </Button>
                </div>
            </form>
        </div>
    );
};

export default IssueToRefinary;

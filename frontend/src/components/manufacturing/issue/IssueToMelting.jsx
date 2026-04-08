import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableBody, TableHeader, TableHead } from "@/components/ui/table";
import { fetchMainItem, fetchPurity, getLedgers, fetchPackets } from "@/services/apiService";
import { createMeltingIssue, fetchNextMeltingIssueNo, fetchMeltingIssueForEdit, updateMeltingIssueForEdit } from "../../../services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import { Edit, Trash2 } from "lucide-react";
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

const IssueToMelting = () => {
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
    const [meltingHouses, setMeltingHouses] = useState([]);
    const [mainItemData, setMainItemData] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [packets, setPackets] = useState([]);

    useEffect(() => {
        async function fetchData() {
            const [mltRes, itemRes, purityRes, packetRes, billNoRes] = await Promise.all([
                getLedgers({ type: "MLT" }),
                fetchMainItem(),
                fetchPurity(),
                fetchPackets(),
                fetchNextMeltingIssueNo(),
            ]);
            if (mltRes.success) setMeltingHouses(mltRes.data.results);
            if (itemRes.success) setMainItemData(itemRes.data);
            if (purityRes.success) setPurityData(purityRes.data);
            if (packetRes.success) setPackets(packetRes.data.results ?? packetRes.data);
            if (billNoRes.success) setValue("form.billno", billNoRes.data.bill_no);
        }

        fetchData().then(() => {
            if (id) {
                fetchMeltingIssueForEdit(id)
                    .then((response) => {
                        if (response.success) {
                            Object.keys(response.data).forEach((key) => {
                                setValue(`form.${key}`, response.data[key]);
                            });
                            if (response.data.meltingissuedetail_set) {
                                setRows(response.data.meltingissuedetail_set);
                            }
                        }
                    })
                    .catch(console.error);
            }
        });
    }, []);

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
        form.meltingissuedetail_set = rs;

        (id ? updateMeltingIssueForEdit(form, id) : createMeltingIssue(form))
            .then((response) => {
                if (response.success) {
                    toast({ title: "Saved successfully!" });
                    setTimeout(() => navigate("/manufacturing/issue/melting/"), 1500);
                } else {
                    toast({
                        title: "Submission failed.",
                        description: renderErrorTree(response.error),
                    });
                }
            })
            .catch(() => toast({ title: "An error occurred. Please try again." }));
    };

    useF4Submit(handleSubmit(onSubmit));

    return (
        <div className="mt-4 px-4">
            <form
                className="p-6 shadow-lg rounded-lg bg-white space-y-6"
                onSubmit={handleSubmit(onSubmit)}
            >
                <h2 className="text-center font-bold text-primary text-lg tracking-wide">
                    {id ? "EDIT" : "ADD"} ISSUE TO MELTING
                </h2>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Field label="Date">
                        <Input type="date" {...register("form.date1")} required className="max-w-[170px]" />
                    </Field>

                    <Field label="Bill No">
                        <div className="text-sm font-mono px-3 py-2 bg-gray-50 rounded border border-gray-200 h-9 flex items-center">
                            {watch("form.billno") || <span className="text-violet-400 text-xs">Auto-generating…</span>}
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
                            autoFocus
                            required
                        />
                        <Input type="hidden" {...register("form.ldgr")} />
                        <datalist id="melting_list">
                            {meltingHouses.map((r) => (
                                <option key={r.id} value={r.ac_name} />
                            ))}
                        </datalist>
                    </Field>
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
                                                    <Edit size={15} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDelete(index)}
                                                    className="text-red-400 hover:text-red-600"
                                                    title="Delete"
                                                >
                                                    <Trash2 size={15} />
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

                <div className="flex justify-end items-center gap-3 pt-2 border-t border-gray-100">
                    <Button type="button" variant="outline" onClick={() => window.history.back()}>
                        Cancel
                    </Button>
                    <Button type="submit" className="bg-primary hover:bg-primary text-white">
                        Save
                    </Button>
                </div>
            </form>
        </div>
    );
};

export default IssueToMelting;

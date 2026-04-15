import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { fetchBarcodes, fetchNextStockTransferNo, fetchStockTransferForEdit, updateStockTransferForEdit, fetchPackets, getLedgers } from "@/services/apiService";
import { createStockTransfer, fetchRetails } from "./services/apiService";
import { useNavigate, useParams } from "react-router-dom";
import { renderErrorTree } from "./Utils";
import { SquarePen, Trash2, ArrowRight, PackageCheck, SendHorizontal, Hash, Scale, Barcode, ScanBarcode } from "lucide-react";

const RetToRetstockTransfer = () => {
    const { toast } = useToast()
    const { id } = useParams()
    const { register: originalRegister, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
        defaultValues: {
            rate_18kt: 0,
            rate_22kt: 0,
            rate_24kt: 0,
            advance_amt
                :
                0,
            est_amount
                :
                0,
            date1: new Date().toISOString().split("T")[0],
            fix_gold_rate: false,
            salesman_1: null,
            form: {
                "date1": new Date().toISOString().split("T")[0],
                "invoice_date": new Date().toISOString().split("T")[0],
                "billno": "",
                "gst_billno": "",
                "ldgr": "",
                "sales_person": "",
                "sales_person2": "",
                "place_of_supply": "WB",
                "remarks": "",
                "freight_charge": 0,
                "freight_amt": 0,
                "mrp": 0,
                "discount": 0,
                "gst_type": "gst1",
                "sgst_per": 0,
                "cgst_per": 0,
                "igst_per": 0,
                "tcs_per": 0,
                "mode_of_transport": "",
            },
            table: {
                "bill_no": null,
                "date1": null,
                "po_no": "",
                "po_sl_no": null,
                "item": null,
                "barcode": null,
                "barcode_txt": "",
                "order_no": null,
                "sl_no": 0,
                "pcs": null,
                "gw": null,
                "size": "",
                "purity": null,
                "pending_pcs": null,
                "pending_gw": null,
                "making_type": "",
                "making_amt": null,
                "item_value": null,
                "remarks": "",
                "purchasevoucherdetails_set": [],
                details: {
                    "main_item": null,
                    "bill_no": "",
                    "date1": null,
                    "sub_item": null,
                    "sub_pcs": 0,
                    "sub_gw": 0,
                    "sub_ct": 0,
                    "metal_purity": null,
                    "loss": 0,
                    "tunch": 0,
                    "fine_wt": 0,
                    "packet": null,
                    "rate": 0,
                    "value": 0
                },
            },
        },
    });

    // Monkey-patching `register`
    const register = (name, options = {}) => {
        const registered = originalRegister(name, options);

        return {
            ...registered,
            onChange: (e) => {
                setCalculate(prev => prev + 1)
                if (options?.onChange) {
                    options.onChange(e); // Call user-defined onChange if provided
                }
                registered.onChange?.(e); // Call default RHF onChange
            },
        };
    };
    const [rs, setRows] = useState([]);
    const [barCodes, setBarcodes] = useState([]);
    const [statesData, setstatesData] = useState([]);
    const [salespersonData, setSalespersonData] = useState([]);
    const [mainItemData, setMainItemData] = useState([]);
    const [customers, setCustomers] = useState([]);
    const [karigars, setKarigars] = useState([])
    const [purityData, setPurityData] = useState([]);
    const [packets, setPackets] = useState([]);
    const [render, setRender] = useState(0);
    const [jobSlNos, setJobSlNos] = useState([]); // Initialize jobSlNos as an empty array
    const [hsns, setHSNs] = useState([]);
    const [retails, setRetails] = useState([]);
    const [calculate, setCalculate] = useState([]);
    const [isSent, setIsSent] = useState(false); // true once sender marks transfer as dispatched
    const navigate=useNavigate();

    const handleBlur = async (e) => {
        const jobId = e.target.value;
        const { slip_type } = getValues();
        const { ref_job_object_id } = getValues("table");
        const response = await fetchStoneIssuesFilterJobs(ref_job_object_id, slip_type);
        if (response.success) {
            const data = response.data.job_items;
            setJobSlNos(data);
        } else {
            toast({ title: "An error occurred. Please try again later." });
        }

    }

    const handleBlur1 = async (e) => {
        const { slip_type } = getValues();
        const { job_sl_object_id, ref_job_object_id } = getValues("table");
        console.log(`Slip type : ${slip_type}`);
        const response = await fetchStoneIssued(ref_job_object_id, job_sl_object_id, slip_type);
        if (response.success) {
            const data = response.data.packets;
            setPackets(data)
        } else {
            toast({ title: "An error occurred. Please try again later." });
        }

    }

    useEffect(() => {
        async function fetchData() {
            const [packets, barcodes, customers, states, salesperson, orderNo, mainItem, purity, poNo, retails] = await Promise.all([
                fetchPackets(),
                fetchBarcodes(),
                getLedgers(),
                getStates(),
                fetchSalesperson(),
                fetchNextStockTransferNo(),
                fetchMainItem(),
                fetchPurity(),
                fetchPos(),
                fetchRetails(),
            ]);
            if (packets.success) setPackets(packets.data.results);
            if (barcodes.success) setBarcodes(barcodes.data.results);

            if (customers.success) setCustomers(customers.data.results);
            if (states.success) setstatesData(states.data);
            if (salesperson.success) setSalespersonData(salesperson.data.results);
            if (!id && orderNo.success) setValue("form.billno", orderNo.data.bill_no);
            if (mainItem.success) setMainItemData(mainItem.data);
            if (purity.success) setPurityData(purity.data);
            if (poNo.success) setValue("po_no", poNo.data.po_no);
            if (retails.success) setRetails(retails.data.results);
        }
         fetchData().then(d => {
                if (id) {
                    fetchStockTransferForEdit(id)
                        .then((response) => {
                            Object.keys(response.data).forEach((key) => {
                                setValue(`form.${key}`, response.data[key]);
                            });

                            // Set items array
                            if (response.data.stocktransfermain_set) {
                                setRows(response.data.stocktransfermain_set);
                            }
                            // Lock form if already dispatched
                            if (response.data.sent_status) {
                                setIsSent(true);
                            }
                        })
                        .catch((error) => {
                            console.error('Error fetching manufacturing issue:', error);
                        });
                }
            });
    }, []);

    const hsn_current = watch('hsn');

    useEffect(() => {
        let hsn_ = hsns.find(e => e.hsn_no === hsn_current);


        if (hsn_) {
            setMainItemData(hsn_.item_set)

            const poc = getValues("form.place_of_supply")


            setValue('form.sgst_per', parseFloat(hsn_.sgst))
            setValue('form.cgst_per', parseFloat(hsn_.cgst))
            setValue('form.igst_per', poc == "WB" ? 0.0 : parseFloat(hsn_.igst))
        }
    }, [hsn_current]);


    const taxable_value_formula = "SUM(rs.item_value) + freight_amt"
    const total_incl_gst_formula = `${taxable_value_formula} + (${taxable_value_formula}) * (cgst_per / 100) + (${taxable_value_formula})* igst_per / 100 + (${taxable_value_formula}) * sgst_per / 100 `
    const tcs_amt_formula = `tcs_per * (${total_incl_gst_formula})`
    const main_formulas = {
        taxable_value: taxable_value_formula,
        cgst: `(${taxable_value_formula}) * (cgst_per / 100) `,
        igst: `(${taxable_value_formula})* igst_per / 100 `,
        sgst: `(${taxable_value_formula}) * sgst_per / 100 `,
        total_incl_gst: `(${total_incl_gst_formula}) - discount_amt`,
        tcs_amt: tcs_amt_formula,
        total_bill_value: `${tcs_amt_formula} + ${total_incl_gst_formula} - discount_amt`

    }


    const evaluateFormula = (formula, data) => {
        try {
            // Handle nested SUM operations first
            let processedFormula = formula.replace(/SUM\(([^)]+)\)/g, (match, path) => {
                const parts = path.trim().split('.');
                let array = data[parts[0]];
                if (!Array.isArray(array)) return 0;
                const sum = array.reduce((acc, item) => {
                    return parseFloat(acc) + parseFloat(item[parts[1]]);
                }, 0);
                return sum;
            });

            processedFormula = processedFormula.replace(/(\b[A-Za-z_][A-Za-z0-9_]*\b)|('[^']*')|(\d+)/g, (match, variable, quoted, number) => {
                if (quoted) return quoted; // Preserve anything inside single quotes
                if (number) return number; // Preserve numbers as they are

                if (data.hasOwnProperty(variable)) {
                    let value = data[variable];
                    return typeof value === "number" ? `(${value})` : `'${value}'`;
                }

                return "0"; // Default replacement if variable is not found
            });




            // Evaluate the final expression
            return new Function(`return ${processedFormula};`)()?.toFixed(2);
        } catch (error) {
            console.error("Formula evaluation error:", error);
            return "";
        }
    };

    const watchedFields = watch('form')
    useEffect(() => {
        console.log("change ryuns")
        const form = { ...getValues('form'), rs: rs };

        console.log(form)

        Object.keys(main_formulas).forEach((col) => {
            setValue(`form.${col}`, evaluateFormula(main_formulas[col], form));
        })

    }, [rs, watchedFields, calculate]);
    

    const onSubmit = (data) => {
        const form = getValues("form");
        form.stocktransfermain_set = [...rs];

          (id ? updateStockTransferForEdit(form, id) :                      createStockTransfer(form))
            .then((response) => {

                if (response.success) {
                    toast({
                        title: "Form submitted successfully!",
                    });  // Success 
                    setTimeout(()=>{
                        navigate("/inventory/stocktransfer");
                    },2000);
                    
                } else if (response.status < 500) {
                    toast({
                        title: "Form submission failed. Please try again.",
                        description: renderErrorTree(response.error),
                    });  // Error toast
                } else {
                    toast({ title: "An error occurred. Please try again later." });
                }
            })
            .catch((error) => {
                console.error("Error submitting form:", error);
                toast({ title: "An error occurred. Please try again later." });  // Error toast on catch
            });
    };

    const handleEdit = (index) => {
        const row = rs[index];
        reset({ form: getValues('form'), table: row });
        setRows((prev) => prev.filter((_, i) => i !== index));
    };

    const handleDelete = (index) => {
        setRows((prev) => prev.filter((_, i) => i !== index));
    };


    const handleKeyDown = (e) => {
        if (e.key === "Tab") {
            e.preventDefault(); // if you want to actually intercept the Tab
           const table = getValues("table");
            handleAddRow();
            const rowVals = {
                ...table,
            }
            setRows([...rs, rowVals])
            reset({ form: { ...getValues('form') } })
        }
    };


    const handleAddRow = () => {
        const newItem = getValues("table"); 
        newItem.sl_no = rs.length +1;

        const matchingBarcode = barCodes.find(b => b.barcode === newItem.barcode);
        if (matchingBarcode) {
            Object.assign(newItem, matchingBarcode);
        }

        setRows([...rs, {...newItem}]);
       
    };

    // Running totals
    const totalGW  = rs.reduce((s, r) => s + (parseFloat(r.gw)  || 0), 0);
    const totalNW  = rs.reduce((s, r) => s + (parseFloat(r.nw)  || 0), 0);
    const totalPcs = rs.reduce((s, r) => s + (parseInt(r.pcs)   || 0), 0);

    const fromRetailCode = localStorage.getItem('retail_code') || '';
    const toRetailCode   = watch('form.to_rt_code') || '';
    const toRetailObj    = retails.find(r => r.retail_code === toRetailCode);

    return (
        <div className="p-4 flex flex-col gap-4 max-w-5xl mx-auto">

            {/* ── Dispatched banner ── */}
            {isSent && (
                <div className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <SendHorizontal className="size-4 mt-0.5 shrink-0" />
                    <div>
                        <span className="font-semibold">Transfer dispatched — read only. </span>
                        <span>This transfer has been marked as sent. The receiving retail can accept it from the transfers list.</span>
                    </div>
                </div>
            )}

            <form id="orderForm" onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">

                {/* ── Header card ── */}
                <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
                        <div className="flex items-center gap-2">
                            <ArrowRight className="size-4 text-muted-foreground" />
                            <span className="text-sm font-semibold">Retail to Retail Stock Transfer</span>
                        </div>
                        <div className="flex items-center gap-2">
                            {isSent ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
                                    <SendHorizontal className="size-3" /> In Transit
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-600">
                                    Draft
                                </span>
                            )}
                            {watch('form.billno') && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono bg-violet-50 text-primary border border-violet-200">
                                    <Hash className="size-3" />{watch('form.billno')}
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-5 px-5 py-4">
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs text-muted-foreground font-medium">Transfer Date *</Label>
                            <Input type="date" {...register("form.date1")} required disabled={isSent} className="h-9 text-sm" />
                        </div>
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs text-muted-foreground font-medium">Bill No</Label>
                            <Input
                                type="text"
                                {...register("form.billno")}
                                readOnly disabled
                                placeholder="Auto-generated on save"
                                className="h-9 text-sm bg-muted/40 text-muted-foreground font-mono"
                            />
                        </div>
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs text-muted-foreground font-medium">To Retail Office *</Label>
                            <Controller
                                name="form.to_rt_code"
                                control={control}
                                render={({ field }) => (
                                    <Select onValueChange={field.onChange} value={field.value || ""} disabled={isSent}>
                                        <SelectTrigger className="h-9 text-sm">
                                            <SelectValue placeholder="Select destination retail" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {retails
                                                .filter(r => r.retail_code !== fromRetailCode)
                                                .map(r => (
                                                    <SelectItem key={r.id} value={r.retail_code}>
                                                        {r.retail_name}
                                                        <span className="ml-1.5 text-muted-foreground font-mono text-[10px]">({r.retail_code})</span>
                                                    </SelectItem>
                                                ))
                                            }
                                        </SelectContent>
                                    </Select>
                                )}
                            />
                        </div>
                    </div>

                    {/* Route strip */}
                    {toRetailCode && (
                        <div className="mx-5 mb-4 flex items-center gap-2 rounded-lg bg-violet-50 border border-violet-100 px-4 py-2 text-sm">
                            <span className="font-mono font-medium text-primary">{fromRetailCode}</span>
                            <ArrowRight className="size-3.5 text-violet-400" />
                            <span className="font-medium text-primary">{toRetailObj?.retail_name || toRetailCode}</span>
                            <span className="font-mono text-xs text-primary">({toRetailCode})</span>
                        </div>
                    )}
                </div>

                {/* ── Barcode entry card ── */}
                {!isSent && (
                    <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                        <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-muted/40">
                            <ScanBarcode className="size-4 text-muted-foreground" />
                            <span className="text-sm font-semibold">Add Barcode</span>
                            <span className="ml-auto text-[11px] text-muted-foreground">
                                Press <kbd className="px-1.5 py-0.5 rounded border bg-background font-mono text-[10px]">Tab</kbd> after each barcode to add it to the list
                            </span>
                        </div>
                        <div className="px-5 py-4 max-w-xs">
                            <div className="flex flex-col gap-1">
                                <Label className="text-xs text-muted-foreground font-medium">Barcode</Label>
                                <Input
                                    type="text"
                                    list="barcode_list"
                                    placeholder="Scan or type barcode..."
                                    onKeyDown={e => handleKeyDown(e)}
                                    {...register("table.barcode")}
                                    className="h-9 text-sm font-mono"
                                    autoFocus
                                />
                                <datalist id="barcode_list">
                                    {barCodes.map((b, i) => <option key={i} value={b.barcode} />)}
                                </datalist>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── Items table card ── */}
                <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
                        <div className="flex items-center gap-2">
                            <Scale className="size-4 text-muted-foreground" />
                            <span className="text-sm font-semibold">Transfer Items</span>
                            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-violet-100 text-primary text-[11px] font-semibold">
                                {rs.length}
                            </span>
                        </div>
                        {rs.length > 0 && (
                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                <span>Pcs: <strong className="text-foreground">{totalPcs}</strong></span>
                                <span>GW: <strong className="text-foreground">{totalGW.toFixed(3)} g</strong></span>
                                <span>NW: <strong className="text-foreground">{totalNW.toFixed(3)} g</strong></span>
                            </div>
                        )}
                    </div>

                    {rs.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-14 gap-2 text-muted-foreground">
                            <ScanBarcode className="size-10 opacity-20" />
                            <p className="text-sm">No barcodes added yet.</p>
                            {!isSent && <p className="text-xs">Enter a barcode above and press Tab.</p>}
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/30">
                                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground w-8">#</th>
                                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Barcode</th>
                                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Item</th>
                                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Purity</th>
                                        <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground">Pcs</th>
                                        <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground">GW (g)</th>
                                        <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground">NW (g)</th>
                                        {!isSent && (
                                            <th className="px-4 py-2.5 text-center text-xs font-medium text-muted-foreground w-20">Actions</th>
                                        )}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border">
                                    {rs.map((row, index) => (
                                        <tr key={index} className="hover:bg-muted/20 transition-colors">
                                            <td className="px-4 py-2.5 text-xs text-muted-foreground">{index + 1}</td>
                                            <td className="px-4 py-2.5 font-mono text-xs text-primary">{row.barcode}</td>
                                            <td className="px-4 py-2.5 text-xs">{row.item_name || row.item || '—'}</td>
                                            <td className="px-4 py-2.5 text-xs text-muted-foreground">{row.purity || '—'}</td>
                                            <td className="px-4 py-2.5 text-xs text-right">{row.pcs || '—'}</td>
                                            <td className="px-4 py-2.5 text-xs text-right font-medium">
                                                {row.gw ? parseFloat(row.gw).toFixed(3) : '—'}
                                            </td>
                                            <td className="px-4 py-2.5 text-xs text-right">
                                                {row.nw ? parseFloat(row.nw).toFixed(3) : '—'}
                                            </td>
                                            {!isSent && (
                                                <td className="px-4 py-2.5">
                                                    <div className="flex items-center justify-center gap-2">
                                                        <button type="button" onClick={() => handleEdit(index)}
                                                            className="text-primary hover:text-primary transition-colors">
                                                            <SquarePen className="size-3.5" />
                                                        </button>
                                                        <button type="button" onClick={() => handleDelete(index)}
                                                            className="text-red-400 hover:text-red-600 transition-colors">
                                                            <Trash2 className="size-3.5" />
                                                        </button>
                                                    </div>
                                                </td>
                                            )}
                                        </tr>
                                    ))}
                                </tbody>
                                <tfoot>
                                    <tr className="border-t-2 border-border bg-muted/30 font-semibold">
                                        <td colSpan={4} className="px-4 py-2.5 text-xs text-right text-muted-foreground">Total</td>
                                        <td className="px-4 py-2.5 text-xs text-right">{totalPcs}</td>
                                        <td className="px-4 py-2.5 text-xs text-right">{totalGW.toFixed(3)}</td>
                                        <td className="px-4 py-2.5 text-xs text-right">{totalNW.toFixed(3)}</td>
                                        {!isSent && <td />}
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    )}
                </div>

                {/* ── Actions ── */}
                <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
                    <Button type="button" variant="outline" onClick={() => window.history.back()}>
                        {isSent ? 'Back' : 'Cancel'}
                    </Button>
                    {!isSent && (
                        <Button
                            type="submit"
                            className="bg-primary hover:bg-primary text-white"
                            disabled={rs.length === 0}
                        >
                            Save Transfer
                        </Button>
                    )}
                </div>

            </form>
        </div>
    );
};

export default RetToRetstockTransfer;

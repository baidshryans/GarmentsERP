import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, createCustomerOrder, getStates, fetchPVNoNext, fetchPoNoNext, fetchPackets, fetchPos, fetchStoneIssuesFilterJobs, fetchStoneIssued, createPurchaseVoucher, fetchBarcodes, fetchHSNs, fetchBarcodeList, splitBarcode, fetchNextBarcode } from "@/services/apiService";
import { Link } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router-dom";
import { Scissors, ScanBarcode, Plus, Pencil, Trash2 } from "lucide-react";

// ── Section header (matches ERP design language) ────────────────────────────
const SectionHeader = ({ icon: Icon, title, subtitle }) => (
  <div className="flex items-center gap-3 mb-4">
    <span className="flex items-center justify-center size-8 rounded-full bg-primary text-white shrink-0">
      <Icon size={16} />
    </span>
    <div>
      <p className="text-sm font-bold text-gray-700 tracking-wider uppercase">{title}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
    </div>
    <div className="flex-1 h-px bg-violet-100" />
  </div>
);

// ── Compact table header cell ────────────────────────────────────────────────
const TH = ({ children, className = "" }) => (
  <th className={`px-2 py-2 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50 border-b border-gray-200 ${className}`}>
    {children}
  </th>
);

// create two new generated barcodes
const BarcodeSplit = () => {
    const { toast } = useToast()
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
                "barcode_text": "",
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
                "barcodedetails_set": [],
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
                    "barcode_text":"",
                    "amt":0,
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

    const navigate=useNavigate();
    const [rs, setRows] = useState([]);
    const [saving, setSaving] = useState(false);
    const[toprs,setTopRows] = useState([]);
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
    const [calculate, setCalculate] = useState([]);

    const [barcodes, setBarcodes] = useState([]);
    const [filteredBarcodes, setFilteredBarcodes] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);

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
            const [packets, barcodes, customers, states, salesperson, orderNo, mainItem, purity, poNo, hsnres] = await Promise.all([
                fetchPackets(),
                fetchBarcodeList(),
                getLedgers(),
                getStates(),
                fetchSalesperson(),
                fetchPVNoNext(),
                fetchMainItem(),
                fetchPurity(),
                fetchPos(),
                fetchHSNs(),
            ]);
            if (packets.success) setPackets(packets.data.results ?? packets.data);
            if (barcodes.success) setBarcodes(barcodes.data.results);

            if (customers.success) setCustomers(customers.data.results);
            if (states.success) setstatesData(states.data);
            if (salesperson.success) setSalespersonData(salesperson.data.results);
            if (orderNo.success) setValue("order_no", orderNo.data.bill_no);
            if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
            if (purity.success) setPurityData(purity.data.results ?? purity.data);
            if (poNo.success) setValue("po_no", poNo.data.po_no);
            if (hsnres.success) setHSNs(hsnres.data.results);
        }
        fetchData();
    }, []);



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

        const summedValues = rs.reduce((acc, curr) => ({
            pcs: acc.pcs + (Number(curr.pcs) || 0),
            ct: acc.ct + (Number(curr.ct) || 0),
            gw: acc.gw + (Number(curr.gw) || 0)
        }), { pcs: 0, ct: 0, gw: 0 });

        console.log('New Barcode Values:');
        console.log('Total Pcs:', summedValues.pcs);
        console.log('Total Ct:', summedValues.ct);
        console.log('Total GW:', summedValues.gw);

        const summedValuesTop = toprs.reduce((acc, curr) => ({
            pcs: acc.pcs + (Number(curr.pcs) || 0),
            ct: acc.ct + (Number(curr.ct) || 0),
            gw: acc.gw + (Number(curr.gw) || 0)
        }), { pcs: 0, ct: 0, gw: 0 });

        console.log('Original Barcode Values:');
        console.log('Total Pcs:', summedValuesTop.pcs);
        console.log('Total Ct:', summedValuesTop.ct);
        console.log('Total GW:', summedValuesTop.gw);

        if (summedValues.pcs !== summedValuesTop.pcs ||
            summedValues.ct !== summedValuesTop.ct ||
            summedValues.gw !== summedValuesTop.gw) {
            toast({
                title: "Values don't match",
                description: "The sum of pieces, carats and gross weight in new barcodes must match the original barcode",
            });
            return;
        }

        setSaving(true);
        splitBarcode (rs,getValues("form.old_barcode"))
            .then((response) => {
            if (response.success) {
                toast({
                title: "Form submitted successfully!",
                });  // Success toast

              setTimeout(()=>{
                navigate("");
              },2000);

            } else if (response.status < 500) {
                    setSaving(false);
                    toast({
                        title: "Form submission failed. Please try again.",
                        description: renderErrorTree(response.error),
                    });  // Error toast
                } else {
                    setSaving(false);
                    toast({ title: "An error occurred. Please try again later." });
                }
            })
            .catch((error) => {
            setSaving(false);
            console.error("Error submitting form:", error);
            toast({ title: "An error occurred. Please try again later." });  // Error toast on catch
            });
    };

    useF4Submit(handleSubmit(onSubmit));

    const handleEdit = (index) => {
        const row = rs[index];
        reset(row);
        setRows((prev) => prev.filter((_, i) => i !== index));
    };

    const handleDelete = (index) => {
        setRows((prev) => prev.filter((_, i) => i !== index));
    };

    const fix_gold_rate = watch("fix_gold_rate")

    // ── Packet ↔ Item mutual exclusion in sub-items ──────────────────────────
    const watchedDetailPacket = watch("table.details.packet")
    const watchedDetailItem   = watch("table.details.item")

    // When a packet is selected, auto-fill the sub-item from the packet's stone_item_id
    useEffect(() => {
        if (!watchedDetailPacket) return;
        const found = packets.find(p => p.pckt_no === watchedDetailPacket);
        if (found?.stone_item_id?.short_code) {
            setValue("table.details.item", found.stone_item_id.short_code);
        }
    }, [watchedDetailPacket, packets]);

    // Item is disabled (auto-filled) when a packet is chosen
    const itemDisabledByPacket  = !!watchedDetailPacket;
    // Packet is disabled when item is typed manually (i.e. item filled but no packet)
    const packetDisabledByItem  = !watchedDetailPacket && !!watchedDetailItem;

    const handleKeyDown = (e) => {
        if (e.key === "Tab") {
            e.preventDefault(); // if you want to actually intercept the Tab
            handleAddRow();
        }
    }


    const handleKeyDownDetails = (e) => {
        console.log("Called details")
        if (e.key === "Tab") {
            e.preventDefault();
            // if you want to actually intercept the Tab
            const vals = getValues("table.details")
            const currentTableValues = getValues("table");
            const currentRowIndex = rs.length - 1;

            if (currentRowIndex >= 0 && rs[currentRowIndex]) {
                const tablevalues = { ...rs[currentRowIndex] };
                if (!tablevalues.barcodedetails_set) {
                    tablevalues.barcodedetails_set = [];
                }
                tablevalues.barcodedetails_set = [...tablevalues.barcodedetails_set, vals];

                setRows((prevData) =>
                    prevData.map((row, i) => (i === currentRowIndex ? { ...tablevalues } : row))
                );

                // Reset only the details part, keep the main item data
                setValue("table.details", {
                    main_item: null,
                    bill_no: "",
                    date1: null,
                    sub_item: null,
                    item: null,
                    sub_pcs: 0,
                    sub_gw: 0,
                    sub_ct: 0,
                    metal_purity: null,
                    loss: 0,
                    tunch: 0,
                    fine_wt: 0,
                    packet: null,
                    rate: 0,
                    barcode_text: "",
                    amt:0,
                    value: 0,
                    sl_no: vals.sl_no + 1, // Increment sl_no for next entry
                });
            }
        }
    };

    const handleAddRow = async () => {
        const newItem = getValues("table"); // all item fields + details

        if (!newItem.item || !newItem.pcs || !newItem.gw) {
            toast({
                title: "Missing required fields",
                description: "Please fill in Item, Pcs, and GW before adding to table",
            });
            return;
        }

        // Add the current item to the rows
        setRows(prevRows => [...prevRows, { ...newItem }]);

        // Generate a fresh barcode for the next split entry
        const bcRes = await fetchNextBarcode();
        const nextBarcode = bcRes.success ? bcRes.data.barcode : "";

        setValue("table", {
            bill_no: null,
            date1: null,
            po_no: "",
            po_sl_no: null,
            item: null,
            barcode: nextBarcode,
            barcode_text: "",
            order_no: null,
            sl_no: 0,
            pcs: null,
            gw: null,
            size: "",
            purity: null,
            pending_pcs: null,
            pending_gw: null,
            making_type: "",
            making_amt: null,
            making: null,
            item_value: null,
            value: null,
            remarks: "",
            barcodedetails_set: [],
            details: {
                main_item: null,
                bill_no: "",
                date1: null,
                sub_item: null,
                item: null,
                sub_pcs: 0,
                sub_gw: 0,
                sub_ct: 0,
                metal_purity: null,
                loss: 0,
                tunch: 0,
                fine_wt: 0,
                packet: null,
                rate: 0,
                barcode_text: "",
                amt: 0,
                value: 0,
                sl_no: 1,
            },
        });
    };

    const handleKeyDownBarcode = async (e) => {
        if (e.key === "Tab") {
            const barcode = getValues("form.old_barcode")
            const foundBarcode = barcodes.find(item => item.barcode === barcode);
            if (foundBarcode) {
                setTopRows([...toprs, { ...foundBarcode }]);
                // Default purity of new barcodes to the source barcode's purity
                const purityVal = typeof foundBarcode.purity === 'object'
                    ? foundBarcode.purity?.purity
                    : foundBarcode.purity;
                if (purityVal) setValue("table.purity", String(purityVal));
                // Auto-generate first new barcode
                const bcRes = await fetchNextBarcode();
                if (bcRes.success) setValue("table.barcode", bcRes.data.barcode);
            }
        }
    };

    return (
        <div className="mt-5 space-y-6">
            <form id="orderForm" onSubmit={handleSubmit(onSubmit)} className="space-y-6">

                {/* ══ SECTION 1 – Source Barcode ══════════════════════════════════ */}
                <div className="p-6 shadow-sm rounded-xl bg-white border border-gray-100">
                    <SectionHeader icon={ScanBarcode} title="Source Barcode" subtitle="Scan or type the barcode to split" />

                    <div className="flex flex-wrap items-end gap-3">
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Barcode</Label>
                            <Input
                                list="barcode_list"
                                onKeyDown={handleKeyDownBarcode}
                                type="text"
                                {...register("form.old_barcode")}
                                placeholder="Scan or type barcode…"
                                className="h-9 w-56 bg-white"
                            />
                            <datalist id="barcode_list">
                                {barcodes.map((barcode, index) => (
                                    <option key={index} value={barcode.barcode} />
                                ))}
                            </datalist>
                        </div>
                        <p className="text-xs text-gray-400 pb-2">
                            Press <kbd className="px-1.5 py-0.5 rounded bg-gray-100 border border-gray-200 font-mono text-gray-600">Tab</kbd> to load details and generate the first new barcode
                        </p>
                    </div>

                    {/* Source barcode details table */}
                    {toprs.length > 0 && (
                        <div className="mt-5 overflow-x-auto rounded-lg border border-violet-100">
                            <table className="w-full text-sm border-collapse">
                                <thead>
                                    <tr>
                                        <TH>Barcode</TH>
                                        <TH>Item</TH>
                                        <TH>Description</TH>
                                        <TH>Pcs</TH>
                                        <TH>Ct</TH>
                                        <TH>GW</TH>
                                        <TH>Purity</TH>
                                        <TH>Making</TH>
                                        <TH>Making Type</TH>
                                        <TH>Oth. Making</TH>
                                    </tr>
                                </thead>
                                <tbody>
                                    {toprs.map((item, idx) => (
                                        <React.Fragment key={idx}>
                                            <tr className="bg-violet-50 border-t border-violet-100">
                                                <td className="px-2 py-1.5 font-semibold text-primary">{item.barcode}</td>
                                                <td className="px-2 py-1.5">{item.item}</td>
                                                <td className="px-2 py-1.5 text-gray-500">{item.item_name}</td>
                                                <td className="px-2 py-1.5">{item.pcs}</td>
                                                <td className="px-2 py-1.5"></td>
                                                <td className="px-2 py-1.5">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</td>
                                                <td className="px-2 py-1.5">{item.purity}</td>
                                                <td className="px-2 py-1.5">{item.making_val}</td>
                                                <td className="px-2 py-1.5">{item.making_type}</td>
                                                <td className="px-2 py-1.5">{item.other_chg}</td>
                                            </tr>
                                            {item.barcodedetails_set?.map((detail, di) => (
                                                <tr key={di} className="bg-violet-50/50 border-t border-violet-50">
                                                    <td className="px-2 py-1 pl-6 text-xs text-gray-400 font-mono">{detail.packet || "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.item}</td>
                                                    <td className="px-2 py-1 text-xs"></td>
                                                    <td className="px-2 py-1 text-xs">{detail.pcs}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.ct != null ? parseFloat(detail.ct).toFixed(3) : "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.gw != null ? parseFloat(detail.gw).toFixed(3) : "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.purity || "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.rate}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.uom}</td>
                                                    <td className="px-2 py-1 text-xs font-medium">{detail.amt}</td>
                                                </tr>
                                            ))}
                                        </React.Fragment>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* ══ SECTION 2 – New Barcode Entry ═══════════════════════════════ */}
                <div className="p-6 shadow-sm rounded-xl bg-white border border-gray-100">
                    <SectionHeader icon={Scissors} title="New Barcode Entry" subtitle="Define split barcodes — press Tab on last field to add row" />

                    {/* Main Item */}
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Main Item</p>
                    <div className="flex flex-wrap items-end gap-3 mb-6 p-4 rounded-lg bg-gray-50 border border-gray-100">
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Item</Label>
                            <Input
                                list="item_list"
                                {...register("table.item")}
                                className="h-9 w-36 bg-white text-sm"
                                placeholder="Item code…"
                            />
                            <datalist id="item_list">
                                {mainItemData.map((item, index) => (
                                    <option key={index} value={item.short_code}>{item.item_name}</option>
                                ))}
                            </datalist>
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Barcode</Label>
                            <Input type="text" {...register("table.barcode")} className="h-9 w-44 bg-white text-sm font-mono" placeholder="Auto-generated…" />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Purity</Label>
                            <Controller
                                name="table.purity"
                                control={control}
                                render={({ field }) => (
                                    <Select onValueChange={field.onChange} value={field.value ?? ""}>
                                        <SelectTrigger className="h-9 w-28 text-sm">
                                            <SelectValue placeholder="Purity" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {purityData.map((item, index) => (
                                                <SelectItem key={index} value={`${item.purity}`}>{item.purity}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )}
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Pcs</Label>
                            <Input type="number" {...register("table.pcs")} className="h-9 w-20 bg-white text-sm" placeholder="0" />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">GW (g)</Label>
                            <Input type="number" step="0.001" {...register("table.gw")} className="h-9 w-28 bg-white text-sm" placeholder="0.000" />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Making</Label>
                            <Input type="text" {...register("table.making")} className="h-9 w-24 bg-white text-sm" placeholder="0" />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Making Type</Label>
                            <Controller
                                name="table.making_type"
                                control={control}
                                render={({ field }) => (
                                    <Select onValueChange={field.onChange} value={field.value ?? ""}>
                                        <SelectTrigger className="h-9 w-32 text-sm">
                                            <SelectValue placeholder="Type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="per_nw">% of wt</SelectItem>
                                            <SelectItem value="val">Value</SelectItem>
                                        </SelectContent>
                                    </Select>
                                )}
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <Label className="text-xs text-gray-500">Oth. Making</Label>
                            <Input
                                onKeyDown={handleKeyDown}
                                type="number"
                                step="0.01"
                                {...register("table.value")}
                                className="h-9 w-28 bg-white text-sm"
                                placeholder="0.00"
                            />
                        </div>
                    </div>

                    {/* Sub Items */}
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Sub Items</p>
                    <div className="overflow-x-auto rounded-lg border border-gray-200">
                        <table className="w-full text-sm border-collapse">
                            <thead>
                                <tr>
                                    <TH>Sl No</TH>
                                    <TH>Packet</TH>
                                    <TH>Sub Item</TH>
                                    <TH>Description</TH>
                                    <TH>Pcs</TH>
                                    <TH>Ct</TH>
                                    <TH>GW</TH>
                                    <TH>Rate</TH>
                                    <TH>Value</TH>
                                </tr>
                            </thead>
                            <tbody>
                                <tr className="bg-white">
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input type="text" {...register("table.details.sl_no")} className="h-9 text-sm bg-white w-16" />
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input
                                            list="packet_list"
                                            {...register("table.details.packet")}
                                            className="h-9 text-sm bg-white w-28 disabled:opacity-50 disabled:cursor-not-allowed"
                                            placeholder="Packet…"
                                            disabled={packetDisabledByItem}
                                        />
                                        <datalist id="packet_list">
                                            {packets.map((packet, index) => (
                                                <option key={index} value={packet.pckt_no}>{packet.pckt_no}</option>
                                            ))}
                                        </datalist>
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input
                                            list="sub_item_list"
                                            {...register("table.details.item")}
                                            className="h-9 text-sm bg-white w-28 disabled:opacity-50 disabled:cursor-not-allowed"
                                            placeholder="Item…"
                                            disabled={itemDisabledByPacket}
                                        />
                                        <datalist id="sub_item_list">
                                            {mainItemData.map((item, index) => (
                                                <option key={index} value={item.short_code}>{item.item_name}</option>
                                            ))}
                                        </datalist>
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input type="number" {...register("table.details.sub_pcs")} className="h-9 text-sm bg-white w-20" placeholder="0" />
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input type="number" step="0.001" {...register("table.details.sub_ct")} className="h-9 text-sm bg-white w-20" placeholder="0.000" />
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input type="number" step="0.001" {...register("table.details.sub_gw")} className="h-9 text-sm bg-white w-24" placeholder="0.000" />
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input type="number" step="0.01" {...register("table.details.rate")} className="h-9 text-sm bg-white w-24" placeholder="0.00" />
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        <Input
                                            type="number"
                                            step="0.01"
                                            onKeyDown={handleKeyDownDetails}
                                            {...register("table.details.value")}
                                            className="h-9 text-sm bg-white w-24"
                                            placeholder="0.00"
                                        />
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* ══ SECTION 3 – New Barcodes Preview ═══════════════════════════ */}
                {rs.length > 0 && (
                    <div className="p-6 shadow-sm rounded-xl bg-white border border-gray-100">
                        <SectionHeader icon={Plus} title="New Barcodes" subtitle="Split barcodes to be created" />

                        <div className="overflow-x-auto rounded-lg border border-violet-100">
                            <table className="w-full text-sm border-collapse">
                                <thead>
                                    <tr>
                                        <TH>Barcode</TH>
                                        <TH>Item</TH>
                                        <TH>Description</TH>
                                        <TH>Pcs</TH>
                                        <TH>Ct</TH>
                                        <TH>GW</TH>
                                        <TH>Purity</TH>
                                        <TH>Making</TH>
                                        <TH>Making Type</TH>
                                        <TH>Oth. Making</TH>
                                        <TH></TH>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rs.map((item, idx) => (
                                        <React.Fragment key={idx}>
                                            <tr className="bg-violet-50 border-t border-violet-100">
                                                <td className="px-2 py-1.5 font-semibold text-primary">{item.barcode}</td>
                                                <td className="px-2 py-1.5">{item.item}</td>
                                                <td className="px-2 py-1.5 text-gray-500">{item.item_name}</td>
                                                <td className="px-2 py-1.5">{item.pcs}</td>
                                                <td className="px-2 py-1.5"></td>
                                                <td className="px-2 py-1.5">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</td>
                                                <td className="px-2 py-1.5">{item.purity}</td>
                                                <td className="px-2 py-1.5">{item.making_val}</td>
                                                <td className="px-2 py-1.5">{item.making_type}</td>
                                                <td className="px-2 py-1.5">{item.other_chg}</td>
                                                <td className="px-2 py-1.5">
                                                    <div className="flex gap-1">
                                                        <button
                                                            type="button"
                                                            onClick={() => handleEdit(idx)}
                                                            className="p-1 rounded text-primary hover:bg-violet-50"
                                                        >
                                                            <Pencil className="size-4" />
                                                        </button>
                                                        <button
                                                            type="button"
                                                            onClick={() => handleDelete(idx)}
                                                            className="p-1 rounded text-red-500 hover:bg-red-50"
                                                        >
                                                            <Trash2 className="size-4" />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                            {item.barcodedetails_set?.map((detail, di) => (
                                                <tr key={di} className="bg-violet-50/50 border-t border-violet-50">
                                                    <td className="px-2 py-1 pl-6 text-xs text-gray-400 font-mono">{detail.packet || "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.item}</td>
                                                    <td className="px-2 py-1 text-xs"></td>
                                                    <td className="px-2 py-1 text-xs">{detail.pcs}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.ct != null ? parseFloat(detail.ct).toFixed(3) : "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.gw != null ? parseFloat(detail.gw).toFixed(3) : "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.purity || "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.rate}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.uom}</td>
                                                    <td className="px-2 py-1 text-xs font-medium">{detail.amt}</td>
                                                    <td className="px-2 py-1 text-xs"></td>
                                                </tr>
                                            ))}
                                        </React.Fragment>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* ══ FOOTER ══════════════════════════════════════════════════════ */}
                <div className="flex justify-end gap-3 pb-4">
                    <Button
                        type="button"
                        variant="outline"
                        className="border-gray-200 text-gray-600 hover:bg-gray-50"
                        onClick={() => navigate("")}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="submit"
                        className="bg-primary hover:bg-primary text-white font-semibold tracking-wide px-6"
                        disabled={saving}
                    >
                        <Scissors size={15} className="mr-2" /> Save Split
                    </Button>
                </div>

            </form>
        </div>
    );
};

export default BarcodeSplit;

import React, { useEffect, useRef, useState } from "react";
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
        const form = { ...getValues('form'), rs: rs };
        Object.keys(main_formulas).forEach((col) => {
            setValue(`form.${col}`, evaluateFormula(main_formulas[col], form));
        })
    }, [rs, watchedFields, calculate]);

    const onSubmit = (data) => {

        // Validate ct + gw conservation against the source barcode. Pcs is intentionally
        // NOT compared — a single source piece may legitimately split into N new barcodes,
        // so summing pcs across new barcodes won't equal the original count.
        const summedValues = rs.reduce((acc, curr) => ({
            ct: acc.ct + (Number(curr.ct) || 0),
            gw: acc.gw + (Number(curr.gw) || 0)
        }), { ct: 0, gw: 0 });

        const summedValuesTop = toprs.reduce((acc, curr) => ({
            ct: acc.ct + (Number(curr.ct) || 0),
            gw: acc.gw + (Number(curr.gw) || 0)
        }), { ct: 0, gw: 0 });

        if (summedValues.ct !== summedValuesTop.ct ||
            summedValues.gw !== summedValuesTop.gw) {
            toast({
                title: "Values don't match",
                description: "The sum of carats and gross weight in new barcodes must match the original barcode",
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

    // Edit a sub-item: pull it into table.details (remap canonical → form names) and
    // remove it from its parent. The parent's total is recomputed too.
    // sl_no carries the 1-based parent index so the next Tab re-commits to the same parent.
    const handleEditSubItem = (parentIdx, subIdx) => {
        const parent = rs[parentIdx];
        const sub = parent?.barcodedetails_set?.[subIdx];
        if (!sub) return;
        setValue("table.details", {
            main_item: null,
            bill_no: "",
            date1: null,
            sub_item: null,
            item: sub.item ?? null,
            sub_pcs: Number(sub.pcs ?? 0),
            sub_gw:  Number(sub.gw  ?? 0),
            sub_ct:  Number(sub.ct  ?? 0),
            metal_purity: sub.purity ?? null,
            loss: 0,
            tunch: 0,
            fine_wt: 0,
            packet: sub.packet ?? null,
            rate: Number(sub.rate ?? 0),
            barcode_text: "",
            amt: 0,
            value: Number(sub.amt ?? 0),
            sl_no: parentIdx + 1,
        });
        setDetailUom(sub.uom || "");
        setRows((prev) => prev.map((row, i) => {
            if (i !== parentIdx) return row;
            const newSet = row.barcodedetails_set.filter((_, j) => j !== subIdx);
            const newRow = { ...row, barcodedetails_set: newSet };
            const { value, total } = computeRowTotal(newRow);
            return { ...newRow, value, total_amount: total, item_value: total };
        }));
    };

    const handleDeleteSubItem = (parentIdx, subIdx) => {
        setRows((prev) => prev.map((row, i) => {
            if (i !== parentIdx) return row;
            const newSet = row.barcodedetails_set.filter((_, j) => j !== subIdx);
            const newRow = { ...row, barcodedetails_set: newSet };
            const { value, total } = computeRowTotal(newRow);
            return { ...newRow, value, total_amount: total, item_value: total };
        }));
    };

    const fix_gold_rate = watch("fix_gold_rate")

    // ── Packet ↔ Item mutual exclusion in sub-items ──────────────────────────
    const watchedDetailPacket = watch("table.details.packet")
    const watchedDetailItem   = watch("table.details.item")
    const watchedDetailCt     = watch("table.details.sub_ct")
    const watchedDetailPcs    = watch("table.details.sub_pcs")
    const watchedDetailGw     = watch("table.details.sub_gw")
    const watchedDetailRate   = watch("table.details.rate")
    const [detailUom, setDetailUom] = useState("");

    // When a packet is selected, auto-fill sub_item / rate / uom from PacketSerializer flat fields.
    // (`stone_item_id` is the plain FK integer — the serializer exposes the joined values via
    // `stone_item_short_code`, `stone_item_name`, `stone_item_uom`.)
    useEffect(() => {
        if (!watchedDetailPacket) return;
        const found = packets.find(p => p.pckt_no === watchedDetailPacket);
        if (!found) return;
        if (found.stone_item_short_code) {
            setValue("table.details.item", found.stone_item_short_code);
        }
        if (found.rate_for_retail != null) {
            setValue("table.details.rate", found.rate_for_retail);
        }
        if (found.stone_item_uom) {
            setDetailUom(String(found.stone_item_uom).toLowerCase());
        }
    }, [watchedDetailPacket, packets]);

    // When the sub-item is typed manually (no packet), pick up its uom from the item master.
    useEffect(() => {
        if (watchedDetailPacket) return; // packet path already set uom
        if (!watchedDetailItem) { setDetailUom(""); return; }
        const it = mainItemData.find(m => m.short_code === watchedDetailItem);
        if (it?.uom) setDetailUom(String(it.uom).toLowerCase());
    }, [watchedDetailItem, watchedDetailPacket, mainItemData]);

    // ct uom → auto-seed gw = ct × 0.2 (1 carat = 0.2 g). User can still override.
    useEffect(() => {
        if (detailUom !== "ct") return;
        const ct = parseFloat(watchedDetailCt || 0);
        if (!Number.isNaN(ct)) {
            setValue("table.details.sub_gw", parseFloat((ct * 0.2).toFixed(3)));
        }
    }, [detailUom, watchedDetailCt]);

    // Auto-compute value = rate × qty, where qty depends on uom.
    useEffect(() => {
        const rate = parseFloat(watchedDetailRate || 0);
        let qty;
        if (detailUom === "ct")       qty = parseFloat(watchedDetailCt  || 0);
        else if (detailUom === "pcs") qty = parseFloat(watchedDetailPcs || 0);
        else                          qty = parseFloat(watchedDetailGw  || 0);
        if (!Number.isNaN(rate) && !Number.isNaN(qty)) {
            setValue("table.details.value", parseFloat((rate * qty).toFixed(2)));
        }
    }, [detailUom, watchedDetailRate, watchedDetailCt, watchedDetailPcs, watchedDetailGw]);

    // Item is disabled (auto-filled) when a packet is chosen
    const itemDisabledByPacket  = !!watchedDetailPacket;
    // Look up the selected sub-item to know its type — Raw (R) items have a purity but no packet,
    // Stone (S) items go through a packet (no purity).
    const selectedSubItemData   = mainItemData.find(m => m.short_code === watchedDetailItem);
    const selectedSubItemType   = selectedSubItemData?.item_type || "";
    const subItemIsRaw          = selectedSubItemType === "R";
    const subItemIsStone        = selectedSubItemType === "S";
    // Packet is disabled when item is typed manually OR when the typed item is Raw (R).
    const packetDisabledByItem  = (!watchedDetailPacket && !!watchedDetailItem) || subItemIsRaw;

    // Raw sub-item → clear packet, pcs, ct (these inputs are hidden for Raw),
    // and seed metal_purity from the parent main item's purity if the user hasn't picked one yet.
    // After handleAddRow commits the main item, table.purity is reset to null, so we must read
    // the purity from the committed parent (rs[last]) — not from the form field.
    const watchedMainPurity      = watch("table.purity");
    const watchedDetailPurity    = watch("table.details.metal_purity");
    useEffect(() => {
        if (!subItemIsRaw) return;
        if (watchedDetailPacket) setValue("table.details.packet", "");
        if (watchedDetailPcs)    setValue("table.details.sub_pcs", 0);
        if (watchedDetailCt)     setValue("table.details.sub_ct", 0);
        const parentPurity = rs.length > 0 ? rs[rs.length - 1]?.purity : null;
        const seedPurity = parentPurity || watchedMainPurity;
        if (!watchedDetailPurity && seedPurity) {
            setValue("table.details.metal_purity", String(seedPurity));
        }
    }, [subItemIsRaw, watchedDetailPacket, watchedDetailPcs, watchedDetailCt, watchedMainPurity, watchedDetailPurity, rs]);

    // Raw sub-item GW auto-fill: when a Raw item is picked, default sub_gw to
    // (parent main item's gw - sum of existing sub-items' gw for that parent).
    // Runs once per (Raw item, parent) selection so the user can still override
    // and not have their typed gw overwritten on every keystroke.
    // Stone sub-item → metal_purity must be null (stones don't carry a metal purity).
    // Without this, a purity left over from a previously-picked Raw sub-item would
    // persist into a Stone sub-item's saved row.
    useEffect(() => {
        if (subItemIsStone && watchedDetailPurity) {
            setValue("table.details.metal_purity", null);
        }
    }, [subItemIsStone, watchedDetailPurity]);

    const lastAutoGwKeyRef = useRef("");
    useEffect(() => {
        if (!subItemIsRaw) { lastAutoGwKeyRef.current = ""; return; }
        if (!watchedDetailItem || rs.length === 0) return;
        const parentIdx = rs.length - 1;
        const childCount = rs[parentIdx]?.barcodedetails_set?.length ?? 0;
        // key changes whenever the user picks a different item OR a sub-item just got committed
        const key = `${parentIdx}|${watchedDetailItem}|${childCount}`;
        if (lastAutoGwKeyRef.current === key) return;
        const parent = rs[parentIdx];
        const parentGw = parseFloat(parent?.gw || 0);
        const usedGw  = (parent?.barcodedetails_set || []).reduce(
            (s, d) => s + parseFloat(d.gw || 0), 0,
        );
        const available = Math.max(0, parentGw - usedGw);
        setValue("table.details.sub_gw", parseFloat(available.toFixed(3)));
        lastAutoGwKeyRef.current = key;
    }, [subItemIsRaw, watchedDetailItem, rs]);

    const handleKeyDown = (e) => {
        if (e.key === "Tab") {
            e.preventDefault(); // if you want to actually intercept the Tab
            handleAddRow();
        }
    }


    const handleKeyDownDetails = (e) => {
        if (e.key === "Tab") {
            e.preventDefault();
            // if you want to actually intercept the Tab
            const vals = getValues("table.details")
            const currentTableValues = getValues("table");
            // sl_no is the 1-based index of the parent main item this sub-item belongs to.
            // Fall back to the latest main item when sl_no isn't set yet.
            const slNo = parseInt(vals.sl_no || 0, 10);
            const currentRowIndex = (slNo > 0 && slNo <= rs.length) ? slNo - 1 : rs.length - 1;

            // ── Validate the sub-item ────────────────────────────────────────────
            // Block commit if no item is selected, or if the qty for the item's
            // UOM is missing / zero. For Stone sub-items entered via a packet, the
            // item gets auto-filled, but the user could still tab through an empty form.
            if (!vals.item && !vals.packet) {
                toast({ title: "Sub-item required", description: "Pick a sub-item or a packet before adding the row." });
                return;
            }
            const subItemMaster = mainItemData.find(m => m.short_code === vals.item);
            const subUom = (subItemMaster?.uom || detailUom || "").toLowerCase();
            let subQty;
            if (subUom === "ct")        subQty = parseFloat(vals.sub_ct  || 0);
            else if (subUom === "pcs")  subQty = parseFloat(vals.sub_pcs || 0);
            else                        subQty = parseFloat(vals.sub_gw  || 0);
            if (!subQty || subQty <= 0 || Number.isNaN(subQty)) {
                const fieldLabel = subUom === "ct" ? "Ct" : subUom === "pcs" ? "Pcs" : "GW";
                toast({
                    title: "Quantity required",
                    description: `Enter a non-zero ${fieldLabel} for this sub-item (UOM: ${subUom || "gm"}).`,
                });
                return;
            }
            // ─────────────────────────────────────────────────────────────────────

            if (currentRowIndex >= 0 && rs[currentRowIndex]) {
                const tablevalues = { ...rs[currentRowIndex] };
                if (!tablevalues.barcodedetails_set) {
                    tablevalues.barcodedetails_set = [];
                }
                // Remap form field names (sub_pcs/sub_ct/sub_gw/value/metal_purity) to the
                // BarcodeDetailsSerializer field names (pcs/ct/gw/amt/purity) so both the local
                // preview and the backend submit get the same shape.
                //
                // Purity rule (enforced here regardless of any stale form state):
                //   item_type 'S' (Stone)  → null
                //   item_type 'R' (Raw)    → the selected metal_purity
                //   otherwise              → null
                const _itemMaster = mainItemData.find(m => m.short_code === vals.item);
                const _type = (_itemMaster?.item_type || "").toUpperCase();
                const detailRow = {
                    sl_no:    vals.sl_no,
                    packet:   vals.packet || null,
                    item:     vals.item,
                    purity:   _type === "R" ? (vals.metal_purity || null) : null,
                    pcs:      Number(vals.sub_pcs || 0),
                    ct:       Number(vals.sub_ct  || 0),
                    gw:       Number(vals.sub_gw  || 0),
                    uom:      detailUom || "",
                    rate:     Number(vals.rate    || 0),
                    amt:      Number(vals.value   || 0),
                };
                tablevalues.barcodedetails_set = [...tablevalues.barcodedetails_set, detailRow];
                // Re-compute value + total_amount for this parent now that another sub-item joined.
                const { value: vNew, total: tNew } = computeRowTotal(tablevalues);
                tablevalues.value        = vNew;
                tablevalues.total_amount = tNew;
                tablevalues.item_value   = tNew;

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
                    // sl_no is the 1-based index of the parent main item this sub-item belongs to.
                    // Multiple sub-items under the same main item all share the same sl_no — it
                    // only bumps when a new main item is added (see handleAddRow).
                    sl_no: rs.length,
                });
                setDetailUom("");
            }
        }
    };

    // Compute BarcodeMain.value and BarcodeMain.total_amount the same way the
    // PurchaseVoucher → barcode flow does:
    //   value        = Σ(sub-item amt) + makingAmt          (metal + making, before other chg)
    //   total_amount = value + other_chg                    (final ticket price)
    //   makingAmt depends on making_type:
    //     'val'    → flat value (use `making` as the amount)
    //     'per_nw' → per-gram rate (making × gw)
    //     ''/null  → 0
    const computeRowTotal = (row) => {
        const subTotal = (row.barcodedetails_set || []).reduce(
            (s, d) => parseFloat(s) + parseFloat(d.amt || 0), 0,
        );
        const makingNum = parseFloat(row.making_val ?? row.making ?? 0) || 0;
        const gwNum     = parseFloat(row.gw || 0) || 0;
        const otherChg  = parseFloat(row.other_chg ?? 0) || 0;
        let makingAmt = 0;
        if (row.making_type === 'val')          makingAmt = makingNum;
        else if (row.making_type === 'per_nw')  makingAmt = makingNum * gwNum;
        const value = parseFloat((subTotal + makingAmt).toFixed(2));
        const total = parseFloat((value + otherChg).toFixed(2));
        return { value, total };
    };

    const handleAddRow = async () => {
        const newItem = getValues("table"); // all item fields + details

        // ── Validate the main item ───────────────────────────────────────────
        // Require an item, plus the qty matching the item's UOM (gw / ct / pcs) — any
        // missing/zero/blank value blocks the commit so we don't add hollow rows.
        if (!newItem.item) {
            toast({ title: "Item required", description: "Select an item before adding the row." });
            return;
        }
        const mainItemMaster = mainItemData.find(m => m.short_code === newItem.item);
        const mainUom = (mainItemMaster?.uom || "").toLowerCase();
        const pcsVal = parseFloat(newItem.pcs || 0);
        const gwVal  = parseFloat(newItem.gw  || 0);
        if (!pcsVal || pcsVal <= 0 || Number.isNaN(pcsVal)) {
            toast({ title: "Pcs required", description: "Enter a non-zero Pcs for the main item." });
            return;
        }
        const primaryQty = mainUom === "ct" ? parseFloat(newItem.ct || 0) : gwVal;
        if (!primaryQty || primaryQty <= 0 || Number.isNaN(primaryQty)) {
            const label = mainUom === "ct" ? "Ct" : "GW";
            toast({
                title: `${label} required`,
                description: `Enter a non-zero ${label} for the main item (UOM: ${mainUom || "gm"}).`,
            });
            return;
        }
        // ─────────────────────────────────────────────────────────────────────

        // Remap form field names to the BarCodeMainSerializer / display canonical names:
        //   table.making  → making_val
        //   table.value   → other_chg   (the Oth. Making input is registered as table.value)
        // Carry item_name through so the bottom preview shows the readable name without a lookup.
        const itemName = (mainItemData.find(m => m.short_code === newItem.item)?.item_name) || "";
        const remapped = {
            ...newItem,
            making_val: newItem.making_val ?? newItem.making ?? 0,
            other_chg:  newItem.other_chg  ?? newItem.value  ?? 0,
            item_name:  newItem.item_name  || itemName,
        };
        // Compute initial value + total_amount (no sub-items yet). Mirror total to
        // item_value so the form-level SUM(rs.item_value) totals still work.
        const { value: initValue, total: initTotal } = computeRowTotal({ ...remapped, barcodedetails_set: [] });
        remapped.value        = initValue;
        remapped.total_amount = initTotal;
        remapped.item_value   = initTotal;

        // Add the current item to the rows
        setRows(prevRows => [...prevRows, remapped]);

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
                // After adding this main item, rs.length is about to become rs.length + 1
                // (setRows above is queued). Next sub-item belongs to the new main item.
                sl_no: rs.length + 1,
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
                                        <TH>Pcs</TH>
                                        <TH>Ct</TH>
                                        <TH>GW</TH>
                                        <TH>Purity</TH>
                                        <TH>Making</TH>
                                        <TH>Rate</TH>
                                        <TH>Oth. Making</TH>
                                    </tr>
                                </thead>
                                <tbody>
                                    {toprs.map((item, idx) => (
                                        <React.Fragment key={idx}>
                                            <tr className="bg-violet-50 border-t border-violet-100">
                                                <td className="px-2 py-1.5 font-semibold text-primary">{item.barcode}</td>
                                                <td className="px-2 py-1.5">{item.item_name || item.item}</td>
                                                <td className="px-2 py-1.5">{item.pcs}</td>
                                                <td className="px-2 py-1.5"></td>
                                                <td className="px-2 py-1.5">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</td>
                                                <td className="px-2 py-1.5">{item.purity}</td>
                                                <td className="px-2 py-1.5">{item.making_val}</td>
                                                <td className="px-2 py-1.5"></td>
                                                <td className="px-2 py-1.5">{item.other_chg}</td>
                                            </tr>
                                            {item.barcodedetails_set?.map((detail, di) => {
                                                const subItemName = (mainItemData.find(m => m.short_code === detail.item)?.item_name) || detail.item;
                                                return (
                                                    <tr key={di} className="bg-violet-50/50 border-t border-violet-50">
                                                        <td className="px-2 py-1 pl-6 text-xs text-gray-400 font-mono">{detail.packet || "—"}</td>
                                                        <td className="px-2 py-1 text-xs">{subItemName}</td>
                                                        <td className="px-2 py-1 text-xs">{detail.pcs}</td>
                                                        <td className="px-2 py-1 text-xs">{detail.ct != null ? parseFloat(detail.ct).toFixed(3) : "—"}</td>
                                                        <td className="px-2 py-1 text-xs">{detail.gw != null ? parseFloat(detail.gw).toFixed(3) : "—"}</td>
                                                        <td className="px-2 py-1 text-xs">{detail.purity || detail.metal_purity || "—"}</td>
                                                        <td className="px-2 py-1 text-xs"></td>
                                                        <td className="px-2 py-1 text-xs">{detail.rate}</td>
                                                        <td className="px-2 py-1 text-xs font-medium">{detail.amt}</td>
                                                    </tr>
                                                );
                                            })}
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
                            <Input type="number" step="0.01" {...register("table.making")} className="h-9 w-24 bg-white text-sm" placeholder="0" />
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
                                    <TH>Purity</TH>
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
                                        <Input type="text" readOnly {...register("table.details.sl_no")} className="h-9 text-sm bg-gray-50 w-16 cursor-not-allowed" />
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        {subItemIsRaw ? (
                                            <span className="text-xs text-gray-300">—</span>
                                        ) : (
                                            <>
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
                                            </>
                                        )}
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
                                            {mainItemData
                                                .filter(item => item.item_type === "R" || item.item_type === "S")
                                                .map((item, index) => (
                                                    <option key={index} value={item.short_code}>{item.item_name}</option>
                                                ))}
                                        </datalist>
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        {subItemIsStone ? (
                                            <span className="text-xs text-gray-300">—</span>
                                        ) : (
                                            <Controller
                                                name="table.details.metal_purity"
                                                control={control}
                                                render={({ field }) => (
                                                    <Select onValueChange={field.onChange} value={field.value ?? ""}>
                                                        <SelectTrigger className="h-9 w-24 text-sm">
                                                            <SelectValue placeholder="Purity" />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {purityData.map((p, i) => (
                                                                <SelectItem key={i} value={`${p.purity}`}>{p.purity}</SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                )}
                                            />
                                        )}
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        {subItemIsRaw ? (
                                            <span className="text-xs text-gray-300">—</span>
                                        ) : (
                                            <Input type="number" {...register("table.details.sub_pcs")} className="h-9 text-sm bg-white w-20" placeholder="0" />
                                        )}
                                    </td>
                                    <td className="px-2 py-1.5 border-b border-gray-100">
                                        {subItemIsRaw ? (
                                            <span className="text-xs text-gray-300">—</span>
                                        ) : (
                                            <Input type="number" step="0.001" {...register("table.details.sub_ct")} className="h-9 text-sm bg-white w-20" placeholder="0.000" />
                                        )}
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
                                        <TH></TH>
                                        <TH>Barcode</TH>
                                        <TH>Item</TH>
                                        <TH>Pcs</TH>
                                        <TH>Ct</TH>
                                        <TH>GW</TH>
                                        <TH>Purity</TH>
                                        <TH>Making</TH>
                                        <TH>Rate</TH>
                                        <TH>Oth. Making</TH>
                                        <TH>Total</TH>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rs.map((item, idx) => {
                                        const parentName = (mainItemData.find(m => m.short_code === item.item)?.item_name) || item.item_name || item.item;
                                        return (
                                        <React.Fragment key={idx}>
                                            <tr className="bg-violet-50 border-t border-violet-100">
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
                                                <td className="px-2 py-1.5 font-semibold text-primary">{item.barcode}</td>
                                                <td className="px-2 py-1.5">{parentName}</td>
                                                <td className="px-2 py-1.5">{item.pcs}</td>
                                                <td className="px-2 py-1.5"></td>
                                                <td className="px-2 py-1.5">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</td>
                                                <td className="px-2 py-1.5">{item.purity}</td>
                                                <td className="px-2 py-1.5">
                                                    {item.making_val ? `${item.making_val}${item.making_type === 'per_nw' ? '/g' : ''}` : ''}
                                                </td>
                                                <td className="px-2 py-1.5"></td>
                                                <td className="px-2 py-1.5">{item.other_chg}</td>
                                                <td className="px-2 py-1.5 font-semibold">{item.total_amount != null ? parseFloat(item.total_amount).toFixed(2) : ''}</td>
                                            </tr>
                                            {item.barcodedetails_set?.map((detail, di) => {
                                                const subItemName = (mainItemData.find(m => m.short_code === detail.item)?.item_name) || detail.item;
                                                return (
                                                <tr key={di} className="bg-violet-50/50 border-t border-violet-50">
                                                    <td className="px-2 py-1 text-xs">
                                                        <div className="flex gap-1">
                                                            <button
                                                                type="button"
                                                                onClick={() => handleEditSubItem(idx, di)}
                                                                className="p-1 rounded text-primary hover:bg-violet-50"
                                                            >
                                                                <Pencil className="size-3.5" />
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDeleteSubItem(idx, di)}
                                                                className="p-1 rounded text-red-500 hover:bg-red-50"
                                                            >
                                                                <Trash2 className="size-3.5" />
                                                            </button>
                                                        </div>
                                                    </td>
                                                    <td className="px-2 py-1 pl-6 text-xs text-gray-400 font-mono">{detail.packet || "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{subItemName}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.pcs}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.ct != null ? parseFloat(detail.ct).toFixed(3) : "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.gw != null ? parseFloat(detail.gw).toFixed(3) : "—"}</td>
                                                    <td className="px-2 py-1 text-xs">{detail.purity || detail.metal_purity || "—"}</td>
                                                    <td className="px-2 py-1 text-xs"></td>
                                                    <td className="px-2 py-1 text-xs">{detail.rate}</td>
                                                    <td className="px-2 py-1 text-xs font-medium">{detail.amt}</td>
                                                    <td className="px-2 py-1 text-xs"></td>
                                                </tr>
                                                );
                                            })}
                                        </React.Fragment>
                                    );
                                })}
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

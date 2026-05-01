import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { useF2Navigate } from "@/hooks/useF2Navigate"
import { useEnterAsTab } from "@/hooks/useEnterAsTab"
import { useQuery ,useQueryClient,useMutation} from '@tanstack/react-query';

import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableHead, TableHeader, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, getLedger, createCustomerOrder, getStates, fetchPVNoNext, fetchPoNoNext, fetchPackets, fetchPos, fetchStoneIssuesFilterJobs, fetchStoneIssued, createPurchaseVoucher, fetchBarcodes, fetchHSNs, fetchLedgerTDSInfo } from "@/services/apiService";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchCustomerOrders, fetchOrderItem, fetchPurchaseVoucherForEdit, fetchSlNosOrders, getCustomerItemAsPurchaseStyle, getGoldRate, updatePurchaseVoucherForEdit, fetchPendingPOItemsByVendor, fetchPendingCustomerOrderItems } from "../../../services/apiService";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { SquarePen, Trash2, Paperclip, X, Upload, FileText } from "lucide-react";
import InvoiceUpload from "@/components/AI/InvoiceUpload";
import PurchaseAttachments from "./PurchaseAttachments";
import { uploadPurchaseAttachment } from "@/services/apiService";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { useNavigate } from "react-router";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";
import { useEditDirty } from "@/hooks/useEditDirty";

const PurchaseVoucher = () => {
  const { toast } = useToast()
  const { id } = useParams()
    const queryClient = useQueryClient();
    const createPVmutaion = useMutation({
  mutationFn: ({ data }) => createPurchaseVoucher(data),   // your API call
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: ["purchaseVouchers"],
    });
  },
  onError: (err) => {
    toast.error(err.message || "Delete failed");
  },
});
    const updatePVmutaion = useMutation({
  mutationFn: ({ id,data }) => updatePurchaseVoucherForEdit(data,id),   // your API call
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: ["purchaseVouchers"],
    });
  },
  onError: (err) => {
    toast.error(err.message || "Delete failed");
  },
});
  const [searchParams] = useSearchParams(); // React Router hook
  const vou_type = searchParams.get('vou_type');
  let navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [pendingFiles, setPendingFiles] = useState([]); // files to upload after create
  const [detailItemDisplay, setDetailItemDisplay] = useState(""); // display label for item field
  const [tableItemDisplay, setTableItemDisplay] = useState(""); // display label for main item field
  const { register: originalRegister, handleSubmit, control, reset, watch, setValue, getValues, formState: { isDirty } } = useForm({
    defaultValues: {
      hsn: "",
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
        "ref_date": new Date().toISOString().split("T")[0],
        "billno": "",
        "gst_billno": "",
        "ldgr": "",
        "sales_person": "",
        "sales_person2": "",
        "remarks": "",
        "freight_charge": 0,
        "freight_amt": 0,
        "mrp": 0,
        "discount_amt": 0,
        "hallmark_charge": 0,
        "add_chrg_amt1": 0,
        "add_chrg_amt2": 0,
        "gst_type": "gst1",
        "sgst_per": 0,
        "cgst_per": 0,
        "igst_per": 0,
        "tcs_per": 0,
        "tcs_amt": 0,
        "round_off": 0,
        "tds_section": null,
        "tds_rate": 0,
        "tds_taxable_value": 0,
        "tds_amt": 0,
        "net_vendor_payable": 0,
        "mode_of_transport": "",
        "voucher_type":"Vendor",
        "is_rcm": false,
      },
      table: {
        "billno": null,
        "date1": null,
        "po_no": "",
        "po_sl_no": null,
        "customer_order_item_id": null,
        "co_no_display": "",
        "co_sl_no_display": null,
        "customer_name_display": "",
        "item": null,
        "barcode": null,
        "barcode_txt": "",
        "order_no": null,
        "sl_no": 0,
        "pcs": null,
        "gw": null,
        "size": "",
        "purity": null,
        "pending_pcs": 0,
        "pending_gw": 0,
        "making_type": "",
        "making_value": null,
        "item_value": null,
        "remarks": "",
        "purchasevoucherdetails_set": [],

      },
      details: {
        "id": null,
        "sl_no": 0,
        "main_item": null,
        "billno": "",
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
      rawDetails: {
        "packet": null,
        "sub_item": null,
        "sub_pcs": 0,
        "sub_ct": 0,
        "sub_gw": 0,
        "metal_purity": null,
        "loss": 0,
        "tunch": 0,
        "fine_wt": 0,
        "rate": 0,
        "value": 0
      }
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
  const editingRowRef = useRef(null); // preserves sub-items while main item is being edited
  const editingSubItemRef = useRef(false); // guards against concurrent sub-item edits & packet effect overwriting rate
  const formRef = useRef(null);
  useEnterAsTab(formRef);
  const [rsRaw, setRsRaw] = useState([]);
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [serialNos, setSerialNos] = useState([]);
  const [statesData, setstatesData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);   // all items (for sub-item lookup & name resolution)
  const [mainItemsM, setMainItemsM] = useState([]);       // type M only (for main item datalist)
  const [customerOrders, setCustomerOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  // Pending-PO picker modal (auto-opens on vendor select)
  const [poPickerOpen, setPoPickerOpen] = useState(false);
  const [pendingPOItems, setPendingPOItems] = useState([]);
  const [poPickerSearch, setPoPickerSearch] = useState("");
  const [selectedPOItemIds, setSelectedPOItemIds] = useState(new Set());
  const [poPickerLoading, setPoPickerLoading] = useState(false);
  // Pending-CO picker modal (direct CO → PV; manual-open only, vendor-agnostic)
  const [coPickerOpen, setCoPickerOpen] = useState(false);
  const [pendingCOItems, setPendingCOItems] = useState([]);
  const [coPickerSearch, setCoPickerSearch] = useState("");
  const [selectedCOItemIds, setSelectedCOItemIds] = useState(new Set());
  const [coPickerLoading, setCoPickerLoading] = useState(false);
  const [purityData, setPurityData] = useState([]);
  const [packets, setPackets] = useState([]);
  const [hsns, setHSNs] = useState([]);
  const [calculate, setCalculate] = useState(0);
  const [tableFormulas, setTableFormulas] = useState({});
  const [uom, setUom] = useState('');
  const [vendorStateCode, setVendorStateCode] = useState('');


  const selectedPacket = watch('details.packet');
  const selectedItem = watch('details.sub_item');
  const detailRate = watch('details.rate');
  const detailSubGw = watch('details.sub_gw');
  const detailSubCt = watch('details.sub_ct');
  const detailSubPcs = watch('details.sub_pcs');
  const selectedPacketData = packets.find(p => p.pckt_no === selectedPacket);
  const detailItemData = mainItemData.find(m => m.short_code === selectedItem);
  const isRawItem = detailItemData?.item_type === "R";
  // Show metal/gold fields only when a raw (gold) item is selected — hide when blank or stone item
  const showMetalFields = isRawItem;
  const detailMetalPurity = watch('details.metal_purity');


  useEffect(() => {
    let uom = null;
    const packet = packets.find(p => p.pckt_no === selectedPacket);
    const selectedItemData = mainItemData.find(i => i.short_code === selectedItem);
    if (!packet && !selectedItemData) return;
    // Use the flat stone_item_uom field returned by PacketSerializer
    if (packet?.stone_item_uom) {
      uom = packet.stone_item_uom.toLowerCase();
    }
    // Item-level UOM takes precedence if item is found in mainItemData
    if (selectedItemData?.uom) {
      uom = selectedItemData.uom.toLowerCase();
    }
    if (uom) setUom(uom);
  }, [selectedPacket, selectedItem, packets])

  useEffect(() => {
    if ((selectedItem?.toLowerCase() ?? "") !== "gold") return;
    const vals = { ...getValues("details") }
    const idx = rs.findIndex(r => r.sl_no === Number(vals.sl_no));
    if (idx >= 0) {
      const tablevalues = rs[idx];
      console.log(tablevalues)
      console.log(evaluateFormula("gw - SUM(purchasevoucherdetails_set.sub_gw)", tablevalues))

      setValue("details.sub_gw", evaluateFormula("gw - SUM(purchasevoucherdetails_set.sub_gw)", tablevalues));
      setValue("details.metal_purity", tablevalues.purity)
      setCalculate(prev => prev + 1)
    }

  }, [uom])

  useEffect(() => {
    if (uom === 'ct') {
      setTableFormulas({
        sub_gw: `sub_ct * 0.2`,
        value: `sub_ct *rate`
      });
    } else if (uom === 'gm') {
      setTableFormulas({
        value: `sub_gw *rate`,
        sub_ct: (selectedItem?.toLowerCase() ?? "") === "gold" ? `(0)` : `sub_gw * 5`
      });
    } else if (uom === 'pcs') {
      setTableFormulas({
        value: `sub_pcs *rate`,
      });
    }
  }, [uom, selectedItem])


  // Auto-fill gold rate from GoldRates when Old Gold item is selected as sub-item
  useEffect(() => {
    const isOldGold = isRawItem && detailItemData?.item_name?.toLowerCase().includes('old gold');
    if (!isOldGold || !detailMetalPurity) return;

    const today = new Date().toISOString().split('T')[0];
    getGoldRate(today).then(res => {
      if (!res.success) return;
      const rateObj = res.data.find(r => r.purity_name === detailMetalPurity);
      if (rateObj) {
        // Standalone old-gold purchase → use buying rate; fall back to legacy rate
        setValue('details.rate', rateObj.buying_rate || rateObj.rate);
        setCalculate(prev => prev + 1);
      }
    });
  }, [isRawItem, detailItemData, detailMetalPurity]);

  useEffect(() => {
    async function fetchData() {
      // All reference data + voucher data (when editing) are fetched in a single
      // Promise.all so every request fires simultaneously instead of sequentially.
      const [
        /* 0 */ ,           // fetchPVNoNext — side-effect only (sets billno), result unused
        /* 1 */ packets,
        /* 2 */ barcodes,
        /* 3 */ customerOrders,
        /* 4 */ customers,
        /* 5 */ states,
        /* 6 */ salesperson,
        /* 7 */ mainItem,
        /* 8 */ mainItemM,
        /* 9 */ purity,
        /* 10 */ poNo,
        /* 11 */ hsnres,
        /* 12 */ voucherResponse,   // null when creating; Response when editing
      ] = await Promise.all([
        fetchPVNoNext(vou_type).then(orderNo => { if (orderNo.success) setValue("form.billno", orderNo.data.billno); }),
        fetchPackets(),
        fetchBarcodes(),
        fetchCustomerOrders(),
        getLedgers({type: vou_type === "Customer" ? "CO,DL" : "VD,KR", page_size: 10000}),
        getStates(),
        fetchSalesperson(),
        fetchMainItem(),
        fetchMainItem({type: "M"}),
        fetchPurity(),
        fetchPos(),
        fetchHSNs(),
        // Fetch the voucher for editing in parallel with all the reference calls above.
        // In create mode (no id) this resolves immediately to null.
        id ? fetchPurchaseVoucherForEdit(id) : Promise.resolve(null),
      ]);

      if (packets.success) setPackets(packets.data.results ?? packets.data);
      if (customerOrders.success) setCustomerOrders(customerOrders.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (states.success) setstatesData(states.data.results ?? states.data);

      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (mainItemM.success) setMainItemsM(mainItemM.data.results ?? mainItemM.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
      if (poNo.success) setValue("po_no", poNo.data.po_no);
      if (hsnres.success) {
        setHSNs(hsnres.data.results);
        // Set default HSN to 711319 (Jewellery plain or studded) in create mode
        if (!id) {
          const jewelleryHsn = hsnres.data.results.find(
            h => h.hsn_no === "711319" || h.description?.toUpperCase().includes("JEWELLERY PLAIN")
          );
          if (jewelleryHsn) setTimeout(() => setValue("hsn", jewelleryHsn.hsn_no), 0);
        }
      }

      // Return the voucher response so the caller can process it after all
      // state setters above have run (avoids potential React batching issues).
      return voucherResponse;
    }

    fetchData().then((voucherResponse) => {
      if (id) {
        if (!voucherResponse?.success) {
          console.error('Error fetching purchase voucher for edit:', voucherResponse?.error);
        } else {
          const data = voucherResponse.data;

          // Set form fields, skipping nested arrays and hsn (handled separately)
          Object.keys(data).forEach((key) => {
            if (key !== 'purchasevoucheritems_set' && key !== 'purchasevoucherdetails_set' && key !== 'hsn') {
              setValue(`form.${key}`, data[key]);
            }
          });

          // Restore HSN at root level (drives tax rate lookup)
          if (data.hsn) {
            setValue("hsn", data.hsn);
          }

          if (data.purchasevoucheritems_set) {
            // Annotate each sub-item with the parent's sl_no so the details
            // input form can correctly reference which row it belongs to.
            setRows(data.purchasevoucheritems_set.map(item => ({
              ...item,
              // Mirror backend FK into the client-side display key used by the row render.
              customer_order_item_id: item.customer_order_item ?? null,
              co_no_display: item.order_no || "",
              purchasevoucherdetails_set: (item.purchasevoucherdetails_set || []).map(d => ({
                ...d,
                sl_no: d.sl_no ?? item.sl_no,
              })),
            })));
          }

          // Only load raw/direct details that are NOT already nested inside items
          if (data.purchasevoucherdetails_set?.length) {
            const nestedIds = new Set();
            (data.purchasevoucheritems_set || []).forEach(item => {
              (item.purchasevoucherdetails_set || []).forEach(d => {
                if (d.id) nestedIds.add(d.id);
              });
            });
            setRsRaw(data.purchasevoucherdetails_set.filter(d => !nestedIds.has(d.id)));
          }

          // vendor_state_code is now embedded in the voucher response (first 2 digits of
          // the vendor GSTIN) — no separate getLedger call needed.
          if (data.vendor_state_code) {
            setVendorStateCode(data.vendor_state_code);
          }
          reset(getValues(), { keepValues: true, keepDirty: false });
          resetTableDirty();
        }
      }

      if (vou_type) {
        setValue("form.voucher_type", vou_type)
        if (vou_type === "Customer") {
          setValue("form.sgst_per", 0)
          setValue("form.cgst_per", 0)
          setValue("form.igst_per", 0)
        }
      }
    });


  }, []);



  const hsn_current       = watch('hsn');
  const current_vou_type  = watch('form.voucher_type');
  const isCustomer        = current_vou_type === 'Customer';

  const sgst_per = watch('form.sgst_per');
  const cgst_per = watch('form.cgst_per');
  const igst_per = watch('form.igst_per');
  const add_chrg_cap1 = watch('form.add_chrg_cap1');
  const add_chrg_cap2 = watch('form.add_chrg_cap2');

  useEffect(() => { if (!add_chrg_cap1) setValue('form.add_chrg_amt1', 0); }, [add_chrg_cap1]);
  useEffect(() => { if (!add_chrg_cap2) setValue('form.add_chrg_amt2', 0); }, [add_chrg_cap2]);

  // Re-fetch party list when voucher type changes in the dropdown
  useEffect(() => {
    if (!current_vou_type) return;
    const roleFilter = current_vou_type === 'Customer' ? 'CO,DL' : 'VD,KR';
    getLedgers({ type: roleFilter, page_size: 10000 }).then(res => {
      if (res.success) setCustomers(res.data.results);
    });
  }, [current_vou_type]);


  // Total excl. taxes = items + all charges (before discount)
  const taxable_value_formula = "SUM(rs.item_value) + SUM(rsRaw.value) + freight_amt + hallmark_charge + add_chrg_amt1 + add_chrg_amt2"
  // GST base = total excl. taxes minus discount
  const gst_base_formula = `(${taxable_value_formula}) - discount_amt`
  const total_incl_gst_formula = `(${gst_base_formula}) + (${gst_base_formula}) * (cgst_per / 100) + (${gst_base_formula}) * (igst_per / 100) + (${gst_base_formula}) * (sgst_per / 100)`
  const tcs_amt_formula = `(tcs_per / 100) * (${total_incl_gst_formula})`
  const main_formulas = {
    taxable_value: taxable_value_formula,
    item_total: taxable_value_formula,
    cgst: `(${gst_base_formula}) * (cgst_per / 100)`,
    igst: `(${gst_base_formula}) * (igst_per / 100)`,
    sgst: `(${gst_base_formula}) * (sgst_per / 100)`,
    total_incl_gst: total_incl_gst_formula,
    tcs_amt: tcs_amt_formula,
    bill_value: `(${total_incl_gst_formula}) + (${tcs_amt_formula}) + round_off`,
    tds_taxable_value: gst_base_formula,
    tds_amt: `(tds_taxable_value * tds_rate) / 100`,
    net_vendor_payable: `bill_value - tds_amt`,
  }

  const stattableFormulas =
  {
    fine_wt: `sub_gw * tunch / 100`
  }
  const statmaintableFormulas =
  {
    pending_gw: `gw`,
    pending_pcs: `pcs`,
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
          if (typeof value === "number") return `(${isNaN(value) ? 0 : value})`;
          return `'${value}'`;
        }

        return "0"; // Default replacement if variable is not found
      });




      // Evaluate the final expression
      return parseFloat(new Function(`return ${processedFormula};`)())?.toFixed(2);
    } catch (error) {
      console.error("Formula evaluation error:", error);
      return "";
    }
  };

  const watchedFields = watch('form')
  const watchedPacketDetail = watch('details.packet')
  const watchedTunch = watch('details.tunch')
  const watchedMaking = watch('table.making')
  const watchedMakingType = watch('table.making_type')



  useEffect(() => {
    const form = { ...getValues('form'), rs: rs, rsRaw: rsRaw };
    const table = getValues('details');
    const maintable = getValues('table');


    Object.keys(main_formulas).forEach((col) => {
      const val = evaluateFormula(main_formulas[col], form);
      setValue(`form.${col}`, val);
      form[col] = parseFloat(val) || 0;   // update local snapshot so later formulas (e.g. bill_value) use fresh cgst/sgst/igst
    })

    Object.keys(tableFormulas).forEach((col) => {
      setValue(`details.${col}`, evaluateFormula(tableFormulas[col], table));
    })

    Object.keys(stattableFormulas).forEach((col) => {
      setValue(`details.${col}`, evaluateFormula(stattableFormulas[col], table));
    })

    Object.keys(statmaintableFormulas).forEach((col) => {
      setValue(`table.${col}`, evaluateFormula(statmaintableFormulas[col], maintable));
    })

    // When tunch is entered for Gold, rate must be 0 (tunch-based pricing)
    if (parseFloat(table.tunch || 0) > 0 && detailItemData?.short_code === "Gold") {
      setValue('details.rate', 0);
    }
  }, [rs, rsRaw, watchedFields, watchedTunch, calculate]);

  // Auto-fill making_value when making_type is 'val' (flat value)
  useEffect(() => {
    if (watchedMakingType === 'val') {
      setValue('table.making_value', parseFloat(watchedMaking) || 0);
    }
  }, [watchedMaking, watchedMakingType]);

  useEffect(() => {
    // Skip when editing a sub-item — rate/value are already set by handleEditSubItem
    if (editingSubItemRef.current) {
      editingSubItemRef.current = false; // consume the guard
      return;
    }
    if (!watchedPacketDetail) {
      setDetailItemDisplay("");
      setValue('details.sub_item', "");
      setValue('details.rate', 0);
      setCalculate(prev => prev + 1);
      return;
    }
    const packet = packets.find(p => p.pckt_no === watchedPacketDetail);
    // Use the flat fields exposed by PacketSerializer (stone_item_short_code, stone_item_name, stone_item_uom)
    if (packet?.stone_item_short_code) {
      setValue('details.sub_item', packet.stone_item_short_code);
      setDetailItemDisplay(packet.stone_item_name || packet.stone_item_short_code);
      setValue('details.rate', packet.rate_for_retail ?? 0);
      // Trigger formula recalculation so value auto-computes based on new rate
      setCalculate(prev => prev + 1);
    }
  }, [watchedPacketDetail, packets]);

  // Auto-calculate value based on UOM
  useEffect(() => {
    const rate = parseFloat(detailRate || 0);
    let qty;
    if (uom === 'ct') {
      qty = parseFloat(detailSubCt || 0);
    } else if (uom === 'pcs') {
      qty = parseFloat(detailSubPcs || 0);
    } else {
      qty = parseFloat(detailSubGw || 0);
    }
    setValue('details.value', parseFloat((rate * qty).toFixed(2)));
  }, [detailRate, detailSubGw, detailSubCt, detailSubPcs, uom]);


  useEffect(() => {
    setValue("details.sl_no", rs.length);
  }, [rs])

  useEffect(() => {
    const current_voucher_type = getValues("form.voucher_type");
    if (current_voucher_type === "Customer") return;

    let hsn_ = hsns.find(e => e.hsn_no === hsn_current);

    if (hsn_) {
      const retailState = sessionStorage.getItem('state_code') || "";
      // IGST applies if vendor is from a different state; CGST+SGST for same state or no GSTIN
      const isIntraState = vendorStateCode ? vendorStateCode === retailState : true;
      setValue('form.sgst_per', isIntraState ? parseFloat(hsn_.sgst) : 0.0);
      setValue('form.cgst_per', isIntraState ? parseFloat(hsn_.cgst) : 0.0);
      setValue('form.igst_per', isIntraState ? 0.0 : parseFloat(hsn_.igst));
      setCalculate(prev => prev + 1);
    }
  }, [hsn_current, vendorStateCode]);

  const onSubmit = async (data) => {
    const form = getValues("form");
    if (rs.length === 0 && rsRaw.length === 0) {
      toast({ title: "Table is empty" })
      return;
    }
    // Weight reconciliation: sub-item GW totals must match parent item GW
    for (const item of rs) {
      const details = item.purchasevoucherdetails_set || [];
      if (!details.length) continue;
      const totalSubGW = details.reduce((sum, d) => sum + parseFloat(d.sub_gw || 0), 0);
      const itemGW = parseFloat(item.gw || 0);
      if (Math.abs(totalSubGW - itemGW) > 0.01) {
        toast({
          title: `Weight mismatch for item "${item.item}"`,
          description: `Sub-items total ${totalSubGW.toFixed(3)}g but item GW is ${itemGW.toFixed(3)}g. Please reconcile.`,
          variant: "destructive",
        });
        return;
      }
    }
    const toIntOrNull = v => (v === "" || v === undefined || v === null || Number.isNaN(Number(v))) ? null : Number(v);
    form.purchasevoucheritems_set = rs.map(item => ({
      ...item,
      pcs: toIntOrNull(item.pcs),
      pending_pcs: toIntOrNull(item.pending_pcs),
      making_value: toIntOrNull(item.making_value),
      // Backend FK: translate client-side `customer_order_item_id` to the
      // DRF field name. Direct CO → PV path; null for PO-linked or manual rows.
      customer_order_item: item.customer_order_item_id ?? null,
      purchasevoucherdetails_set: (item.purchasevoucherdetails_set || []).map(d => ({
        ...d,
        sub_pcs: toIntOrNull(d.sub_pcs),
      })),
    }));
    form.purchasevoucherdetails_set = rsRaw.map(d => ({
      ...d,
      sub_pcs: toIntOrNull(d.sub_pcs),
    }));
    form.hsn = getValues("hsn") || null;

    // Recompute bill_value fresh from current row data right before sending,
    // so we never rely on the formula-effect having already converged.
    const _itemValueSum = rs.reduce((s, item) => s + parseFloat(item.item_value || 0), 0)
                        + rsRaw.reduce((s, d) => s + parseFloat(d.value || 0), 0);
    const _taxable = _itemValueSum
      + parseFloat(form.freight_amt || 0)
      + parseFloat(form.hallmark_charge || 0)
      + parseFloat(form.add_chrg_amt1 || 0)
      + parseFloat(form.add_chrg_amt2 || 0);
    form.bill_value = parseFloat(
      (_taxable
        + parseFloat(form.cgst || 0)
        + parseFloat(form.sgst || 0)
        + parseFloat(form.igst || 0)
        + parseFloat(form.tcs_amt || 0)
        + parseFloat(form.round_off || 0)
      ).toFixed(2)
    );
    setSaving(true);
    try {
      const response = id
        ? await updatePVmutaion.mutateAsync({ data: form, id })
        : await createPVmutaion.mutateAsync({ data: form });

      if (response.success) {
        // Upload any pending files (add mode)
        if (!id && pendingFiles.length > 0) {
          const newId = response.data.id;
          for (const file of pendingFiles) {
            await uploadPurchaseAttachment(newId, file);
          }
          setPendingFiles([]);
        }
        toast({ title: "Form submitted successfully!" });
        setTimeout(() => navigate("/purchase/list/"), 500);
      } else {
        setSaving(false);
        toast({
          title: "Form submission failed.",
          description: renderErrorTree(response.error),
          variant: "destructive",
        });
      }
    } catch {
      setSaving(false);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(onSubmit));
  useF2Navigate("/purchase/add/");

  const handleBlur = async (e) => {
    const { customer_order_id } = getValues();
    try {
      const data = await fetchSlNosOrders(customer_order_id);
      setSerialNos(data.data.sl_no_list);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }

  const handleBlur1 = async (e) => {

    const { customer_order_id, sl_no } = getValues();
    try {
      const data = await getCustomerItemAsPurchaseStyle(customer_order_id, sl_no);
      console.log(data)
      Object.keys(data.data).forEach((key) => {
        setValue(`table.${key}`, data.data[key]);
      });

    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }

  const handleEdit = (index) => {
    const row = rs[index];
    editingRowRef.current = { index, row }; // preserve index + full row
    reset({ table: row, form: getValues('form'), hsn: getValues('hsn'), details: getValues('details') });
    const itemData = mainItemsM.find(m => m.short_code === row.item);
    setTableItemDisplay(itemData ? itemData.item_name : (row.item || ""));
    // Mark row as being-edited instead of removing it — sub-items stay visible
    setRows(prev => prev.map((r, i) => i === index ? { ...r, _editing: true } : r));
    markTableDirty();
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const handleDeleteSubItem = (rowIndex, subIndex, key) => {
    setRows((prev) =>
      prev.map((row, i) => {
        if (i !== rowIndex) return row;
        const updatedDetails = row[key].filter((_, j) => j !== subIndex);
        const subTotal = updatedDetails.reduce((sum, d) => parseFloat(sum) + parseFloat(d.value || 0), 0);
        const makingAmt = row.making_type === 'val' ? parseFloat(row.making_value || 0) : 0;
        const updatedItemValue = parseFloat((subTotal + makingAmt).toFixed(2));
        return { ...row, [key]: updatedDetails, item_value: updatedItemValue };
      })
    );
  };

  const handleEditSubItem = (rowIndex, subIndex, key) => {
    // Prevent editing multiple sub-items at once — the first would be lost
    const currentDetails = getValues('details');
    if (currentDetails.sub_item) {
      toast({ title: "Finish editing the current sub-item first", description: "Press Tab to save the current sub-item before editing another.", variant: "destructive" });
      return;
    }

    const subItem = rs[rowIndex][key][subIndex];
    // Set guard BEFORE setValue calls so the packet effect doesn't overwrite rate
    editingSubItemRef.current = true;

    // Populate the input row with the sub-item's values.
    // Preserve the database id so the backend UPDATES the existing record in-place
    // (cleaner than delete+recreate; delta-based inventory signals handle the adjustment).
    setValue('details.id', subItem.id ?? null);
    setValue('details.sl_no', rs[rowIndex].sl_no);
    setValue('details.packet', subItem.packet || "");
    setValue('details.sub_item', subItem.sub_item || "");
    setValue('details.sub_pcs', subItem.sub_pcs || 0);
    setValue('details.sub_ct', subItem.sub_ct || 0);
    setValue('details.sub_gw', subItem.sub_gw || 0);
    setValue('details.metal_purity', subItem.metal_purity || "");
    setValue('details.loss', subItem.loss || 0);
    setValue('details.tunch', subItem.tunch || 0);
    setValue('details.fine_wt', subItem.fine_wt || 0);
    setValue('details.rate', subItem.rate || 0);
    setValue('details.value', subItem.value || 0);
    const subItemData = mainItemData.find(m => m.short_code === subItem.sub_item);
    setDetailItemDisplay(subItemData ? subItemData.item_name : (subItem.sub_item || ""));
    // Trigger formula recalculation so value/fine_wt auto-compute correctly in edit mode
    setCalculate(prev => prev + 1);

    // Remove from saved list so user can re-add after editing
    // Also recalculate item_value so bill_value stays consistent
    setRows((prev) =>
      prev.map((row, i) => {
        if (i !== rowIndex) return row;
        const updatedDetails = row[key].filter((_, j) => j !== subIndex);
        const subTotal = updatedDetails.reduce((sum, d) => parseFloat(sum) + parseFloat(d.value || 0), 0);
        const makingAmt = row.making_type === 'val' ? parseFloat(row.making_value || 0) : 0;
        const updatedItemValue = parseFloat((subTotal + makingAmt).toFixed(2));
        return { ...row, [key]: updatedDetails, item_value: updatedItemValue };
      })
    );
  };


  const handleKeyDown = (e) => {
    if (e.key === "Tab") {
      e.preventDefault(); // if you want to actually intercept the Tab
      handleAddRow();
    }
  };

  const handleKeyDownDetails = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      // if you want to actually intercept the Tab
      const vals = { ...getValues("details") }
      console.log(vals)
      if (!vals.sub_item) { toast({ title: "No item added" }); return; }

      // No main item entered → save as standalone sub-item (e.g. raw stones / gold).
      if (rs.length === 0) {
        markTableDirty();
        setRsRaw(prev => [...prev, { ...vals }]);
        reset({
          form: getValues('form'),
          hsn: getValues('hsn'),
          table: getValues('table'),
          details: {
            id: null,
            sl_no: "",
            billno: "",
            packet: "",
            sub_item: "",
            sub_pcs: 0,
            sub_ct: 0.0,
            sub_gw: 0.0,
            metal_purity: "",
            loss: 0,
            tunch: 0.0,
            fine_wt: 0.0,
            rate: 0.0,
            value: 0.0,
          },
        });
        setDetailItemDisplay("");
        return;
      }
      const idx = rs.findIndex(r => r.sl_no === Number(vals.sl_no));
      if (idx < 0) {
        const validSlNos = rs.map(r => r.sl_no).join(", ");
        toast({ title: `Invalid Sl No — valid numbers: ${validSlNos}` });
        return;
      }
      if (idx >= 0) {
        const tablevalues = { ...rs[idx] };
        const existing = Array.isArray(tablevalues.purchasevoucherdetails_set)
          ? tablevalues.purchasevoucherdetails_set
          : [];

        // Weight validation: sub-item GW must not exceed remaining balance
        const usedGW = existing.reduce((sum, d) => sum + parseFloat(d.sub_gw || 0), 0);
        const newGW  = parseFloat(vals.sub_gw || 0);
        const parentGW = parseFloat(tablevalues.gw || 0);
        if (newGW > 0 && usedGW + newGW > parentGW + 0.001) {
          toast({
            title: "GW exceeds balance",
            description: `Available: ${(parentGW - usedGW).toFixed(3)}g, Entered: ${newGW.toFixed(3)}g`,
            variant: "destructive",
          });
          return;
        }

        tablevalues.purchasevoucherdetails_set = [...existing, vals];
        const subTotal = tablevalues.purchasevoucherdetails_set.reduce((sum, detail) => parseFloat(sum) + parseFloat(detail.value || 0), 0);
        const makingAmt = tablevalues.making_type === 'val' ? parseFloat(tablevalues.making_value || 0) : 0;
        tablevalues.item_value = parseFloat((subTotal + makingAmt).toFixed(2));

        markTableDirty();
        setRows((prevData) =>
          prevData.map((row, i) => (i === idx ? { ...tablevalues } : row))
        );
        const lastSlNo = rs.length > 0 ? rs[rs.length - 1].sl_no : 1;
        reset({
          form: getValues('form'),
          hsn: getValues('hsn'),
          table: getValues('table'),
          details: {
            id: null,
            sl_no: lastSlNo,
            billno: "",
            packet: "",
            sub_item: "",
            sub_pcs: 0,
            sub_ct: 0.0,
            sub_gw: 0.0,
            metal_purity: "",
            loss: 0,
            tunch: 0.0,
            fine_wt: 0.0,
            rate: 0.0,
            value: 0.0,
          },
        });
        setDetailItemDisplay("");
      }

    }
  };


  const handleAddRow = () => {
    const newItem = getValues("table");
    if (!newItem.item) { toast({ title: "No item added" }); return; }

    // Before adding a new row, verify existing rows with sub-items are GW-reconciled
    if (!editingRowRef.current && rs.filter(r => !r._editing).length > 0) {
      for (const row of rs.filter(r => !r._editing)) {
        const details = row.purchasevoucherdetails_set || [];
        if (!details.length) continue; // direct item — no check needed
        const totalSubGW = details.reduce((sum, d) => sum + parseFloat(d.sub_gw || 0), 0);
        const itemGW = parseFloat(row.gw || 0);
        if (Math.abs(totalSubGW - itemGW) > 0.001) {
          toast({
            title: `Sub-item GW doesn't match for Sl No ${row.sl_no}`,
            description: `Sub-items total: ${totalSubGW.toFixed(3)}g, Item GW: ${itemGW.toFixed(3)}g. Reconcile before adding another item.`,
            variant: "destructive",
          });
          return;
        }
      }
    }

    if (editingRowRef.current) {
      // Update the row in-place: restore sl_no and sub-items, clear editing flag
      const { index, row } = editingRowRef.current;
      newItem.sl_no = row.sl_no;
      newItem.purchasevoucherdetails_set = row.purchasevoucherdetails_set || [];
      delete newItem._editing;
      editingRowRef.current = null;
      setRows(prev => prev.map((r, i) => i === index ? { ...newItem } : r));
      markTableDirty();
    } else {
      // New row: assign next sl_no
      newItem.sl_no = rs.length > 0 ? Math.max(...rs.filter(r => !r._editing).map(r => r.sl_no || 0)) + 1 : 1;
      if (!Array.isArray(newItem.purchasevoucherdetails_set)) {
        newItem.purchasevoucherdetails_set = [];
      }
      setRows([...rs, { ...newItem }]);
      markTableDirty();
    }
    setTableItemDisplay("");
    reset({
      form: { ...getValues('form') },
      hsn: getValues('hsn'),
      table: {
        billno: "",
        barcode: "",
        item: "",
        order_no: "",
        po_no: "",
        po_sl_no: null,
        customer_order_item_id: null,
        co_no_display: "",
        co_sl_no_display: null,
        customer_name_display: "",
        pcs: 0,
        pending_pcs: 0,
        gw: 0.0,
        pending_gw: 0.0,
        size: "",
        purity: 0,
        making: 0.0,
        making_type: "",
        making_value: 0,
        item_value: 0,
        ret_status: false,
        amount: 0,
        remarks: "",
        purchasevoucherdetails_set: [],
      },
      details: {
        sl_no: "",
        billno: "",
        packet: "",
        sub_item: "",
        sub_pcs: 0,
        sub_ct: 0.0,
        sub_gw: 0.0,
        metal_purity: "",
        loss: 0,
        tunch: 0.0,
        fine_wt: 0.0,
        rate: 0.0,
        value: 0.0,
      },
    });
  };

  const handleAddRawRow = () => {
    const newItem = getValues("rawDetails");
    if (!newItem.sub_item) { toast({ title: "No item added" }); return; }
    setRsRaw([...rsRaw, { ...newItem }]);
    markTableDirty();
    reset({
      form: getValues('form'),
      hsn: getValues('hsn'),
      table: getValues('table'),
      details: getValues('details'),
      rawDetails: {
        packet: null,
        sub_item: null,
        sub_pcs: 0,
        sub_ct: 0,
        sub_gw: 0,
        metal_purity: null,
        loss: 0,
        tunch: 0,
        fine_wt: 0,
        rate: 0,
        value: 0,
      },
    });
  };

  const handleDeleteRawRow = (index) => {
    setRsRaw((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const handleEditRawRow = (index) => {
    // Prevent editing multiple sub-items at once.
    const currentDetails = getValues('details');
    if (currentDetails.sub_item) {
      toast({ title: "Finish editing the current sub-item first", description: "Press Tab to save the current sub-item before editing another.", variant: "destructive" });
      return;
    }
    const subItem = rsRaw[index];
    if (!subItem) return;

    editingSubItemRef.current = true;

    setValue('details.id', subItem.id ?? null);
    setValue('details.sl_no', subItem.sl_no ?? null);
    setValue('details.packet', subItem.packet || "");
    setValue('details.sub_item', subItem.sub_item || "");
    setValue('details.sub_pcs', subItem.sub_pcs || 0);
    setValue('details.sub_ct', subItem.sub_ct || 0);
    setValue('details.sub_gw', subItem.sub_gw || 0);
    setValue('details.metal_purity', subItem.metal_purity || "");
    setValue('details.loss', subItem.loss || 0);
    setValue('details.tunch', subItem.tunch || 0);
    setValue('details.fine_wt', subItem.fine_wt || 0);
    setValue('details.rate', subItem.rate || 0);
    setValue('details.value', subItem.value || 0);
    const subItemData = mainItemData.find(m => m.short_code === subItem.sub_item);
    setDetailItemDisplay(subItemData ? subItemData.item_name : (subItem.sub_item || ""));
    setCalculate(prev => prev + 1);

    // Remove from rsRaw so the user can re-add after editing.
    setRsRaw((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const billSummaryRows = [
    { label: 'Hallmark Charge',    field: 'form.hallmark_charge', editable: true },
    { label: 'Freight Charge',     field: 'form.freight_amt',     editable: true },
    { label: '', field: 'form.add_chrg_amt1', captionField: 'form.add_chrg_cap1', captionPlaceholder: 'Charge 1 name' },
    { label: '', field: 'form.add_chrg_amt2', captionField: 'form.add_chrg_cap2', captionPlaceholder: 'Charge 2 name' },
    { isSeparator: true },
    { label: 'Total excl. Taxes',  field: 'form.taxable_value' },
    { label: 'Discount',           field: 'form.discount_amt',    editable: true },
    { isSeparator: true },
    ...(!isCustomer && cgst_per !== 0 ? [{ label: `CGST @ ${cgst_per}%`, field: 'form.cgst' }] : []),
    ...(!isCustomer && sgst_per !== 0 ? [{ label: `SGST @ ${sgst_per}%`, field: 'form.sgst' }] : []),
    ...(!isCustomer && igst_per !== 0 ? [{ label: `IGST @ ${igst_per}%`, field: 'form.igst' }] : []),
    { label: isCustomer ? 'Total' : 'Total incl. GST', field: 'form.total_incl_gst' },
    { isSeparator: true },
    { label: 'TCS',                field: 'form.tcs_amt',         editable: true },
    { label: 'Round Off',          field: 'form.round_off',       editable: true, step: '0.001' },
    { label: 'Bill Total',         field: 'form.bill_value',      isTotal: true },
    ...(watch('form.tds_rate') > 0 ? [
      { isSeparator: true },
      { label: `TDS @ ${watch('form.tds_rate')}% (deducted)`, field: 'form.tds_amt' },
      { label: 'Net Payable to Vendor', field: 'form.net_vendor_payable', isTotal: true },
    ] : []),
  ];

  return (
    <div className="container mt-4">
      <form
        ref={formRef}
        className="p-6 shadow-sm rounded-xl bg-white border border-gray-100"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">1</span>
            <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">Bill Details</span>
          </div>
          <InvoiceUpload
            onExtracted={(data) => {
              if (data.invoice_date) setValue("form.date1", data.invoice_date);
              if (data.invoice_number) setValue("form.billno", data.invoice_number);
              if (data.total_amount) setValue("form.bill_value", data.total_amount);
            }}
          />
        </div>
        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4 mb-4 mt-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
          </FieldContainer>
          <FieldContainer>
            <Label className="text-nowrap">Bill No</Label>
            <div className="flex items-center gap-2 flex-1">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate">
                {watch("form.billno") || <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>}
              </span>
              <input type="hidden" {...register("form.billno")} />
            </div>
          </FieldContainer>

          <FieldContainer>
            <Label className="text-nowrap">Voucher Type</Label>
            <Controller
              name="form.voucher_type"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value}
                  disabled={vou_type}
                  onValueChange={(val) => {
                    field.onChange(val);
                    setRows([]);
                    markTableDirty();
                    setTableItemDisplay("");
                    setDetailItemDisplay("");
                    setValue("hsn", "");
                  }}
                >
                  <SelectTrigger data-testid="voucher-type">
                    <SelectValue> {field.value}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem id="ven" key={"Vendor"} value="Vendor">Vendor</SelectItem>
                    <SelectItem id='cus' key={"Customer"} value="Customer">Customer</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>




          {/* Party Details */}
          <FieldContainer>
            <Label className="text-nowrap">Party Name</Label>
            <SearchableComboBox
              options={customers}
              value={watch("form.ldgr_name") ?? ""}
              onSelect={async (opt) => {
                setValue("form.ldgr_name", opt.ac_name)
                setValue("form.ldgr", opt.id)
                // Extract state code from vendor's GSTIN (first 2 digits = state code)
                const gstStateCode = opt.gst ? opt.gst.substring(0, 2) : "";
                setVendorStateCode(gstStateCode);
                const tdsRes = await fetchLedgerTDSInfo(opt.id);
                if (tdsRes.success && tdsRes.data.tds_applicable) {
                  setValue("form.tds_section", tdsRes.data.section_id);
                  setValue("form.tds_rate", tdsRes.data.rate);
                } else {
                  setValue("form.tds_section", null);
                  setValue("form.tds_rate", 0);
                  setValue("form.tds_amt", 0);
                  setValue("form.net_vendor_payable", 0);
                }
                // Auto-open Purchase-Order picker only if vendor has pending items.
                if (!isCustomer && !id) {
                  setSelectedPOItemIds(new Set());
                  setPoPickerSearch("");
                  setPoPickerLoading(true);
                  const res = await fetchPendingPOItemsByVendor(opt.id);
                  const items = res.success ? (res.data || []) : [];
                  setPendingPOItems(items);
                  setPoPickerLoading(false);
                  if (items.length > 0) setPoPickerOpen(true);
                }
              }}
              placeholder={isCustomer ? "Search customer / dealer…" : "Search vendor / karigar…"}
            />
            <input type="hidden" {...register("form.ldgr", { required: true })} />
          </FieldContainer>

          {!isCustomer && (
          <FieldContainer>
            <Label className="text-nowrap">HSN code <span className="text-primary font-normal text-xs">(select to add items)</span></Label>

            {/* When rows exist (or editing), Radix Select never opens so SelectValue
                can't resolve the label — render a plain disabled input instead. */}
            {rs.length > 0 ? (
              <Input
                disabled
                value={(() => {
                  const match = hsns.find(h => h.hsn_no === hsn_current);
                  return match ? `${match.hsn_no} — ${match.description || ''}`.trim() : (hsn_current || '');
                })()}
              />
            ) : (
              <Controller
                name="hsn"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger data-testid="hsn-select">
                      <SelectValue placeholder="Select HSN" />
                    </SelectTrigger>

                    <SelectContent>
                      {hsns.map((hsn, index) => (
                        <SelectItem key={index} value={hsn.hsn_no}>{hsn.description || hsn.hsn_no}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            )}

          </FieldContainer>
          )}
          <FieldContainer>
            <Label htmlFor="ref_no " className="text-nowrap">Bill Ref No.</Label>
            <Input type="text" {...register("form.ref_no")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="ref_date">Ref.Date</Label>
            <Input type="date" {...register("form.ref_date")} required />
          </FieldContainer>
          <Input type="hidden" {...register("form.ldgr_code")} />
          <Input type="hidden" {...register("customer_order_item")} />
        </div>
        {hsn_current || id ? <>

          {/* Item Details */}
          <div className="flex items-center gap-3 my-5">
            <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">2</span>
            <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">Main and Sub Item Details</span>
            <div className="flex-1 h-px bg-violet-100" />
            {!isCustomer && !id && watch("form.ldgr") && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setPoPickerOpen(true)}
                className="cursor-pointer h-7 px-2.5 text-xs gap-1.5 shrink-0"
              >
                Pick from Purchase Orders
                {pendingPOItems.length > 0 && (
                  <span className="inline-flex items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-semibold px-1.5 min-w-4 h-4">
                    {pendingPOItems.length}
                  </span>
                )}
              </Button>
            )}
            {!isCustomer && !id && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={async () => {
                  setCoPickerLoading(true);
                  setCoPickerOpen(true);
                  setSelectedCOItemIds(new Set());
                  setCoPickerSearch("");
                  const res = await fetchPendingCustomerOrderItems();
                  setPendingCOItems(res.success ? (res.data || []) : []);
                  setCoPickerLoading(false);
                }}
                className="cursor-pointer h-7 px-2.5 text-xs gap-1.5 shrink-0"
              >
                Pick from Customer Orders
                {pendingCOItems.length > 0 && (
                  <span className="inline-flex items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-semibold px-1.5 min-w-4 h-4">
                    {pendingCOItems.length}
                  </span>
                )}
              </Button>
            )}
          </div>
          <br></br>
          <div className="overflow-x-auto">
          <Table className="w-full table-fixed border-collapse">
            <TableBody>
              <TableRow className="w-full bg-violet-50">
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Item</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Pcs</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">GW</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Size</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Purity</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Making</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Making Type</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Making Amt</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Value</TableCell>
                <TableCell className="px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Remarks</TableCell>
              </TableRow>

              <TableRow>



                <TableCell className="w-28 px-4 py-2 border">
                  <Input
                    list="item_list"
                    value={tableItemDisplay}
                    onChange={(e) => {
                      const typed = e.target.value;
                      setTableItemDisplay(typed);
                      const found = mainItemsM.find(m => m.item_name === typed || m.short_code === typed);
                      setValue('table.item', found ? found.short_code : typed);
                      if (found?.default_purity) {
                        setValue('table.purity', found.default_purity);
                      }
                    }}
                    placeholder="Item"
                  />
                  <datalist id="item_list">
                    {mainItemsM.map((item, index) => (
                      <option key={index} value={item.item_name} />
                    ))}
                  </datalist>
                  <input type="hidden" {...register("table.item")} />
                </TableCell>




                <TableCell className="px-4 py-2 border">
                  <Input type="number" {...register("table.pcs", { setValueAs: v => v === "" || v === undefined ? null : Number(v) })} />
                </TableCell>
                <TableCell className="px-4 py-2 border">
                  <Input type="number" step="0.001" {...register("table.gw")} />
                </TableCell>
                <TableCell className="px-4 py-2 border">
                  <Input type="text" {...register("table.size")} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Controller
                    name={`table.purity`}
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger data-testid="table-purity">
                          <SelectValue placeholder="Select Purity" />
                        </SelectTrigger>
                        <SelectContent>
                          {purityData.map((item, index) => (
                            <SelectItem key={index} value={`${item.purity}`}>{item.purity}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>


                <TableCell className="px-4 py-2 border">
                  <Input type="number" {...register("table.making")} />
                </TableCell>
                <TableCell className="px-4 py-2 border" >
                  <Controller
                    name="table.making_type"
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger data-testid="making-type">
                          <SelectValue placeholder="Making type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="per_nw">% of wt</SelectItem>
                          <SelectItem value="val">Value</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>
                <TableCell className="px-4 py-2 border">
                  <Input type="number" {...register("table.making_value", { setValueAs: v => v === "" || v === undefined ? null : Number(v) })} />
                </TableCell>
                <TableCell className="px-4 py-2 border">
                  <Input type="number" {...register("table.item_value")} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register("table.remarks")} />
                </TableCell>

              </TableRow>




            </TableBody>
          </Table>
          </div>


          <br></br>

          <div className="overflow-x-auto">
          <Table className="w-full table-fixed border-collapse">
            <TableBody>
              <TableRow className="w-full bg-violet-50">
                <TableCell className="w-32 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Sl No</TableCell>
                <TableCell className={`w-40 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${!!selectedItem && !selectedPacketData ? " hidden" : ""}`}>Packet</TableCell>
                <TableCell className="w-48 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Item</TableCell>
                <TableCell className={`w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${isRawItem ? " hidden" : ""}`}>Pcs</TableCell>
                <TableCell className={`w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${isRawItem ? " hidden" : ""}`}>Ct</TableCell>
                <TableCell className="w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">GW</TableCell>
                <TableCell className={`w-32 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${showMetalFields ? "" : " hidden"}`}>Metal Purity</TableCell>
                <TableCell className={`w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${showMetalFields ? "" : " hidden"}`}>Loss</TableCell>
                <TableCell className={`w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${showMetalFields ? "" : " hidden"}`}>Tunch</TableCell>
                <TableCell className={`w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap${showMetalFields ? "" : " hidden"}`}>Fine Wt</TableCell>
                <TableCell className="w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Rate</TableCell>
                <TableCell className="w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Value</TableCell>
              </TableRow>

              {/* Input Row */}
              <TableRow>

                <TableCell className="px-4 py-2 border">
                  <Input type="text" {...register("details.sl_no")} />
                </TableCell>

                <TableCell className={`w-40 px-4 py-2 border${!!selectedItem && !selectedPacketData ? " hidden" : ""}`}>
                  <Input list="packet_list" {...register("details.packet")} disabled={!!selectedItem && !selectedPacketData} />
                  <datalist id="packet_list">
                    {packets.map((packet, index) => (
                      <option key={index} value={packet.pckt_no}>
                        {packet.pckt_no}
                      </option>
                    ))}
                  </datalist>
                </TableCell>
                <TableCell className="w-48 px-4 py-2 border">
                  <Input
                    list="sub_item_list"
                    value={detailItemDisplay}
                    onChange={(e) => {
                      const typed = e.target.value;
                      setDetailItemDisplay(typed);
                      const found = mainItemData.find(m => m.item_name === typed || m.short_code === typed);
                      setValue('details.sub_item', found ? found.short_code : typed);
                    }}
                    disabled={!!selectedPacketData}
                    placeholder="Item"
                    className={selectedPacketData ? "bg-muted text-muted-foreground cursor-not-allowed" : ""}
                  />
                  <datalist id="sub_item_list">
                    {mainItemData.filter(item => item.item_type !== 'S').map((item, index) => (
                      <option key={index} value={item.item_name} />
                    ))}
                  </datalist>
                  <input type="hidden" {...register("details.sub_item")} />
                </TableCell>
                <TableCell className={`w-28 px-4 py-2 border${isRawItem ? " hidden" : ""}`}>
                  <Input
                    type="number"
                    {...register("details.sub_pcs")}
                    placeholder="Sub Pcs"
                    disabled={isRawItem}
                  />
                </TableCell>
                <TableCell className={`w-28 px-4 py-2 border${isRawItem ? " hidden" : ""}`}>
                  <Input
                    type="number"
                    step="0.001"
                    {...register("details.sub_ct")}
                    placeholder="Sub Ct"
                    disabled={isRawItem}
                  />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input
                    type="number"
                    step="0.01"
                    {...register("details.sub_gw")}
                    placeholder="Sub GW"
                  />
                </TableCell>

                <TableCell className={`w-28 px-4 py-2 border${showMetalFields ? "" : " hidden"}`}>
                  <Controller
                    name={`details.metal_purity`}
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger data-testid="select-purity">
                          <SelectValue placeholder="Select Purity" />
                        </SelectTrigger>
                        <SelectContent>
                          {purityData.map((item, index) => (
                            <SelectItem key={index} value={`${item.purity}`}>{item.purity}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </TableCell>
                <TableCell className={`w-28 px-4 py-2 border${showMetalFields ? "" : " hidden"}`}>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("details.loss")}
                    placeholder="Loss"
                  />
                </TableCell>
                <TableCell className={`w-28 px-4 py-2 border${showMetalFields && detailItemData?.short_code === "Gold" ? "" : " hidden"}`}>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("details.tunch")}
                    placeholder="Tunch"
                  />
                </TableCell>
                <TableCell className={`w-28 px-4 py-2 border${showMetalFields ? "" : " hidden"}`}>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("details.fine_wt")}
                    placeholder="Fine Wt"
                  />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input
                    type="number"
                    step="0.01"
                    {...register("details.rate")}
                    placeholder="Rate"
                    disabled={parseFloat(watchedTunch || 0) > 0 && detailItemData?.short_code === "Gold"}
                  />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input
                    type="number"
                    step="0.01"
                    onKeyDown={(e) => handleKeyDownDetails(e)}
                    {...register("details.value")}
                    placeholder="Value"
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          </div>
          <br></br>

          <div className="overflow-x-auto">
          <Table className="w-full table-fixed border-collapse">

            <TableBody>
              <TableRow className="bg-violet-50">
                <TableCell className="w-32 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Options</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Sl No</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Packet</TableCell>
                <TableCell className="w-48 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Item</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">PO No</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Pcs</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Ct</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">GW</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Size</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Purity</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Loss</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Tunch</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Fine Wt</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Rate</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Making</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Value</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Remarks</TableCell>
              </TableRow>

              {rs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={17} className="px-4 py-6 border text-center text-sm text-gray-400">
                    No items added yet. Add a main item above and press <kbd className="px-1 py-0.5 rounded bg-gray-100 border text-gray-500 font-mono text-[11px]">Tab</kbd> on Remarks to add it here.
                  </TableCell>
                </TableRow>
              )}
              {[...rs].sort((a, b) => (a.sl_no || 0) - (b.sl_no || 0)).map((item, idx) => (
                <React.Fragment key={item.sl_no ?? idx}>
                  <TableRow className={item._editing ? "bg-amber-50 border-t-2 border-amber-400 opacity-70 font-bold" : "bg-violet-50 border-t-2 border-violet-300 border-l-4 border-l-violet-400 font-bold"}>
                    <TableCell className="px-4 py-2 border align-middle">
                      <div className="flex flex-row justify-center items-center gap-3">

                        <SquarePen className={`w-4 h-4 mr-1 ${item._editing ? "opacity-30 pointer-events-none" : "cursor-pointer"}`} onClick={() => handleEdit(rs.indexOf(item))} />
                        <Trash2 color="#d45959" className={`w-4 h-4 mr-1 ${item._editing ? "opacity-30 pointer-events-none" : "cursor-pointer"}`} onClick={() => handleDelete(rs.indexOf(item))} />
                      </div>
                    </TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.sl_no}</TableCell>

                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-48 px-4 py-2 border">{mainItemData.find(m => m.short_code === item.item)?.item_name || item.item}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border text-xs font-mono">
                      {item.customer_order_item_id ? (
                        <span
                          className="inline-flex flex-col gap-0.5 rounded-md border border-violet-200 bg-violet-50 px-1.5 py-0.5 leading-tight"
                          title={`Customer Order ${item.co_no_display || item.order_no || ''} · Sl ${item.co_sl_no_display ?? ''}${item.customer_name_display ? ` · ${item.customer_name_display}` : ''}`}
                        >
                          <span className="text-[11px] font-semibold text-violet-800">
                            {item.co_no_display || item.order_no || '—'}
                          </span>
                          {item.co_sl_no_display != null && (
                            <span className="text-[10px] text-violet-700/80">Sl {item.co_sl_no_display}</span>
                          )}
                        </span>
                      ) : item.po_no ? (
                        <>{item.po_no}{item.po_sl_no ? ` · ${item.po_sl_no}` : ""}</>
                      ) : "—"}
                    </TableCell>

                    <TableCell className="w-28 px-4 py-2 border">{item.pcs}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.size}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.purity}</TableCell>

                    <TableCell className="w-28 px-4 py-2 border"></TableCell>

                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.making_value}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.item_value}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.remarks}</TableCell>
                  </TableRow>

                  {item.purchasevoucherdetails_set?.map((detail, sub_id) => (
                    <TableRow key={sub_id} className="bg-white">
                      <TableCell className="px-4 py-2 border align-middle">
                        <div className="flex flex-row justify-center items-center gap-1">
                          <SquarePen color="#6d6d6d" className="size-4 cursor-pointer" onClick={() => handleEditSubItem(rs.indexOf(item), sub_id, 'purchasevoucherdetails_set')} />
                          <Trash2 color="#d45959" className="size-4 cursor-pointer" onClick={() => handleDeleteSubItem(rs.indexOf(item), sub_id, 'purchasevoucherdetails_set')} />
                        </div>
                      </TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{item.sl_no}</TableCell>
                      {/* <TableCell className="w-28 px-4 py-2 border">{detail.bill_no}</TableCell> */}
                      <TableCell className="w-28 px-4 py-2 border">{detail.packet}</TableCell>

                      <TableCell className="w-48 px-4 py-2 border">{mainItemData.find(m => m.short_code === detail.sub_item)?.item_name || detail.sub_item}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border"></TableCell>


                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_pcs}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_gw}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border"></TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.metal_purity}</TableCell>


                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_item === "Gold" ? detail.loss : ""}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_item === "Gold" ? detail.tunch : ""}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_item === "Gold" ? detail.fine_wt : ""}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.rate}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border"></TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.value}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border"></TableCell>

                    </TableRow>
                  ))}
                </React.Fragment>
              ))}

            </TableBody>
          </Table>
          </div> </> : <></>}

        {/* Legacy direct items — shown in edit mode only if the voucher had them */}

        {rsRaw.length > 0 && (
          <div className="overflow-x-auto">
          <Table className="w-full table-fixed border-collapse mt-2">
            <TableBody>
              <TableRow className="bg-violet-50">
                <TableCell className="w-12 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider"></TableCell>
                <TableCell className="w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Packet</TableCell>
                <TableCell className="w-24 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Item</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Pcs</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Ct</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">GW</TableCell>
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Purity</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Loss</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Tunch</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Fine Wt</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Rate</TableCell>
                <TableCell className="w-20 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider">Value</TableCell>
              </TableRow>
              {rsRaw.map((detail, idx) => (
                <TableRow key={idx}>
                  <TableCell className="px-4 py-2 border text-center">
                    <div className="flex flex-row justify-center items-center gap-1">
                      <SquarePen color="#6d6d6d" className="size-4 cursor-pointer" onClick={() => handleEditRawRow(idx)} />
                      <Trash2 color="#d45959" className="size-4 cursor-pointer" onClick={() => handleDeleteRawRow(idx)} />
                    </div>
                  </TableCell>
                  <TableCell className="w-24 px-4 py-2 border">{detail.packet}</TableCell>
                  <TableCell className="w-24 px-4 py-2 border">{detail.sub_item}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_pcs}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_gw}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{detail.metal_purity}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_item === "Gold" ? detail.loss : ""}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_item === "Gold" ? detail.tunch : ""}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_item === "Gold" ? detail.fine_wt : ""}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.rate}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border font-semibold">{detail.value}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          </div>
        )}

        <div className="container mt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <FieldContainer>
              <Label htmlFor="narration" className="text-nowrap">Narration</Label>
              <Input type="text" {...register("form.narration")} />
            </FieldContainer>
          </div>
        </div>

        {/* Bill Summary + Attachments side by side */}
        <div className="flex items-start gap-6 mt-8 mb-6 px-2">
          {/* Attachment panel (add mode) */}
          {!id && !isCustomer && (
            <div className="flex-1 rounded-lg border border-dashed border-border bg-muted/20 p-4 self-stretch flex flex-col">
              <div className="flex items-center gap-2 mb-3">
                <Paperclip className="size-4 text-muted-foreground" />
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Bill Attachments</span>
                <span className="ml-auto text-[10px] text-muted-foreground">{pendingFiles.length}/3</span>
              </div>
              <div className="flex flex-col gap-1.5 flex-1">
                {pendingFiles.length === 0 && (
                  <p className="text-xs text-muted-foreground text-center py-6">No files attached. Attach scanned bills or invoices before saving.</p>
                )}
                {pendingFiles.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-md bg-background border border-border">
                    <FileText className="size-4 text-muted-foreground shrink-0" />
                    <span className="text-xs flex-1 truncate">{f.name}</span>
                    <button type="button" onClick={() => setPendingFiles((prev) => prev.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-destructive">
                      <X className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
              {pendingFiles.length < 3 && (
                <label className="flex items-center justify-center gap-2 mt-3 py-2.5 rounded-md border border-dashed border-border cursor-pointer hover:bg-muted/40 transition-colors">
                  <Upload className="size-4 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">Click to attach a file</span>
                  <input
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      if (pendingFiles.length >= 3) { toast({ title: "Maximum 3 attachments allowed." }); return; }
                      setPendingFiles((prev) => [...prev, file]);
                      e.target.value = "";
                    }}
                  />
                </label>
              )}
            </div>
          )}

          {/* Attachment panel (edit mode) — compact trigger sitting beside bill summary */}
          {id && !isCustomer && (
            <div className="flex-1 rounded-lg border border-border bg-muted/20 p-4 self-stretch flex flex-col">
              <div className="flex items-center gap-2 mb-3">
                <Paperclip className="size-4 text-muted-foreground" />
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Bill Attachments</span>
              </div>
              <p className="text-xs text-muted-foreground mb-3">Attach scanned bills or supporting documents (up to 3 files).</p>
              <div className="mt-auto">
                <PurchaseAttachments purchaseId={id} billNo={watch("form.billno") || ""} />
              </div>
            </div>
          )}

          {/* Bill Summary — ml-auto pushes it right when no attachment panel is visible */}
          <div className="w-[480px] shrink-0 ml-auto">
            <BillSummaryPanel rows={billSummaryRows} register={register} watch={watch} standalone={false} />
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-center items-center gap-3 mt-2 pt-4 border-t border-gray-100">
          <Button type="submit" className="bg-primary hover:bg-primary text-white px-8" disabled={saving || !canSave}>
            {saveLabel(saving)}
          </Button>
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>

      {/* ── Pending Purchase-Order Picker Modal ── */}
      <Dialog open={poPickerOpen} onOpenChange={setPoPickerOpen}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Pending Purchase-Order Items</DialogTitle>
          </DialogHeader>

          <Input
            placeholder="Search PO #, item, purity…"
            value={poPickerSearch}
            onChange={(e) => setPoPickerSearch(e.target.value)}
            className="mb-1"
          />

          <div className="max-h-[55vh] overflow-auto rounded-md border border-border">
            {poPickerLoading ? (
              <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>
            ) : pendingPOItems.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No pending purchase-order items for this vendor.
              </div>
            ) : (
              <Table className="w-full text-sm">
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="w-10 px-2 py-2" />
                    <TableHead className="px-3 py-2">PO Date</TableHead>
                    <TableHead className="px-3 py-2">PO #</TableHead>
                    <TableHead className="px-3 py-2 w-12">Sl</TableHead>
                    <TableHead className="px-3 py-2">Item</TableHead>
                    <TableHead className="px-3 py-2">Purity</TableHead>
                    <TableHead className="px-3 py-2 text-right">Pcs</TableHead>
                    <TableHead className="px-3 py-2 text-right">Approx Wt</TableHead>
                    <TableHead className="px-3 py-2">Size</TableHead>
                    <TableHead className="px-3 py-2">Due</TableHead>
                    <TableHead className="px-3 py-2">Remarks</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingPOItems
                    .filter((p) => {
                      const q = poPickerSearch.trim().toLowerCase();
                      if (!q) return true;
                      return (
                        (p.po_no || "").toLowerCase().includes(q) ||
                        (p.item_name || "").toLowerCase().includes(q) ||
                        (p.item || "").toLowerCase().includes(q) ||
                        (p.purity || "").toLowerCase().includes(q)
                      );
                    })
                    .map((p) => {
                      const alreadyAdded = rs.some(r => r.po_no === p.po_no && r.po_sl_no === p.po_sl_no);
                      const checked = selectedPOItemIds.has(p.po_item_id);
                      const toggle = () => {
                        if (alreadyAdded) return;
                        setSelectedPOItemIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(p.po_item_id)) next.delete(p.po_item_id);
                          else next.add(p.po_item_id);
                          return next;
                        });
                      };
                      return (
                        <TableRow
                          key={p.po_item_id}
                          className={`odd:bg-muted/10 transition-colors duration-100 ${alreadyAdded ? "opacity-40 cursor-not-allowed" : "cursor-pointer"} ${checked ? "bg-primary/5 hover:bg-primary/10" : !alreadyAdded ? "hover:bg-muted/20" : ""}`}
                          onClick={toggle}
                        >
                          <TableCell className="px-2 py-2">
                            {alreadyAdded ? (
                              <span className="text-[10px] text-muted-foreground font-medium whitespace-nowrap">Added</span>
                            ) : (
                            <Checkbox
                              checked={checked}
                              onCheckedChange={toggle}
                              onClick={(e) => e.stopPropagation()}
                              className="cursor-pointer"
                            />
                            )}
                          </TableCell>
                          <TableCell className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{p.po_date || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs font-mono">{p.po_no || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-center">{p.po_sl_no}</TableCell>
                          <TableCell className="px-3 py-2">
                            <div className="flex flex-col leading-tight">
                              <span className="font-medium">{p.item_name || p.item || "—"}</span>
                              {p.item && p.item_name && p.item !== p.item_name && (
                                <span className="text-[10px] text-muted-foreground font-mono">{p.item}</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="px-3 py-2">{p.purity || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-right tabular-nums">{p.pcs ?? "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-right tabular-nums">{p.approx_wt ?? "—"}</TableCell>
                          <TableCell className="px-3 py-2">{p.size || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs whitespace-nowrap">{p.due_date || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-muted-foreground">{p.remarks || "—"}</TableCell>
                        </TableRow>
                      );
                    })}
                </TableBody>
              </Table>
            )}
          </div>

          <DialogFooter>
            <div className="flex items-center justify-between w-full">
              <span className="text-xs text-muted-foreground">
                {selectedPOItemIds.size} selected
              </span>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" onClick={() => setPoPickerOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="button"
                  disabled={selectedPOItemIds.size === 0}
                  onClick={() => {
                    const picked = pendingPOItems.filter((p) => selectedPOItemIds.has(p.po_item_id));
                    if (picked.length === 0) return;

                    if (picked.length === 1) {
                      // Single selection → populate the input row so the user can
                      // adjust weights and add sub-items before pressing Tab to add.
                      const p = picked[0];
                      setValue("table.item", p.item || "");
                      setValue("table.purity", p.purity || "");  // string e.g. "22K"
                      setValue("table.pcs", p.pcs ?? "");
                      setValue("table.gw", p.approx_wt ?? "");
                      setValue("table.pending_pcs", p.pcs ?? "");
                      setValue("table.pending_gw", p.approx_wt ?? "");
                      setValue("table.size", p.size || "");
                      setValue("table.remarks", p.remarks || "");
                      setValue("table.po_no", p.po_no || "");
                      setValue("table.po_sl_no", p.po_sl_no ?? null);
                      setValue("table.order_no", "");
                      setTableItemDisplay(p.item_name || p.item || "");
                    } else {
                      // Multiple selections → add all to the table directly.
                      // Use the Edit (pencil) button on each row to adjust
                      // weights and add sub-items afterwards.
                      const startSlNo = rs.length > 0 ? Math.max(...rs.map(r => r.sl_no || 0)) : 0;
                      const newRows = picked.map((p, i) => ({
                        sl_no: startSlNo + i + 1,
                        po_no: p.po_no || "",
                        po_sl_no: p.po_sl_no ?? null,
                        item: p.item || "",
                        item_name: p.item_name || "",
                        purity: p.purity || "",       // string e.g. "22K"
                        pcs: p.pcs ?? 0,
                        gw: p.approx_wt ?? 0,
                        pending_pcs: p.pcs ?? 0,
                        pending_gw: p.approx_wt ?? 0,
                        size: p.size || "",
                        remarks: p.remarks || "",
                        order_no: "",
                        barcode: null,
                        barcode_txt: "",
                        making: 0,
                        making_type: "",
                        making_value: 0,
                        item_value: 0,
                        purchasevoucherdetails_set: [],
                      }));
                      setRows([...rs, ...newRows]); markTableDirty();
                    }

                    setPoPickerOpen(false);
                    setSelectedPOItemIds(new Set());
                  }}
                >
                  Add Selected
                </Button>
              </div>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Pending Customer-Order Picker Modal (direct CO → PV) ── */}
      <Dialog open={coPickerOpen} onOpenChange={setCoPickerOpen}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Pending Customer-Order Items</DialogTitle>
          </DialogHeader>

          <Input
            placeholder="Search CO #, customer, item, purity…"
            value={coPickerSearch}
            onChange={(e) => setCoPickerSearch(e.target.value)}
            className="mb-1"
          />

          <div className="max-h-[55vh] overflow-auto rounded-md border border-border">
            {coPickerLoading ? (
              <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>
            ) : pendingCOItems.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No pending customer-order items.
              </div>
            ) : (
              <Table className="w-full text-sm">
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="w-10 px-2 py-2" />
                    <TableHead className="px-3 py-2">CO Date</TableHead>
                    <TableHead className="px-3 py-2">CO #</TableHead>
                    <TableHead className="px-3 py-2">Customer</TableHead>
                    <TableHead className="px-3 py-2 w-12">Sl</TableHead>
                    <TableHead className="px-3 py-2">Item</TableHead>
                    <TableHead className="px-3 py-2">Purity</TableHead>
                    <TableHead className="px-3 py-2 text-right">Pcs</TableHead>
                    <TableHead className="px-3 py-2 text-right">Approx Wt</TableHead>
                    <TableHead className="px-3 py-2">Due</TableHead>
                    <TableHead className="px-3 py-2">Remarks</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingCOItems
                    .filter((p) => {
                      const q = coPickerSearch.trim().toLowerCase();
                      if (!q) return true;
                      return (
                        (p.co_no || "").toLowerCase().includes(q) ||
                        (p.customer_name || "").toLowerCase().includes(q) ||
                        (p.item_name || "").toLowerCase().includes(q) ||
                        (p.item || "").toLowerCase().includes(q) ||
                        (p.purity || "").toLowerCase().includes(q)
                      );
                    })
                    .map((p) => {
                      const alreadyAdded = rs.some(r => r.customer_order_item_id === p.co_item_id);
                      const checked = selectedCOItemIds.has(p.co_item_id);
                      const toggle = () => {
                        if (alreadyAdded) return;
                        setSelectedCOItemIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(p.co_item_id)) next.delete(p.co_item_id);
                          else next.add(p.co_item_id);
                          return next;
                        });
                      };
                      return (
                        <TableRow
                          key={p.co_item_id}
                          className={`odd:bg-muted/10 transition-colors duration-100 ${alreadyAdded ? "opacity-40 cursor-not-allowed" : "cursor-pointer"} ${checked ? "bg-violet-50 hover:bg-violet-100" : !alreadyAdded ? "hover:bg-muted/20" : ""}`}
                          onClick={toggle}
                        >
                          <TableCell className="px-2 py-2">
                            {alreadyAdded ? (
                              <span className="text-[10px] text-muted-foreground font-medium whitespace-nowrap">Added</span>
                            ) : (
                              <Checkbox
                                checked={checked}
                                onCheckedChange={toggle}
                                onClick={(e) => e.stopPropagation()}
                                className="cursor-pointer"
                              />
                            )}
                          </TableCell>
                          <TableCell className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{p.co_date || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs font-mono">{p.co_no || "—"}</TableCell>
                          <TableCell className="px-3 py-2 font-medium">{p.customer_name || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-center">{p.sl_no}</TableCell>
                          <TableCell className="px-3 py-2">
                            <div className="flex flex-col leading-tight">
                              <span className="font-medium">{p.item_name || p.item || "—"}</span>
                              {p.item && p.item_name && p.item !== p.item_name && (
                                <span className="text-[10px] text-muted-foreground font-mono">{p.item}</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="px-3 py-2">{p.purity || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-right tabular-nums">{p.pcs ?? "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-right tabular-nums">{p.approx_wt ?? "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs whitespace-nowrap">{p.due_date || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-muted-foreground">{p.remarks || "—"}</TableCell>
                        </TableRow>
                      );
                    })}
                </TableBody>
              </Table>
            )}
          </div>

          <DialogFooter>
            <div className="flex items-center justify-between w-full">
              <span className="text-xs text-muted-foreground">
                {selectedCOItemIds.size} selected
              </span>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" onClick={() => setCoPickerOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="button"
                  disabled={selectedCOItemIds.size === 0}
                  onClick={() => {
                    const picked = pendingCOItems.filter((p) => selectedCOItemIds.has(p.co_item_id));
                    if (picked.length === 0) return;

                    if (picked.length === 1) {
                      // Single → populate the input row for weight/sub-item editing.
                      const p = picked[0];
                      setValue("table.item", p.item || "");
                      setValue("table.purity", p.purity || "");
                      setValue("table.pcs", p.pcs ?? "");
                      setValue("table.gw", p.approx_wt ?? "");
                      setValue("table.pending_pcs", p.pcs ?? "");
                      setValue("table.pending_gw", p.approx_wt ?? "");
                      setValue("table.size", p.size || "");
                      setValue("table.remarks", p.remarks || "");
                      // Mutually exclusive with PO link → clear PO fields.
                      setValue("table.po_no", "");
                      setValue("table.po_sl_no", null);
                      setValue("table.customer_order_item_id", p.co_item_id);
                      setValue("table.order_no", p.co_no || "");
                      setValue("table.co_no_display", p.co_no || "");
                      setValue("table.co_sl_no_display", p.sl_no ?? null);
                      setValue("table.customer_name_display", p.customer_name || "");
                      setTableItemDisplay(p.item_name || p.item || "");
                    } else {
                      // Multi → push all to the grid.
                      const startSlNo = rs.length > 0 ? Math.max(...rs.map(r => r.sl_no || 0)) : 0;
                      const newRows = picked.map((p, i) => ({
                        sl_no: startSlNo + i + 1,
                        po_no: "",
                        po_sl_no: null,
                        customer_order_item_id: p.co_item_id,
                        co_no_display: p.co_no || "",
                        co_sl_no_display: p.sl_no ?? null,
                        customer_name_display: p.customer_name || "",
                        order_no: p.co_no || "",
                        item: p.item || "",
                        item_name: p.item_name || "",
                        purity: p.purity || "",
                        pcs: p.pcs ?? 0,
                        gw: p.approx_wt ?? 0,
                        pending_pcs: p.pcs ?? 0,
                        pending_gw: p.approx_wt ?? 0,
                        size: p.size || "",
                        remarks: p.remarks || "",
                        barcode: null,
                        barcode_txt: "",
                        making: 0,
                        making_type: "",
                        making_value: 0,
                        item_value: 0,
                        purchasevoucherdetails_set: [],
                      }));
                      setRows([...rs, ...newRows]); markTableDirty();
                    }

                    setCoPickerOpen(false);
                    setSelectedCOItemIds(new Set());
                  }}
                >
                  Add Selected
                </Button>
              </div>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PurchaseVoucher;



















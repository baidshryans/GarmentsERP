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
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, createCustomerOrder, getStates, fetchPVNoNext, fetchPoNoNext, fetchPackets, fetchPos, fetchStoneIssuesFilterJobs, fetchStoneIssued, createPurchaseVoucher, fetchBarcodes, fetchHSNs, fetchLedgerTDSInfo } from "@/services/apiService";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchCustomerOrders, fetchOrderItem, fetchPurchaseVoucherForEdit, fetchSlNosOrders, getCustomerItemAsPurchaseStyle, getGoldRate, updatePurchaseVoucherForEdit } from "../../../services/apiService";
import { SquarePen, Trash2, Paperclip, X, Upload, FileText } from "lucide-react";
import InvoiceUpload from "@/components/AI/InvoiceUpload";
import PurchaseAttachments from "./PurchaseAttachments";
import { uploadPurchaseAttachment } from "@/services/apiService";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { useNavigate } from "react-router";
import BillSummaryPanel from "@/components/shared/BillSummaryPanel";

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
  const [pendingFiles, setPendingFiles] = useState([]); // files to upload after create
  const [detailItemDisplay, setDetailItemDisplay] = useState(""); // display label for item field
  const [tableItemDisplay, setTableItemDisplay] = useState(""); // display label for main item field
  const { register: originalRegister, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
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
  const formRef = useRef(null);
  useEnterAsTab(formRef);
  const [rsRaw, setRsRaw] = useState([]);
  const [serialNos, setSerialNos] = useState([]);
  const [statesData, setstatesData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);   // all items (for sub-item lookup & name resolution)
  const [mainItemsM, setMainItemsM] = useState([]);       // type M only (for main item datalist)
  const [customerOrders, setCustomerOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
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
      const [orderNo, packets, barcodes, customerOrders, customers, states, salesperson, mainItem, mainItemM, purity, poNo, hsnres] = await Promise.all([
        fetchPVNoNext().then(orderNo => { if (orderNo.success) setValue("form.billno", orderNo.data.billno); }),
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
          // Defer so Select items render before value is set
          if (jewelleryHsn) setTimeout(() => setValue("hsn", jewelleryHsn.hsn_no), 0);
        }
      }
    }



    fetchData().then(d => {
      if (id) {
        fetchPurchaseVoucherForEdit(id)
          .then((response) => {
            const data = response.data;
            // Set form fields, skipping nested arrays that are handled separately
            Object.keys(data).forEach((key) => {
              if (key !== 'purchasevoucheritems_set' && key !== 'purchasevoucherdetails_set') {
                setValue(`form.${key}`, data[key]);
              }
            });

            if (data.purchasevoucheritems_set) {
              setRows(data.purchasevoucheritems_set);
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
          })
          .catch((error) => {
            console.error('Error fetching manufacturing issue:', error);
          });
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
    fine_wt: ` (tunch !== '0' && tunch !== ''  )? ((tunch/100) * sub_gw) : sub_gw`
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



  useEffect(() => {
    const form = { ...getValues('form'), rs: rs, rsRaw: rsRaw };
    const table = getValues('details');
    const maintable = getValues('table');


    Object.keys(main_formulas).forEach((col) => {
      setValue(`form.${col}`, evaluateFormula(main_formulas[col], form));
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
  }, [rs, rsRaw, watchedFields, calculate]);

  useEffect(() => {
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
      const retailState = localStorage.getItem('state_code') || "";
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
    if (rs.length === 0) {
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
    }));
    form.purchasevoucherdetails_set = [...rsRaw];
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
        toast({
          title: "Form submission failed.",
          description: renderErrorTree(response.error),
          variant: "destructive",
        });
      }
    } catch {
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
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDeleteSubItem = (rowIndex, subIndex, key) => {
    const tablevalues = { ...rs[rowIndex] };

    setRows((prev) =>
      prev.map((row, i) =>
        i === rowIndex
          ? {
            ...row,
            [key]: row[key].filter((_, j) => j !== subIndex),
          }
          : row
      )
    );
  };

  const handleEditSubItem = (rowIndex, subIndex, key) => {
    const subItem = rs[rowIndex][key][subIndex];
    // Populate the input row with the sub-item's values
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
    setRows((prev) =>
      prev.map((row, i) =>
        i === rowIndex
          ? { ...row, [key]: row[key].filter((_, j) => j !== subIndex) }
          : row
      )
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

      if (rs.length === 0) {
        toast({ title: "Add a main item first", description: "Enter the main item (Section 2) before adding sub-items." });
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
        tablevalues.item_value = parseFloat(tablevalues.purchasevoucherdetails_set.reduce((sum, detail) => parseFloat(sum) + parseFloat(detail.value || 0), 0).toFixed(2));

        setRows((prevData) =>
          prevData.map((row, i) => (i === idx ? { ...tablevalues } : row))
        );
        const lastSlNo = rs.length > 0 ? rs[rs.length - 1].sl_no : 1;
        reset({
          form: getValues('form'),
          hsn: getValues('hsn'),
          table: getValues('table'),
          details: {
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
    } else {
      // New row: assign next sl_no
      newItem.sl_no = rs.length > 0 ? Math.max(...rs.filter(r => !r._editing).map(r => r.sl_no || 0)) + 1 : 1;
      if (!Array.isArray(newItem.purchasevoucherdetails_set)) {
        newItem.purchasevoucherdetails_set = [];
      }
      setRows([...rs, { ...newItem }]);
    }
    setTableItemDisplay("");
    reset({
      form: { ...getValues('form') },
      hsn: getValues('hsn'),
      table: {
        billno: "",
        barcode: "",
        item: "",
        pcs: 0,
        pending_pcs: 0,
        gw: 0.0,
        pending_gw: 0.0,
        making: 0.0,
        making_type: "",
        making_value: 0,
        purity: 0,
        ret_status: false,
        amount: 0,
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
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">1</span>
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
              }}
              placeholder={isCustomer ? "Search customer / dealer…" : "Search vendor / karigar…"}
            />
            <input type="hidden" {...register("form.ldgr", { required: true })} />
          </FieldContainer>
          {isCustomer && (
            <div className="col-span-2 flex flex-col gap-1">
              <Label className="text-nowrap">RCM (Reverse Charge)</Label>
              <div className="flex items-center gap-3 h-9">
                <Controller
                  name="form.is_rcm"
                  control={control}
                  render={({ field }) => (
                    <Checkbox
                      checked={!!field.value}
                      onCheckedChange={field.onChange}
                      id="is_rcm"
                    />
                  )}
                />
                <label htmlFor="is_rcm" className="text-sm text-gray-600 cursor-pointer select-none">
                  Unregistered seller — RCM @ 3% applies
                </label>
              </div>
              {watch('form.is_rcm') && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                  GST payable under Reverse Charge. Record in RCM payable ledger via journal entry.
                </p>
              )}
            </div>
          )}

          {!isCustomer && (
          <FieldContainer>
            <Label className="text-nowrap">HSN code <span className="text-primary font-normal text-xs">(select to add items)</span></Label>

            <Controller
              name="hsn"
              control={control}
              render={({ field }) => (
                <Select disabled={rs.length > 0} onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-testid="hsn-select">
                    <SelectValue placeholder="Select HSN" value={null} />
                  </SelectTrigger>

                  <SelectContent>
                    {hsns.map((hsn, index) => (
                      <SelectItem key={index} value={hsn.hsn_no}>{hsn.description || hsn.hsn_no}</SelectItem>
                    ))}

                  </SelectContent>
                </Select>
              )}
            />

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
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Order No</Label>
            <Input list="customer_order_list"
              onBlur={handleBlur}
              onChange={(e) => {
                const selectedCustomerOrder = customerOrders.find(
                  (customerOrder) => customerOrder.order_no === e.target.value
                );
                selectedCustomerOrder ? setValue("customer_order_id", selectedCustomerOrder.id) : e.target.value;

              }} />

          </FieldContainer>
          <Input type="hidden" {...register("form.ldgr_code")} />
          <datalist id="customer_order_list" >
            {customerOrders.map((customerOrders, index) => (
              <option key={index} value={customerOrders.order_no}></option>

            ))}

          </datalist>


          <FieldContainer>
            <Label htmlFor="serial_no_list" className="text-nowrap">Sl No</Label>
            <Input list="serial_no_list"

              {...register("sl_no", {
                onBlur: handleBlur1
              })}
              disabled={getValues("form.issue_slip_type") === 'Stock'} readOnly={getValues("form.issue_slip_type") === 'Stock'} />

          </FieldContainer>
          <Input type="hidden" {...register("customer_order_item")} />
          <datalist id="serial_no_list" >
            {serialNos.map((serialNo, index) => (
              <option key={index} value={serialNo.sl_no}></option>

            ))}

          </datalist>


        </div>
        {hsn_current || id ? <>

          {/* Item Details */}
          <div className="flex items-center gap-3 my-5">
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-white text-[11px] font-bold shrink-0">2</span>
            <span className="text-sm font-bold text-gray-700 tracking-wider uppercase">Main and Sub Item Details</span>
            <div className="flex-1 h-px bg-violet-100" />
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
                  <Input type="number" {...register("table.gw")} />
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
                    {mainItemData.map((item, index) => (
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
                <TableCell className={`w-28 px-4 py-2 border${showMetalFields ? "" : " hidden"}`}>
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
                <TableCell className="w-28 px-4 py-2.5 border text-xs font-semibold text-primary uppercase tracking-wider whitespace-nowrap">Order No</TableCell>
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

                        <SquarePen size={20} className={`mr-1 ${item._editing ? "opacity-30 pointer-events-none" : "cursor-pointer"}`} onClick={() => handleEdit(rs.indexOf(item))} />
                        <Trash2 size={20} color="#d45959" className={`mr-1 ${item._editing ? "opacity-30 pointer-events-none" : "cursor-pointer"}`} onClick={() => handleDelete(rs.indexOf(item))} />
                      </div>
                    </TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.sl_no}</TableCell>

                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-48 px-4 py-2 border">{mainItemData.find(m => m.short_code === item.item)?.item_name || item.item}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.order_no}</TableCell>

                    <TableCell className="w-28 px-4 py-2 border">{item.pcs}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.gw}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.size}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.purity}</TableCell>

                    <TableCell className="w-28 px-4 py-2 border"></TableCell>

                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.making_value}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.item_value}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{item.remarks}</TableCell>
                  </TableRow>

                  {item.purchasevoucherdetails_set?.map((detail, sub_id) => (
                    <TableRow key={sub_id} className="bg-white">
                      <TableCell className="px-4 py-2 border align-middle">
                        <div className="flex flex-row justify-center items-center gap-1">
                          <SquarePen size={16} color="#6d6d6d" className="cursor-pointer" onClick={() => handleEditSubItem(rs.indexOf(item), sub_id, 'purchasevoucherdetails_set')} />
                          <Trash2 size={16} color="#d45959" className="cursor-pointer" onClick={() => handleDeleteSubItem(rs.indexOf(item), sub_id, 'purchasevoucherdetails_set')} />
                        </div>
                      </TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.sl_no}</TableCell>
                      {/* <TableCell className="w-28 px-4 py-2 border">{detail.bill_no}</TableCell> */}
                      <TableCell className="w-28 px-4 py-2 border">{detail.packet}</TableCell>

                      <TableCell className="w-48 px-4 py-2 border">{mainItemData.find(m => m.short_code === detail.sub_item)?.item_name || detail.sub_item}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border"></TableCell>


                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_pcs}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.sub_gw}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border"></TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.metal_purity}</TableCell>


                      <TableCell className="w-28 px-4 py-2 border">{detail.loss}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.tunch}</TableCell>
                      <TableCell className="w-28 px-4 py-2 border">{detail.fine_wt}</TableCell>
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
                    <Trash2 size={16} color="#d45959" className="cursor-pointer mx-auto" onClick={() => handleDeleteRawRow(idx)} />
                  </TableCell>
                  <TableCell className="w-24 px-4 py-2 border">{detail.packet}</TableCell>
                  <TableCell className="w-24 px-4 py-2 border">{detail.sub_item}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_pcs}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.sub_gw}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{detail.metal_purity}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.loss}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.tunch}</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">{detail.fine_wt}</TableCell>
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
          <Button type="submit" className="bg-primary hover:bg-primary text-white px-8">
            Save
          </Button>
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default PurchaseVoucher;



















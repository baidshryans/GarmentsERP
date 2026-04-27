import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { fetchMainItem, fetchNextStoneBillNo, getStates, fetchPurity, fetchPackets, getLedgers, createKarigarStoneIssue, fetchStoneIssuesFilterJobs, fetchPos, fetchSaleVoucherInitialData, fetchPacketBalance } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchStoneIssueForEdit, updateKarigarStoneIssue } from "../../../services/apiService";
import { SquarePen, Trash2 } from "lucide-react";
import { renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router-dom";

const tableDefaultValue = {
  packet: "",
  item: "",
  pcs: 0,
  ct: 0,
  gw: 0,
  rate: 0,
  taxable_value: 0,
  cgst: 0,
  cgst_rate: 0,
  sgst: 0,
  sgst_rate: 0,
  igst: 0,
  igst_rate: 0,
  tot_val: 0,
  remarks: ""
};

const StoneIssue = () => {
  const {id } = useParams()
  const { toast } = useToast()
  const { register, handleSubmit, control, reset, watch, setValue, getValues,setFocus } = useForm({
    defaultValues: {
      form:{
      place_of_supply:"WB",

      date1: new Date().toISOString().split("T")[0],
    },
      table: { ...tableDefaultValue },

    },
  });
  const navigate=useNavigate();

  const [rs, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [statesData, setstatesData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [packets, setPackets] = useState([]);
  const [uom, setUOM] = useState("pcs")
  const [jobItems, setJobItems] = useState([]);
  const [selectedJobItem, setSelectedJobItem] = useState(null);
  const [stype, setStype] = useState("Job Order");
  const [retailStateCode, setRetailStateCode] = useState("");
  const [currentPacketHsnRates, setCurrentPacketHsnRates] = useState({ cgst: 0, sgst: 0, igst: 0 });
  const [packetBalance, setPacketBalance] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(false);

  const loadJobItems = async (jobId) => {
    const slip_type = getValues("form.slip_type");
    const response = await fetchStoneIssuesFilterJobs(jobId, slip_type);
    if (response.success) {
      setJobItems(response.data.job_items || []);
    } else {
      toast({ title: "Failed to load job order items.", variant: "destructive" });
    }
  };

  useEffect(() => {
    async function fetchData() {
      const [packets, karigars, customers, states, orderNo, mainItem, purity, initialData] = await Promise.all([
        fetchPackets(),
        fetchPos("Job Order"),
        getLedgers(),
        getStates(),
        fetchNextStoneBillNo(),
        fetchMainItem(),
        fetchPurity(),
        fetchSaleVoucherInitialData(),
      ]);
      if (packets.success) setPackets(packets.data.results ?? packets.data);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (states.success) setstatesData(states.data.results ?? states.data);
      if (orderNo.success) setValue("form.billno", orderNo.data.bill_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
      if (initialData.success) setRetailStateCode(initialData.data.retail_state_code || "");
    }
    fetchData().then(d => {
          if (id) {
    
            
              fetchStoneIssueForEdit(id)
                .then((response) => {
                  Object.keys(response.data).forEach((key) => {
                    setValue(`form.${key}`, response.data[key]);
                  });
          
                  // Set items array
                  if (response.data.karigarstoneissue_set) {
                    setRows(response.data.karigarstoneissue_set);
                  }
                })
                .catch((error) => {
                  console.error('Error fetching manufacturing issue:', error);
                });
          }
        });
  }, []);

  useEffect(() => {
        // Calculate the total sum
        const taxable_total = rs.reduce((sum, item) => sum + item.taxable_value, 0);
        const sgst_total = rs.reduce((sum, item) => sum + item.sgst, 0);
        const cgst_total = rs.reduce((sum, item) => sum + item.cgst, 0);
        const igst_total = rs.reduce((sum, item) => sum + item.igst, 0);

        // Update the form field with the calculated total
        setValue("taxable_amt", taxable_total);
        setValue("form.sgst_per", sgst_total);
        setValue("form.cgst_per", cgst_total);
        setValue("form.igst_per", igst_total);

        setValue("total_amt",taxable_total+cgst_total+igst_total+sgst_total)

  }, [rs]);

  const tablePacket = watch("table.packet");
  const slip_type = watch("form.slip_type")
  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([
        fetchPos(slip_type),

      ]);
      if (karigars.success) setKarigars(karigars.data.results);
    }
    fetchData();
    setValue("form.ref_job_name", "");
    setValue("form.ref_job_object_id", "");
    setSelectedJobItem(null);
    setJobItems([]);
  }, [slip_type]);

  const place_of_supply = watch("form.place_of_supply");
  useEffect(() => {
    if (!retailStateCode) return;
    const isIntra = place_of_supply === retailStateCode;
    const cgst_rate = isIntra ? currentPacketHsnRates.cgst : 0;
    const sgst_rate = isIntra ? currentPacketHsnRates.sgst : 0;
    const igst_rate = isIntra ? 0 : currentPacketHsnRates.igst;
    setValue('table.cgst_rate', cgst_rate);
    setValue('table.sgst_rate', sgst_rate);
    setValue('table.igst_rate', igst_rate);
    const tv = parseFloat(getValues("table.taxable_value")) || 0;
    const sgst_val = (sgst_rate * tv / 100) || 0;
    const cgst_val = (cgst_rate * tv / 100) || 0;
    const igst_val = (igst_rate * tv / 100) || 0;
    setValue("table.sgst", sgst_val);
    setValue("table.cgst", cgst_val);
    setValue("table.igst", igst_val);
    setValue("table.tot_val", cgst_val + sgst_val + igst_val + tv);
  }, [place_of_supply, retailStateCode, currentPacketHsnRates]);

  const karigarLdgrName = watch("form.karigar_ldgr_name");
  useEffect(() => {
    if (karigarLdgrName) {
      getLedgers({search : karigarLdgrName}).then(response => {
        if (response.success) {
          setCustomers(response.data.results);
        }
      });
    }
  }, [karigarLdgrName]);
  const onSubmit = (data) => {
    if (!slip_type) {
      toast({ title: "Please select a Slip Type before saving.", variant: "destructive" });
      return;
    }
    if (rs.length === 0) {
      toast({ title: "Please add at least one item.", variant: "destructive" });
      return;
    }

    const refJobId = getValues("form.ref_job_object_id");
    if (!refJobId) {
      toast({ title: "Please select a Job Work Slip No.", variant: "destructive" });
      return;
    }
    if (!selectedJobItem) {
      toast({ title: "Please select an item from the job order.", variant: "destructive" });
      return;
    }

    rs.forEach(e => {
      e.job_sl_content_type = slip_type === "Job Order" ? "karigarissueitem" : "purchaseorderitems";
      e.ref_job_content_type = slip_type === "Job Order" ? "karigarissue" : "purchaseorder";
      e.ref_job_object_id = refJobId;
      e.job_sl_object_id = selectedJobItem.id;
    });

    const formdata = getValues('form');
    formdata.karigarstoneissue_set = rs;

    setSaving(true);
    (id ? updateKarigarStoneIssue(formdata, id) : createKarigarStoneIssue(formdata))
      .then((response) => {
        if (response.success) {
          toast({ title: "Form submitted successfully!" });
          setTimeout(() => navigate("/manufacturing/issue/stoneissue/"), 2000);
        } else {
          setSaving(false);
          toast({
            title: "Form submission failed. Please try again.",
            description: renderErrorTree(response.error),
            variant: "destructive",
          });
        }
      })
      .catch((error) => {
        setSaving(false);
        console.error("Error submitting form:", error);
        toast({ title: "An error occurred. Please try again later." });
      });
  };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    const row = rs[index];
    reset({form:getValues('form'),table:row});
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };


  const handleKeyDown = (e) => {

    if (e.key === "Tab") {
      const table = getValues("table");
      if(!table.ct) table.ct=0;
      const place_of_supply = getValues("form.place_of_supply");
      const sl_no = rs.length + 1;

      const rowVals = {
        sl_no,
        ...table,
        place_of_supply,
      }
      e.preventDefault()
      setRows([...rs, rowVals])
      reset({form:{...getValues('form')},table:{...tableDefaultValue}})
      setPacketBalance(null);
      setFocus('table.packet')

    }
  };

  const issuedTotalsForPacket = (pckt_no) =>
    rs.filter((r) => r.packet === pckt_no).reduce(
      (acc, r) => ({
        pcs: acc.pcs + (parseFloat(r.pcs) || 0),
        ct: acc.ct + (parseFloat(r.ct) || 0),
        gw: acc.gw + (parseFloat(r.gw) || 0),
      }),
      { pcs: 0, ct: 0, gw: 0 }
    );

  const handlePacketChange = (e) => {
    const selectedValue = typeof e === "string" ? e : e.target.value;
    const selectedPacket = packets.find((packet) => packet.pckt_no === selectedValue);

    setPacketBalance(null);
    if (!selectedValue) {
      setValue("table.item", "");
      setValue("table.rate", 0);
      setValue("table.pcs", 0);
      setValue("table.ct", 0);
      setValue("table.gw", 0);
      setValue("table.taxable_value", 0);
      setValue("table.sgst", 0);
      setValue("table.cgst", 0);
      setValue("table.igst", 0);
      setValue("table.tot_val", 0);
      setCurrentPacketHsnRates({ cgst: 0, sgst: 0, igst: 0 });
      setUOM("pcs");
      return;
    }

    setBalanceLoading(true);
    fetchPacketBalance(selectedValue).then((response) => {
      setBalanceLoading(false);
      if (response.success) {
        setPacketBalance(response.data);
      } else {
        setPacketBalance({ error: response.error?.error || "Balance unavailable" });
      }
    });

    if (selectedPacket) {
      setValue('table.item', selectedPacket.stone_item_name || "");
      setValue('table.rate', selectedPacket.rate_for_retail || 0);

      const hsn_cgst = selectedPacket.stone_item_hsn_cgst || 0;
      const hsn_sgst = selectedPacket.stone_item_hsn_sgst || 0;
      const hsn_igst = selectedPacket.stone_item_hsn_igst || 0;
      setCurrentPacketHsnRates({ cgst: hsn_cgst, sgst: hsn_sgst, igst: hsn_igst });

      const pos = getValues("form.place_of_supply");
      const isIntra = retailStateCode && pos === retailStateCode;
      setValue('table.cgst_rate', isIntra ? hsn_cgst : 0);
      setValue('table.sgst_rate', isIntra ? hsn_sgst : 0);
      setValue('table.igst_rate', isIntra ? 0 : hsn_igst);

      const newUom = selectedPacket.stone_item_uom || "pcs";
      setUOM(newUom);
      setValue("table.ct", 0);
      setValue("table.gw", 0);
      setValue("table.pcs", 0);
      setValue("table.taxable_value", 0);
      setValue("table.sgst", 0);
      setValue("table.cgst", 0);
      setValue("table.igst", 0);
      setValue("table.tot_val", 0);
    }
  };

  const recalcTax = (calculatedValue) => {
    const { sgst_rate, cgst_rate, igst_rate } = getValues("table");
    const sgst_val = (sgst_rate * calculatedValue / 100) || 0;
    const cgst_val = (cgst_rate * calculatedValue / 100) || 0;
    const igst_val = (igst_rate * calculatedValue / 100) || 0;
    setValue("table.sgst", sgst_val);
    setValue("table.cgst", cgst_val);
    setValue("table.igst", igst_val);
    setValue("table.tot_val", cgst_val + sgst_val + igst_val + calculatedValue);
  };

  const remainingForCurrentPacket = (field) => {
    if (!packetBalance || packetBalance.error) return null;
    const balKey = field === "pcs" ? "balance_pcs" : field === "ct" ? "balance_ct" : "balance_gw";
    const issued = issuedTotalsForPacket(getValues("table.packet"))[field];
    return (parseFloat(packetBalance[balKey]) || 0) - issued;
  };

  const clampToBalance = (field) => {
    const remaining = remainingForCurrentPacket(field);
    if (remaining == null) return false;
    const current = parseFloat(getValues(`table.${field}`)) || 0;
    if (current > remaining) {
      const safe = Math.max(0, parseFloat(remaining.toFixed(3)));
      setValue(`table.${field}`, safe);
      toast({
        title: "Exceeds available balance",
        description: `Only ${safe} ${field} remaining in this packet.`,
        variant: "destructive",
      });
      return true;
    }
    return false;
  };

  const handleGWchange = (e) => {
    clampToBalance("gw");
    const { gw, rate } = getValues("table");
    const calculatedValue = (parseFloat(gw) * parseFloat(rate)) || 0;
    setValue("table.taxable_value", calculatedValue);
    recalcTax(calculatedValue);
  };

  const handlePCSchange = (e) => {
    clampToBalance("pcs");
    const { pcs, rate } = getValues("table");
    const calculatedValue = (parseFloat(pcs) * parseFloat(rate)) || 0;
    setValue("table.taxable_value", calculatedValue);
    recalcTax(calculatedValue);
  };

  const handleCTchange = (e) => {
    clampToBalance("ct");
    const { ct, rate } = getValues("table");
    const calculatedValue = (parseFloat(ct) * parseFloat(rate)) || 0;
    setValue("table.taxable_value", calculatedValue);
    recalcTax(calculatedValue);
    setValue("table.gw", parseFloat((parseFloat(ct) / 5).toFixed(3)) || 0);
  };

  return (
    <form
      id="orderForm"
      onSubmit={handleSubmit(onSubmit)}
      className="px-8 py-4 space-y-4 text-sm"
    >
      <h2 className="text-xl font-semibold">Stone Issue to Karigar</h2>

      {/* ── Issue Details ── */}
      <div className="rounded-lg border bg-card">
        <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 rounded-t-lg text-sm font-medium text-primary">
          Issue Details
        </div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="si-date">Date</Label>
            <Input id="si-date" type="date" {...register("form.date1")} required />
          </div>
          <div>
            <Label>Issue Slip No</Label>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate h-9">
                {watch("form.billno") || <span className="text-violet-400 text-xs font-normal">Auto-generating…</span>}
              </span>
              <input type="hidden" {...register("form.billno")} />
            </div>
          </div>
          <div>
            <Label htmlFor="si-slip-type">Slip Type <span className="text-red-500">*</span></Label>
            <Controller
              name="form.slip_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger id="si-slip-type" data-id="slip-type">
                    <SelectValue placeholder="Select slip type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Job Order">Job Order</SelectItem>
                    <SelectItem value="Purchase Order">Purchase Order</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div>
            <Label htmlFor="si-pos">Place of Supply</Label>
            <Controller
              name="form.place_of_supply"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger id="si-pos">
                    <SelectValue placeholder="Select State" />
                  </SelectTrigger>
                  <SelectContent>
                    {statesData.map((sp, index) => (
                      <SelectItem key={index} value={`${sp.code}`}>{sp.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div>
            <Label>Karigar <span className="text-red-500">*</span></Label>
            <SearchableComboBox
              options={customers}
              value={watch("form.karigar_ldgr_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.karigar_ldgr_name", opt.ac_name);
                setValue("form.karigar_ldgr", opt.id);
              }}
              placeholder="Search karigar…"
            />
            <input type="hidden" {...register("form.karigar_ldgr")} />
          </div>
          <div>
            <Label>{slip_type === "Purchase Order" ? "Purchase Order No" : "Job Work Slip No"} <span className="text-red-500">*</span></Label>
            <SearchableComboBox
              options={karigars.map(k => ({ id: k.id, ac_name: k.name }))}
              value={watch("form.ref_job_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.ref_job_name", opt.ac_name);
                setValue("form.ref_job_object_id", opt.id);
                setSelectedJobItem(null);
                loadJobItems(opt.id);
              }}
              placeholder={`Search ${slip_type === "Purchase Order" ? "purchase order" : "job order"}…`}
            />
            <input type="hidden" {...register("form.ref_job_object_id")} />
          </div>
        </div>
      </div>

      {/* ── Job Order Items ── */}
      {jobItems.length > 0 && (
        <div className="rounded-lg border bg-card">
          <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 rounded-t-lg text-sm font-medium text-primary flex items-center justify-between">
            <span>Pick Item to Issue Stones Against</span>
            {selectedJobItem && rs.length > 0 && (
              <span className="text-xs text-muted-foreground font-normal">
                Locked — clear stones to switch
              </span>
            )}
          </div>
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {jobItems.map((it) => {
              const isSelected = selectedJobItem?.id === it.id;
              const locked = rs.length > 0 && !isSelected;
              return (
                <div
                  key={it.id}
                  onClick={() => {
                    if (locked) {
                      toast({
                        title: "Item locked",
                        description: "Stones already added against another item. Remove all rows to switch items.",
                        variant: "destructive",
                      });
                      return;
                    }
                    setSelectedJobItem(it);
                  }}
                  className={`rounded-md border p-3 text-sm transition ${
                    isSelected
                      ? "border-primary bg-violet-50 ring-2 ring-primary cursor-pointer"
                      : locked
                      ? "border-gray-200 opacity-50 cursor-not-allowed"
                      : "border-gray-200 hover:border-primary hover:bg-muted/40 cursor-pointer"
                  }`}
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-semibold text-muted-foreground">Sl No · {it.job_sl_no}</span>
                    {isSelected && <span className="text-xs font-semibold text-primary">✓ Selected</span>}
                  </div>
                  <div className="font-semibold text-foreground">{it.item_name || "—"}</div>
                  <div className="text-xs text-muted-foreground mt-1.5 grid grid-cols-2 gap-x-2 gap-y-0.5">
                    <span>Pcs: <span className="text-foreground">{it.pcs}</span></span>
                    <span>Wt: <span className="text-foreground">{it.approx_wt}</span></span>
                    {it.purity && <span>Purity: <span className="text-foreground">{it.purity}</span></span>}
                    {it.size && <span>Size: <span className="text-foreground">{it.size}</span></span>}
                    {it.design_code && <span className="col-span-2">Design: <span className="text-foreground">{it.design_code}</span></span>}
                    {it.remarks && <span className="col-span-2 truncate">Note: <span className="text-foreground">{it.remarks}</span></span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Stone Entry ── */}
      <div className="rounded-lg border bg-card">
        <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 rounded-t-lg text-sm font-medium text-primary flex items-center justify-between">
          <span>Stones</span>
          <span className="text-xs text-muted-foreground font-normal">Tab on Remarks to add row</span>
        </div>

        {(balanceLoading || packetBalance) && (
          <div className="px-4 py-2 border-b bg-muted/40 text-xs flex flex-wrap items-center gap-x-6 gap-y-1">
            {balanceLoading && <span className="text-muted-foreground italic">Fetching packet balance…</span>}
            {packetBalance?.error && (
              <span className="text-red-600 font-medium">{packetBalance.error}</span>
            )}
            {packetBalance && !packetBalance.error && (() => {
              const issued = issuedTotalsForPacket(getValues("table.packet"));
              const u = (packetBalance.uom || "").toLowerCase();
              const showCt = u !== "gm" && u !== "pcs";
              const showGw = u !== "ct";
              const fmt = (n) => Number(n || 0).toFixed(3);
              return (
                <>
                  <span className="font-medium">
                    {packetBalance.pckt_no} · {packetBalance.item_name} <span className="uppercase text-muted-foreground">({packetBalance.uom || "—"})</span>
                  </span>
                  <span>Pcs: <span className="font-semibold tabular-nums">{fmt(packetBalance.balance_pcs - issued.pcs)}</span> <span className="text-muted-foreground">/ {fmt(packetBalance.balance_pcs)}</span></span>
                  {showCt && <span>Ct: <span className="font-semibold tabular-nums">{fmt(packetBalance.balance_ct - issued.ct)}</span> <span className="text-muted-foreground">/ {fmt(packetBalance.balance_ct)}</span></span>}
                  {showGw && <span>GW: <span className="font-semibold tabular-nums">{fmt(packetBalance.balance_gw - issued.gw)}</span> <span className="text-muted-foreground">/ {fmt(packetBalance.balance_gw)}</span></span>}
                </>
              );
            })()}
          </div>
        )}

        <div className="overflow-x-auto">
          <Table className="w-full text-sm">
            <TableHeader>
              <TableRow className="bg-violet-50/70 hover:bg-violet-50/70">
                <TableHead className="w-12 py-2 px-2 text-center">#</TableHead>
                <TableHead className="w-32 py-2 px-2">Packet</TableHead>
                <TableHead className="py-2 px-2">Item</TableHead>
                <TableHead className="w-16 py-2 px-2 text-right">Pcs</TableHead>
                <TableHead className="w-20 py-2 px-2 text-right">Ct</TableHead>
                <TableHead className="w-20 py-2 px-2 text-right">GW</TableHead>
                <TableHead className="w-24 py-2 px-2 text-right">Rate</TableHead>
                <TableHead className="w-28 py-2 px-2 text-right">Taxable Value</TableHead>
                <TableHead className="w-32 py-2 px-2">Remarks</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow className="bg-muted/20">
                <TableCell className="py-1.5 px-2 text-center text-muted-foreground">{rs.length + 1}</TableCell>
                <TableCell className="py-1.5 px-2">
                  <SearchableComboBox
                    options={packets}
                    labelKey="pckt_no"
                    searchKeys={["stone_item_name"]}
                    value={watch("table.packet") ?? ""}
                    onSelect={(opt) => {
                      setValue("table.packet", opt.pckt_no);
                      handlePacketChange(opt.pckt_no);
                    }}
                    onInputChange={(val) => {
                      setValue("table.packet", val);
                      if (!val) handlePacketChange("");
                    }}
                    placeholder="Search packet…"
                    className="h-8"
                  />
                  <input type="hidden" {...register("table.packet")} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input
                    type="text"
                    className="h-8 bg-muted text-muted-foreground cursor-not-allowed"
                    readOnly
                    {...register("table.item")}
                  />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input type="number" className="h-8 text-right" {...register("table.pcs", { onChange: handlePCSchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input type="number" step="0.001" className="h-8 text-right" {...register("table.ct", {
                    onChange: handleCTchange,
                    disabled: (uom === "gm") || (uom === "pcs"),
                    readOnly: (uom === "gm") || (uom === "pcs"),
                  })} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input type="number" step="0.001" className="h-8 text-right" {...register("table.gw", {
                    onChange: handleGWchange,
                    disabled: (uom === "ct"),
                    readOnly: (uom === "ct"),
                  })} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input type="number" className="h-8 text-right bg-muted" {...register("table.rate")} readOnly />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input type="number" className="h-8 text-right bg-muted" {...register("table.taxable_value", { valueAsNumber: true })} readOnly />
                  <Input type="hidden" {...register("table.tot_val")} />
                  <Input type="hidden" {...register("table.cgst", { valueAsNumber: true })} />
                  <Input type="hidden" {...register("table.cgst_rate")} />
                  <Input type="hidden" {...register("table.sgst", { valueAsNumber: true })} />
                  <Input type="hidden" {...register("table.sgst_rate")} />
                  <Input type="hidden" {...register("table.igst", { valueAsNumber: true })} />
                  <Input type="hidden" {...register("table.igst_rate")} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input onKeyDown={(e) => handleKeyDown(e)} type="text" className="h-8" {...register("table.remarks")} />
                </TableCell>
              </TableRow>

              {rs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="py-6 text-center text-muted-foreground italic">
                    No stones added yet. Fill the row above and press Tab on Remarks.
                  </TableCell>
                </TableRow>
              ) : (
                rs.map((row, index) => (
                  <TableRow key={index} className="hover:bg-muted/30">
                    <TableCell className="py-2 px-2 text-center">
                      <div className="flex gap-2 justify-center">
                        <SquarePen className="size-4 cursor-pointer text-muted-foreground hover:text-primary" onClick={() => handleEdit(index)} />
                        <Trash2 className="size-4 cursor-pointer text-muted-foreground hover:text-red-500" onClick={() => handleDelete(index)} />
                      </div>
                    </TableCell>
                    <TableCell className="py-2 px-2">{row.packet}</TableCell>
                    <TableCell className="py-2 px-2">{row.item}</TableCell>
                    <TableCell className="py-2 px-2 text-right tabular-nums">{row.pcs}</TableCell>
                    <TableCell className="py-2 px-2 text-right tabular-nums">{row.ct != null ? parseFloat(row.ct).toFixed(3) : "—"}</TableCell>
                    <TableCell className="py-2 px-2 text-right tabular-nums">{row.gw != null ? parseFloat(row.gw).toFixed(3) : "—"}</TableCell>
                    <TableCell className="py-2 px-2 text-right tabular-nums">{row.rate}</TableCell>
                    <TableCell className="py-2 px-2 text-right tabular-nums">{Number(row.taxable_value || 0).toFixed(2)}</TableCell>
                    <TableCell className="py-2 px-2 truncate max-w-[8rem]">{row.remarks}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Hidden totals */}
      <input type="hidden" {...register("taxable_amt")} />
      <input type="hidden" {...register("form.sgst_per")} />
      <input type="hidden" {...register("form.cgst_per")} />
      <input type="hidden" {...register("form.igst_per")} />
      <input type="hidden" {...register("total_amt")} />

      {/* ── Bill Summary ── */}
      <div className="flex justify-end">
        <div className="w-full md:w-80 rounded-lg border bg-card overflow-hidden">
          <div className="divide-y text-sm">
            <div className="flex justify-between items-center px-4 py-2">
              <span className="text-muted-foreground">Taxable Value</span>
              <span className="tabular-nums">{(watch("taxable_amt") || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center px-4 py-2">
              <span className="text-muted-foreground">CGST</span>
              <span className="tabular-nums">{(watch("form.cgst_per") || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center px-4 py-2">
              <span className="text-muted-foreground">SGST</span>
              <span className="tabular-nums">{(watch("form.sgst_per") || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center px-4 py-2">
              <span className="text-muted-foreground">IGST</span>
              <span className="tabular-nums">{(watch("form.igst_per") || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center px-4 py-2.5 bg-violet-50/60 font-semibold">
              <span>Total Amount</span>
              <span className="tabular-nums">{(watch("total_amt") || 0).toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Actions ── */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.history.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
};

export default StoneIssue;

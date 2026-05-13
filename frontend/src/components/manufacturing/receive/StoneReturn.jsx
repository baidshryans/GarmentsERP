import React, { useEffect, useRef, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import {
  fetchMainItem,
  getStates,
  fetchPurity,
  getLedgers,
  fetchStoneIssuesFilterJobs,
  fetchPos,
  fetchStoneReceiveBillNo,
  createKarigarStoneReceive,
  fetchKarigarStoneReceiveforEdit,
  fetchStoneIssued,
  updateKarigarStoneReceiveforEdit,
} from "@/services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import { useEditDirty } from "@/hooks/useEditDirty";
import { SquarePen, Trash2 } from "lucide-react";
import { renderErrorTree } from "../../../Utils";

const tableDefaultValue = {
  packet: "",
  item: "",
  return_pcs: 0,
  return_ct: 0,
  return_gw: 0,
  broken_pcs: 0,
  broken_ct: 0,
  broken_gw: 0,
  loss_pcs: 0,
  loss_ct: 0,
  loss_gw: 0,
  rate: 0,
  taxable_value: 0,
  cgst: 0,
  cgst_rate: 0,
  sgst: 0,
  sgst_rate: 0,
  igst: 0,
  igst_rate: 0,
  tot_val: 0,
  remarks: "",
};

const StoneReturn = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();
  const { register, handleSubmit, control, reset, watch, setValue, getValues, setFocus, formState: { isDirty } } = useForm({
    defaultValues: {
      form: {
        place_of_supply: "WB",
        date1: new Date().toISOString().split("T")[0],
      },
      table: { ...tableDefaultValue },
    },
  });

  const [rs, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [statesData, setstatesData] = useState([]);
  const [, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [packets, setPackets] = useState([]);
  const [uom, setUOM] = useState();
  const [jobSlNos, setJobSlNos] = useState([]);
  const [maxpcs, setMaxpcs] = useState(0);
  const [maxct, setMaxct] = useState(0);
  const [maxgw, setMaxgw] = useState(0);
  const [selectedJobSl, setSelectedJobSl] = useState(null);
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const hydratingRef = useRef(!!id);

  const slip_type = watch("form.slip_type");

  useEffect(() => {
    async function fetchData() {
      const [karigars, customers, states, orderNo, mainItem, purity] = await Promise.all([
        fetchPos("Job Order"),
        getLedgers(),
        getStates(),
        fetchStoneReceiveBillNo(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (states.success) setstatesData(states.data.results ?? states.data);
      if (orderNo.success) setValue("form.billno", orderNo.data.bill_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
    }
    fetchData().then(() => {
      if (!id) return;
      fetchKarigarStoneReceiveforEdit(id)
        .then(async (response) => {
          Object.keys(response.data).forEach((key) => {
            setValue(`form.${key}`, response.data[key]);
          });

          const detailRows = response.data.karigarstonereceive_set || [];
          setRows(detailRows);

          if (detailRows.length > 0) {
            const refJobId = detailRows[0].ref_job_object_id;
            const jobSlId = detailRows[0].job_sl_object_id;
            const refJobCt = (detailRows[0].ref_job_content_type || "").toLowerCase();
            const slipType =
              response.data.slip_type ||
              (refJobCt === "karigarissue" ? "Job Order" : refJobCt === "purchaseorder" ? "Purchase Order" : "");
            if (slipType) setValue("form.slip_type", slipType);

            const k = await fetchPos(slipType);
            const karigarList = k.success ? k.data.results : [];
            setKarigars(karigarList);

            const found = karigarList.find((x) => x.id === refJobId);
            if (found) setValue("form.ref_job_name", found.name);
            setValue("form.ref_job_object_id", refJobId);
            setValue("table.ref_job_object_id", refJobId);

            const jobResp = await fetchStoneIssuesFilterJobs(refJobId, slipType);
            if (jobResp.success) {
              const items = jobResp.data.job_items || [];
              setJobSlNos(items);
              const sel = items.find((x) => x.id === jobSlId);
              if (sel) {
                setSelectedJobSl(sel);
                setValue("table.job_sl_object_id", sel.id);
              }
            }

            const pktResp = await fetchStoneIssued(refJobId, jobSlId, slipType);
            if (pktResp.success) {
              const data = pktResp.data;
              setPackets(Array.isArray(data) ? data : data?.packets ?? []);
            }
          }
          reset(getValues(), { keepValues: true, keepDirty: false });
          resetTableDirty();
          hydratingRef.current = false;
        })
        .catch((error) => {
          console.error("Error fetching stone return:", error);
          hydratingRef.current = false;
        });
    });
  }, []);

  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([fetchPos(slip_type)]);
      if (karigars.success) setKarigars(karigars.data.results);
    }
    if (slip_type) fetchData();
    if (hydratingRef.current) return;
    setValue("form.ref_job_name", "");
    setValue("form.ref_job_object_id", "");
    setSelectedJobSl(null);
    setJobSlNos([]);
    setPackets([]);
  }, [slip_type]);

  // Auto-totals
  useEffect(() => {
    const taxable_total = rs.reduce((s, i) => s + (parseFloat(i.taxable_value) || 0), 0);
    const sgst_total = rs.reduce((s, i) => s + (parseFloat(i.sgst) || 0), 0);
    const cgst_total = rs.reduce((s, i) => s + (parseFloat(i.cgst) || 0), 0);
    const igst_total = rs.reduce((s, i) => s + (parseFloat(i.igst) || 0), 0);
    setValue("taxable_amt", taxable_total);
    setValue("form.sgst_per", sgst_total);
    setValue("form.cgst_per", cgst_total);
    setValue("form.igst_per", igst_total);
    setValue("total_amt", taxable_total + cgst_total + sgst_total + igst_total);
  }, [rs]);

  const loadJobSlNos = async (jobId) => {
    const response = await fetchStoneIssuesFilterJobs(jobId, slip_type);
    if (response.success) {
      setJobSlNos(response.data.job_items || []);
    } else {
      toast({ title: "Failed to load job items.", variant: "destructive" });
    }
  };

  const loadIssuedPackets = async (refJobId, jobSlObjectId) => {
    if (!refJobId || !jobSlObjectId || !slip_type) return;
    const response = await fetchStoneIssued(refJobId, jobSlObjectId, slip_type);
    if (response.success) {
      const data = response.data;
      setPackets(Array.isArray(data) ? data : data?.packets ?? []);
    } else {
      toast({ title: "Failed to load issued stones.", variant: "destructive" });
    }
  };

  const onSubmit = () => {
    if (rs.length === 0) {
      toast({ title: "Please add at least one item.", variant: "destructive" });
      return;
    }
    rs.forEach((e) => {
      e.job_sl_content_type = slip_type === "Job Order" ? "karigarissueitem" : "purchaseorderitems";
      e.ref_job_content_type = slip_type === "Job Order" ? "karigarissue" : "purchaseorder";
    });
    const da = getValues("form");
    da.karigarstonereceive_set = [...rs];
    setSaving(true);
    (id ? updateKarigarStoneReceiveforEdit(da, id) : createKarigarStoneReceive(da))
      .then((response) => {
        if (response.success) {
          toast({ title: "Form submitted successfully!" });
          setTimeout(() => navigate("/manufacturing/receive/stonereturn/"), 1500);
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
    reset({ form: getValues("form"), table: row });
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();

    const pkt = packets.find((p) => p.pckt_no === row.packet);
    const rowPcs = (parseFloat(row.return_pcs) || 0) + (parseFloat(row.broken_pcs) || 0) + (parseFloat(row.loss_pcs) || 0);
    const rowCt = (parseFloat(row.return_ct) || 0) + (parseFloat(row.broken_ct) || 0) + (parseFloat(row.loss_ct) || 0);
    const rowGw = (parseFloat(row.return_gw) || 0) + (parseFloat(row.broken_gw) || 0) + (parseFloat(row.loss_gw) || 0);
    if (pkt) {
      setMaxpcs((pkt.total_receivable_pcs ?? 0) + rowPcs);
      setMaxct((pkt.total_receivable_ct ?? 0) + rowCt);
      setMaxgw((pkt.total_receivable_gw ?? 0) + rowGw);
      setUOM(pkt.stone_item_id?.uom);
    } else {
      setMaxpcs(rowPcs);
      setMaxct(rowCt);
      setMaxgw(rowGw);
    }
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const handleKeyDown = (e) => {
    if (e.key !== "Tab") return;
    const table = getValues("table");
    const totalPcs = (parseFloat(table.return_pcs) || 0) + (parseFloat(table.broken_pcs) || 0) + (parseFloat(table.loss_pcs) || 0);
    const totalCt = (parseFloat(table.return_ct) || 0) + (parseFloat(table.broken_ct) || 0) + (parseFloat(table.loss_ct) || 0);
    const totalGw = (parseFloat(table.return_gw) || 0) + (parseFloat(table.broken_gw) || 0) + (parseFloat(table.loss_gw) || 0);

    if (!table.packet) {
      e.preventDefault();
      toast({ title: "Select a packet before adding the row.", variant: "destructive" });
      return;
    }
    if (totalPcs <= 0 && totalCt <= 0 && totalGw <= 0) {
      e.preventDefault();
      toast({ title: "Enter at least one quantity (returned, broken, or loss).", variant: "destructive" });
      return;
    }

    if (totalPcs > maxpcs) {
      toast({ title: `Max pieces exceeded (${maxpcs} pcs available)`, variant: "destructive" });
      return;
    }
    if (totalCt > maxct) {
      toast({ title: `Max carats exceeded (${maxct} ct available)`, variant: "destructive" });
      return;
    }
    if (totalGw > maxgw) {
      toast({ title: `Max weight exceeded (${maxgw} gm available)`, variant: "destructive" });
      return;
    }
    e.preventDefault();
    const sl_no = rs.length + 1;
    setRows([...rs, { sl_no, ...table }]);
    markTableDirty();
    reset({ form: { ...getValues("form") }, table: { ...tableDefaultValue } });
    setUOM(undefined);
    setMaxpcs(0);
    setMaxct(0);
    setMaxgw(0);
    setTimeout(() => {
      const el = document.querySelector('[data-packet-combo] input');
      if (el) el.focus();
    }, 0);
  };

  const handlePacketChange = (selectedValue) => {
    const selectedPacket = packets.find((p) => p.pckt_no === selectedValue);
    setMaxpcs(selectedPacket?.total_receivable_pcs ?? 0);
    setMaxgw(selectedPacket?.total_receivable_gw ?? 0);
    setMaxct(selectedPacket?.total_receivable_ct ?? 0);

    if (!selectedPacket) {
      setUOM(undefined);
      return;
    }
    setValue("table.item", selectedPacket.stone_item_id?.short_code || "");
    setValue("table.rate", selectedPacket.rate_for_retail || 0);
    setValue("table.sgst_rate", selectedPacket.stone_item_id?.hsn_no?.sgst ?? 0);
    setValue("table.igst_rate", selectedPacket.stone_item_id?.hsn_no?.igst ?? 0);
    setValue("table.cgst_rate", selectedPacket.stone_item_id?.hsn_no?.cgst ?? 0);

    const newUom = selectedPacket.stone_item_id?.uom;
    setUOM(newUom);
    setValue("table.return_pcs", 0);
    setValue("table.return_ct", 0);
    setValue("table.return_gw", 0);
    setValue("table.broken_pcs", 0);
    setValue("table.broken_ct", 0);
    setValue("table.broken_gw", 0);
    setValue("table.loss_pcs", 0);
    setValue("table.loss_ct", 0);
    setValue("table.loss_gw", 0);
    setValue("table.taxable_value", 0);
    setValue("table.cgst", 0);
    setValue("table.sgst", 0);
    setValue("table.igst", 0);
    setValue("table.tot_val", 0);
  };

  const recalcTax = (taxable) => {
    const { sgst_rate, cgst_rate, igst_rate } = getValues("table");
    const sgst_val = ((parseFloat(sgst_rate) || 0) * taxable) / 100;
    const cgst_val = ((parseFloat(cgst_rate) || 0) * taxable) / 100;
    const igst_val = ((parseFloat(igst_rate) || 0) * taxable) / 100;
    setValue("table.sgst", sgst_val);
    setValue("table.cgst", cgst_val);
    setValue("table.igst", igst_val);
    setValue("table.tot_val", taxable + sgst_val + cgst_val + igst_val);
  };

  const handleGWchange = () => {
    const { return_gw, broken_gw, loss_gw, rate } = getValues("table");
    const totalGw = (parseFloat(return_gw) || 0) + (parseFloat(broken_gw) || 0) + (parseFloat(loss_gw) || 0);
    const taxable = totalGw * (parseFloat(rate) || 0);
    setValue("table.taxable_value", taxable);
    setValue("table.return_ct", parseFloat(((parseFloat(return_gw) || 0) * 5).toFixed(3)));
    setValue("table.broken_ct", parseFloat(((parseFloat(broken_gw) || 0) * 5).toFixed(3)));
    setValue("table.loss_ct", parseFloat(((parseFloat(loss_gw) || 0) * 5).toFixed(3)));
    recalcTax(taxable);
  };

  const handleCTchange = () => {
    const { return_ct, broken_ct, loss_ct, rate } = getValues("table");
    const totalCt = (parseFloat(return_ct) || 0) + (parseFloat(broken_ct) || 0) + (parseFloat(loss_ct) || 0);
    const taxable = totalCt * (parseFloat(rate) || 0);
    setValue("table.taxable_value", taxable);
    setValue("table.return_gw", parseFloat(((parseFloat(return_ct) || 0) / 5).toFixed(3)));
    setValue("table.broken_gw", parseFloat(((parseFloat(broken_ct) || 0) / 5).toFixed(3)));
    setValue("table.loss_gw", parseFloat(((parseFloat(loss_ct) || 0) / 5).toFixed(3)));
    recalcTax(taxable);
  };

  const handlePCSchange = () => {
    const { return_pcs, broken_pcs, loss_pcs, rate } = getValues("table");
    const totalPcs = (parseFloat(return_pcs) || 0) + (parseFloat(broken_pcs) || 0) + (parseFloat(loss_pcs) || 0);
    const taxable = totalPcs * (parseFloat(rate) || 0);
    setValue("table.taxable_value", taxable);
    recalcTax(taxable);
  };

  const ctDisabled = uom?.toLowerCase() === "gm";
  const gwDisabled = uom?.toLowerCase() === "ct";

  return (
    <form
      id="orderForm"
      onSubmit={handleSubmit(onSubmit)}
      className="px-8 py-4 space-y-4 text-sm"
    >
      <h2 className="text-xl font-semibold">Stone Return from Karigar</h2>

      {/* ── Return Details ── */}
      <div className="rounded-lg border bg-card">
        <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 rounded-t-lg text-sm font-medium text-primary">
          Return Details
        </div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="sr-date">Date</Label>
            <Input id="sr-date" type="date" {...register("form.date1")} required />
          </div>
          <div>
            <Label>Return Slip No</Label>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-3 py-1.5 rounded-md bg-violet-50 border border-violet-200 text-primary text-sm font-semibold min-w-0 flex-1 truncate h-9">
                {watch("form.billno") || (
                  <span className="text-violet-400 text-xs font-normal">Auto-generating�</span>
                )}
              </span>
              <input type="hidden" {...register("form.billno")} />
            </div>
          </div>
          <div>
            <Label htmlFor="sr-slip-type">
              Slip Type <span className="text-red-500">*</span>
            </Label>
            <Controller
              name="form.slip_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger id="sr-slip-type" data-id="slip-type">
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
            <Label htmlFor="sr-pos">Place of Supply</Label>
            <Controller
              name="form.place_of_supply"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger id="sr-pos">
                    <SelectValue placeholder="Select State" />
                  </SelectTrigger>
                  <SelectContent>
                    {statesData.map((sp, index) => (
                      <SelectItem key={index} value={`${sp.code}`}>
                        {sp.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div>
            <Label>
              Karigar <span className="text-red-500">*</span>
            </Label>
            <SearchableComboBox
              options={customers}
              value={watch("form.karigar_ldgr_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.karigar_ldgr_name", opt.ac_name);
                setValue("form.karigar_ldgr", opt.id);
              }}
              placeholder="Search karigar�"
            />
            <input type="hidden" {...register("form.karigar_ldgr")} />
          </div>
          <div>
            <Label>
              {slip_type === "Purchase Order" ? "Purchase Order No" : "Job Work Slip No"}{" "}
              <span className="text-red-500">*</span>
            </Label>
            <SearchableComboBox
              options={karigars.map((k) => ({ id: k.id, ac_name: k.name }))}
              value={watch("form.ref_job_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.ref_job_name", opt.ac_name);
                setValue("form.ref_job_object_id", opt.id);
                setValue("table.ref_job_object_id", opt.id);
                setSelectedJobSl(null);
                setJobSlNos([]);
                setPackets([]);
                loadJobSlNos(opt.id);
              }}
              placeholder={`Search ${slip_type === "Purchase Order" ? "purchase order" : "job order"}�`}
            />
            <input type="hidden" {...register("form.ref_job_object_id")} />
            <input type="hidden" {...register("table.ref_job_object_id")} />
          </div>
        </div>
      </div>

      {/* ── Job Sl No Picker ── */}
      {jobSlNos.length > 0 && (
        <div className="rounded-lg border bg-card">
          <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 rounded-t-lg text-sm font-medium text-primary flex items-center justify-between">
            <span>Pick Item to Return Stones Against</span>
            {selectedJobSl && rs.length > 0 && (
              <span className="text-xs text-muted-foreground font-normal">
                Locked � clear stones to switch
              </span>
            )}
          </div>
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {jobSlNos.map((it) => {
              const isSelected = selectedJobSl?.id === it.id;
              const locked = rs.length > 0 && !isSelected;
              return (
                <div
                  key={it.id}
                  onClick={() => {
                    if (locked) {
                      toast({
                        title: "Item locked",
                        description: "Stones already added against another item. Remove all rows to switch.",
                        variant: "destructive",
                      });
                      return;
                    }
                    setSelectedJobSl(it);
                    setValue("table.job_sl_object_id", it.id);
                    loadIssuedPackets(getValues("form.ref_job_object_id"), it.id);
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
                    <span className="text-xs font-semibold text-muted-foreground">
                      Sl No � {it.job_sl_no}
                    </span>
                    {isSelected && <span className="text-xs font-semibold text-primary">✓ Selected</span>}
                  </div>
                  <div className="font-semibold text-foreground">{it.item_name || "�"}</div>
                  <div className="text-xs text-muted-foreground mt-1.5 grid grid-cols-2 gap-x-2 gap-y-0.5">
                    <span>Pcs: <span className="text-foreground">{it.pcs}</span></span>
                    <span>Wt: <span className="text-foreground">{it.approx_wt}</span></span>
                    {it.purity && <span>Purity: <span className="text-foreground">{it.purity}</span></span>}
                    {it.size && <span>Size: <span className="text-foreground">{it.size}</span></span>}
                    {it.design_code && (
                      <span className="col-span-2">
                        Design: <span className="text-foreground">{it.design_code}</span>
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
            <input type="hidden" {...register("table.job_sl_object_id")} />
          </div>
        </div>
      )}

      {/* ── Stone Return Entry ── */}
      <div className="rounded-lg border bg-card">
        <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 rounded-t-lg text-sm font-medium text-primary flex items-center justify-between">
          <span>Stones</span>
          <span className="text-xs text-muted-foreground font-normal">Tab on Remarks to add row</span>
        </div>

        {watch("table.packet") && (maxpcs > 0 || maxct > 0 || maxgw > 0) && (
          <div className="px-4 py-2 border-b bg-muted/40 text-xs flex flex-wrap items-center gap-x-6 gap-y-1">
            <span className="font-medium">
              {watch("table.packet")} � {watch("table.item")}{" "}
              <span className="uppercase text-muted-foreground">({uom || "�"})</span>
            </span>
            <span>
              Receivable Pcs: <span className="font-semibold tabular-nums">{maxpcs}</span>
            </span>
            <span>
              Receivable Ct: <span className="font-semibold tabular-nums">{maxct}</span>
            </span>
            <span>
              Receivable GW: <span className="font-semibold tabular-nums">{maxgw}</span>
            </span>
          </div>
        )}

        <div className="overflow-x-auto">
          <Table className="w-full text-sm">
            <TableHeader>
              <TableRow className="bg-violet-50/70 hover:bg-violet-50/70">
                <TableHead rowSpan={2} className="w-12 py-2 px-2 text-center align-middle border-r">#</TableHead>
                <TableHead rowSpan={2} className="w-32 py-2 px-2 align-middle border-r">Packet</TableHead>
                <TableHead rowSpan={2} className="w-28 py-2 px-2 align-middle border-r">Item</TableHead>
                <TableHead colSpan={3} className="py-1.5 px-2 text-center text-emerald-700 border-r">
                  Returned
                </TableHead>
                <TableHead colSpan={3} className="py-1.5 px-2 text-center text-amber-700 border-r">
                  Broken
                </TableHead>
                <TableHead colSpan={3} className="py-1.5 px-2 text-center text-rose-700 border-r">
                  Loss
                </TableHead>
                <TableHead rowSpan={2} className="w-20 py-2 px-2 text-right align-middle border-r">Rate</TableHead>
                <TableHead rowSpan={2} className="w-32 py-2 px-2 align-middle">Remarks</TableHead>
              </TableRow>
              <TableRow className="bg-violet-50/40 hover:bg-violet-50/40">
                <TableHead className="w-14 py-1 px-1 text-right text-emerald-700 font-normal">Pcs</TableHead>
                <TableHead className="w-16 py-1 px-1 text-right text-emerald-700 font-normal">Ct</TableHead>
                <TableHead className="w-16 py-1 px-1 text-right text-emerald-700 font-normal border-r">GW</TableHead>
                <TableHead className="w-14 py-1 px-1 text-right text-amber-700 font-normal">Pcs</TableHead>
                <TableHead className="w-16 py-1 px-1 text-right text-amber-700 font-normal">Ct</TableHead>
                <TableHead className="w-16 py-1 px-1 text-right text-amber-700 font-normal border-r">GW</TableHead>
                <TableHead className="w-14 py-1 px-1 text-right text-rose-700 font-normal">Pcs</TableHead>
                <TableHead className="w-16 py-1 px-1 text-right text-rose-700 font-normal">Ct</TableHead>
                <TableHead className="w-16 py-1 px-1 text-right text-rose-700 font-normal border-r">GW</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow className="bg-muted/20">
                <TableCell className="py-1.5 px-2 text-center text-muted-foreground">{rs.length + 1}</TableCell>
                <TableCell className="py-1.5 px-2" data-packet-combo>
                  <SearchableComboBox
                    options={packets}
                    labelKey="pckt_no"
                    value={watch("table.packet") ?? ""}
                    onSelect={(opt) => {
                      setValue("table.packet", opt.pckt_no);
                      handlePacketChange(opt.pckt_no);
                    }}
                    onInputChange={(val) => {
                      setValue("table.packet", val);
                      if (!val) handlePacketChange("");
                    }}
                    placeholder="Search packet�"
                    className="h-8"
                  />
                  <input type="hidden" {...register("table.packet")} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input type="text" className="h-8 bg-muted text-muted-foreground" readOnly {...register("table.item")} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" className="h-8 text-right" {...register("table.return_pcs", { valueAsNumber: true, onChange: handlePCSchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" step="0.001" className="h-8 text-right" disabled={ctDisabled} readOnly={ctDisabled} {...register("table.return_ct", { valueAsNumber: true, onChange: handleCTchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" step="0.001" className="h-8 text-right" disabled={gwDisabled} readOnly={gwDisabled} {...register("table.return_gw", { valueAsNumber: true, onChange: handleGWchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" className="h-8 text-right" {...register("table.broken_pcs", { valueAsNumber: true, onChange: handlePCSchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" step="0.001" className="h-8 text-right" disabled={ctDisabled} readOnly={ctDisabled} {...register("table.broken_ct", { valueAsNumber: true, onChange: handleCTchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" step="0.001" className="h-8 text-right" disabled={gwDisabled} readOnly={gwDisabled} {...register("table.broken_gw", { valueAsNumber: true, onChange: handleGWchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" className="h-8 text-right" {...register("table.loss_pcs", { valueAsNumber: true, onChange: handlePCSchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" step="0.001" className="h-8 text-right" disabled={ctDisabled} readOnly={ctDisabled} {...register("table.loss_ct", { valueAsNumber: true, onChange: handleCTchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" step="0.001" className="h-8 text-right" disabled={gwDisabled} readOnly={gwDisabled} {...register("table.loss_gw", { valueAsNumber: true, onChange: handleGWchange })} />
                </TableCell>
                <TableCell className="py-1.5 px-1">
                  <Input type="number" className="h-8 text-right bg-muted" readOnly {...register("table.rate", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.taxable_value", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.cgst", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.cgst_rate", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.sgst", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.sgst_rate", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.igst", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.igst_rate", { valueAsNumber: true })} />
                  <input type="hidden" {...register("table.tot_val", { valueAsNumber: true })} />
                </TableCell>
                <TableCell className="py-1.5 px-2">
                  <Input onKeyDown={handleKeyDown} type="text" className="h-8" {...register("table.remarks")} />
                </TableCell>
              </TableRow>

              {rs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={14} className="py-6 text-center text-muted-foreground italic">
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
                    <TableCell className="py-2 px-1 text-right tabular-nums text-emerald-700">{row.return_pcs || 0}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-emerald-700">{Number(row.return_ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-emerald-700">{Number(row.return_gw || 0).toFixed(3)}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-amber-700">{row.broken_pcs || 0}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-amber-700">{Number(row.broken_ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-amber-700">{Number(row.broken_gw || 0).toFixed(3)}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-rose-700">{row.loss_pcs || 0}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-rose-700">{Number(row.loss_ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums text-rose-700">{Number(row.loss_gw || 0).toFixed(3)}</TableCell>
                    <TableCell className="py-2 px-1 text-right tabular-nums">{row.rate}</TableCell>
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
        <Button type="submit" disabled={saving || !canSave}>
          {saveLabel(saving)}
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.history.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
};

export default StoneReturn;

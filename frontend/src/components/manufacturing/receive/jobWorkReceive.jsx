import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { fetchMainItem, fetchOrderItem, fetchReceiveSlipNo, fetchKarigarIssues, fetchPurity, getLedgers, createCustomerOrder, fetchPackets, getStates, fetchStoneIssuesFilterJobs, fetchMainItemDetails, createKarigarReceive, fetchKarigarReceive, fetchKarigarReceivewithID, updateKarigarReceive, fetchSampleIssues, fetchSampleIssueForEdit } from "@/services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router-dom";


function SectionCard({ title, children, className = "", action, subtitle }) {
  return (
    <div className={`bg-white border border-border rounded-xl shadow-sm ${className}`}>
      <div className="px-5 py-3 border-b border-border bg-muted/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-0.5 h-4 rounded-full bg-primary inline-block" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">{title}</h3>
          {subtitle ? <span className="text-xs text-muted-foreground">· {subtitle}</span> : null}
        </div>
        {action ? <div>{action}</div> : null}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

const JobWorkReceive = () => {
  const { id } = useParams()
  const { toast } = useToast()
  const { register, control, handleSubmit, reset, watch, setValue, getValues, trigger, formState: { isDirty } } = useForm({
    defaultValues: {
      form: {
        date1: new Date().toISOString().split('T')[0],
        place_of_supply: "WB",
        source_type: "job",
        table: []
      }
    }
  });
  const navigate=useNavigate();
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [change, setChange] = useState(0);
  const [saving, setSaving] = useState(false);
  const [serialNos, setSerialNos] = useState([]);
  const [rs, setRows] = useState([]);
  const [statesData, setstatesData] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [jobSlNos, setJobSlNos] = useState([]);
  const [packets, setPackets] = useState([]);
  const [sampleIssues, setSampleIssues] = useState([]);
  const [sampleItems, setSampleItems] = useState([]);

  const { fields, append, remove } = useFieldArray({
    control,
    name: "table",
  });

  const watchFields = watch("table") || [];
  const watchedRefJobNoId = watch("form.ref_job_no_id");

  useEffect(() => {
    if (watchedRefJobNoId) {
      loadSerialNos(watchedRefJobNoId);
    } else {
      setSerialNos([]);
    }
  }, [watchedRefJobNoId]);
function modifyData(data) {
  data.items.forEach(item => {
    // Calculate pending values from received pcs/gw minus what's already in details
    const pending_pcs = item.pcs - (item.details.reduce((sum, detail) => sum + (parseFloat(detail.balance_pcs) || 0), 0));
    const pending_gw = item.nw - (item.details.reduce((sum, detail) => sum + (parseFloat(detail.balance_gw) || 0), 0));

    // Set pending values on the main item object
    item.pending_pcs = pending_pcs;
    item.pending_gw = pending_gw;

    let newDetail = {
      broken_pcs: 0,
      issue_pcs: 0,
      return_pcs: 0,
      rate: 0,
      item: "Gold",
      metal_purity: item.purity,
      balance_ct: "0",
      balance_gw: item.nw,
      balance_pcs: 0,
      sl_no: item.sl_no,
    };

    item.details.push(newDetail);
  });
  return data;
}

  const loadSerialNos = async (refJobNoId) => {
    console.log("[JobWorkReceive] loadSerialNos called with refJobNoId =", refJobNoId);
    if (!refJobNoId) {
      setSerialNos([]);
      return;
    }
    const response = await fetchStoneIssuesFilterJobs(refJobNoId, "Job Order");
    console.log("[JobWorkReceive] filter-job-items response:", response);
    if (response.success) {
      let items = response.data.job_items || [];
      // Filter to show only items that have been issued but not yet fully received
      items = items.filter(item => {
        const issued = parseFloat(item.issued_qty || item.pcs || 0);
        const received = parseFloat(item.received_qty || 0);
        return issued > received;
      });
      console.log("[JobWorkReceive] setting serialNos to", items.length, "items (after filtering for pending):", items);
      setSerialNos(items);
    } else {
      toast({ title: "An error occurred. Please try again later." });
    }
  }

  const handleBlur = async (e) => {
    const { ref_job_no_id } = getValues("form");
    await loadSerialNos(ref_job_no_id);
  }

  const round3 = (v) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? Number(n.toFixed(3)) : v;
  };
  const WEIGHT_FIELDS = [
    "gw", "nw", "less_gw", "supplied_gw", "sample_piece_gw",
    "main_total_wt", "wastage", "fine_wt",
    "issue_gw", "return_gw", "broken_gw", "balance_gw",
    "issue_ct", "return_ct", "broken_ct", "balance_ct",
  ];
  const round3WeightFields = (obj) => {
    if (!obj) return obj;
    WEIGHT_FIELDS.forEach((k) => {
      if (obj[k] !== undefined && obj[k] !== null && obj[k] !== "") {
        obj[k] = round3(obj[k]);
      }
    });
    return obj;
  };

  const handleBlur1 = async (e) => {

    const { ref_job_no, ref_job_no_id, sl_no } = getValues("form");
    if (!ref_job_no || !sl_no) {
      return;
    }
    try {
      const data = await fetchMainItemDetails(ref_job_no, sl_no);
      const sl = getValues("table").length + 1
      const matchingSerial = serialNos.find(
        (s) => String(s.job_sl_no) === String(sl_no)
      );

      // Check for duplicate: prevent adding the same job item twice
      const refJobSlNo = matchingSerial?.id || null;
      const existingItem = getValues("table").find(
        (item) => item.ref_job_sl_no === refJobSlNo
      );
      if (existingItem) {
        toast({
          title: "Duplicate Item",
          description: `Item '${ref_job_no}' with SL No '${sl_no}' is already added in this receive slip.`,
        });
        return;
      }

      const stone_details = [...data.data.details]
      data.data.date1 = getValues("form.date1")
      data.data.sl_no = sl
      data.data.ref_job_no = ref_job_no_id || matchingSerial?.job_id || null;
      data.data.ref_job_sl_no = matchingSerial?.id || null;
      data.data._source_label = `Job · ${ref_job_no} · Sl ${sl_no}`;
      data.data.details = stone_details
        .map(detail => {
          // Calculate amount based on UOM
          const rate = parseFloat(detail.rate) || 0;
          let amount = 0;
          detail.sl_no = sl

          switch (detail.uom?.toLowerCase()) {
            case 'ct':
              amount = (parseFloat(detail.balance_ct) || 0) * rate;
              break;
            case 'gm':
              amount = (parseFloat(detail.balance_gw) || 0) * rate;
              break;
            case 'pcs':
              amount = (parseFloat(detail.balance_pcs) || 0) * rate;
              break;
          }


          return {
            ...detail,
            amt: amount.toFixed(0)
          };
        })



      console.log(data.data)
      data.data.tunch_per = 0
      data.data.less_gw = 0
      data.data.loss = 0

      data.data.nw = round3(data.data.gw - data.data.details.reduce((sum, detail) => sum + (parseFloat(detail.balance_gw) || 0), 0))
      round3WeightFields(data.data);
      data.data.details = (data.data.details || []).map(round3WeightFields);

      append(data.data)
      markTableDirty();
      setTimeout(() => {
        handletunchChange(getValues("table").length - 1);
        handlelossChange(getValues("table").length - 1);
      }, 500)

      setValue("form.ref_job_no", "");
      setValue("form.ref_job_no_id", "");
      setValue("form.sl_no", "");
      setSerialNos([]);

    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }

  const handleSampleBlur = async () => {
    const { ref_sample_issue_id } = getValues("form");
    if (!ref_sample_issue_id) return;
    const resp = await fetchSampleIssueForEdit(ref_sample_issue_id);
    if (resp.success) {
      setSampleItems(resp.data.items || []);
    } else {
      toast({ title: "Failed to load sample issue items." });
    }
  }

  const handleSampleItemBlur = async () => {
    const { ref_sample_issue_id, ref_sample_sl_no } = getValues("form");
    if (!ref_sample_issue_id || !ref_sample_sl_no) return;
    const itm = sampleItems.find(it => String(it.sl_no) === String(ref_sample_sl_no));
    if (!itm) return;
    const sl = getValues("table").length + 1;
    const row = {
      sl_no: sl,
      item: itm.piece_item_name || "",
      purity: itm.piece_purity || "",
      finish_status: false,
      pcs: itm.piece_pcs || 0,
      gw: round3(itm.piece_gw || 0),
      nw: round3(itm.piece_gw || 0),
      less_gw: 0,
      loss: 0,
      tunch_per: 0,
      fine_wt: 0,
      main_total_wt: 0,
      wastage: 0,
      add_field_type: 0,
      making: 0,
      rhodium: 0,
      remarks: "",
      details: [],
      ref_sample_issue: ref_sample_issue_id,
      ref_sample_issue_item: itm.id,
      sample_piece_gw: itm.piece_gw || 0,
      _source_label: `Sample · ${getValues("form.ref_sample_issue_billno") || ""} · Sl ${ref_sample_sl_no}`,
    };
    append(row);
    markTableDirty();

    setValue("form.ref_sample_issue_billno", "");
    setValue("form.ref_sample_issue_id", "");
    setValue("form.ref_sample_sl_no", "");
    setSampleItems([]);
  }

  useEffect(() => {
    async function fetchData() {
      const [packets, states, karigars, customers, salesperson, orderNo, mainItem, purity, sampleIssueList] = await Promise.all([
        fetchPackets(),
        getStates(),
        fetchKarigarIssues({ page_size: 500 }),
        getLedgers(),
        getStates(),
        fetchReceiveSlipNo(),
        fetchMainItem(),
        fetchPurity(),
        fetchSampleIssues(),
      ]);
      if (packets.success) setPackets(packets.data.results);
      if (states.success) setstatesData(states.data);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (salesperson.success) setSalespersonData(salesperson.data.results ?? salesperson.data);
      if (orderNo.success) setValue("form.receive_slip_no", orderNo.data.receive_slip_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
      if (sampleIssueList.success) setSampleIssues(sampleIssueList.data.results ?? sampleIssueList.data);
    }
    fetchData().then((d) => {

      if (id) {

        fetchKarigarReceivewithID(id).then(data => {
          if (data.success) {
            const formData = {
              form: {
              ...data.data,
              table: JSON.parse(JSON.stringify(data.data.items)).map(item => {
                const cleaned = round3WeightFields({
                  ...item,
                  details: item.details
                    .filter(detail => String(detail.item || '').toLowerCase() !== 'gold')
                    .map(round3WeightFields)
                });
                return cleaned;
              })
              }
            };
            setValue("form.place_of_supply", "TN")
            Object.keys(formData.form).forEach(key => {
              if (key === 'table') {
                formData.form[key].forEach((item, index) => {
                  append(item);
                });
              } else {
                setValue(`form.${key}`, formData.form[key]);
              }
            });
            reset(getValues(), { keepValues: true, keepDirty: false });
            resetTableDirty();
          }
        })
      }


    });

  }, []);

  const onSubmit = (data) => {
    const form_data = getValues("form");
    form_data.items = (getValues('table') || []).map((row) => {
      const { _source_label, ...rest } = row || {};
      ['rhodium', 'making', 'wastage'].forEach((k) => {
        if (rest[k] === '' || rest[k] === undefined) rest[k] = null;
      });
      return rest;
    });
    // Per-item ref_* fields drive routing; strip header-level helpers that aren't on the backend model.
    delete form_data.source_type;
    delete form_data.ref_sample_issue_billno;
    delete form_data.ref_sample_issue_id;
    delete form_data.ref_sample_sl_no;
    delete form_data.ref_job_no;
    delete form_data.ref_job_no_id;
    delete form_data.sl_no;
    let newData = JSON.parse(JSON.stringify(form_data));
    console.log(modifyData)
    modifyData(newData);

    setSaving(true);
    (id ? updateKarigarReceive(id, newData) : createKarigarReceive(newData))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });  // Success toast

          setTimeout(()=>{
            navigate("/manufacturing/receive/jobworkreceive/");
          },2000);

        }else {
                  setSaving(false);
                  toast({
                    title: "Form submission failed. Please try again.",
                    description: renderErrorTree(response.error),
                  });  // Error toast
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
    reset(row);
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const recalcNw = (index) => {
    const gw = parseFloat(getValues(`table.${index}.gw`)) || 0;
    const details = getValues(`table.${index}.details`) || [];
    const stoneGw = details.reduce(
      (sum, d) => sum + (parseFloat(d?.balance_gw) || 0),
      0
    );
    const nw = gw - stoneGw;
    setValue(`table.${index}.nw`, Number(nw.toFixed(3)));
    handlelossChange(index);
    handletunchChange(index);
  }

  const handletunchChange = (index) => {
    const tunch = parseFloat(getValues(`table.${index}.tunch_per`)) || 0;
    const nw = parseFloat(getValues(`table.${index}.nw`)) || 0;
    const value = (tunch / 100) * nw;
    setValue(`table.${index}.fine_wt`, Number(value.toFixed(3)))
  }

  const handlelossChange = (index) => {
    const lossPct = parseFloat(getValues(`table.${index}.loss`)) || 0;
    const nw = parseFloat(getValues(`table.${index}.nw`)) || 0;
    const less = parseFloat(getValues(`table.${index}.less_gw`)) || 0;
    const lossFrac = lossPct / 100;
    const base = nw - less;

    setValue(`table.${index}.main_total_wt`, Number((base * (1 + lossFrac)).toFixed(3)))
    setValue(`table.${index}.wastage`, Number((base * lossFrac).toFixed(3)))
  }

  const handlelesswtChange = (index) => {
    handlelossChange(index);
  }

  const handleaddwtChange = (index) => {
    // const value = parseFloat(getValues(`table.${index}.tunch_per`)) * parseFloat(getValues(`table.${index}.nw`)) 

    // setValue(`table.${index}.fine_wt`,`${value}`)
  }



  const handleKeyDown = (event) => {
    event.preventDefault();
    if (event.key === "Tab") {
      const detail = getValues("details")
      console.log(detail)
      const currentTableIndex = parseInt(detail.sl_no) - 1;
      if (currentTableIndex >= 0) {

        const tableValue = getValues(`table.${currentTableIndex}.details`) || [];
        console.log(tableValue);
        tableValue.push(detail);
        setValue(`table.${currentTableIndex}.details`, [...tableValue]);
        setChange(prev => prev + 1)

        setValue("details", {
          sl_no: "",
          packet: "",
          item: "",
          issue_pcs: "",
          issue_ct: "",
          issue_gw: "",
          return_pcs: "",
          return_ct: "",
          return_gw: "",
          broken_pcs: "",
          broken_ct: "",
          broken_gw: "",
          balance_pcs: "",
          balance_ct: "",
          balance_gw: "",
          rate: "",
          amt: ""
        });
      }

    }
  };

  return (
    <div className="w-[96%] max-w-[1500px] mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <button type="button" onClick={() => navigate("/")} className="hover:text-foreground">Home</button>
        <span>/</span>
        <button type="button" onClick={() => navigate("/manufacturing/receive/jobworkreceive/")} className="hover:text-foreground">Job Work Receive</button>
        <span>/</span>
        <span className="text-foreground">{id ? "Edit" : "New"}</span>
      </div>

      <div className="flex items-center justify-between sticky top-0 z-20 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70 -mx-4 px-4 py-2 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold text-foreground">
            {id ? "Edit Job Work Receive" : "New Job Work Receive"}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">Receive finished pieces from karigars against job orders or samples.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.history.back()}>Cancel</Button>
          <Button
            type="submit"
            form="orderForm"
            size="sm"
            className="bg-primary hover:bg-primary/90 text-primary-foreground"
            disabled={saving}
          >
            {saving ? "Saving..." : (id ? "Update" : "Save Receive")}
          </Button>
        </div>
      </div>

      <form
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-4"
      >
        <SectionCard title="Receive Reference">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3 lg:grid-cols-4">
            <FieldContainer>
              <Label htmlFor="date">Date</Label>
              <Input type="date" {...register("form.date1")} required />
            </FieldContainer>
            <FieldContainer>
              <Label htmlFor="receive_slip_no" className="text-nowrap">Receive Slip No</Label>
              <Input type="text" {...register("form.receive_slip_no")} readOnly disabled className="bg-muted/40" />
            </FieldContainer>
            <FieldContainer>
              <Label htmlFor="place_of_supply" className="text-nowrap">Place of Supply</Label>
              <Controller
                name="form.place_of_supply"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger>
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
            </FieldContainer>
            <FieldContainer>
              <Label htmlFor="party_name_display" className="text-nowrap">Karigar Name</Label>
              <SearchableComboBox
                options={customers}
                value={watch("form.karigar_ldgr_name") ?? ""}
                onSelect={(opt) => {
                  setValue("form.karigar_ldgr_name", opt.ac_name)
                  setValue("form.karigar_ldgr", opt.id)
                }}
                placeholder="Search karigar…"
              />
              <input type="hidden" {...register("form.karigar_ldgr")} />
            </FieldContainer>
          </div>
        </SectionCard>

        <SectionCard
          title="Add Item"
          subtitle="Pick from a job order or a sample issue. The picker clears after each row added."
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-lg border border-border bg-muted/10 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-semibold">JW</span>
                <span className="text-xs font-semibold uppercase tracking-wider text-foreground">From Job Work</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <FieldContainer>
              <Label htmlFor="ref_no_list" className="text-nowrap">Ref Job No</Label>
              <Input type="hidden" {...register("form.ref_job_no_id")} />
              <Input list="ref_no_list"
                {...register("form.ref_job_no", {
                  onBlur: handleBlur,
                  onChange: async (e) => {
                    const selectedSlipNo = e.target.value;
                    setValue("form.sl_no", "");
                    let selectedKarigar = karigars.find(
                      (serialNo) => serialNo.issue_slip_no === selectedSlipNo
                    );
                    if (!selectedKarigar && selectedSlipNo) {
                      const search = await fetchKarigarIssues({ search: selectedSlipNo, page_size: 50 });
                      if (search.success) {
                        const list = search.data.results || search.data || [];
                        selectedKarigar = list.find(
                          (k) => k.issue_slip_no === selectedSlipNo
                        );
                        if (selectedKarigar) {
                          setKarigars((prev) => {
                            const existingIds = new Set(prev.map((p) => p.id));
                            return existingIds.has(selectedKarigar.id) ? prev : [...prev, selectedKarigar];
                          });
                        }
                      }
                    }
                    if (selectedKarigar) {
                      setValue("form.ref_job_no_id", selectedKarigar.id);
                      loadSerialNos(selectedKarigar.id);
                    } else {
                      setValue("form.ref_job_no_id", "");
                      setSerialNos([]);
                    }
                  }
                })}
              />
              <datalist id="ref_no_list" >
                {karigars.map((serialNo, index) => (
                  <option key={index} value={serialNo.issue_slip_no}></option>
                ))}
              </datalist>
            </FieldContainer>

                <FieldContainer>
                  <Label htmlFor="serial_no_list" className="text-nowrap">Sl No</Label>
                  <Input list="serial_no_list"
                    {...register("form.sl_no", { onBlur: handleBlur1 })}
                  />
                  <datalist id="serial_no_list">
                    {serialNos.map((serialNo, index) => (
                      <option key={index} value={serialNo.job_sl_no}></option>
                    ))}
                  </datalist>
                </FieldContainer>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-muted/10 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-semibold">SM</span>
                <span className="text-xs font-semibold uppercase tracking-wider text-foreground">From Sample</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <FieldContainer>
                  <Label className="text-nowrap">Sample Issue Billno</Label>
                  <Input type="hidden" {...register("form.ref_sample_issue_id")} />
                  <Input list="sample_issue_list"
                    {...register("form.ref_sample_issue_billno", {
                      onBlur: handleSampleBlur,
                      onChange: (e) => {
                        const billno = e.target.value;
                        const selected = sampleIssues.find((s) => s.billno === billno);
                        if (selected) setValue("form.ref_sample_issue_id", selected.id);
                      }
                    })}
                  />
                  <datalist id="sample_issue_list">
                    {sampleIssues.map((s, i) => (
                      <option key={i} value={s.billno}></option>
                    ))}
                  </datalist>
                </FieldContainer>

                <FieldContainer>
                  <Label className="text-nowrap">Sample Sl No</Label>
                  <Input list="sample_sl_no_list"
                    {...register("form.ref_sample_sl_no", { onBlur: handleSampleItemBlur })}
                  />
                  <datalist id="sample_sl_no_list">
                    {sampleItems.map((it, i) => (
                      <option key={i} value={it.sl_no}>{it.piece_label}</option>
                    ))}
                  </datalist>
                </FieldContainer>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          title="Item Details"
          subtitle={`${(watchFields || []).length} item(s)`}
        >
        <div className="overflow-x-auto -mx-2">
        <Table className="w-full text-sm border-collapse">
          <TableBody>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider">Sl.No</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider">Source</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider">Item</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider">Purity</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-center">Finish</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Pcs</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Gw</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Nw</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Incr GW</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Less</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Loss %</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Wastage</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Karigar Cr</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Tunch</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Fine Wt</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Add</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Making</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider text-right">Rhodium</TableCell>
              <TableCell className="px-2 py-2 border text-xs font-semibold text-muted-foreground uppercase tracking-wider">Remarks</TableCell>
            </TableRow>
            {(watchFields || []).length === 0 && (
              <TableRow>
                <TableCell colSpan={19} className="px-4 py-8 text-center text-sm text-muted-foreground border">
                  No items added yet. Use the pickers above to add items from a Job Work or Sample.
                </TableCell>
              </TableRow>
            )}
            {watchFields.map((field, index) => {
              const tightInput = "h-8 text-right text-xs border border-input/60 focus-visible:ring-1 bg-white";
              const locked = !!field.has_barcode;
              const lockedInput = locked
                ? "h-8 text-right text-xs border border-input/40 bg-muted/30 cursor-not-allowed"
                : tightInput;
              return (
                <TableRow key={field.id ?? index} className={`hover:bg-muted/20 transition-colors ${locked ? "bg-amber-50/40" : "odd:bg-muted/10"}`}>
                  <TableCell className="px-2 py-1.5 border text-xs">
                    <div className="flex items-center gap-1.5">
                      <span>{field.sl_no}</span>
                      {locked && (
                        <span title="Barcoded — cannot be edited" className="inline-flex items-center text-[10px] font-medium text-amber-700 bg-amber-100 border border-amber-200 rounded px-1 py-0.5 leading-none">🔒 Barcoded</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-[11px] text-muted-foreground">
                    {field._source_label
                      || (field.ref_job_sl_no ? "Job" : (field.ref_sample_issue_item ? "Sample" : "—"))}
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs">{field.item}</TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs">
                    <span className="inline-block px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{field.purity}</span>
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-center">
                    <Controller
                      name={`table.${index}.finish_status`}
                      control={control}
                      render={({ field: ctlField }) => (
                        <Checkbox checked={ctlField.value} onCheckedChange={ctlField.onChange} disabled={locked} />
                      )}
                    />
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs text-right tabular-nums">{field.pcs}</TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" step="0.001" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.gw`, { onChange: () => recalcNw(index) })} />
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" step="0.001" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.nw`)} defaultValue={0.000} />
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs text-right tabular-nums text-muted-foreground bg-muted/20">
                    {(
                      Number(watch(`table.${index}.nw`) || 0)
                      - Number(watch(`table.${index}.supplied_gw`) || 0)
                      - Number(watch(`table.${index}.sample_piece_gw`) || 0)
                    ).toFixed(3)}
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" step="0.001" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.less_gw`, { onChange: e => handlelesswtChange(index) })} />
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" step="0.01" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.loss`, { onChange: e => handlelossChange(index) })} />
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs text-right tabular-nums text-muted-foreground bg-muted/20">
                    {Number(watch(`table.${index}.wastage`) || 0).toFixed(3)}
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs text-right tabular-nums font-medium text-foreground bg-primary/5">
                    {Number(watch(`table.${index}.main_total_wt`) || 0).toFixed(3)}
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" step="0.01" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.tunch_per`, { onChange: e => handletunchChange(index) })} />
                  </TableCell>
                  <TableCell className="px-2 py-1.5 border text-xs text-right tabular-nums text-muted-foreground bg-muted/20">
                    {Number(watch(`table.${index}.fine_wt`) || 0).toFixed(3)}
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.add_field_type`)} />
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.making`)} />
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="number" className={lockedInput} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.rhodium`)} />
                  </TableCell>
                  <TableCell className="px-1 py-1 border">
                    <Input type="text" className={locked ? "h-8 text-xs border border-input/40 bg-muted/30 cursor-not-allowed" : "h-8 text-xs border border-input/60 focus-visible:ring-1 bg-white"} readOnly={locked} disabled={locked}
                      {...register(`table.${index}.remarks`)} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        </div>
        </SectionCard>

        <SectionCard
          title="Stone Detail"
          subtitle="Read-only — populated from the linked job order"
        >
        <div className="overflow-x-auto -mx-2">
        <Table className="w-full text-[12.5px] border-collapse stone-detail-table">
          <TableBody>
            {/* Group header row — stage names with subtle alternating violet bands */}
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={3} className="px-3 py-2.5 border bg-slate-100"></TableCell>
              <TableCell colSpan={3} className="px-3 py-2.5 border text-center text-[11px] font-semibold uppercase tracking-wider bg-[hsl(242_64%_95%)] text-[hsl(242_64%_38%)]">Issued</TableCell>
              <TableCell colSpan={3} className="px-3 py-2.5 border text-center text-[11px] font-semibold uppercase tracking-wider bg-[hsl(242_64%_97.5%)] text-[hsl(242_64%_38%)]">Returned</TableCell>
              <TableCell colSpan={3} className="px-3 py-2.5 border text-center text-[11px] font-semibold uppercase tracking-wider bg-[hsl(242_64%_95%)] text-[hsl(242_64%_38%)]">Broken &amp; Loss</TableCell>
              <TableCell colSpan={3} className="px-3 py-2.5 border text-center text-[11px] font-semibold uppercase tracking-wider bg-[hsl(242_64%_97.5%)] text-[hsl(242_64%_38%)]">Used</TableCell>
              <TableCell colSpan={2} className="px-3 py-2.5 border bg-slate-100"></TableCell>
            </TableRow>

            {/* Sub-header row — Pcs / Ct / Gw with the same alternating bands */}
            <TableRow className="hover:bg-transparent bg-slate-50">
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Sno</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Packet</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Item</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Pcs</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Ct</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Gw</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Pcs</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Ct</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Gw</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Pcs</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Ct</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Gw</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Pcs</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Ct</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Gw</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right">Rate</TableCell>
              <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right">Value</TableCell>
            </TableRow>

            {(() => {
              const stageA = "bg-[hsl(220_30%_97.5%)]";
              const stageB = "bg-[hsl(242_30%_97.5%)]";
              const lossText = "text-[hsl(0_65%_47%)] font-semibold";
              const muted = "text-slate-400";
              const totals = {
                issue_pcs: 0, issue_ct: 0, issue_gw: 0,
                return_pcs: 0, return_ct: 0, return_gw: 0,
                broken_pcs: 0, broken_ct: 0, broken_gw: 0,
                balance_pcs: 0, balance_ct: 0, balance_gw: 0,
                amt: 0,
              };
              let stoneCount = 0;
              const rendered = [];

              fields.forEach((parentField, parentIndex) => {
                if (!parentField.details || parentField.details.length === 0) return;

                const headerGw = Number(watch(`table.${parentIndex}.gw`)) || parentField.gw || 0;
                rendered.push(
                  <TableRow key={`group-${parentField.id ?? parentIndex}`} className="hover:bg-transparent">
                    <TableCell colSpan={17} className="px-4 py-2.5 border-y-2 border-y-[hsl(242_30%_86%)] bg-[hsl(242_40%_96%)] text-[hsl(242_64%_38%)] text-[12.5px]">
                      <span className="text-[11px] uppercase tracking-wider font-semibold mr-2">Received piece #{parentIndex + 1}</span>
                      <span className="font-semibold">{parentField.item || "—"}</span>
                      {parentField.purity ? <span className="mx-1.5 text-slate-400">·</span> : null}
                      {parentField.purity ? <span>{parentField.purity}</span> : null}
                      {headerGw ? <span className="mx-1.5 text-slate-400">·</span> : null}
                      {headerGw ? <span className="tabular-nums">{Number(headerGw).toFixed(3)} g</span> : null}
                    </TableCell>
                  </TableRow>
                );

                parentField.details.forEach((childField, childIndex) => {
                  const numAt = (name) => {
                    const raw = watch(`table.${parentIndex}.details.${childIndex}.${name}`);
                    const num = parseFloat(raw);
                    return Number.isFinite(num) ? num : 0;
                  };
                  const v = (name, dp) => {
                    const raw = watch(`table.${parentIndex}.details.${childIndex}.${name}`);
                    const num = parseFloat(raw);
                    if (!Number.isFinite(num)) return "—";
                    return dp === 0 ? String(Math.round(num)) : num.toFixed(dp);
                  };
                  const issuePcs = numAt("issue_pcs"), issueCt = numAt("issue_ct"), issueGw = numAt("issue_gw");
                  const returnPcs = numAt("return_pcs"), returnCt = numAt("return_ct"), returnGw = numAt("return_gw");
                  const brokenPcs = numAt("broken_pcs"), brokenCt = numAt("broken_ct"), brokenGw = numAt("broken_gw");
                  const balPcs = numAt("balance_pcs"), balCt = numAt("balance_ct"), balGw = numAt("balance_gw");
                  const amtVal = numAt("amt");
                  totals.issue_pcs += issuePcs; totals.issue_ct += issueCt; totals.issue_gw += issueGw;
                  totals.return_pcs += returnPcs; totals.return_ct += returnCt; totals.return_gw += returnGw;
                  totals.broken_pcs += brokenPcs; totals.broken_ct += brokenCt; totals.broken_gw += brokenGw;
                  totals.balance_pcs += balPcs; totals.balance_ct += balCt; totals.balance_gw += balGw;
                  totals.amt += amtVal;
                  stoneCount += 1;

                  const cls = (val, base) => `px-3 py-2.5 border text-right tabular-nums ${base} ${val > 0 ? "" : muted}`;
                  const lossCls = (val, base) => `px-3 py-2.5 border text-right tabular-nums ${base} ${val > 0 ? lossText : muted}`;

                  rendered.push(
                    <TableRow key={childField.id} className="hover:bg-slate-50/60">
                      <TableCell className="px-3 py-2.5 border">{childField.sl_no}</TableCell>
                      <TableCell className="px-3 py-2.5 border">{childField.packet || "—"}</TableCell>
                      <TableCell className="px-3 py-2.5 border">{childField.item || "—"}</TableCell>
                      <TableCell className={cls(issuePcs, stageA)}>{v("issue_pcs", 0)}</TableCell>
                      <TableCell className={cls(issueCt, stageA)}>{v("issue_ct", 3)}</TableCell>
                      <TableCell className={cls(issueGw, stageA)}>{v("issue_gw", 3)}</TableCell>
                      <TableCell className={cls(returnPcs, stageB)}>{v("return_pcs", 0)}</TableCell>
                      <TableCell className={cls(returnCt, stageB)}>{v("return_ct", 3)}</TableCell>
                      <TableCell className={cls(returnGw, stageB)}>{v("return_gw", 3)}</TableCell>
                      <TableCell className={lossCls(brokenPcs, stageA)}>{v("broken_pcs", 0)}</TableCell>
                      <TableCell className={lossCls(brokenCt, stageA)}>{v("broken_ct", 3)}</TableCell>
                      <TableCell className={lossCls(brokenGw, stageA)}>{v("broken_gw", 3)}</TableCell>
                      <TableCell className={cls(balPcs, stageB)}>{v("balance_pcs", 0)}</TableCell>
                      <TableCell className={cls(balCt, stageB)}>{v("balance_ct", 3)}</TableCell>
                      <TableCell className={cls(balGw, stageB)}>{v("balance_gw", 3)}</TableCell>
                      <TableCell className="px-3 py-2.5 border text-right tabular-nums">{v("rate", 2)}</TableCell>
                      <TableCell className="px-3 py-2.5 border text-right tabular-nums font-semibold">{v("amt", 2)}</TableCell>
                    </TableRow>
                  );
                });
              });

              if (stoneCount > 0) {
                const fmt = (n, dp) => (dp === 0 ? String(Math.round(n)) : n.toFixed(dp));
                rendered.push(
                  <TableRow key="stone-totals" className="hover:bg-transparent">
                    <TableCell colSpan={3} className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] font-semibold text-slate-900">Total · {stoneCount} stone{stoneCount === 1 ? "" : "s"}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.issue_pcs, 0)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.issue_ct, 3)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.issue_gw, 3)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.return_pcs, 0)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.return_ct, 3)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.return_gw, 3)}</TableCell>
                    <TableCell className={`px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold ${totals.broken_pcs > 0 ? lossText : ""}`}>{fmt(totals.broken_pcs, 0)}</TableCell>
                    <TableCell className={`px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold ${totals.broken_ct > 0 ? lossText : ""}`}>{fmt(totals.broken_ct, 3)}</TableCell>
                    <TableCell className={`px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold ${totals.broken_gw > 0 ? lossText : ""}`}>{fmt(totals.broken_gw, 3)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.balance_pcs, 0)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.balance_ct, 3)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.balance_gw, 3)}</TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)]"></TableCell>
                    <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold">{fmt(totals.amt, 2)}</TableCell>
                  </TableRow>
                );
              }
              return rendered;
            })()}
          </TableBody>
        </Table>
        </div>
        </SectionCard>

        {(() => {
          const taxable = Number(watch("taxable_value")) || 0;
          const sgst = Number(watch("sgst_per")) || 0;
          const cgst = Number(watch("cgst_per")) || 0;
          const igst = Number(watch("igst_per")) || 0;
          const sgstAmt = (taxable * sgst) / 100;
          const cgstAmt = (taxable * cgst) / 100;
          const igstAmt = (taxable * igst) / 100;
          const total = taxable + sgstAmt + cgstAmt + igstAmt;
          const fmt = (n) => (Number.isFinite(n) ? n.toFixed(2) : "0.00");

          const SummaryRow = ({ label, children }) => (
            <div className="flex items-center justify-between gap-4 py-1.5 border-b border-slate-100 last:border-b-0">
              <Label className="text-sm text-slate-600 mb-0">{label}</Label>
              <div className="w-40">{children}</div>
            </div>
          );

          return (
            <SectionCard title="Bill Summary">
              <div className="flex justify-end">
                <div className="w-full max-w-sm">
                  <SummaryRow label="Taxable Value">
                    <Input
                      type="number"
                      step="0.01"
                      className="h-8 text-right text-sm"
                      {...register("taxable_value")}
                    />
                  </SummaryRow>

                  <SummaryRow label="SGST %">
                    <div className="flex items-center gap-2">
                      <Input type="number" step="0.01" className="h-8 w-20 text-right text-sm"
                        {...register("sgst_per")} />
                      <span className="text-xs text-muted-foreground w-20 text-right tabular-nums">{fmt(sgstAmt)}</span>
                    </div>
                  </SummaryRow>

                  <SummaryRow label="CGST %">
                    <div className="flex items-center gap-2">
                      <Input type="number" step="0.01" className="h-8 w-20 text-right text-sm"
                        {...register("cgst_per")} />
                      <span className="text-xs text-muted-foreground w-20 text-right tabular-nums">{fmt(cgstAmt)}</span>
                    </div>
                  </SummaryRow>

                  <SummaryRow label="IGST %">
                    <div className="flex items-center gap-2">
                      <Input type="number" step="0.01" className="h-8 w-20 text-right text-sm"
                        {...register("igst_per")} />
                      <span className="text-xs text-muted-foreground w-20 text-right tabular-nums">{fmt(igstAmt)}</span>
                    </div>
                  </SummaryRow>

                  <div className="flex items-center justify-between gap-4 pt-3 mt-2 border-t-2 border-border">
                    <Label className="text-sm font-semibold mb-0">Total Amount</Label>
                    <span className="w-40 text-right text-base font-semibold text-primary tabular-nums">{fmt(total)}</span>
                  </div>
                </div>
              </div>
            </SectionCard>
          );
        })()}

        <div className="flex justify-end items-center gap-2 pt-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.history.back()}>Cancel</Button>
          <Button type="submit" size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground" disabled={saving || !canSave}>
            {saving ? (id ? "Updating…" : "Saving…") : (id ? "Update Receive" : "Save Receive")}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default JobWorkReceive;
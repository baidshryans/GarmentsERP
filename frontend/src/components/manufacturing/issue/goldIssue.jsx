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
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, createCustomerOrder } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { createKarigarGoldIssue, fetchGoldIssueForEdit, fetchGoldIssuewithID, FetchKarigarGoldIssueBill, fetchPos, fetchStoneIssuesFilterJobs, updateGoldIssue } from "../../../services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";
import { SquarePen, Trash2 } from "lucide-react";
import { evaluateFormula,renderErrorTree} from "../../../Utils";
import { useWatch } from "react-hook-form";
import { useNavigate } from "react-router-dom";



const GoldIssue = () => {
  const { id } = useParams()
  const { toast } = useToast()
  const defaultTableValues = {
    item: "",
    metal_purity: "",         // from Select (Controller)
    item_gw: "",              // number input
    conv_purity: "",          // from Select (Controller)
    alloy_wt: "",             // text input
    conv_wt: "",              // text input
    remarks: "",              // text input
  };

  const { register, handleSubmit, control, reset, watch, setValue, getValues, setFocus, formState: { isDirty } } = useForm({
    defaultValues: {

      form: {
        date1: new Date().toISOString().split("T")[0],
      },
      table: { ...defaultTableValues }
    },
  });
  const navigate = useNavigate();
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [rs, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [jobSlNos, setJobSlNos] = useState([]); // Initialize jobSlNos as an empty array

  const handleBlur = async (e) => {
    const jobId = e.target.value;
    const { slip_type } = getValues('form');
    const { ref_job_object_id, } = getValues("table");
    const response = await fetchStoneIssuesFilterJobs(ref_job_object_id, slip_type);
    if (response.success) {
      const data = response.data.job_items;
      setJobSlNos(data);
    } else {
      toast({ title: "An error occurred. Please try again later." });
    }

  }

  useEffect(() => {
    async function fetchData() {
      const [customers, salesperson, orderNo, mainItem, purity] = await Promise.all([
        getLedgers(),
        fetchSalesperson(),
        FetchKarigarGoldIssueBill(),
        fetchMainItem({type:"R"}),
        fetchPurity(),
      ]);
      if (customers.success) setCustomers(customers.data.results);
      if (salesperson.success) setSalespersonData(salesperson.data.results);
      if (orderNo.success) setValue("form.billno", orderNo.data.bill_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
    }
    fetchData().then(d => {
      if (id) {


        fetchGoldIssueForEdit(id)
          .then((response) => {
            Object.keys(response.data).forEach((key) => {
              setValue(`form.${key}`, response.data[key]);
            });

            // Set items array
            if (response.data.karigargoldissue_set) {
              setRows(response.data.karigargoldissue_set);
            }
            reset(getValues(), { keepValues: true, keepDirty: false });
            resetTableDirty();
          })
          .catch((error) => {
            console.error('Error fetching manufacturing issue:', error);
          });
      }
    });
  }, []);




  const slip_type = watch("form.slip_type")
  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([
        fetchPos(slip_type),

      ]);
      if (karigars.success) setJobs(karigars.data.results);
    }
    fetchData();
  }, [slip_type]);

  const table = watch('table')

  const statmaintableFormulas = {
    conv_wt: `(metal_purity_gw_per / conv_purity_gw_per) * item_gw`,
    alloy_wt: `((metal_purity_gw_per / conv_purity_gw_per) * item_gw ) - item_gw`,
  };

  const metalPurity = useWatch({ control, name: "table.metal_purity" });
  const convPurity = useWatch({ control, name: "table.conv_purity" });
  const itemGw = useWatch({ control, name: "table.item_gw" });
  useEffect(() => {
    const maintable = getValues('table');
    // Find metal purity and conv purity objects
    const metalPurityObj = purityData.find(p => `${p.purity}` === maintable.metal_purity);
    const convPurityObj = purityData.find(p => `${p.purity}` === maintable.conv_purity);

    // Set gw_per values if found
    setValue("table.metal_purity_gw_per", metalPurityObj ? `${metalPurityObj.gw_per}` : "");
    setValue("table.conv_purity_gw_per", convPurityObj ? `${convPurityObj.gw_per}` : "");
    Object.keys(statmaintableFormulas).forEach((col) => {
      const val = evaluateFormula(statmaintableFormulas[col], maintable);
      setValue(`table.${col}`, val && !isNaN(val) ? val : "0.00");
    })
  }, [table, metalPurity, convPurity, itemGw]);

  const onSubmit = (data) => {
    const dat = rs.map(e => {
      e.job_sl_content_type = slip_type === "Job Order" ? "karigarissueitem" : "purchaseorderitems"
      e.ref_job_content_type = slip_type === "Job Order" ? "karigarissue" : "purchaseorder"
    })
     if (rs.length === 0) {
      toast({ title: "Table is empty " })
      return;
    }
    const da = getValues('form')
    da.karigargoldissue_set = [...rs];
    setSaving(true);
    (!id ? createKarigarGoldIssue(da) : updateGoldIssue(id, da))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });  // Success toast
          setTimeout(() => {
            navigate("/manufacturing/issue/goldissue/")
          }, 2000);
        } else {
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
        toast({ title: "An error occurred. Please try again later." });  // Error toast on catch
      });
  };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    const row = rs[index];
    reset({ form: getValues("form"), table: row });
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };


  const handleKeyDown = (e) => {
    const table = getValues("table");
    const sl_no = rs.length + 1

    const rowVals = {
      sl_no,
      ...table,
    }
    if (e.key === "Tab") {
      setRows([...rs, rowVals])
      markTableDirty();
      setFocus("table.item")

      reset({ form: getValues("form"), table: { ...defaultTableValues } })


    }
  };

  return (
    <div className="mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >

        <hr className="my-3" />

        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
          </FieldContainer>

          <FieldContainer>
            <Label htmlFor="order_no" className="text-nowrap">Bill No</Label>
            <Input type="text" {...register("form.billno")} readOnly disabled />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="salesperson1" className="text-nowrap">Slip Type</Label>
            <Controller
              name="form.slip_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={(e) => {
                  field.onChange(e)

                }} value={field.value}>

                  <SelectTrigger data-testid="slip-type" >
                    <SelectValue placeholder="Select Slip Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem key={1} value="Job Order">Job Order</SelectItem>
                    <SelectItem key={2} value="Purchase Order">Purchase Order</SelectItem>


                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>



        </div>


        {/* Party Details */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Karigar Name</Label>
            <SearchableComboBox
              options={customers}
              value={watch("form.karigar_ldgr_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.karigar_ldgr_name", opt.ac_name)
                setValue("form.karigar_ldgr", opt.id)
              }}
              placeholder="Search karigar�"
            />
            <input type="hidden" {...register("form.karigar_ldgr")} />



          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Job Work Slip No</Label>
            <Input list="job_list"
              onBlur={handleBlur}
              onChange={(e) => {
                const selectedKarigarIssue = jobs.find(
                  (karigar) => karigar.name === e.target.value
                );
                selectedKarigarIssue ? setValue("table.ref_job_object_id", selectedKarigarIssue.id) : e.target.value;

              }} />
            <Input type="hidden" {...register("table.ref_job_object_id")} />
            <datalist id="job_list" >
              {jobs.map((karigar, index) => (
                <option key={index} value={karigar.name}></option>

              ))}

            </datalist>

          </FieldContainer>


          <FieldContainer>
            <Label htmlFor="status">Sl.No</Label>
            <Input list="job_sl_list" onChange={(e) => {
              const selectedJobSl = jobSlNos.find(
                (jobSl) => jobSl.job_sl_no === parseInt(e.target.value)
              );
              console.log(selectedJobSl)
              selectedJobSl ? setValue("table.job_sl_object_id", selectedJobSl.id) : e.target.value;

            }}
            />
            <Input type="number" className="invisible" {...register("table.job_sl_object_id", {

            })} />
            <datalist id="job_sl_list" >
              {jobSlNos.map((jobSl, index) => (
                <option key={index} value={jobSl.job_sl_no}></option>

              ))}

            </datalist>
          </FieldContainer>
        </div>

        {/* Item Details */}

        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-16 px-4 py-2 border">Options</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Item Gw</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Converted Purity</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Alloy Wt</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Converted Gw</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Remarks</TableCell>

            </TableRow>

            <TableRow>
              <TableCell className="w-20 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input list="item_list" {...register("table.item")} />
                <datalist id="item_list">
                  {mainItemData.map((item, index) => (
                    <option key={index} value={item.short_code}  > {item.item_name}</option>
                  ))}

                </datalist>
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Controller
                  name="table.metal_purity"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger data-testid="select-purity">
                        <SelectValue placeholder="Select Purity" />
                      </SelectTrigger>
                      <SelectContent>
                        {purityData.map((item, index) => (
                          <SelectItem key={index} value={`${item.purity}`}  > {item.purity}</SelectItem>
                        ))}


                      </SelectContent>
                    </Select>
                  )}
                />

              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.item_gw")} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Controller
                  name="table.conv_purity"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger data-testid="purity">
                        <SelectValue placeholder="Select Purity" />
                      </SelectTrigger>
                      <SelectContent>
                        {purityData.map((item, index) => (
                          <SelectItem key={index} value={`${item.purity}`}  > {item.purity}</SelectItem>
                        ))}


                      </SelectContent>
                    </Select>
                  )}
                />

              </TableCell>
              
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="text" {...register("table.alloy_wt")} readOnly className="bg-muted cursor-not-allowed" />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="text" {...register("table.conv_wt")} readOnly className="bg-muted cursor-not-allowed" />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register("table.remarks")} />
              </TableCell>
            </TableRow>
            {rs.map((row, index) => (
              <TableRow key={index} className="w-full bg-white">
                <TableCell className="w-24 px-4 py-2 border">
                  <div className="flex gap-4">
                    <SquarePen className="size-4 mr-1 cursor-pointer" onClick={() => handleEdit(index)} />

                    <Trash2 color="#d45959" className="size-4 mr-1 cursor-pointer" onClick={() => handleDelete(index)} />
                  </div>
                </TableCell>
                <TableCell className="w-32 px-4 py-2 border">
                  {row.item}
                </TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.metal_purity}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.item_gw}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.conv_purity}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.alloy_wt}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.conv_wt}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.remarks}</TableCell>

              </TableRow>
            ))}



          </TableBody>
        </Table>


        {/* Submit */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="submit" className="bg-primary hover:bg-primary text-white" disabled={saving || !canSave}>
            {saveLabel(saving)}
          </Button>
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default GoldIssue;

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
import { fetchMainItem, fetchNextStoneBillNo, getStates, fetchPurity, fetchPackets, getLedgers, createKarigarStoneIssue, fetchStoneIssuesFilterJobs, fetchPos } from "@/services/apiService";
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
      table: {
        sgst: 0,
        igst: 0,
        cgst: 0,
        ct: 0,
        gw: 0
      },

    },
  });
  const navigate=useNavigate();

  const [rs, setRows] = useState([]);
  const [statesData, setstatesData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [packets, setPackets] = useState([]);
  const [uom, setUOM] = useState("pcs")
  const [jobSlNos, setJobSlNos] = useState([]); // Initialize jobSlNos as an empty array
  const [stype, setStype] = useState("Job Order");

  const handleBlur = async (e) => {
    const { ref_job_object_id } = getValues("table");
    const { slip_type } = getValues("form");
    const response = await fetchStoneIssuesFilterJobs(ref_job_object_id, slip_type);
    if (response.success) {
      const data = response.data.job_items;
      setJobSlNos(data);
      console.log("job  set")
    } else {
      toast({ title: "An error occurred. Please try again later." });
    }

  }

  useEffect(() => {
    async function fetchData() {
      const [packets, karigars, customers, states, orderNo, mainItem, purity] = await Promise.all([
        fetchPackets(),
        fetchPos("Job Order"),
        getLedgers(),
        getStates(),
        fetchNextStoneBillNo(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (packets.success) setPackets(packets.data);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (states.success) setstatesData(states.data);
      if (orderNo.success) setValue("form.billno", orderNo.data.bill_no);
      if (mainItem.success) setMainItemData(mainItem.data);
      if (purity.success) setPurityData(purity.data);
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

  const slip_type = watch("form.slip_type")
  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([
        fetchPos(slip_type),

      ]);
      if (karigars.success) setKarigars(karigars.data.results);
    }
    fetchData();
  }, [slip_type]);

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
    const dat = rs.map(e => {
      e.job_sl_content_type = slip_type === "Job Order" ? "karigarissueitem" : "purchaseorderitems"
      e.ref_job_content_type = slip_type === "Job Order" ? "karigarissue" : "purchaseorder"
    })

    const formdata = getValues('form')
    formdata.karigarstoneissue_set = rs;

    (id ? updateKarigarStoneIssue(formdata,id) : createKarigarStoneIssue(formdata))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });  // Success toast
          setTimeout(() => {
            navigate("/manufacturing/issue/stoneissue/")
          }, 2000);
        } else if (response.status < 500) {
          toast({
            title: "Form submission failed. Please try again.",
            description: renderErrorTree(response.error),
          });  // Error toast
        } else {
          toast({ title: "Cancel the form" });
        }
      })
      .catch((error) => {
        console.error("Error submitting form:", error);
        toast({ title: "An error occurred. Please try again later." });  // Error toast on catch
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
      const { karigar_ldgr, billno, date1, slip_type,place_of_supply } = getValues();
      console.log(place_of_supply)
      const sl_no = rs.length + 1;
  
  
      const rowVals = {
        sl_no,
        ...table, karigar_ldgr, billno, date1, slip_type,place_of_supply
      }
      e.preventDefault()
      setRows([...rs, rowVals])
      reset({form:{...getValues('form')},table:{...tableDefaultValue}})
      setFocus('table.packet')

    }
  };

  const handlePacketChange = (e) => {
    const selectedValue = e.target.value;
    const selectedPacket = packets.find((packet) => packet.pckt_no === selectedValue);

    if (selectedPacket) {
      setValue('table.item', selectedPacket.stone_item_id.item_name);
      setValue('table.rate', selectedPacket.rate_for_retail || 0);

      setValue('table.sgst_rate', selectedPacket.stone_item_id?.hsn_no?.sgst ?? 0)
      setValue('table.igst_rate', selectedPacket.stone_item_id?.hsn_no?.igst ?? 0)
      setValue('table.cgst_rate', selectedPacket.stone_item_id?.hsn_no?.cgst ?? 0)


      setUOM(selectedPacket.stone_item_id.uom);
      if (selectedPacket.stone_item_id.uom === 'ct') {
        setValue("table.ct", 0);
        setValue("table.gw", 0);
      } else {
        setValue("table.ct", 0);

        setValue("table.gw", 0);

      }
    }
  };

  const handleGWchange = (e) => {
    const { gw, rate } = getValues("table")

    const calculatedValue = gw * rate;
    setValue("table.taxable_value", calculatedValue)
    if (true) {
      const { sgst_rate, cgst_rate } = getValues("table");
      const sgst_val = sgst_rate * calculatedValue / 100
      const cgst_val = cgst_rate * calculatedValue / 100
      const tot = cgst_rate + sgst_rate + calculatedValue
      setValue("table.sgst", sgst_val ?? 0)
      setValue("table.cgst", cgst_val?? 0)
      setValue("table.tot_val", tot ?? 0)
    } else { }
  }
  const handlePCSchange = (e) => { }

  const handleCTchange = (e) => {
    const { ct, rate } = getValues("table")

    const calculatedValue = parseInt(ct) * parseInt(rate);
    setValue("table.taxable_value", calculatedValue)
    if (true) {
      const { sgst_rate, cgst_rate } = getValues("table");
      const sgst_val = parseInt(sgst_rate * calculatedValue / 100)
      const cgst_val = parseInt(cgst_rate * calculatedValue / 100)
      const tot = cgst_val + sgst_val + calculatedValue
      setValue("table.sgst", sgst_val)
      setValue("table.cgst", cgst_val)
      setValue("table.tot_val", tot)
      setValue("table.gw",parseFloat(ct)/5)
      console.log(sgst_val)
      console.log(cgst_val)
      console.log(tot)
    } else { }
  }

  return (
    <div className="container mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >

        <hr className="my-3" />

        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
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

                  <SelectTrigger data-id="slip-type" >
                    <SelectValue placeholder="Select Slip Type  " />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem key={1} value="Job Order">Job Order</SelectItem>
                    <SelectItem key={2} value="Purchase Order">Purchase Order</SelectItem>


                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="order_no" className="text-nowrap">Bill No</Label>
            <Input type="text" {...register("form.billno")} readOnly disabled />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="place_of_supply" className="text-nowrap">Place of Supply</Label>
            <Controller
              name="form.place_of_supply"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger >
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


        </div>


        {/* Party Details */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Karigar Name</Label>
            <Input list="party_list" {...register("form.karigar_ldgr_name",{onChange:(e) => {
                const selectedCustomer = customers.find(
                  (customer) => customer.ac_name === e.target.value
                );
                selectedCustomer ? setValue("form.karigar_ldgr", selectedCustomer.id) : e.target.value;

              }})}
              />
            <Input type="hidden" {...register("form.karigar_ldgr")} />
            <datalist id="party_list" >
              {customers.map((customer, index) => (
                <option key={index} value={customer.ac_name}>{customer.id}</option>

              ))}

            </datalist>



          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Job Work Slip No</Label>
            <Input list="job_list"
              onBlur={handleBlur}
              onChange={(e) => {
                const selectedKarigarIssue = karigars.find(
                  (karigar) => karigar.name === e.target.value
                );
                selectedKarigarIssue ? setValue("table.ref_job_object_id", selectedKarigarIssue.id) : e.target.value;

              }}  />
            <Input type="hidden" {...register("table.ref_job_object_id")} />
            <datalist id="job_list" >
              {karigars.map((karigar, index) => (
                <option key={index} value={karigar.name}></option>

              ))}

            </datalist>

          </FieldContainer>


          <FieldContainer>
            <Label htmlFor="status">Sl.No</Label>
            <Input list="job_sl_list"
              onChange={(e) => {
                const selectedJobSl = jobSlNos.find(
                  (jobSl) => jobSl.job_sl_no === parseInt(e.target.value)
                );
                console.log(selectedJobSl)
                selectedJobSl ? setValue("table.job_sl_object_id", selectedJobSl.id) : e.target.value;

              }} />
            <Input type="number" className="invisible" {...register("table.job_sl_object_id")} />
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
              <TableCell className="w-32 px-4 py-2 border">Option</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Packet</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-16 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Taxable Value</TableCell>
              <TableCell className="w-32 px-4 py-2 border">CGST</TableCell>
              <TableCell className="w-16 px-4 py-2 border">SGST</TableCell>
              <TableCell className="w-16 px-4 py-2 border">IGST</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Total Val</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Remarks</TableCell>

            </TableRow>

            <TableRow>
              <TableCell className="w-24 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input list="item_list" {...register("table.packet", {
                  onChange: handlePacketChange
                })} />
                <datalist id="item_list">
                  {packets.map((item, index) => (
                    <option key={index} value={item.pckt_no}  ></option>
                  ))}

                </datalist>
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="text" {...register("table.item")} />

              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.pcs", {
                  onChange: handlePCSchange
                })} />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.ct", {
                  onChange: handleCTchange
                  , disabled: (uom === "gm")||(uom === "pcs") , readOnly :(uom === "gm")||(uom === "pcs") 
                })} />
              </TableCell>
              <TableCell className="w-24 px-4 py-2 border">
                <Input type="number" {...register("table.gw", {
                  onChange: handleGWchange
                  ,disabled: (uom === "ct"),readOnly: (uom === "ct")
                })} />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="number"  {...register("table.rate") } readOnly />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="number" {...register("table.taxable_value" ,{ valueAsNumber: true })} readOnly />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.cgst",{ valueAsNumber: true })} readOnly />
                <Input type="hidden" {...register("table.cgst_rate")} readOnly />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.sgst",{ valueAsNumber: true })} readOnly />
                <Input type="hidden" {...register("table.sgst_rate")} readOnly />

              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.igst",{ valueAsNumber: true })} readOnly />
                <Input type="hidden" {...register("table.igst_rate")} readOnly />

              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="text" {...register("table.tot_val")} readOnly />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register("table.remarks")} />
              </TableCell>
            </TableRow>

            {rs.map((row, index) => (
              <TableRow key={index} className="w-full bg-white">
                <TableCell className="w-32 px-4 py-2 border">
                  <div className="flex gap-4">
                    <SquarePen size={24} className="mr-1 cursor-pointer" onClick={() => handleEdit(index)} />

                    <Trash2 size={24} color="#d45959" className="mr-1 cursor-pointer" onClick={() => handleDelete(index)} />
                </div>
                </TableCell>
                 <TableCell className="w-16 px-4 py-2 border">{row.packet}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.item}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.pcs}</TableCell>
                <TableCell className="w-24 px-4 py-2 border">{row.ct}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.gw}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.rate}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.taxable_value}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.cgst}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.sgst}</TableCell>

                <TableCell className="w-20 px-4 py-2 border">{row.igst}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.tot_val}</TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.remarks}</TableCell>
              </TableRow>
            ))}



          </TableBody>
        </Table>
        <br></br>
        <br></br>
        <h6 className="text-lg font-semibold text-right pr-52 mb-10">Bill Summary</h6>
        <div className="flex justify-end">
          <div className="grid grid-cols-1 gap-4 w-full max-w-md">
            <div className="grid grid-cols-4 gap-4 mb-4 text-balance">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="advance_amt" className="text-nowrap">Taxable Value</Label>
                  <Input type="number" {...register("taxable_amt")} readOnly />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-balance">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="sgst_per" className="text-nowrap">SGST</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.sgst_per")}
                    readOnly
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-balance">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="cgst_per" className="text-nowrap">CGST</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.cgst_per")}
                    readOnly
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-balance">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="igst_per" className="text-nowrap">IGST</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.igst_per")}
                    readOnly
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-balance">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="advance_amt" className="text-nowrap">Total Amount</Label>
                  <Input type="number" {...register("total_amt")} readOnly />
                </FieldContainer>
              </div>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
          <Button type="submit" className="bg-primary hover:bg-primary text-white">
            Save
          </Button>
        </div>
      </form>
    </div>
  );
};

export default StoneIssue;

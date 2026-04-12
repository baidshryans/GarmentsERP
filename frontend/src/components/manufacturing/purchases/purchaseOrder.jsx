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
import { fetchMainItem, fetchNextStoneBillNo, getStates, fetchPurity, fetchPackets, getLedgers, createKarigarStoneIssue, fetchStoneIssuesFilterJobs, fetchPos, createPurchaseOrder } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchPoNoNext, fetchPurchaseOrderForEdit, updatePurchaseOrderForEdit } from "../../../services/apiService";
import { SquarePen, Trash2 } from "lucide-react";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router";


const PurchaseOrder = () => {
  const { toast } = useToast()
  const {id} = useParams()
  const { register, handleSubmit, control, reset, watch, setValue, getValues,setFocus } = useForm({
    defaultValues: {form:{
      place_of_supply:"WB",
      table: {
        sgst: 0,
        igst: 0,
        cgst: 0,
        ct:0,
        gw:0
      },
      date1: new Date().toISOString().split("T")[0],
    
    }},
  });

  const tableDefaultValue={

    slno:"",
    design_no:"",
    main_item:"",
    purity:"",
    pcs:"",
    approx_wt:"",
    size:"",
    due_date:"",
    remarks:"",

  }

  let navigate = useNavigate();
  const [rs, setRows] = useState([]);
  const [statesData, setstatesData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([])
  const [packets, setPackets] = useState([]);
  const [uom, setUOM] = useState()
  const [jobSlNos, setJobSlNos] = useState([]); // Initialize jobSlNos as an empty array
  const [stype,setStype] = useState("Job Order");

  const handleBlur = async (e) => {
    const jobId = e.target.value;
    const {slip_type} = getValues();
    const {ref_job_object_id} = getValues("@/table");
    const response = await fetchStoneIssuesFilterJobs(ref_job_object_id,slip_type); 
    if(response.success){
      const data = response.data.job_items; 
      setJobSlNos(data); 
    }else{
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
        fetchPoNoNext(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (packets.success) setPackets(packets.data.results);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (states.success) setstatesData(states.data);
      if (orderNo.success) setValue("form.po_no", orderNo.data.billno);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
    }
    fetchData().then(d => {
      if (id) {

        
        fetchPurchaseOrderForEdit(id)
            .then((response) => {
              Object.keys(response.data).forEach((key) => {
                setValue(`form.${key}`, response.data[key]);
              });
      
              // Set items array
              if (response.data.purchaseorderitems_set) {
                setRows(response.data.purchaseorderitems_set);
              }
            })
            .catch((error) => {
              console.error('Error fetching manufacturing issue:', error);
            });
      }
    });
  }, []);

  const slip_type = watch("slip_type")
  useEffect(() => {
    async function fetchData() {
      const [ karigars] = await Promise.all([
        fetchPos(slip_type),
        
      ]);
      if (karigars.success) setKarigars(karigars.data.results);
    }
    fetchData()
  }, [slip_type]);


  const onSubmit = (data) => {
     const dat = getValues('form')
     dat.purchaseorderitems_set = rs; 
     
      if (rs.length === 0) {
       toast({ title: "Table is empty " })
       return;
    }

    (id? updatePurchaseOrderForEdit (dat, id) : createPurchaseOrder(dat))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });  // Success toast

          setTimeout(() => {
            navigate("/purchase/purchaseorder/list/");
          }, 2000);
        } else {
          toast({
            title: "Form submission failed. Please try again.",
            description: renderErrorTree(response.error),
          });  // Error toast
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
    const table= getValues("table");
  

    const sl_no = rs.length + 1;


    const rowVals = {
     
    ...table,
    }

    if (e.key === "Tab") {
      setRows([...rs, rowVals])
       reset({form:{...getValues('form')},table:{...tableDefaultValue}})
      setFocus('table.po_sl_no')

    }
  };



  return (
    <div className=" mt-5">
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
            <Label htmlFor="order_no" className="text-nowrap">Po No</Label>
            <Input type="text" {...register("form.po_no")}  />
          </FieldContainer>
         
          <FieldContainer>
            <Label htmlFor="salesperson1" className="text-nowrap">Po Type</Label>
            <Controller
              name="form.po_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={ (e) =>{
                  field.onChange(e)

                  }} value={field.value}>

                  <SelectTrigger data-testid="slip">
                    <SelectValue placeholder="Select Slip Type  " />
                  </SelectTrigger>
                  <SelectContent>
                  <SelectItem key = {1} value="Customer Order">Customer Order</SelectItem>
                  <SelectItem key = {2} value="Stock">Stock</SelectItem>
                  <SelectItem key = {2} value="Repair">Repair</SelectItem>
                    

                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
          
          <FieldContainer>
            <Label htmlFor="salesperson2" className="text-nowrap">Place of Supply</Label>
            <Controller
              name="form.place_of_supply"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-testid="state" >
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
            <SearchableComboBox
              options={customers}
              value={watch("form.ldgr_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.ldgr_name", opt.ac_name)
                setValue("form.ldgr", opt.id)
              }}
              placeholder="Search vendor / karigar…"
            />
            <input type="hidden" {...register("form.ldgr")} />



          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap"> Order No</Label>
            <Input list="job_list"
              onBlur={handleBlur}
              onChange={(e) => {
                const selectedKarigarIssue = karigars.find(
                  (karigar) => karigar.name === e.target.value
                );
                selectedKarigarIssue ? setValue("table.ref_job_object_id", selectedKarigarIssue.id) : e.target.value;

              }} />
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
        <h6 className="text-lg font-semibold my-3 text-start">Item Detail</h6>
        <Table className="w-full table-fixed border-collapse">
                         <TableBody>
                           <TableRow className=" w-full bg-gray-100">
                             <TableCell className="w-28 px-4 py-2 border">Option</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Sl No</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Design No</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Main Item</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Approx Wt</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Size</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Due Date</TableCell>
                             <TableCell className="w-28 px-4 py-2 border">Remarks</TableCell>
                           </TableRow>
               
                           <TableRow>
                           <TableCell className="w-24 px-4 py-2 border"></TableCell>
                           <TableCell className="w-28 px-4 py-2 border">
                               <Input type="number" {...register("table.po_sl_no")} />
                             </TableCell>
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input type="number" {...register("table.design_code")} />
                             </TableCell>
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input list="item_list" {...register("table.item")} />
                               <datalist id="item_list">
                                 {mainItemData.map((item, index) => (
                                   <option key={index} value={item.short_code}  > {item.item_name}</option>
                                 ))}
               
                               </datalist>
                             </TableCell>
                             <TableCell className="w-28 px-4 py-2 border">
                               <Controller
                                 name="table.purity"
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
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input type="number" {...register("table.pcs")} />
                             </TableCell>
                             
                            
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input type="number" {...register("table.approx_wt")} />
                             </TableCell>
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input type="number" {...register("table.size")} />
                             </TableCell>
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input type="date" {...register("table.due_date")} />
                             </TableCell>
                             <TableCell className="w-28 px-4 py-2 border">
                               <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register("table.remarks")} />
                             </TableCell>
                           </TableRow>
                           {rs.map((row, index) => (
                             <TableRow key={index} className="w-full bg-white">
                               <TableCell className="w-28 px-4 py-2 border">
                                 <div className="flex gap-4">
                                   <SquarePen size={20} className="mr-1 cursor-pointer" onClick={() => handleEdit(index)} />

                                   <Trash2 size={20} color="#d45959" className="mr-1 cursor-pointer" onClick={() => handleDelete(index)} />
                                 </div>
                               </TableCell>
                                <TableCell className="w-20 px-4 py-2 border"> {row.po_sl_no}</TableCell>
                               <TableCell className="w-20 px-4 py-2 border">{row.design_code}</TableCell>
                               <TableCell className="w-16 px-4 py-2 border">{row.item}</TableCell>
                               <TableCell className="w-16 px-4 py-2 border">{row.purity}</TableCell>
                               <TableCell className="w-24 px-4 py-2 border">{row.pcs}</TableCell>
                               <TableCell className="w-32 px-4 py-2 border">{row.approx_wt}</TableCell>
                               <TableCell className="w-16 px-4 py-2 border">{row.size}</TableCell>
                               <TableCell className="w-32 px-4 py-2 border">{row.due_date}</TableCell>

                               <TableCell className="w-32 px-4 py-2 border">{row.remarks}</TableCell>
                             </TableRow>
                           ))}
               
               
               
                         </TableBody>
        </Table>


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

export default PurchaseOrder;

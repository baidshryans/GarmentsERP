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
import { fetchMainItem, fetchStoneReturn, getStates, fetchPurity, getLedgers, fetchStoneIssuesFilterJobs, fetchPos, fetchStoneReceiveBillNo, createKarigarStoneReceive } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import StoneReturnAdd from "./stoneReturnList";
import { fetchKarigarStoneReceiveforEdit, fetchStoneIssued, updateKarigarStoneReceiveforEdit } from "../../../services/apiService";
import { SquarePen, Trash2 } from "lucide-react";
import { renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router-dom";

const StoneReturn = () => {
  const { toast } = useToast()
  const { id } = useParams()
  const { register, handleSubmit, control, reset, watch, setValue, getValues, setFocus } = useForm({
    defaultValues: {
      form: {
        place_of_supply: "WB",
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

  const tableDefaultValue = {
    packet: "",
    item: "",
    pcs: "",
    ct: "",
    gw: "",
    rate: "",
    taxable_value: "",
    cgst: "",
    sgst: "",
    igst: "",
    total_val: "",
    remarks: "",

  };
  
  const navigate=useNavigate();
  const [rs, setRows] = useState([]);
  const [packetData, setPacketData] = useState([]);
  const [statesData, setstatesData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([])
  const [packets, setPackets] = useState([]);
  const [uom, setUOM] = useState()
  const [jobSlNos, setJobSlNos] = useState([]); // Initialize jobSlNos as an empty array
  const [stype, setStype] = useState("Job Order");
  const [maxpcs, setMaxpcs] = useState(0);
  const [maxct, setMaxct] = useState(0);
  const [maxgw, setMaxgw] = useState(0); 522

  const handleBlur = async (e) => {
    const jobId = e.target.value;
    const { slip_type } = getValues('form');
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
    const { slip_type } = getValues('form');
    const { job_sl_object_id, ref_job_object_id } = getValues("table");
    console.log(job_sl_object_id)
    console.log(`Slip type : ${slip_type}`);
    const response = await fetchStoneIssued(ref_job_object_id, job_sl_object_id, slip_type,);
    if (response.success) {
      const data = response.data;
      setPackets(data)
    } else {
      toast({ title: "An error occurred. Please try again later." });
    }

  }

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
      if (states.success) setstatesData(states.data);
      if (orderNo.success) setValue("form.billno", orderNo.data.bill_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
    }
    fetchData().then(d => {
      if (id) {
        fetchKarigarStoneReceiveforEdit(id)
          .then((response) => {
            Object.keys(response.data).forEach((key) => {
              setValue(`form.${key}`, response.data[key]);
            });

            // Set items array
            if (response.data.karigarstonereceive_set) {
              setRows(response.data.karigarstonereceive_set);
            }
          })
          .catch((error) => {
            console.error('Error fetching manufacturing issue:', error);
          });
      }
    });;
  }, []);

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
    da.karigarstonereceive_set = [...rs];
    //  (id ? updateKarigarStoneIssue(formdata,id) : createKarigarStoneIssue(formdata))
    (id ? updateKarigarStoneReceiveforEdit(da, id) : createKarigarStoneReceive(da))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });  // Success toast

          setTimeout(()=>{
            navigate("/manufacturing/receive/stonereturn/");
          },2000);
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
    reset({ form: getValues('form'), table: row });
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };


  const handleKeyDown = (e) => {


    if (e.key === "Tab") {
      const table = getValues("table");


      const totalPcs = (table.return_pcs || 0) + (table.broken_pcs || 0) + (table.loss_pcs || 0);
      const totalCt = (table.return_ct || 0) + (table.broken_ct || 0) + (table.loss_ct || 0);
      const totalGw = (table.return_gw || 0) + (table.broken_gw || 0) + (table.loss_gw || 0);

      if (totalPcs > maxpcs) {
        toast({
          title: `Max pieces exceeded (${maxpcs} pieces)`,
        });
        return;
      }

      if (totalCt > maxct) {
        toast({
          title: `Max carats exceeded (${maxct} ct)`,
        });
        return;
      }

      if (totalGw > maxgw) {
        toast({
          title: `Max weight exceeded (${maxgw} gm)`,
        });
        return;
      }

      const sl_no = rs.length + 1;


      const rowVals = {
        sl_no,
        ...table,
      }
      e.preventDefault()

      setRows([...rs, rowVals])
      reset({ form: { ...getValues('form') }, table: { ...tableDefaultValue } })
      setFocus('table.packet')

    }
  };

  const handlePacketChange = (e) => {
    const selectedValue = e.target.value;
    const selectedPacket = packets.find((packet) => packet.pckt_no === selectedValue);
    setMaxpcs(selectedPacket?.total_receivable_pcs ?? 0)
    setMaxgw(selectedPacket?.total_receivable_gw ?? 0)
    setMaxct(selectedPacket?.total_receivable_ct ?? 0)

    if (selectedPacket) {
      setValue('table.item', selectedPacket.stone_item_id.short_code);
      setValue('table.rate', selectedPacket.rate_for_retail || 0);
      setValue('table.sgst_rate', selectedPacket.stone_item_id?.hsn_no?.sgst ?? 0)
      setValue('table.igst_rate', selectedPacket.stone_item_id?.hsn_no?.igst ?? 0)
      setValue('table.cgst_rate', selectedPacket.stone_item_id?.hsn_no?.cgst ?? 0)


      setUOM(selectedPacket.stone_item_id.uom);
      if (selectedPacket.stone_item_id.uom?.toLowerCase() === 'ct') {
        setValue("table.loss_ct", 0);
        setValue("table.loss_pcs", 0);
        setValue("table.loss_gw", 0);
        setValue("table.return_ct", 0);
        setValue("table.return_pcs", 0);
        setValue("table.return_gw", 0);
        setValue("table.broken_ct", 0);
        setValue("table.broken_gw", 0);
        setValue("table.broken_pcs", 0);
      } else {
        setValue("table.ct", 0);

        setValue("table.gw", 0);

      }
    }
  };

  const handleGWchange = (e) => {
    const { return_gw, broken_gw, loss_gw, rate } = getValues("table")

    const calculatedValue = (parseInt(loss_gw) + parseInt(broken_gw) + parseInt(return_gw)) * parseInt(rate);
    setValue("table.taxable_value", calculatedValue)
    if (true) {
      const { sgst_rate, cgst_rate } = getValues("table");
      const sgst_val = sgst_rate * calculatedValue / 100
      const cgst_val = cgst_rate * calculatedValue / 100
      const tot = cgst_rate + sgst_rate + calculatedValue
      setValue("table.sgst", sgst_val)
      setValue("table.cgst", cgst_val)
      setValue("table.tot_val", tot)
      setValue("table.return_ct", parseFloat(return_gw) * 5)
      setValue("table.broken_ct", parseFloat(broken_gw) * 5)
      setValue("table.loss_ct", parseFloat(loss_gw) * 5)

    } else { }
  }
  const handlePCSchange = (e) => { }
  const handleCTchange = (e) => {
    const { return_ct, broken_ct, loss_ct, rate } = getValues("table")

    const calculatedValue = (parseInt(loss_ct) + parseInt(broken_ct) + parseInt(return_ct)) * parseInt(rate);
    setValue("table.taxable_value", calculatedValue)
    if (true) {
      const { sgst_rate, cgst_rate } = getValues("table");
      const sgst_val = parseInt(sgst_rate * calculatedValue / 100)
      const cgst_val = parseInt(cgst_rate * calculatedValue / 100)
      const tot = cgst_val + sgst_val + calculatedValue
      setValue("table.sgst", sgst_val)
      setValue("table.cgst", cgst_val)
      setValue("table.tot_val", tot)
      setValue("table.return_gw", parseFloat(return_ct) / 5)
      setValue("table.broken_gw", parseFloat(broken_ct) / 5)
      setValue("table.loss_gw", parseFloat(loss_ct) / 5)

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
                  </SelectTrigger >
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
            <Label htmlFor="salesperson2" className="text-nowrap">Place of Supply</Label>
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
            <Input list="party_list" {...register("form.karigar_ldgr_name")}
              onChange={(e) => {
                const selectedCustomer = customers.find(
                  (customer) => customer.ac_name === e.target.value
                );
                selectedCustomer ? setValue("form.karigar_ldgr", selectedCustomer.id) : e.target.value;

              }} required />
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
              onBlur={handleBlur1}
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
              <TableCell className="w-32 px-4 py-2 "></TableCell>
              <TableCell className="w-32 px-4 py-2 "></TableCell>

              <TableCell className="w-24 px-10 py-2 text-nowrap ">Goods Returned Back</TableCell>
              <TableCell className="w-24  px-4 py-2  "></TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>

              <TableCell className="w-24 px-4 py-2 "></TableCell>
              <TableCell className="w-24 px-1 py-2 text-nowrap ">Broken Items</TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>

              <TableCell className="w-24 px-4 py-2 "></TableCell>
              <TableCell className="w-24 scroll-px-px1 py-2 text-nowrap">Loss Items</TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>

              <TableCell className="w-24 px-4 py-2 "></TableCell>
              <TableCell className="w-32 px-4 py-2 "></TableCell>

              <TableCell className="w-32 px-4 py-2 "></TableCell>
              <TableCell className="w-24 px-4 py-2 ">Values</TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>
              <TableCell className="w-24 px-4 py-2 "></TableCell>

            </TableRow>

            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-20 px-4 py-2 border">Option</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Packet</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Item</TableCell>

              <TableCell className="w-24 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-24 px-4 py-2 border">GW</TableCell>

              <TableCell className="w-24 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-24 px-4 py-2 border">GW</TableCell>

              <TableCell className="w-24 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-24 px-4 py-2 border">GW</TableCell>

              <TableCell className="w-24 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Taxable Value</TableCell>
              <TableCell className="w-32 px-4 py-2 border">CGST</TableCell>
              <TableCell className="w-24 px-4 py-2 border">SGST</TableCell>
              <TableCell className="w-24 px-4 py-2 border">IGST</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Total Val</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Remarks</TableCell>

            </TableRow>

            <TableRow>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
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
              <TableCell className="w-28 px-4 py-2 border">
                <Input  {...register("table.item")} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.return_pcs", {
                  valueAsNumber: true,
                  onChange: handlePCSchange
                })} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.return_ct", {
                  valueAsNumber: true,

                  onChange: handleCTchange
                  ,
                })} disabled={(uom?.toLowerCase() === "gm")} readOnly={uom?.toLowerCase() === "gm"} />
              </TableCell>
              <TableCell className="w-24 px-4 py-2 border">
                <Input type="number" {...register("table.return_gw", {
                  valueAsNumber: true,

                  onChange: handleGWchange

                  ,
                })} disabled={uom?.toLowerCase() === "ct"} readOnly={uom?.toLowerCase() === "ct"} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.broken_pcs", {
                  valueAsNumber: true,

                  onChange: handlePCSchange
                })} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.broken_ct", {
                  valueAsNumber: true,

                  onChange: handleCTchange
                  ,
                })} disabled={uom?.toLowerCase() === "gm"} readOnly={uom?.toLowerCase() === "gm"} />
              </TableCell>
              <TableCell className="w-24 px-4 py-2 border">
                <Input type="number" {...register("table.broken_gw", {
                  valueAsNumber: true,

                  onChange: handleGWchange

                })}
                  disabled={(uom?.toLowerCase() === "ct")} readOnly={uom?.toLowerCase() === "ct"}
                />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.loss_pcs", {
                  valueAsNumber: true,

                  onChange: handlePCSchange
                })}

                />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.loss_ct", {
                  valueAsNumber: true,

                  onChange: handleCTchange

                })} disabled={uom?.toLowerCase() === "gm"} readOnly={uom?.toLowerCase() === "gm"} />
              </TableCell>
              <TableCell className="w-24 px-4 py-2 border">
                <Input type="number" {...register("table.loss_gw", {
                  valueAsNumber: true,

                  onChange: handleGWchange


                  ,
                })}
                  disabled={(uom?.toLowerCase() === "ct")} readOnly={uom?.toLowerCase() === "ct"}

                />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="number"  {...register("table.rate",
                  { valueAsNumber: true, }

                )} />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="number" {...register("table.taxable_value", {
                  valueAsNumber: true,

                })} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.cgst", {
                  valueAsNumber: true,

                })} />
                <Input type="hidden" {...register("table.cgst_rate", {
                  valueAsNumber: true,

                })} />
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.sgst", {
                  valueAsNumber: true,

                })} />
                <Input type="hidden" {...register("table.sgst_rate", {
                  valueAsNumber: true,

                })} />

              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="number" {...register("table.igst", {
                  valueAsNumber: true,

                })} />
                <Input type="hidden" {...register("table.igst_rate", {
                  valueAsNumber: true,

                })} />

              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Input type="text" {...register("table.tot_val", {
                  valueAsNumber: true,

                })} />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register("remarks",)} />
              </TableCell>
            </TableRow>

            {rs.map((row, index) => (
              <TableRow key={index} className="w-full bg-white">
                <TableCell className="w-32 px-4 py-2 border">
                  <div className="flex gap-3">
                    <SquarePen size={24} className="mr-1 cursor-pointer" onClick={() => handleEdit(index)} />

                    <Trash2 size={24} color="#d45959" className="mr-1 cursor-pointer" onClick={() => handleDelete(index)} />
                  </div>
                </TableCell>
                 <TableCell className="w-16 px-4 py-2 border"> {row.packet}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.item}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.return_pcs}</TableCell>
                <TableCell className="w-24 px-4 py-2 border">{row.return_ct}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.return_gw}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.broken_pcs}</TableCell>
                <TableCell className="w-24 px-4 py-2 border">{row.broken_ct}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.broken_gw}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.loss_pcs}</TableCell>
                <TableCell className="w-24 px-4 py-2 border">{row.loss_ct}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.loss_gw}</TableCell>
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
        <h6 className="text-lg font-semibold text-right pr-48 mb-10">Bill Summary</h6>
        <div className="flex justify-end">
          <div className="grid grid-cols-1 gap-4 w-full max-w-md">
            <div className="grid grid-cols-4 gap-4 mb-4 text-left">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="advance_amt" className="text-nowrap">Taxable Value</Label>
                  <Input type="number" {...register("advance_amt")} />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-left">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="sgst_per" className="text-nowrap">SGST</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.sgst_per")}
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-left">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="cgst_per" className="text-nowrap">CGST</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.cgst_per")}
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-left">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="igst_per" className="text-nowrap">IGST</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.igst_per")}
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-left">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="advances_amt" className="text-nowrap">Total Amount</Label>
                  <Input type="number" {...register("advances_amt")} />
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

export default StoneReturn;

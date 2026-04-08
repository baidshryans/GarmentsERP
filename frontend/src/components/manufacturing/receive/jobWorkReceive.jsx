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
import { fetchMainItem, fetchOrderItem, fetchReceiveSlipNo, fetchKarigarIssues, fetchPurity, getLedgers, createCustomerOrder, fetchPackets, getStates, fetchStoneIssuesFilterJobs, fetchMainItemDetails, createKarigarReceive, fetchKarigarReceive, fetchKarigarReceivewithID, updateKarigarReceive } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router-dom";


const JobWorkReceive = () => {
  const { id } = useParams()
  const { toast } = useToast()
  const { register, control, handleSubmit, reset, watch, setValue, getValues, trigger } = useForm({
    defaultValues: {
      form: {
        date1: new Date().toISOString().split('T')[0],
        place_of_supply: "WB",
        table: []
      }
    }
  });
  const navigate=useNavigate();
  const [change, setChange] = useState(0);
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

  const { fields, append, remove } = useFieldArray({
    control,
    name: "table",
  });

  const watchFields = watch("table") || [];
function modifyData(data) {
  data.items.forEach(item => {
    // Calculate pending values
    const pending_pcs = item.pcs - (item.details.reduce((sum, detail) => sum + (parseFloat(detail.balance_pcs) || 0), 0));
    const pending_gw = item.nw - (item.details.reduce((sum, detail) => sum + (parseFloat(detail.balance_gw) || 0), 0));

    let newDetail = {
      broken_pcs: 0,
      issue_pcs: 0,
      return_pcs: 0,
      rate: 0,
      item: "GOLD",
      metal_purity: item.purity,
      balance_ct: "0",
      balance_gw: item.nw,
      balance_pcs: 0,
      sl_no: item.sl_no,
      pending_pcs:0,  // Add pending values
      pending_gw:0,    // Add pending values
    };

    item.details.push(newDetail);
  });
  return data;
}

  const handleBlur = async (e) => {
    const { ref_job_no_id } = getValues("form");
    const response = await fetchStoneIssuesFilterJobs(ref_job_no_id, "Job Order");
    if (response.success) {
      const data = response.data.job_items;
      setSerialNos(data);
    } else {
      toast({ title: "An error occurred. Please try again later." });
    }

  }

  const handleBlur1 = async (e) => {

    const { ref_job_no, sl_no } = getValues("form");
    try {
      const data = await fetchMainItemDetails(ref_job_no, sl_no);
      const sl = getValues("table").length + 1
      console.log(sl)
      const stone_details = [...data.data.details]
      data.data.date1 = getValues("form.date1")
      data.data.sl_no = sl
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

      data.data.nw = data.data.gw - data.data.details.reduce((sum, detail) => sum + (parseFloat(detail.balance_gw) || 0), 0) - data.data.sample_issued_items.reduce((sum, detail) => sum + (parseFloat(detail.nw) || 0), 0) // - sample issue 
      


      append(data.data)
      setTimeout(() => {
        handletunchChange(getValues("table").length - 1);
        handlelossChange(getValues("table").length - 1);

      }, 500)

    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }

  useEffect(() => {
    async function fetchData() {
      const [packets, states, karigars, customers, salesperson, orderNo, mainItem, purity] = await Promise.all([
        fetchPackets(),
        getStates(),
        fetchKarigarIssues(),
        getLedgers(),
        getStates(),
        fetchReceiveSlipNo(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (packets.success) setPackets(packets.data.results);
      if (states.success) setstatesData(states.data);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (salesperson.success) setSalespersonData(salesperson.data);
      if (orderNo.success) setValue("form.receive_slip_no", orderNo.data.receive_slip_no);
      if (mainItem.success) setMainItemData(mainItem.data);
      if (purity.success) setPurityData(purity.data);
    }
    fetchData().then((d) => {

      if (id) {

        fetchKarigarReceivewithID(id).then(data => {
          if (data.success) {
            const formData = {
              form: {
              ...data.data,
              table: JSON.parse(JSON.stringify(data.data.items)).map(item => ({
                ...item,
                details: item.details.filter(detail => detail.item !== 'GOLD')
              }))
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
          }
        })
      }


    });

  }, []);

  const onSubmit = (data) => {
    const form_data = getValues("form");
    form_data.items = getValues('table')
    let newData = JSON.parse(JSON.stringify(form_data));
    console.log(modifyData)
    modifyData(newData);

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
                  toast({
                    title: "Form submission failed. Please try again.",
                    description: renderErrorTree(response.error),
                  });  // Error toast
                } 

      })
      .catch((error) => {
        console.error("Error submitting form:", error);
        toast({ title: "An error occurred. Please try again later." });
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

  const handletunchChange = (index) => {
    const value = parseFloat(getValues(`table.${index}.tunch_per`)) * parseFloat(getValues(`table.${index}.nw`)) // tunch% * nw
    console.log(index)
    setValue(`table.${index}.fine_wt`, `${value}`)
  }

  const handlelossChange = (index) => {

    const loss = parseFloat(getValues(`table.${index}.loss`))
    const nw = parseFloat(getValues(`table.${index}.nw`))
    const less = parseFloat(getValues(`table.${index}.less_gw`))

    setValue(`table.${index}.main_total_wt`, `${(nw - less) * (1 + loss)}`)
    setValue(`table.${index}.wastage`, `${(nw - less) * loss}`)
  }

  const handlelesswtChange = (index) => {
    const loss = parseFloat(getValues(`table.${index}.loss`))
    const nw = parseFloat(getValues(`table.${index}.nw`))
    const less = parseFloat(getValues(`table.${index}.less_gw`))

    setValue(`table.${index}.main_total_wt`, `${(nw - less) * (1 + loss)}`)
    setValue(`table.${index}.wastage`, `${(nw - less) * loss}`)
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
    <div className="container mt-5" >
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >

        <hr className="my-3" />

        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="receive_slip_no " className="text-nowrap">Receive Slip No</Label>
            <Input type="text" {...register("form.receive_slip_no")} readOnly disabled />
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
            <Label htmlFor="party_name_display" className="text-nowrap">
              Karigar Name
            </Label>
            {/* Datalist for picking a ledger */}
            <Input
              list="party_list"
              {...register("form.karigar_ldgr_name")}
              onChange={(e) => {
                const selected = customers.find(
                  (cust) => cust.ac_name === e.target.value
                );
                if (selected) {
                  setValue("form.karigar_ldgr", selected.id);
                }
              }}
            // required
            />
            <Input type="hidden" {...register("form.karigar_ldgr")} />
            <datalist id="party_list">
              {customers.map((customer, idx) => (
                <option key={idx} value={customer.ac_name}>
                  {customer.id}
                </option>
              ))}
            </datalist>
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="serial_no_list" className="text-nowrap">Ref Job No</Label>
            <Input type="hidden" {...register("form.ref_job_no_id")} />
            <Input list="ref_no_list"

              {...register("form.ref_job_no", {
                onBlur: handleBlur,
                onChange: (e) => {
                  const selectedSlipNo = e.target.value;

                  // Find the corresponding `serialNo` object from the `karigars` array
                  const selectedKarigar = karigars.find(
                    (serialNo) => serialNo.issue_slip_no === selectedSlipNo
                  );
                  if (selectedKarigar) {
                    setValue("form.ref_job_no_id", selectedKarigar.id); // Update ID
                  }
                }
              })}
            // required
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

              {...register("form.sl_no", {
                onBlur: handleBlur1
              })}
            // required
            />
            <datalist id="serial_no_list" >
              {serialNos.map((serialNo, index) => (
                <option key={index} value={serialNo.job_slip_no}></option>

              ))}

            </datalist>
          </FieldContainer>
        </div>

        {/* Item Details */}
        <h6 className="text-lg font-semibold my-3 text-start">Item Detail</h6>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className="w-full bg-gray-100">
              <TableCell className="w-28 px-4 py-2 border">Sl.No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Finish Status</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Nw</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Less</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Loss(%)</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Karigar Cr wt</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Tunch</TableCell>

              <TableCell className="w-28 px-4 py-2 border">Fine Wt</TableCell>

              <TableCell className="w-28 px-4 py-2 border">Wastage</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Add</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Chg</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rhodium Chg</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Remarks</TableCell>
            </TableRow>
            {watchFields.map((field, index) => (
              <TableRow>
                <TableCell className="w-28 px-4 py-2 border">
                  {/* <Input type="number" {...register(`table.${index}.sl_no`)} /> */}
                  {field.sl_no}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  {/* <Input list="item_list" {...register(`table.${index}.item`)} />
                  <datalist id="item_list">
                    {mainItemData.map((item, index) => (
                      <option key={index} value={item.short_code}>{item.item_name}</option>
                    ))}
                  </datalist> */}
                  {field.item}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  {/* {<Controller
                    name={`table.${index}.purity`}
                    control={control}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select Purity" />
                        </SelectTrigger>
                        <SelectContent>
                          {purityData.map((item, index) => (
                            <SelectItem key={index} value={`${item.purity}`}>{item.purity}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />} */}
                  {field.purity}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Controller
                    name={`table.${index}.finish_status`}
                    control={control}
                    render={({ field }) => (
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    )}
                  />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  {/* <Input type="number" {...register(`table.${index}.pcs`)} /> */}
                  {field.pcs}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`table.${index}.gw`)} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" step="0.01" {...register(`table.${index}.nw`)} defaultValue={0.00} />

                  {/* {field.nw} */}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`table.${index}.less_gw`, { onChange: e => handlelesswtChange(index) })} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" step="0.01" {...register(`table.${index}.loss`, { onChange: e => handlelossChange(index) })} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  {/* <Input type="text" {...register(`table.${index}.main_total_wt`)} /> */}
                  {field.main_total_wt}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="text" {...register(`table.${index}.tunch_per`, { onChange: e => handletunchChange(index) })} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  {/* <Input type="number" {...register(`table.${index}.fine_wt`)} /> */}
                  {field.fine_wt}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`table.${index}.wastage`)} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`table.${index}.add_field_type`)} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`table.${index}.making`)} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`table.${index}.rhodium`)} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="text" {...register(`table.${index}.remarks`)} />
                </TableCell>




              </TableRow>
            ))}

          </TableBody>
        </Table>

        <br></br>
        <h6 className="text-lg font-semibold my-3">Issued Sample Detail</h6>

        <Table className="w-full table-fixed border-collapse">
          <TableBody>


            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Nw</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>


            </TableRow>
            {fields.map((parentField, parentIndex) =>
              parentField.
              sample_issued_items
              .map((childField, childIndex) => (
              <TableRow>

                <TableCell className="w-28 px-4 py-2 border">
                  {childField.item}

                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                {childField.pcs}

                </TableCell>
              
                <TableCell className="w-28 px-4 py-2 border">
                {childField.gw}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                {childField.nw}
                </TableCell>

                <TableCell className="w-28 px-4 py-2 border">
                {childField.rate}
                </TableCell>
                
              </TableRow>)))
            }




          </TableBody>
        </Table>

        <br></br>

        {/* Stone Details*/}
        <h6 className="text-lg font-semibold my-3">Stone Detail</h6>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>

            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-28 px-4 py-2 "></TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>

              <TableCell className="w-28 px-10 py-2   "></TableCell>
              <TableCell className="w-28 px-4 py-2 text-nowrap">Goods Issued</TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>

              <TableCell className="w-28 px-4 py-2  "></TableCell>
              <TableCell className="w-28 px-1 py-2 text-nowrap">Goods Returned</TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>

              <TableCell className="w-28 px-4 py-2  "></TableCell>
              <TableCell className="w-28 px-0 py-2 text-nowrap">Broken and Loss Items</TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>

              <TableCell className="w-28 px-4 py-2  "></TableCell>
              <TableCell className="w-28 px-0  py-2 text-nowrap">Items used in Jewellery</TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>

              <TableCell className="w-28 px-4 py-2 "></TableCell>
              <TableCell className="w-28 px-4 py-2 "></TableCell>



            </TableRow>

            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-28 px-4 py-2 border">Sno</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Packet</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              {/* issue */}
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>
              {/* ?returne */}
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>

              {/* broken */}
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>

              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>


              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Value</TableCell>
            </TableRow>

            <TableRow >
              <TableCell>
                <Input
                  type="text"
                  {...register(
                    `details.sl_no`,

                  )}
                  placeholder="Serial No"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="text"
                  {...register(
                    `details.packet`
                  )}
                  placeholder="Pckt No"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="text"
                  {...register(
                    `details.item`
                  )}
                  placeholder="Item Name"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.issue_pcs`

                  )}
                  placeholder="Issue Pcs"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="0.01"

                  {...register(
                    `details.issue_ct`
                  )}
                  placeholder="Issue Ct"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"

                  step="0.01"
                  {...register(
                    `details.issue_gw`,
                    { valueAsNumber: true, }
                  )}
                  placeholder="Issue Gw"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.return_pcs`
                  )}
                  placeholder="Broken Pcs"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="0.01"

                  {...register(
                    `details.return_ct`
                  )}
                  placeholder="Broken Ct"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="0.01"

                  {...register(
                    `details.return_gw`, { valueAsNumber: true, }
                  )}
                  placeholder="Broken Gw"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.broken_pcs`
                  )}
                  placeholder="Return Pcs"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.broken_ct`
                  )}
                  placeholder="Return Ct"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.broken_gw`, { valueAsNumber: true, }
                  )}
                  placeholder="Return Gw"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.balance_pcs`
                  )}
                  placeholder="Balance Pcs"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.balance_ct`
                  )}
                  placeholder="Balance Ct"
                />
              </TableCell>
              <TableCell>
                <Input
                step='any'

                  {...register(
                    `details.balance_gw`, { valueAsNumber: true, }
                  )}
                  placeholder="Balance Gw"
                />
              </TableCell>


              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.rate`
                  )}
                  placeholder="Rate"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  {...register(
                    `details.amt`
                  )}

                  onKeyDown={handleKeyDown}
                  placeholder="Amount"
                />
              </TableCell>
            </TableRow>
        
            {fields.map((parentField, parentIndex) =>
              parentField.details.map((childField, childIndex) => (
                <TableRow key={childField.id}>
                  <TableCell>
                    <Input
                      type="text"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.sl_no`,

                      )}
                      placeholder="Serial No"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="text"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.packet`
                      )}
                      placeholder="Pckt No"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="text"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.item`
                      )}
                      placeholder="Item Name"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.issue_pcs`

                      )}
                      placeholder="Issue Pcs"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      step="0.01"

                      {...register(
                        `table.${parentIndex}.details.${childIndex}.issue_ct`
                      )}
                      placeholder="Issue Ct"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"

                      step="0.01"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.issue_gw`,
                        { valueAsNumber: true, }
                      )}
                      placeholder="Issue Gw"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.return_pcs`
                      )}
                      placeholder="Broken Pcs"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      step="0.01"

                      {...register(
                        `table.${parentIndex}.details.${childIndex}.return_ct`
                      )}
                      placeholder="Broken Ct"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      step="0.01"

                      {...register(
                        `table.${parentIndex}.details.${childIndex}.return_gw`, { valueAsNumber: true, }
                      )}
                      placeholder="Broken Gw"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.broken_pcs`
                      )}
                      placeholder="Return Pcs"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.broken_ct`
                      )}
                      placeholder="Return Ct"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.broken_gw`, { valueAsNumber: true, }
                      )}
                      placeholder="Return Gw"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.balance_pcs`
                      )}
                      placeholder="Balance Pcs"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.balance_ct`
                      )}
                      placeholder="Balance Ct"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      step='any'
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.balance_gw`, { valueAsNumber: true, }
                      )}
                      placeholder="Balance Gw"
                    />
                  </TableCell>


                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.rate`
                      )}
                      placeholder="Rate"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      {...register(
                        `table.${parentIndex}.details.${childIndex}.amt`
                      )}
                      placeholder="Amount"
                    />
                  </TableCell>
                </TableRow>
              )))}
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
                    {...register("sgst_per")}
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
                    {...register("cgst_per")}
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
                    {...register("igst_per")}
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4 mb-4 text-left">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="advance_amt" className="text-nowrap">Total Amount</Label>
                  <Input type="number" {...register("advance_amt")} />
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

export default JobWorkReceive;
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
import { fetchMainItem, fetchSlipNoNext, fetchSalesperson, fetchPurity, getLedgers, createKarigarIssue, fetchCustomerOrders, fetchSlNosOrders, fetchOrderItem, fetchPos, } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils.jsx"
import { useNavigate } from "react-router-dom";
import { convertBarcode, fetchBarcodes, fetchKarigarIssueForEdit, fetchUnBarcodedList, updateKarigarIssue } from "../../../services/apiService";

import { default as MulSelect } from "react-select";
import { SquarePen, Trash2 } from "lucide-react";
import { selectRowsFn } from "@tanstack/react-table";
import { renderErrorTree } from "../../../Utils";


const KarigarIssue = () => {
  const { id } = useParams();
  const { toast } = useToast()
  const { register, handleSubmit, control, reset, watch, setValue, getValues , setFocus} = useForm({
    defaultValues: {
      form: {
        issue_slip_type: 'Stock',
        date1: new Date().toISOString().split("T")[0],
        issued_sample_items:[],
      }

    },
  });
  const [karigars, setKarigars] = useState([]);
  const [rs, setRows] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customerOrders, setCustomerOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [serialNos, setSerialNos] = useState([]);
  const [change, setChange] = useState('')
  const [unbarcodedList , setUnbarcodedList] = useState([]);
  const [barCodes, setBarcodes] = useState([]);
  const navigate = useNavigate();

  const tableDefaultValue = {
    design_code: "",
    item: "",
    purity: "", // or a default purity value like "916" if needed
    issued_sample_items: [], // since this is a multi-select
    pcs: "", // or 0 if you prefer numeric defaults
    approx_wt: "", // or 0
    size: "",
    due_date: "", // in "YYYY-MM-DD" format if a default is needed
    remarks: "",
  }

  useEffect(() => {
    async function fetchData() {
      const [customers, orderNo, mainItem, purity, customerOrders, karigars, unb,barcodes] = await Promise.all([
        getLedgers(),
        fetchSlipNoNext(),
        fetchMainItem(),
        fetchPurity(),
        fetchCustomerOrders(),
        fetchPos("Job Order"),
        fetchUnBarcodedList(),
        fetchBarcodes (),
      ]);
      if (customers.success) setCustomers(customers.data.results);
      if (orderNo.success) setValue("form.issue_slip_no", orderNo.data.next_slip_no);
      if (mainItem.success) setMainItemData(mainItem.data);
      if (purity.success) setPurityData(purity.data);
      if (customerOrders.success) setCustomerOrders(customerOrders.data.results);
      if (karigars.success) setKarigars(karigars.data.results);
      if (unb.success) setUnbarcodedList(transformData(unb.data.results,'label'));
      if (barcodes.success) setBarcodes(barcodes.data.results);
      
      
    }
    fetchData();

    if (id) {
      fetchKarigarIssueForEdit(id)
        .then((response) => {
          Object.keys(response.data).forEach((key) => {
            setValue(`form.${key}`, response.data[key]);
          });

          // Set items array
          if (response.data.items) {
            setRows(response.data.items);
          }
        })
        .catch((error) => {
          console.error('Error fetching manufacturing issue:', error);
        });
    }


  }, []);

  const slip_type = watch("form.issue_slip_type")
  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([
        fetchPos(slip_type),

      ]);
      if (karigars.success) setKarigars(karigars.data.results);
    }
    fetchData();
  }, [slip_type]);

  const onSubmit = (formdata) => {
    const data = getValues("form")
    console.log(data);
    data.items = rs;
    if (rs.length === 0) {
      toast({ title: "Table is empty " })
      return;
    }


    (!id ? createKarigarIssue(data) : updateKarigarIssue(id, data))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });
          setTimeout(() => {
            navigate("/manufacturing/issue/jobwork")
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
        toast({ title: "An error occurred. Please try again later." });
      });
  };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    const row = rs[index];
    reset({ form: getValues('form'), table: row });
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

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
      const data = await fetchOrderItem(customer_order_id, sl_no);
      console.log(data)
      Object.keys(data.data.item_data).forEach((key) => {
        setValue(`table.${key}`, data.data.item_data[key]);
      });

    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

function transformData(jsonData, labelKey) {
    return jsonData.map(item => ({
        value: item.id,
        label: item[labelKey] || "N/A"  // Fallback to "N/A" if the labelKey doesn't exist
    }));
}

  const handleKeyDown = (e) => {


    if (e.key === "Tab") {
      e.preventDefault()
      const table = getValues("table");
      const issue_sl_no = rs.length + 1
      console.log(table.issued_sample_items)

      table.issued_sample_items = table.issued_sample_items?.map(e=>e.value) ?? []
      console.log(table.issued_sample_items)
      const rowVals = {
        issue_sl_no,
        ...table,
      }
      setRows([...rs, rowVals])
      reset({form:{...getValues('form')},table:{...tableDefaultValue}})
      setFocus('table.design_code')
      


    }
  };

  return (
    <div className="mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >
        <h6 className="text-lg font-semibold">Karigar Issue</h6>
        <hr className="my-3" />

        <div className="grid grid-cols-3 gap-12 mb-4">
        <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Barcode </Label>
            

            <Input list="barcode_list" type="text" {...register("table.barcode")}/>
                <datalist id="barcode_list">
                  {barCodes.map((itm, idx) => (
                    <option key={idx} value={itm.barcode}>
                      {itm.barcode}
                    </option>
                  ))}
                </datalist>
            
          </FieldContainer>
          <FieldContainer>
            <Button onClick={async (e) => {
              e.preventDefault()
              const barcode = getValues("table.barcode");
              try {
                const response = await convertBarcode(barcode);
                if (response.success) {
                  window.location.reload()
                }
              } catch (error) {
                console.error("Error fetching barcode data:", error);
              }
            }}>
              Convert to unbarcoded
            </Button>
            
          </FieldContainer>

        </div>
        <div className="grid grid-cols-3 gap-12 mb-4">
          <FieldContainer><Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required /></FieldContainer>
          <FieldContainer>
            <Label htmlFor="issue_slip_no" className="text-nowrap">Slip No</Label>
            <Input type="text" {...register("form.issue_slip_no")} readOnly disabled />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="salesperson1" className="text-nowrap">Slip Type</Label>
            <Controller
              name="form.issue_slip_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-id="slip-type">
                    <SelectValue placeholder="Select Slip type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem key={0} value={`Customer Order`}>Customer Order</SelectItem>
                    <SelectItem key={1} value={`Stock`}>Stock</SelectItem>
                    <SelectItem key={2} value={`Repair`}>Repair</SelectItem>

                  </SelectContent>
                </Select>
              )}
            />

          </FieldContainer>


        </div>


        {/* Party Details */}
        <div className="grid grid-cols-3 gap-12 mb-4">
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Karigar Name </Label>
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
            <Label htmlFor="party_name_display" className="text-nowrap">Order No</Label>
            <Input list="customer_order_list"
              onBlur={handleBlur}
              onChange={(e) => {
                const selectedCustomerOrder = customerOrders.find(
                  (customerOrder) => customerOrder.order_no === e.target.value
                );
                selectedCustomerOrder ? setValue("customer_order_id", selectedCustomerOrder.id) : e.target.value;

              }} disabled={slip_type === 'Stock'} readOnly={slip_type === 'Stock'} />
            <Input type="hidden" {...register("form.ldgr_code")} />
            <datalist id="customer_order_list" >
              {customerOrders.map((customerOrders, index) => (
                <option key={index} value={customerOrders.order_no}></option>

              ))}

            </datalist>
          </FieldContainer>


          <FieldContainer>
            <Label htmlFor="serial_no_list" className="text-nowrap">Sl No</Label>
            <Input list="serial_no_list"

              {...register("sl_no", {
                onBlur: handleBlur1
              })}
              disabled={getValues("form.issue_slip_type") === 'Stock'} readOnly={getValues("form.issue_slip_type") === 'Stock'} />
            <Input type="hidden" {...register("customer_order_item")} />
            <datalist id="serial_no_list" >
              {serialNos.map((serialNo, index) => (
                <option key={index} value={serialNo.sl_no}></option>

              ))}

            </datalist>
          </FieldContainer>
        </div>

        {/* Item Details */}
        <h6 className="text-lg font-semibold my-3">Order Item Detail</h6>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-20 px-4 py-2 border">Option</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Design No</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Main Item</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Sample Issue</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>

              <TableCell className="w-32 px-4 py-2 border">Approx wt</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Size</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Due Date</TableCell>

              <TableCell className="w-32 px-4 py-2 border">Remarks</TableCell>
            </TableRow>

            <TableRow>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="text" {...register("table.design_code")} />
              </TableCell>
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
                  name="table.purity"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger data-id="purity">
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
              <TableCell className="w-32 px-4 py-2 border">
                <Controller
                  name="table.issued_sample_items"
                  control={control}
                  render={({ field }) => (
                    <MulSelect
                      {...field}
                      isMulti
                      options={unbarcodedList}
                      onChange={(selectedOption) => {
                        
                        field.onChange(selectedOption )}
                        
                      }
                    />
                  )}
                />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.pcs")} />
              </TableCell>


              <TableCell className="w-32 px-4 py-2 border">
                <Input type="number" {...register("table.approx_wt")} />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="text" {...register("table.size")} />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="date" {...register("table.due_date")} />
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
                <TableCell className="w-32 px-4 py-2 border"> {row.design_code}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">
                  {row.item}
                </TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.purity}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.issued_sample_items.map(e => `${e} ,`)}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.pcs}</TableCell>
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

export default KarigarIssue;

import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, createCustomerOrder } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { fetchCustomerOrderForEdit, getGoldRate, updateCustomerOrderForEdit } from "./services/apiService";
import { SquarePen, Search, Trash2 } from "lucide-react";
import { arrayToObject } from "./Utils";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "./Utils";

const CustomerOrderForm = () => {
  const defaultTableValues = {
      item_id: "",
      purity: "",
      pcs: 0,
      gw: 0,
      making: "",
      making_type: "",
      other_chg: 0,
      size: "",
      remarks: ""
  };
  const { toast } = useToast()
  const {id} = useParams()
  const { register, setFocus,handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {
      form:{
        rate_18kt: 0,
        rate_22kt: 0,
        rate_24kt: 0,
        // advance_amt is derived from linked RCPT vouchers (backend property)
        est_amount
          :
          0,
        date1: new Date().toISOString().split("T")[0],
        fix_gold_rate: false,
        gold_rate_date:null,
        salesman_1: null,
        salesman_2: null,
        nature:"new_booking",
        delivery_status: "pending",
        actual_delivery_date: null,
      },
      table:{...defaultTableValues}

    },
  });
  const navigate = useNavigate();
  const [rs, setRows] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);

  const party_name = watch("form.ldgr_code_name")
  const gold_rate_date = watch("form.gold_rate_date")
  
  useEffect(() => {
    async function fetchData() {
      const [customers] = await Promise.all([
        getLedgers({ type: "CO" ,search:party_name}),
      ]);
      if (customers.success) setCustomers(customers.data.results);
    }
    console.log('runs')
    fetchData();
  
  }, [party_name]);

  useEffect(() => {
    async function fetchGoldRates() {
      try {
        console.log("runnin")
        const response = await getGoldRate(gold_rate_date);
        const data = response;
        if (data.success) {
          const dict = arrayToObject(data.data, 'purity_name', 'rate')
          console.log(dict)

            setValue("form.rate_18kt", dict['18'] ?? 0);
            setValue("form.rate_22kt", dict['22'] ?? 0);
            setValue("form.rate_24kt", dict['24'] ?? 0);
          
        }
      } catch (error) {
        console.error("Error fetching gold rates:", error);
      }
    }
    console.log(gold_rate_date)
    if (gold_rate_date) {
      fetchGoldRates();
    }
  }, [gold_rate_date]);

  useEffect(() => {
    async function fetchData() {
      const [customers, salesperson, orderNo, mainItem, purity] = await Promise.all([
        getLedgers({ type: "CO" }),
        fetchSalesperson(),
        fetchOrderNoNext(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (customers.success) setCustomers(Array.isArray(customers.data.results) ? customers.data.results : (Array.isArray(customers.data) ? customers.data : []));
      if (salesperson.success) setSalespersonData(Array.isArray(salesperson.data) ? salesperson.data : (Array.isArray(salesperson.data?.results) ? salesperson.data.results : []));
      if (orderNo.success) setValue("form.order_no", orderNo.data.order_no);
      if (mainItem.success) setMainItemData(Array.isArray(mainItem.data) ? mainItem.data : (Array.isArray(mainItem.data?.results) ? mainItem.data.results : []));
      if (purity.success) setPurityData(Array.isArray(purity.data) ? purity.data : (Array.isArray(purity.data?.results) ? purity.data.results : []));
    }
    fetchData().then(d =>{
                if(id){
          
                fetchCustomerOrderForEdit(id).then(data => {
                  if(data.success){
                    Object.entries(data.data).forEach(([key, value]) => {
                      if (key !== 'items') {
                        setValue(`form.${key}`, value);
                      }
                    })
                    };
                    setRows(JSON.parse(JSON.stringify(data.data.items)))
                    
                  })
                
                }
    });
  }, []);

  const onSubmit = (da) => {

    const data = getValues("form")

    // advance_amt is now a computed backend property — never send it as part
    // of the order payload. It is derived from linked Receipt Vouchers.
    delete data.advance_amt;
    delete data.advance_reconciled;
    delete data.advance_available;

    data.items = [...rs];

    if(rs.length===0){
      toast({title: "Table is empty"})
      return;
    }


    (id ? updateCustomerOrderForEdit(data,id): createCustomerOrder(data))
      .then((response) => {

        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          });  // Success toast

          setTimeout(() => {
            navigate("/sales/customerorder/list/");
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

  const handleEdit = (index) => {
    const row = rs[index];
    reset({form:getValues('form'),table:row});
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const fix_gold_rate = watch("form.fix_gold_rate")

  const handleKeyDown = (e) => {
    const row = getValues("table");
    const sl_no = rs.length + 1
    const iss_status = false;
    const rec_status = false;
    const del_status = false;
    const sale_status = false;
    const rowVals = {
      sl_no,
      ...row
    }
    if (e.key === "Tab") {
      e.preventDefault()
      setRows([...rs, rowVals])
      reset({form:getValues('form'),table:defaultTableValues})
      setFocus("table.item_id")

    }
  };

  return (
    <div className="mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >
        <h6 className="text-lg font-semibold">Add Customer Order</h6>
        <hr className="my-3" />

        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-7 gap-4 mb-4">
          <div>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
          </div>
          <div>
            <Label htmlFor="order_no">Order No</Label>
            <Input type="text" {...register("form.order_no")} readOnly disabled />
          </div>
          <div className="flex items-center">
            <Checkbox id="fix_rate" checked={fix_gold_rate}
              onCheckedChange={(checked) => setValue("form.fix_gold_rate", checked)}
            />
            <Label htmlFor="fix_rate" className="ml-2">
              Fixed Gold Rate
            </Label>
          </div>
          <div>
            <Label htmlFor="fix_date">Gold Rate Date</Label>
            <Input type="date" {...register("form.gold_rate_date")}  />
          </div>

          <div>
            <Label htmlFor="rate_18kt">18K Rate</Label>
            <Input type="number" {...register("form.rate_18kt", {
              valueAsNumber: true,
            })} />
          </div>
          <div>
            <Label htmlFor="rate_22kt">22K Rate</Label>
            <Input type="number" {...register("form.rate_22kt", {
              valueAsNumber: true,
            })} />
          </div>
          <div>
            <Label htmlFor="rate_24kt">24K Rate</Label>
            <Input type="number" {...register("form.rate_24kt", {

              valueAsNumber: true, // Converts input to a number
            })} />
          </div>
        </div>


        {/* Party Details */}
        <div className="grid grid-cols-6 gap-4 mb-4">
          <div>
            <Label htmlFor="party_name_display">Party Name</Label>
            <Input list="party_list" {...register("form.ldgr_code_name",{onChange : (e) => {
                const selectedCustomer = customers.find(
                  (customer) => customer.ac_name === e.target.value
                );
                selectedCustomer ? setValue("form.ldgr", selectedCustomer.id) : e.target.value;

                }})}
             required className="self-end" />
              <Input type="hidden" {...register("form.ldgr")} />
              <datalist id="party_list" >
                {(Array.isArray(customers) ? customers : []).map((customer, index) => (
                <option key={index} value={customer.ac_name}>{customer.mobile1}</option>

                ))}

              </datalist>
              </div>
              <div className="self-end">
              <Link to="/crm/ledger/add/" ><Button>New</Button>  </Link>

              </div>
              <div>
              <Label htmlFor="salesperson1">Salesperson 1</Label>
              <Controller
                name="form.salesman_1"
                control={control}
                render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-id="saleperson-1">
                  <SelectValue placeholder="Select Sales" />
                  </SelectTrigger>
                  <SelectContent>
                  {(Array.isArray(salespersonData) ? salespersonData : []).map((sp, index) => (
                    <SelectItem key={index} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>
                  ))}

                  </SelectContent>
                </Select>
                )}
              />

              </div>
              <div>
              <Label htmlFor="salesperson2">Salesperson 2</Label>
              <Controller
                name="form.salesman_2"
                control={control}
                render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-id="saleperson-2">
                  <SelectValue placeholder="Select Sales" />
                  </SelectTrigger>

                  <SelectContent>
                  {salespersonData.map((sp, index) => (
                    <SelectItem key={`sp2-${index}`} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>
                  ))}

                  </SelectContent>
                </Select>
                )}
              />

              </div>
              <div>
              <Label htmlFor="advance_amt">Advance (from receipts)</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  value={watch("form.advance_amt") || 0}
                  readOnly
                  disabled
                  className="bg-gray-50"
                />
                {id && watch("form.ldgr") && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const ldgrId = watch("form.ldgr");
                      const ldgrName = watch("form.ldgr_code_name") || "";
                      const orderNo = watch("form.order_no") || "";
                      const qs = new URLSearchParams({
                        customer_order: String(id),
                        order_no: orderNo,
                        ldgr: String(ldgrId),
                        ldgr_name: ldgrName,
                      }).toString();
                      window.open(`/accounting/AddJournal/RCPT/add?${qs}`, "_blank");
                    }}
                  >
                    + Receipt
                  </Button>
                )}
              </div>
              {id && (
                <p className="text-[10px] text-muted-foreground mt-1">
                  Advance is the sum of linked receipt vouchers — click <strong>+ Receipt</strong> to record one.
                </p>
              )}
              </div>
              <div>
              <Label htmlFor="est_amount">Estimated Amount</Label>
              <Input type="number" {...register("form.est_amount")} />
              </div>
              <div>
              <Label htmlFor="delivery_date">Estimated Delivery date</Label>
              <Input type="date" {...register("form.delivery_date")} required />
              </div>
              <div>
              <Label htmlFor="nature">Nature</Label>
              <Controller
                name="form.nature"
                control={control}
                render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-id="select-sales">
                  <SelectValue placeholder="Select Sales" />
                  </SelectTrigger>

                  <SelectContent>
                  <SelectItem key="new_booking" value="new_booking">{`New Booking`}</SelectItem>
                  <SelectItem key="repair" value="repair">{`Repair`}</SelectItem>
                  <SelectItem key="sample" value="sample">{`Sample`}</SelectItem>
                  <SelectItem key="to_be_altered" value="to_be_altered">{`To be altered`}</SelectItem>
                  <SelectItem key="valuation" value="valuation">{`Valuation`}</SelectItem>
                  <SelectItem key="melting" value="melting">{`Melting`}</SelectItem>

                  </SelectContent>
                </Select>
                )}
              />

              {/* <Input type="text" {...register("nature")} /> */}
          </div>
          <div>
            <Label htmlFor="status">Billing Status</Label>
            <Input type="text" {...register("form.status")} />
          </div>
          <div>
            <Label htmlFor="delivery_status">Delivery Status</Label>
            <Controller
              name="form.delivery_status"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value || 'pending'}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="ready">Ready for Delivery</SelectItem>
                    <SelectItem value="delivered">Delivered</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div>
            <Label htmlFor="actual_delivery_date">Actual Delivery Date</Label>
            <Input type="date" {...register("form.actual_delivery_date")} />
          </div>
        </div>

        {/* Item Details */}
        <h6 className="text-lg font-semibold my-3">Item Detail</h6>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-32 px-4 py-2 border">OPtions</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Main Item</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-16 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-24 px-4 py-2 border">Making</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Making Type</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Other Charges</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Size</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Remarks</TableCell>
            </TableRow>

            <TableRow>
            <TableCell className="w-32 px-4 py-2 border">
                
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Input list="item_list" {...register("table.item_id")} />
                <datalist id="item_list">
                  {mainItemData && Array.isArray(mainItemData) ? mainItemData.map((item, index) => (
                    <option key={index} value={item.short_code}  > {item.item_name}</option>
                  )) : null}

                </datalist>
              </TableCell>
              <TableCell className="w-20 px-4 py-2 border">
                <Controller
                  name="table.purity"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value || ""}>
                      <SelectTrigger data-id="pty">
                        <SelectValue placeholder="Select Purity" />
                      </SelectTrigger>
                      <SelectContent>
                        {(Array.isArray(purityData) ? purityData : []).map((item, index) => (
                          <SelectItem key={index} value={`${item.purity}`}> {item.purity}</SelectItem>
                        ))}


                      </SelectContent>
                    </Select>
                  )}
                />

              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.pcs")} />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="number" {...register("table.gw")} />
              </TableCell>
              <TableCell className="w-24 px-4 py-2 border">
                <Input type="number" {...register("table.making_amt")} />
              </TableCell>
              <TableCell className="w-32 px-4 py-2 border">
                <Controller
                  name="table.making_type"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value || ""}>
                      <SelectTrigger data-id="making">
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
              <TableCell className="w-32 px-4 py-2 border">
                <Input type="number" {...register("table.other_chg",{valueAsNumber:true})} />
              </TableCell>
              <TableCell className="w-16 px-4 py-2 border">
                <Input type="text" {...register("table.size")} />
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
                <TableCell className="w-32 px-4 py-2 border">
                  {row.item_id}

                </TableCell>

                  

                <TableCell className="w-20 px-4 py-2 border">{row.purity}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.pcs}</TableCell>

                <TableCell className="w-16 px-4 py-2 border">{row.gw}</TableCell>
                <TableCell className="w-24 px-4 py-2 border">{row.making_amt}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.making_type}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.other_chg}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.size}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.remarks}</TableCell>
              </TableRow>
            ))}



          </TableBody>
        </Table>


        {/* Submit */}
        <div className="flex justify-center mt-5">
          <Button type="submit" className="mr-4">
            Save
          </Button>
          <Button variant="outline">Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default CustomerOrderForm;

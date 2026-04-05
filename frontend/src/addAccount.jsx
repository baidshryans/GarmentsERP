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
import { Link } from "react-router-dom";
import { FieldContainer } from "@/Utils";

const AddAccount = () => {
  const { toast } = useToast()
  const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {
      rate_18kt: 0,
      rate_22kt: 0,
      rate_24kt: 0,
      advance_amt
        :
        0,
      est_amount
        :
        0,
      date1: new Date().toISOString().split("T")[0],
      fix_gold_rate: false,
      salesman_1: null
    },
  });
  const [rs, setRows] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);

  useEffect(() => {
    async function fetchData() {
      const [customers, salesperson, orderNo, mainItem, purity] = await Promise.all([
        getLedgers(),
        fetchSalesperson(),
        fetchOrderNoNext(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (customers.success) setCustomers(customers.data.results);
      if (salesperson.success) setSalespersonData(salesperson.data.results);
      if (orderNo.success) setValue("order_no", orderNo.data.order_no);
      if (mainItem.success) setMainItemData(mainItem.data);
      if (purity.success) setPurityData(purity.data);
    }
    fetchData();
  }, []);

  const onSubmit = (data) => {
    const { gw, main_item, making, making_type, other_chg, pcs, purity, remarks, size } = data;
    const ex = { gw, main_item, making, making_type, other_chg, pcs, purity, remarks, size }
    Object.keys(ex).forEach(key => {
      if (data[key] === ex[key]) {
        delete data[key];
      }
    });

    data.items = rs;
    if (data.salesman_2) data.salesman_2 = parseInt(data.salesman_2); else data.salesman_2 = null
    data.salesman_1 = parseInt(data.salesman_1)
    console.log(data)

    createCustomerOrder(data)
      .then((response) => {
       
        if (response.success) {
          toast({ title: "Form submitted successfully!" ,
          });  // Success toast
        } else {
          toast({ title: "Form submission failed. Please try again.",
            description: "There was a problem with your request.",
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
    reset(row);
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const fix_gold_rate = watch("fix_gold_rate")

  const handleKeyDown = (e) => {
    const { gw, main_item, making, making_type, other_chg, pcs, purity, remarks, size } = getValues();
    const sl_no = rs.length + 1
    const iss_status = false;
    const rec_status = false;
    const del_status = false;
    const sale_status = false;
    const rowVals = {
      sl_no,
      gw, main_item, making_amt:making, making_type, other_chg, pcs, purity, remarks, size, iss_status, rec_status, del_status,
      sale_status,
    }
    if (e.key === "Tab") {
      setRows([...rs, rowVals])

    }
  };

  return (
    <div className="container mt-40 ">
        <form className=" form-floating  mx auto card p-4 shadow-lg rounded-lg bg-white "
        id="accountForm"
        onSubmit={handleSubmit(onSubmit)}>
      
        <h3 className="text-lg font-semibold text-center">Add New Account</h3>
        <hr className="my-3" />
<br></br>
        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-4 gap-4 mb-4 text-center">
          <FieldContainer>
            <Label htmlFor="advance_amt" className="text-nowrap">Account Name*</Label>
            <Input type="text" {...register("advance_amt")} />
          </FieldContainer>
          
          
        </div>
        <br></br>
        <div className="grid grid-cols-4 gap-4 mb-4 text-center">
        <FieldContainer>
            <Label htmlFor="salesperson1" className="text-nowrap">Parent Account(Optional)</Label>
            <Controller
              name="salesman_1"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger >
                    <SelectValue placeholder="Select Sales" />
                  </SelectTrigger>
                  <SelectContent>
                    {salespersonData.map((sp, index) => (
                      <SelectItem key={index} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>
                    ))}

                  </SelectContent>
                </Select>
              )}
            />

          </FieldContainer>
          </div>
          <div className="grid grid-cols-4 gap-4 mb-4">
        <FieldContainer>
            <Label htmlFor="advance_amt" className="text-nowrap">Account Code</Label>
            <Input type="number" {...register("advance_amt")} />
          </FieldContainer>
          </div>
         <div className="flex justify-center mt-5">
                     <Button type="submit" className="mr-4"> Add Account</Button>
        </div> 
      
    </form>
        
    </div>
  );
};

export default AddAccount;

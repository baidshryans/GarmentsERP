/* eslint-disable no-unused-vars */
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
import { fetchMainItem, fetchOrderItem, fetchReceiveSlipNo, fetchKarigarIssues, fetchPurity, getLedgers, createCustomerOrder, getStates, fetchStoneIssuesFilterJobs, fetchBarcodes, fetchPackets, createPurchaseReturn, fetchDetailsForPurchaseReturn } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchPRNoNext, fetchPurchaseReturnForEdit, updatePurchaseReturnForEdit } from "../../../services/apiService";
import { Edit, Trash2 } from "lucide-react";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router";

const PurchaseReturnadd = () => {

  const { toast } = useToast();
  const {id} = useParams();
  const {
    register,
    handleSubmit,
    control,
    reset,
    watch,
    setValue,
    getValues,
  } = useForm({
    defaultValues: {
      form: {
        // The top-level "Sales Voucher" fields
        date1: new Date().toISOString().split("T")[0],
        invoice_date: new Date().toISOString().split("T")[0],
        billno: "",
        gst_billno: "",
        ldgr: "",
        sales_person: "",
        sales_person2: "",
        place_of_supply: "WB",
        taxable_value: "",
        ret_status: false,
        remarks: "",
        freight_charge: 0,
        mrp: 0,
        discount: 0,
        gst_type: "gst1", // "gst1" => LOCAL, "gst2" => OUTSTATION
        sgst_per: 0,
        cgst_per: 0,
        igst_per: 0,
        tcs_per: 0,
        mode_of_transport: "",
        pv_billno:"",
      },
      // The single "@/table" object for new-item input
      table: {
        barcode: "",
        barcode_txt: "",
        item: "",
        pcs: 0,
        gw: 0.0,
        making: 0.0,
        making_type: 0.0,
        purity: 0,
        ret_status: false,
        amount: 0,
        purchasereturndetails_set: {
          billno: "",
          main_item: "",
          item: "",
          pcs: 0,
          ct: 0.0,
          gw: 0.0,
          metal_purity: "",
          tunch: 0.0,
          rate: 0.0,
          amount: 0.0,
          packet: "",
          // fine_wt is read_only => not included
        },
      },
    },
  });

  // Data-lists from your APIs
  const [rs, setRows] = useState([]); // array of items to be submitted
  const [mainItemData, setMainItemData] = useState([]);
  const [customerOrders, setCustomerOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [serialNos, setSerialNos] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [packetData, setPacketData] = useState([])
  const [barCodes, setBarcodes] = useState([])
  const [ledgers, setLedgerData] = useState([]);

  const navigate = useNavigate();

  // On mount, fetch needed data
  useEffect(() => {
    async function fetchData() {
      const [
        ledgersRes,
        mainItemRes,
        purityRes,
        packets,
        barcodes,
        billno
      ] = await Promise.all([
        getLedgers(),
        fetchMainItem(),
        fetchPurity(),
        fetchPackets(),
        fetchBarcodes(),
        fetchPRNoNext()
      ]);


      if (barcodes.success) {
        setBarcodes(barcodes.data.results);
      }

      if(billno.success) setValue("form.billno",billno.data.billno)

      // Ledgers (parties / customers)
      if (ledgersRes.success) {
        setLedgerData(ledgersRes.data.results);
        setCustomers(ledgersRes.data.results);
      }



      // MainItem
      if (mainItemRes.success) {
        setMainItemData(mainItemRes.data);
      }

      // Purity
      if (purityRes.success) {
        setPurityData(purityRes.data);
      }

      // Purity
      if (packets.success) {
        setPacketData(packets.data);
      }



    }
        fetchData().then(d => {
                      if (id) {
                
                        
                        fetchPurchaseReturnForEdit(id)
                            .then((response) => {
                              Object.keys(response.data).forEach((key) => {
                                setValue(`form.${key}`, response.data[key]);
                              });
                      
                              // Set items array
                              if (response.data.purchasereturnitems_set) {
                                setRows(response.data.purchasereturnitems_set);
                              }
                            })
                            .catch((error) => {
                              console.error('Error fetching manufacturing issue:', error);
                            });
                      }
                    });
  }, [setValue]);


  const handleBillNoKeyDown = async (e) => {
      if (e.key === 'Tab') {
        // e.preventDefault();
        const billNo = getValues('form.billno');
        if (billNo) {
          try {
            const response = await fetchDetailsForPurchaseReturn(billNo);
            if (response.success && response.data) {
              console.log(response.data)
              const cleanData = removeIds(response.data)
              reset({cleanData})
              // reset(cleanData)
              setRows(prev => [...prev,...cleanData.purchasereturnitems_set
                ])
              // setRows(cleanData.purchasereturnitems_set || []);
            }
          } catch (error) {
            console.error('Error fetching order:', error);
            toast({ title: 'Error fetching order details' });
          }
        }
      }
    };
    function removeIds(obj) {
      // Handle arrays by mapping each element
      if (Array.isArray(obj)) {
        return obj.map(removeIds);
      } 
      // Handle objects by filtering out only lowercase "id" fields
      else if (typeof obj === 'object' && obj !== null) {
        return Object.fromEntries(
          Object.entries(obj)
            .filter(([key]) => key !== 'id') // Only filter exact match "id"
            .map(([key, value]) => [key, removeIds(value)])
        );
      }
      // Return primitive values as is
      return obj;
    }


    const handleEdit = (index) => {
      const itemToEdit = rs[index];
      reset({
        ...getValues(),
        table: itemToEdit,
      });
      setRows((prev) => prev.filter((_, i) => i !== index));
    };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDeleteSubItem = (rowIndex, subIndex, key) => {
    const tablevalues = { ...rs[rowIndex] };

    setRows((prev) =>
      prev.map((row, i) =>
        i === rowIndex
          ? {
            ...row,
            [key]: row[key].filter((_, j) => j !== subIndex),
          }
          : row
      )
    );
  };
  
  
  
  const handleBillNoKeyDowns = async (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const pvbillNo = getValues('form.pv_billno');
      if (pvbillNo) {
        try {
          const response = await fetchDetailsForPurchaseReturn(pvbillNo);
          if (response.success && response.data) {
            const cleanData = removeIds(response.data);
             const { billno, bill_no, ...restCleanData } = cleanData;
            reset({
              ...getValues(),
              form: {
                ...getValues().form,
                ...restCleanData,
              }
            });
            setRows(cleanData.purchasereturnitems_set || []);
          }
        } catch (error) {
          console.error('Error fetching order:', error);
          toast({ title: 'Error fetching order details' });
        }
      }
    }
  };

    function removeIds(obj) {
      // Handle arrays by mapping each element
      if (Array.isArray(obj)) {
        return obj.map(removeIds);
      } 
      // Handle objects by filtering out only lowercase "id" fields
      else if (typeof obj === 'object' && obj !== null) {
        return Object.fromEntries(
          Object.entries(obj)
            .filter(([key]) => key !== 'id') // Only filter exact match "id"
            .map(([key, value]) => [key, removeIds(value)])
        );
      }
      // Return primitive values as is
      return obj;
    }
    

  // ---------------------------------
  // SUBMIT HANDLER (createSalesReturn)
  // ---------------------------------
  const handleSalesReturnSubmit = async (formData) => {
    try {
      const data = getValues("form");
      // attach items
      data.purchasereturnitems_set = rs; // the array of item object
      console.log("Submitting Sales Voucher data:", data);
      
      if(rs.length===0){
        toast({title:"Table is empty"})
      }

      const response = await (id ? updatePurchaseReturnForEdit(data,id) : createPurchaseReturn(data));
      if (response.success) {
        toast({ title: "Form submitted successfully!" });
        reset(); // Clear entire form
        setRows([]); // Clear item array
       
        setTimeout(() => {
          navigate("/purchase/purchasereturn/list/");
        }, 2000);

      } else {
        toast({
          title: "Form submission failed. Please try again.",
          description: renderErrorTree(response.error),
        });  // Error toast
      }

    } catch (error) {
      console.error("Error creating Sales Voucher:", error);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(handleSalesReturnSubmit));

  // ---------------------------
  // ADDING a NEW ITEM to "rs"
  // ---------------------------
  const handleAddItem = () => {
    // Grab the "@/table" object from the form (the single item input)
    const itemData = getValues("@table");
    // Add to array
    setRows((prev) => [...prev, itemData]);
    // Reset the single "@/table" input fields to blank
    reset({
      ...getValues(),
      table: {
        date1: new Date().toISOString().split("T")[0],
        sale_billno: "",
        barcode: "",
        item: "",
        pcs: 0,
        gw: 0,
        purity: "",
        making: 0,
        making_type: "",
        making_value: 0,
        item_value: 0,
        remarks: "",
        purchasereturndetails_set: {
          date1: new Date().toISOString().split("T")[0],
          main_item: "",
          metal_purity: "",
          pcs: 0,
          ct: 0,
          gw: 0,
          tunch: 0,
          rate: 0,
          amount: 0,
          packet: "",
        },
      },
    });
  };

  // Add item to table on Tab press (or you can do a button click)
  const handleKeyDown = (e) => {
    if (e.key === "Tab") {
      e.preventDefault(); // if you want to actually intercept the Tab
      handleAddRow();
    }
  };

  const handleAddRow = () => {
    const newItem = getValues("table"); // all item fields + details
    // push to the array
    const billNo = getValues("form.billno");
    // const det = { ...newItem.details }
    // const det = { ...newItem.details, billno:billNo };
    // newItem.purchasereturndetails_set = [det]
     let details = newItem.purchasereturndetails_set;
  if (!Array.isArray(details)) {
    details = [details];
  }
  details = details.map(detail => ({
    ...detail,
    billno: billNo || detail.billno || "",
  }));
    setRows([...rs, {...newItem}]);
    // optionally reset the single "@/table" fields after adding
    reset({
      ...getValues(),
      table: {
        barcode: "",
        item: "",
        pcs: 0,
        gw: 0.0,
        making: 0.0,
        making_type: 0.0,
        purity: 0,
        ret_status: false,
        amount: 0,
        purchasereturndetails_set: {
          main_item: "",
          item: "",
          pcs: 0,
          ct: 0.0,
          gw: 0.0,
          metal_purity: "",
          tunch: 0.0,
          rate: 0.0,
          amount: 0.0,
          packet: "",
          billno:billNo
        },
      },
    });
  };
  
 
  
  const  handleKeyDownDetails = (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const vals = {...getValues("table.details")}
    const billNo = getValues("form.billno");
    vals.billno = billNo || vals.billno || "";
    const idx = vals.sl_no - 1;
    if (idx >= 0) {
      const tablevalues = { ...rs[idx] };
      // Ensure purchasereturndetails_set is always an array
      const detailsArr = Array.isArray(tablevalues.purchasereturndetails_set)
        ? tablevalues.purchasereturndetails_set
        : tablevalues.purchasereturndetails_set
          ? [tablevalues.purchasereturndetails_set]
          : [];
      tablevalues.purchasereturndetails_set = [...detailsArr, vals];
      setRows((prevData) =>
        prevData.map((row, i) => (i === idx ? { ...tablevalues } : row))
      );
      reset({
        ...getValues(),
        table: {
          ...getValues().table,
          details: {
            purchasereturndetails_set: [],
            billno: "",
            main_item: "",
            item: "",
            pcs: 0,
            ct: 0.0,
            gw: 0.0,
            metal_purity: "",
            tunch: 0.0,
            rate: 0.0,
            amount: 0.0,
            packet: "",
          },
        },
      });
    }
  }
};
   
  // Example: if you want to remove a row
  const handleDeleteItem = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="container mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(handleSalesReturnSubmit)}
      >
        <h3 className="text-xl font-semibold mb-3">Purchase Return</h3>
        <hr className="my-3" />
        <br></br>
        {/* Top-level fields (matching your "OPTIONS" schema) */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          {/* date1 */}
          <FieldContainer>
            <Label htmlFor="date1" className="text-nowrap">Date</Label>
            <Input
              type="date"
              {...register("form.date1", { required: true })}
            />
          </FieldContainer>

     
          <FieldContainer>
            <Label htmlFor="billno" className="text-nowrap">Bill No</Label>
            <Input
              type="text"
              onKeyDown={handleBillNoKeyDown}
              {...register("form.billno", { required: true })}
            />
          </FieldContainer>

          {/* ldgr -> same approach as "sales_person" with a <Controller> + <Select> */}
          <FieldContainer>
            <Label htmlFor="ldgr" className="text-nowrap">Ledger</Label>
            <Controller
              name="form.ldgr"
              control={control}
              rules={{ required: true }}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger data-led="ledger">
                    <SelectValue placeholder="Select a Ledger" />
                  </SelectTrigger>
                  <SelectContent>
                    {ledgers.map((ledger) => (
                      <SelectItem key={ledger.id} value={`${ledger.id}`}>
                        {ledger.ac_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
        </div>

        
          
        {/* </div> */}
        <div className="grid grid-cols-3 gap-4 mb-4">


          <FieldContainer>
            <Label htmlFor="mode_of_transport" className="text-nowrap">Mode of Transport</Label>
            <Input
              type="text"
              {...register("form.mode_of_transport")}
            />
          </FieldContainer>
          
         <FieldContainer>
         <Label htmlFor="gst_type" className="text-nowrap">
              GST Type
            </Label>
            <Controller
              control={control}
              name="form.gst_type"
              render={({ field }) => (
                <Select
                  onValueChange={field.onChange}
                  value={field.value}
                >
                  <SelectTrigger gst="gst-type">
                    <SelectValue placeholder="Select GST Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gst1" className="text-nowrap">LOCAL</SelectItem>
                    <SelectItem value="gst2" className="text-nowrap">OUTSTATION</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer> 

          <FieldContainer>
            <Label htmlFor="pv_billno" className="text-nowrap">PV_BillNo</Label>
            <Input
              type="text"
              onKeyDown={handleBillNoKeyDowns}
              {...register("form.pv_billno", { required: true })}
            />
          </FieldContainer> 
        </div>

       <br></br>
        {/* <h6 className="text-lg font-semibold my-3 text-start">Add an Item</h6>
      
        <Table className="w-full table-fixed border-collapse mb-4">
          <TableBody>
            <TableRow className="bg-gray-100">
              <TableCell className="w-28 px-4 py-2 border">Barcode</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Barcode txt</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Sl No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Type</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Amount</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item Value</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Remarks</TableCell>
            </TableRow>
          </TableBody>
          <TableBody>
            <TableRow>

              <TableCell className="w-28 px-4 py-2 border">
                <Input list="barcode_list" type="text" {...register("table.barcode")} />
                <datalist id="barcode_list">
                  {barCodes.map((itm, idx) => (
                    <option key={idx} value={itm.barcode}>
                      {itm.barcode}
                    </option>
                  ))}
                </datalist>
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="text" {...register("table.barcode_txt")} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.sl_no")} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input list="item_list" {...register("table.item")} />
                <datalist id="item_list">
                  {mainItemData.map((itm, idx) => (
                    <option key={idx} value={itm.short_code}>
                      {itm.item_name}
                    </option>
                  ))}
                </datalist>
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.pcs")} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" step="0.01" {...register("table.gw")} />
              </TableCell>

              <TableCell>
                <Controller
                  name="table.making_type"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger data-testid="making-type">
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
              <TableCell className="w-28 px-4 py-2 border">
                <Controller
                  name={`table.purity`}
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger data-id="purity">
                        <SelectValue placeholder="Select Purity" />
                      </SelectTrigger>
                      <SelectContent>
                        {purityData.map((item, index) => (
                          <SelectItem key={index} value={`${item.purity}`}>{item.purity}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.001"
                  {...register("table.making_amt")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.001"
                  {...register("table.item_value")}
                />
              </TableCell>



              <TableCell className="w-28 px-4 py-2 border">
                <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register("table.remarks")} />
              </TableCell>
            </TableRow>
          </TableBody> */}
        {/* </Table> */}
        <br></br>

        {/* Next, the "details" sub-object fields */}
        <h6 className="text-md font-semibold mb-2">Nested Details</h6>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className="w-full bg-gray-100">
           
              <TableCell className="w-28 px-4 py-2 border">Sl No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Bill No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Metal Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Tunch</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Amount</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Loss</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Packet</TableCell>
            </TableRow>

            
          </TableBody>
          <TableBody>
            <TableRow>
            
            <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="text"
                  
                  {...register("table.details.sl_no")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="text"
                  {...register("table.details.billno")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input list="item_list" {...register("table.details.item")} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  {...register("table.details.pcs")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.001"
                  {...register("table.details.ct")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.001"
                  {...register("table.details.gw")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Controller
                  name={`table.details.metal_purity`}
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger data-testid="purity">
                        <SelectValue placeholder="Select Purity" />
                      </SelectTrigger>
                      <SelectContent>
                        {purityData.map((item, index) => (
                          <SelectItem key={index} value={`${item.purity}`}>{item.purity}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.01"
                  {...register("table.details.tunch")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.001"
                  {...register("table.details.rate")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.01"
                  {...register("table.details.value")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.01"
                  {...register("table.details.loss")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input 
                onKeyDown={(e) =>handleKeyDownDetails(e)}
                list="packet_list" {...register("table.details.packet")} />
                <datalist id="packet_list">
                  {packetData.map((itm, idx) => (
                    <option key={idx} value={itm.pckt_no}>
                      {itm.pckt_no}
                    </option>
                  ))}
                </datalist>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <br></br>

        <Table className="w-full table-fixed border-collapse">

          <TableBody>
            <TableRow className="bg-violet-100">
              <TableCell className="w-32 px-4 py-2 border">Options</TableCell>            
              <TableCell className="w-28 px-4 py-2 border">Barcode</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Barcode Txt</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Sl No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Type</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Amount</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item value</TableCell>
              <TableCell className="w-28 px-4 py-2 border">remarks</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Bill No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Tunch</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Loss</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Packet</TableCell>
            </TableRow>

            {rs.map((item, idx) => (
              <React.Fragment key={idx}>
                <TableRow className="bg-gray-100">

                  <TableCell className="px-4 py-2 border flex flex-row justify-center items-center gap-3">

                      <Edit size={20} className="mr-1 cursor-pointer" onClick={() => handleEdit(idx)} />

                      <Trash2 size={20} color="#d45959" className="mr-1 cursor-pointer" onClick={() => handleDelete(idx)} />
                    </TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.barcode}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.barcode_txt}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.sl_no}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.item}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.pcs}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.gw}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.making_type}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.purity}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.making_amt}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.item_value}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.remarks}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                </TableRow>
                {item.purchasereturndetails_set && Array.isArray(item.purchasereturndetails_set) && item.purchasereturndetails_set.map((detail, detailIdx) => (
                  <TableRow className="bg-gray-100" key={detailIdx}>
                    <TableCell className="px-4 py-2 border flex flex-row justify-center items-center">
                     <Trash2 size={20} color="#d45959" className="mr-1 cursor-pointer" onClick={() => handleDeleteSubItem(idx,  detailIdx,'purchasereturndetails_set')} /> 

                     </TableCell>
                                           
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.item}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.pcs}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.ct}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.gw}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.metal_purity}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.value}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.billno}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.tunch}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.rate}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.loss}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.packet}</TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}

          </TableBody>
        </Table>

        
                    


       <br></br>

        <div className="grid grid-cols-4 gap-4 mb-4">
         <FieldContainer>
            <Label htmlFor="narration" className="text-nowrap">Narration</Label>
            <Input
              type="text"
              {...register("form.narration")}
            />
          </FieldContainer>
        </div>

        <br></br>
        <h4 className="text-lg font-semibold text-right pr-56 mb-10">Bill Summary</h4>
        <br></br>
        <div className="flex justify-end">
          <div className="grid grid-cols-1 gap-4 w-full max-w-md">
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="item_total" className="text-nowrap">Item Total</Label>
                  <Input
                    type="number"
                    {...register("form.item_total")}
                  />
                </FieldContainer>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="tcs_amt" className="text-nowrap">Tcs Amount</Label>
                  <Input
                    type="number"
                    {...register("form.tcs_amt")}
                  />
                </FieldContainer>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div className="flex justify-end col-span-3">
                {/* taxable_value */}
                <FieldContainer>
                  <Label htmlFor="taxable_value" className="text-nowrap">Taxable Value</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.taxable_value", { required: true })}
                  />
                </FieldContainer>
              </div>
            </div>
            {/* discount */}
            <div className="grid grid-cols-4 gap-4">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="discount" className="text-nowrap">Discount</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.discount", { required: true })}
                  />
                </FieldContainer>
              </div>
            </div>
            {/* cgst_amt */}
            <div className="grid grid-cols-4 gap-4">
              <div className="flex justify-end col-span-3">
                <FieldContainer>
                  <Label htmlFor="cgst_amt" className="text-nowrap">CGST Amount</Label>
                  <Input
                    type="number"
                    step="0.01"
                    {...register("form.cgst_amt", { required: true })}
                  />
                </FieldContainer>
              </div>
            </div>
          

        <div className="grid grid-cols-4 gap-4">
          <div className="flex justify-end col-span-3">
          {/* sgst_amt */}
          <FieldContainer>
            <Label htmlFor="sgst_amt" className="text-nowrap">SGST Amount</Label>
            <Input
              type="number"
              step="0.01"
              {...register("form.sgst_amt", { required: true })}
            />
          </FieldContainer>
          </div>
        </div>
        {/* igst_amt */}
        <div className="grid grid-cols-4 gap-4">
          <div className="flex justify-end col-span-3">
          <FieldContainer>
            <Label htmlFor="igst_amt" className="text-nowrap">IGST Amount</Label>
            <Input
              type="number"
              step="0.01"
              {...register("form.igst_amt", { required: true })}
            />
          </FieldContainer>
          </div>
        </div>
        </div>
        </div>
       
        {/* FINAL SUBMIT BUTTONS */}
        <div className="flex justify-center mt-5">
          <Button type="submit" className="mr-4">
            Save
          </Button>
          <Button
            variant="outline" onClick={() => window.history.back()}
            type="button"
            // onClick={() => {
            //   reset();
            //   setRows([]);
            // }}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
};

export default PurchaseReturnadd

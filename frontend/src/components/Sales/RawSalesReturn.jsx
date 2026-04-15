import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { arrayToObject, renderErrorTree } from "../../Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableRow,
  TableCell,
  TableHead,
  TableBody
} from "@/components/ui/table";
import { SquarePen, Trash2 } from "lucide-react";

import {
  fetchMainItem,
  fetchSlipNoNext,
  fetchSalesperson,
  fetchPurity,
  fetchPackets,
  fetchBarcodes,
  getLedgers,
  fetchCustomerOrders,
  fetchSlNosOrders,
  fetchOrderItem,
  createSalesVoucher,
  createSalesReturn,
  fetchDetailsforSaleReturn,
  fetchSaleRetNext,
} from "@/services/apiService";

import { Link, useParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";


import { FieldContainer } from "@/Utils";
import { fetchSalesReturnById, updateSalesReturn } from "../../services/apiService";

const RawSalesReturn = () => {
  const { toast } = useToast();
    const {id } = useParams()
  
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
      },
      // The single "@/table" object for new-item input
      table: {
        billno: "",
        barcode: "",
        item: "",
        pcs: 0,
        gw: 0.0,
        making: 0.0,
        making_type: 0.0,
        purity: 0,
        ret_status: false,
        amount: 0,
        salereturndetails_set:[],
        details: {
          salereturndetails_set:[],
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
        slipNoRes,
        mainItemRes,
        purityRes,
        packets,
        custOrdersRes,
        salesPersonsRes,
        barcodes
      ] = await Promise.all([
        getLedgers(),
        fetchSaleRetNext(),

        fetchMainItem(),
        fetchPurity(),
        fetchPackets(),
        fetchCustomerOrders(),
        fetchSalesperson(),
        fetchBarcodes()
      ]);

      // SalesPerson
      if (salesPersonsRes.success) {
        setSalespersonData(salesPersonsRes.data.results);
      }

      if (barcodes.success) {
        setBarcodes(barcodes.data.results);
      }

      // Ledgers (parties / customers)
      if (ledgersRes.success) {
        setLedgerData(ledgersRes.data.results);
        setCustomers(ledgersRes.data.results);
      }

      // SlipNo
      if (slipNoRes.success) {
        // If you want to store it in the form (e.g. hidden field)
        setValue("form.billno", slipNoRes.data.billno);
      }

      // MainItem
      if (mainItemRes.success) {
        setMainItemData(mainItemRes.data.results ?? mainItemRes.data);
      }

      // Purity
      if (purityRes.success) {
        setPurityData(purityRes.data.results ?? purityRes.data);
      }

      // Purity
      if (packets.success) {
        setPacketData(packets.data);
      }

      // Customer Orders
      if (custOrdersRes.success) {
        setCustomerOrders(custOrdersRes.data);
      }
    }
    fetchData().then((d)=>{
    
          if(id){
    
          fetchSalesReturnById(id).then(data => {
            if(data.success){
              const formData = {
                form: {
                  ...data.data,
                  salereturnitem_set: JSON.parse(JSON.stringify(data.data.salereturnitem_set)),
                }
              };
              reset({form:{...data.data}})
              setRows(JSON.parse(JSON.stringify(data.data.salereturnitem_set)))
              
            }
          })
          }
          
          
        });
  }, [setValue]);


  


  // ---------------------------------
  // SUBMIT HANDLER (createSalesReturn)
  // ---------------------------------
  const handleSalesReturnSubmit = async (formData) => {
    try {
      let data = getValues("form");
      // attach items
      data = {...data, salereturnitem_set :rs} ; // the array of item objects
    
      console.log("Submitting Sales Voucher data:", data);

      if(rs.length===0){
        toast({title: "Table is empty"})
        return;
      }

      // const response = await createSalesReturn(data);
      const response= id ? (await updateSalesReturn(data,id))  : ( await createSalesReturn(data));
      
      if (response.success) {
        toast({ title: "Form submitted successfully!" });
        reset(); // Clear entire form
        setRows([]); // Clear item array
      
        setTimeout(() => {
          navigate("/sales/salesreturn/list/");
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
    // Grab the "@/salereturnitem_set" object from the form (the single item input)
    const itemData = getValues("@/table");
    // Add to array
    setRows((prev) => [...prev, itemData]);
    // Reset the single "@/table" input fields to blank
    reset({
      ...getValues(),
      table: {
        date1: new Date().toISOString().split("T")[0],
        sale_billno: "",
        billno: "",
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
        details: {
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
    const det = { ...newItem.details }
    newItem.details = [det]

    setRows([...rs, {...newItem}]);
    // optionally reset the single "@/table" fields after adding
    reset({
      ...getValues(),
      table: {
        billno: "",
        barcode: "",
        item: "",
        pcs: 0,
        gw: 0.0,
        making: 0.0,
        making_type: 0.0,
        purity: 0,
        ret_status: false,
        amount: 0,
        details: {
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
  };

  


  const  handleKeyDownDetails = (e) => {
    console.log("Called details")
    if (e.key === "Tab") {
      e.preventDefault();
       // if you want to actually intercept the Tab
      const vals = {...getValues("table.details")}
       const idx = vals.sl_no - 1;
       if (idx>=0){
        const tablevalues = rs[idx];
        tablevalues.salereturndetails_set = [...tablevalues.salereturndetails_set,vals]
        setRows((prevData) =>
          prevData.map((row, i) => (i === idx ? { ...tablevalues } : row))
        );
        reset({
          ...getValues(),
          table: {
            billno: "",
            barcode: "",
            item: "",
            pcs: 0,
            gw: 0.0,
            making: 0.0,
            making_type: 0.0,
            purity: 0,
            ret_status: false,
            amount: 0,
            salereturndetails_set:[],
            details: {
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



  const handleBillNoKeyDown = async (e) => {
    if (e.key === 'Tab') {
      const billNo = getValues('billno');
      if (billNo) {
        try {
          const response = await fetchDetailsforSaleReturn(billNo);
          if (response.success && response.data) {
            // console.log(response.data)
            // response.data.billno = getValues('form.billno'); 

            // reset({form:response.data})
            const currentForm = getValues('form');
          reset({
            form: {
              ...currentForm,
              ...response.data,
              billno: currentForm.billno, 
              date1: response.data.date1 || currentForm.date1, 
              ldgr: response.data.ldgr || currentForm.ldgr,   
            }
          });
            setRows(prev => [...prev,...response.data.salereturnitem_set
              ])
          }
        } catch (error) {
          console.error('Error fetching order:', error);
          toast({ title: 'Error fetching order details' });
        }
      }
    }
  };

  

  // Example: if you want to remove a row
  const handleDeleteItem = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleEdit = (index) => {
    const itemToEdit = rs[index];
    reset({
      ...getValues(),
      table: {
        ...itemToEdit,
        // If you want to edit the first detail as well, you can do:
        details: itemToEdit.salereturndetails_set?.[0] || {},
      },
    });
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDeleteDetail = (itemIdx, detailIdx) => {
    setRows((prev) =>
      prev.map((item, idx) =>
        idx === itemIdx
          ? {
              ...item,
              salereturndetails_set: item.salereturndetails_set.filter((_, i) => i !== detailIdx),
            }
          : item
      )
    );
  };


  return (
    <div className="mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(handleSalesReturnSubmit)}
      >
        <h3 className="text-xl font-semibold mb-3">Sales Return</h3>
        <hr className="my-3" />

        {/* Top-level fields (matching your "OPTIONS" schema) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          {/* date1 */}
          <FieldContainer>
            <Label htmlFor="date1" className="text-nowrap">Date</Label>
            <Input
              type="date"
              {...register("form.date1", { required: true })}
            />
          </FieldContainer>

          {/* billno */}
          <FieldContainer>
            <Label htmlFor="billno" className="text-nowrap">Bill No</Label>
            <Input
              type="text"
      
              {...register("form.billno", { required: true })}
            />
          </FieldContainer>

          <FieldContainer>
            <Label htmlFor="billno" className="text-nowrap">Ref Bill No</Label>
            <Input
              type="text"
              onKeyDown={handleBillNoKeyDown}
              {...register("billno")}
            />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="ldgr" className="text-nowrap">Ledger</Label>
            <SearchableComboBox
              options={ledgers}
              value={ledgers.find((l) => String(l.id) === String(watch("form.ldgr")))?.ac_name ?? ""}
              onSelect={(opt) => setValue("form.ldgr", opt.id)}
              placeholder="Search customer…"
            />
            <input type="hidden" {...register("form.ldgr", { required: true })} />
          </FieldContainer>

          
        </div>

      

        {/* <h6 className="text-lg font-semibold my-3 text-start">Add an Item</h6>
        
        <Table className="w-full table-fixed border-collapse mb-4">
          <TableBody>
            <TableRow className="bg-gray-100">
              <TableCell className="w-28 px-4 py-2 border">Barcode</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Type</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Amount</TableCell>
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
                <Input type="number" step="0.001" {...register("table.gw")} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input
                  type="number"
                  step="0.001"
                  {...register("table.making")}
                />
              </TableCell>
              <TableCell>
                <Controller
                  name="table.making_type"
                  control={control}
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
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
                <Input onKeyDown={(e) => handleKeyDown(e)} type="number" {...register("table.amount")} />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table> */}

        <br></br>
        
        {/* Next, the "details" sub-object fields */}
        <br></br>
        
        <h6 className="text-md font-semibold mb-2">Item Details</h6>
        <div className="overflow-x-auto">
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className="w-full bg-gray-100">
              {/* <TableCell className="w-28 px-4 py-2 border">Sl no</TableCell> */}
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Metal Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Tunch</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Amount</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Packet</TableCell>
            </TableRow>
          </TableBody>
          <TableBody>
            <TableRow>
            {/* <TableCell className="w-28 px-4 py-2 border">
                <Input {...register("table.details.sl_no")} />
              </TableCell> */}
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
                      <SelectTrigger data-id="metal-py">
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
                  {...register("table.details.amount")}
                />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input list="packet_list" 
                onKeyDown={(e) => handleKeyDownDetails(e)}
                {...register("table.details.packet")} />
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
        </div>
        <br></br>

        <div className="overflow-x-auto">
        <Table>

          <TableBody>
            <TableRow className="bg-violet-100">
              <TableCell className="w-32 px-4 py-2 border">Options</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Barcode</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">GW</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making Type</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Tunch</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Packet</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Amount</TableCell>
            </TableRow>

            {rs.map((item, idx) => (
              <React.Fragment key={idx}>
                <TableRow className="bg-gray-100">
                  <TableCell className="px-4 py-2 border flex flex-row justify-center items-center gap-2">
                    <SquarePen
                      size={20}
                      className="cursor-pointer"
                      onClick={() => handleEdit(idx)}
                    />
                    <Trash2
                      size={20}
                      color="#d45959"
                      className="cursor-pointer"
                      onClick={() => handleDeleteItem(idx)}
                    />
                  </TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.barcode}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.item}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.pcs}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.making}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.making_type}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.purity}</TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border"></TableCell>
                  <TableCell className="w-28 px-4 py-2 border">{item.amount}</TableCell>
                </TableRow>
                {item?.salereturndetails_set?.map((detail, detailIdx) => (
                  <TableRow className="bg-gray-100" key={detailIdx}>
                    <TableCell className="px-4 py-2 border flex flex-row justify-center items-center">
                      <Trash2
                        size={20}
                        color="#d45959"
                        className="cursor-pointer"
                        onClick={() => handleDeleteDetail(idx, detailIdx)}
                      />
                    </TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.item}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.pcs}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{Number(detail.ct || 0).toFixed(3)}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.gw}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border"></TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.metal_purity}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.tunch}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.rate}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.packet}</TableCell>
                    <TableCell className="w-28 px-4 py-2 border">{detail.amount}</TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}

          </TableBody>
        </Table>
        </div>
        <br/><br/>

            <br/><br/>
        <h6 className="text-lg font-semibold text-right pr-10 mb-10">3.Bill Summary</h6>
        <div className="flex justify-end">
          <div className="grid grid-cols-1 gap-4 mb-4">
            {/* taxable_value */}
            <FieldContainer>
              <Label htmlFor="taxable_value" className="text-nowrap">Taxable Value</Label>
              <Input
                type="number"
                step="0.001"
                {...register("form.taxable_value", { required: true })}
              />
            </FieldContainer>

            {/* discount */}

            <FieldContainer>
              <Label htmlFor="discount" className="text-nowrap">Discount</Label>
              <Input
                type="number"
                step="0.001"
                {...register("form.discount", { required: true })}
              />
            </FieldContainer>

            {/* cgst_amt */}
            <FieldContainer>
              <Label htmlFor="cgst_amt" className="text-nowrap">CGST Amount</Label>
              <Input
                type="number"
                step="0.001"
                {...register("form.cgst_amt", { required: true })}
              />
            </FieldContainer>

            {/* sgst_amt */}
            <FieldContainer>
              <Label htmlFor="sgst_amt" className="text-nowrap">SGST Amount</Label>
              <Input
                type="number"
                step="0.001"
                {...register("form.sgst_amt", { required: true })}
              />
            </FieldContainer>

            {/* igst_amt */}
            <FieldContainer>
              <Label htmlFor="igst_amt" className="text-nowrap">IGST Amount</Label>
              <Input
                type="number"
                step="0.001"
                {...register("form.igst_amt", { required: true })}
              />
            </FieldContainer>
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

export default RawSalesReturn;

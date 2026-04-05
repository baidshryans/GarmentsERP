import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchReceiveSlipNo, fetchKarigarIssues, fetchPurity, getLedgers, createCustomerOrder, getStates, fetchNextBarcode, fetchReceiveItemsForBarcode, createBarcode } from "@/services/apiService";
import { Link, useLocation, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchBarcodeForEdit,fetchPurhcaseItemsForBarcode,updateBarcodeForEdit} from "../../../services/apiService";
import { Edit, Trash2 } from "lucide-react";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router-dom";

const BarcodeManagementList = () => {
  const location = useLocation();
  const {id} = useParams()
  const searchParams = new URLSearchParams(location.search);
  const sl_no = searchParams.get('sl_no');
  const rec_slip_no = decodeURIComponent(searchParams.get('rec_sl_no'));
  const bill_no = decodeURIComponent(searchParams.get('bill_no'));

  const { toast } = useToast();
  const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {
      form: {
        created_date: new Date().toISOString().split("T")[0],
        'other_chg':0,
        barcodedetails_set: []
      }
    },
  });

  const navigate=useNavigate();
  const [rs, setRows] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const { fields, append, remove } = useFieldArray({
    control,
    name: "form.barcodedetails_set",
  });
  const making = watch("form.making_val")
  useEffect(() => {
    console.log(rec_slip_no);
    console.log(rec_slip_no == null);
    console.log(rec_slip_no == "null");
    console.log(bill_no);
    console.log(sl_no);
    if (sl_no && rec_slip_no && rec_slip_no !== "null") {
      fetchReceiveItemsForBarcode(sl_no, rec_slip_no)
        .then(response => {
          if (response.success) {
            reset({ form: { ...response.data } });
          }
        })
        .catch(error => {
          toast({
            title: "Error fetching data",
            description: "Failed to load barcode details",
          });
        });
    } else if (sl_no && bill_no) {
      fetchPurhcaseItemsForBarcode(sl_no, bill_no).then(response => {
        if (response.success) {
          reset({ form: response.data });
          for (var i = 0; i < response.data.barcodedetails_set.length; i++) {
            handleEditRate(i)
          }

        }
      })
        .catch(error => {
          toast({
            title: "Error fetching data",
            description: "Failed to load barcode details",
          });
        });
    }
  }, [sl_no, rec_slip_no, reset]);

  useEffect(() => {
    async function fetchData() {
      const [karigars, customers, salesperson, orderNo, mainItem, purity] = await Promise.all([
        fetchKarigarIssues(),
        getLedgers(),
        getStates(),
        fetchNextBarcode(),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (karigars.success) setKarigars(karigars.data.results);
      if (customers.success) setCustomers(customers.data.results);
      if (salesperson.success) setSalespersonData(salesperson.data);
      if (orderNo.success) setValue("form.barcode", orderNo.data.barcode);
      if (mainItem.success) setMainItemData(mainItem.data);
      if (purity.success) setPurityData(purity.data);
    }
    
  fetchData().then(d => {
        if (id) {
          fetchBarcodeForEdit(id)
              .then((response) => {
                Object.keys(response.data).forEach((key) => {
                  setValue(`form.${key}`, response.data[key]);
                });
        
                // Set items array
                if (response.data.barcodedetails_set) {
                  setRows(response.data.barcodedetails_set);
                }
              })
              .catch((error) => {
                console.error('Error fetching manufacturing issue:', error);
              });
        }
      });
     }, []);
  

  const onSubmit = (data) => {
    const form_data = getValues("form");
    const mod_data = form_data.barcodedetails_set.map(item => ({ ...item, barcode_text: form_data.barcode }));
    form_data.barcodedetails_set = mod_data;
    console.log(form_data);

      ((id? updateBarcodeForEdit (form_data, id) :createBarcode(form_data))
      .then((response) => {
        if (response.success) {
          toast({
            title: "Form submitted successfully!",
          }); // Success toast
          setTimeout(()=>{
            navigate("/inventory/barcodemanagement/list/");
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
        toast({ title: "An error occurred. Please try again later." }); // Error toast on catch
      })
 ) };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    const row = rs[index];
    reset(row);
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleEditRate = (index) => {
    console.log("called");

    const rate = parseInt(getValues(`form.barcodedetails_set.${index}.rate`)) || 0;
    const uom = getValues(`form.barcodedetails_set.${index}.uom`);
    let quantity;
    switch (uom.toString().toLowerCase()) {
      case 'ct':
        quantity = parseInt(getValues(`form.barcodedetails_set.${index}.ct`)) || 0;
        break;
      case 'gm':
        quantity = parseInt(getValues(`form.barcodedetails_set.${index}.gw`)) || 0;
        break;
      case 'pcs':
        quantity = parseInt(getValues(`form.barcodedetails_set.${index}.pcs`)) || 0;
        break;
      default:
        quantity = 0;
    }
    setValue(`form.barcodedetails_set.${index}.amt`, rate * quantity);
    console.log(rate);
    console.log(uom);
  };

  const handleKeyDown = (e) => {
    const { gw, main_item, making, making_type, other_chg, pcs, purity, remarks, size } = getValues();
    const sl_no = rs.length + 1;
    const iss_status = false;
    const rec_status = false;
    const del_status = false;
    const sale_status = false;
    const rowVals = {
      sl_no,
      gw, main_item, making_amt: making, making_type, other_chg, pcs, purity, remarks, size, iss_status, rec_status, del_status,
      sale_status,
    };
    if (e.key === "Tab") {
      setRows([...rs, rowVals]);
    }
  };

  const item_name = watch("form.item_name");

  return (
    <div className="mt-5">
      <form
        className="p-4 shadow rounded bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >
        {/* Existing form fields */}
        <br></br>

        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-5 gap-4 mb-4">
        {/* <FieldContainer>
          <Label htmlFor="date">Date</Label>
          <Input type="date" {...register("form.created_date")} required />
        </FieldContainer> */}
        </div>
        <div className="grid grid-cols-5 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Barcode</Label>
            <Input type="text" {...register("form.barcode")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Voucher No</Label>
            <Input type="text" {...register("form.voucher_no")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Design No</Label>
            <Input type="text" {...register("form.design_code")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Kr Code</Label>
            <Input type="text" {...register("form.kr_code")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">HUID</Label>
            <Input type="text" {...register("form.huid")} />
          </FieldContainer>
        </div>

        {/* Party Details */}
        <div className="grid grid-cols-5 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Order No</Label>
            <Input type="text" {...register("form.order_no")} />
          </FieldContainer>

          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Cust. Making</Label>
            <Input type="text" {...register("form.making_val")} />
          </FieldContainer>
          <FieldContainer>
             <Label htmlFor="status" className="text-nowrap">Making Type</Label>
            <Controller
              name="form.making_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger className="making-type">
                    <SelectValue placeholder="Making type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="per_nw">% of wt</SelectItem>
                    <SelectItem value="val">Value</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="other_chg" className="text-nowrap">Other Charges</Label>
            <Input type="number" {...register("form.other_chg")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="design_master" className="text-nowrap">Add to Design Master</Label>
            <Controller
              control={control}
              name="form.add_to_design"
              render={({ field }) => (
                <Checkbox
                  checked={field.value}
                  onCheckedChange={(val) => field.onChange(Boolean(val))}
                />
              )}
            />
          </FieldContainer>
        </div>



        {/* Stone Details*/}
        <h6 className="text-lg font-semibold my-3">Pricing Detail</h6>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>


            <TableRow className=" w-full bg-gray-100 font-semibold">
              <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pckt</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Rate</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Making</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Value</TableCell>


            </TableRow>
            <TableRow className=" w-full bg-orange-100">

              <TableCell className="w-28 px-4 py-2 border">

                <Input type="text" list="item_list" {...register(`form.item`, {
                  onChange: e => {
                    mainItemData.find((item) => {
                      if (item.short_code === e.target.value) {
                        setValue('form.item_name', item.item_name);
                      }
                    }
                    )
                  }
                })} />
                <datalist id="item_list">
                  {mainItemData.map((item, index) => (
                    <option key={index} value={item.short_code}  ></option>
                  ))}
                </datalist>
                <span className="text-slate-500 text-nowrap text-xs font-medium">
                  {item_name}
                </span> </TableCell>
              <TableCell className="w-28 px-4 py-2 border"></TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="text" {...register(`form.pcs`)} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border"></TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register(`form.gw`)} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border"></TableCell>
              <TableCell className="w-28 px-4 py-2 border">{making}</TableCell>
              <TableCell className="w-28 px-4 py-2 border"></TableCell>


            </TableRow>
            {fields.map((field, index) =>
              <TableRow>

                <TableCell className="w-28 px-4 py-2 border">
                  {field.item_name}

                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  {field.packet}
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="text" {...register(`form.barcodedetails_set.${index}.pcs`)} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="text" {...register(`form.barcodedetails_set.${index}.ct`)} 
                   />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="text" {...register(`form.barcodedetails_set.${index}.gw`)} />
                </TableCell>

                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register(`form.barcodedetails_set.${index}.rate`, { onChange: () => handleEditRate(index) })} />
                </TableCell>
                <TableCell className="w-28 px-4 py-2 border"></TableCell>

                <TableCell className="w-28 px-4 py-2 border">
                  <Input onKeyDown={(e) => handleKeyDown(e)} type="text" {...register(`form.barcodedetails_set.${index}.amt`)} />
                </TableCell>
              </TableRow>)
            }





          </TableBody>
        </Table>



        {/* Submit */}
        <div className="flex justify-center mt-5">
          <Button type="submit" className="mr-4">
            Save
          </Button>
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
        </div>
      </form>
    </div>
  );
};

export default BarcodeManagementList;
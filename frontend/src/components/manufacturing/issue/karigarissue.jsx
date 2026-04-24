import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { fetchMainItem, fetchSlipNoNext, fetchSalesperson, fetchPurity, getLedgers, createKarigarIssue, fetchCustomerOrders, fetchSlNosOrders, fetchOrderItem, fetchPos, fetchPendingCustomerOrderItems, } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils.jsx"
import { useNavigate } from "react-router-dom";
import { convertBarcode, fetchBarcodes, fetchKarigarIssueForEdit, fetchUnBarcodedList, updateKarigarIssue } from "../../../services/apiService";

import { default as MulSelect } from "react-select";
import { SquarePen, Trash2, ShoppingCart } from "lucide-react";
import { selectRowsFn } from "@tanstack/react-table";
import { renderErrorTree } from "../../../Utils";
import Fuse from 'fuse.js';
import { useSpellCheck } from '@/hooks/useSpellCheck';


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
  const spellCheckEnabled = useSpellCheck();
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
  const [pendingItems, setPendingItems] = useState([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [pickerSearch, setPickerSearch] = useState("");
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
      const [customers, orderNo, mainItem, purity, customerOrders, karigars, unb, barcodes, pending] = await Promise.all([
        getLedgers({ type: "KR" }),
        fetchSlipNoNext(),
        fetchMainItem(),
        fetchPurity(),
        fetchCustomerOrders(),
        fetchPos("Job Order"),
        fetchUnBarcodedList(),
        fetchBarcodes(),
        fetchPendingCustomerOrderItems(),
      ]);
      if (customers.success) setCustomers(customers.data.results);
      if (orderNo.success) setValue("form.issue_slip_no", orderNo.data.next_slip_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
      if (customerOrders.success) setCustomerOrders(customerOrders.data.results);
      if (karigars.success) setKarigars(karigars.data.results);
      if (unb.success) setUnbarcodedList(transformData(unb.data.results,'label'));
      if (barcodes.success) setBarcodes(barcodes.data.results);
      if (pending.success) setPendingItems(pending.data);
      
      
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
    data.items = rs.map(({ _co_display, ...rest }) => rest);
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
    setRows((prev) => {
      const removed = prev[index];
      if (removed && removed.customer_order_item && removed._co_display) {
        setPendingItems((pi) => [
          ...pi,
          {
            co_item_id: removed.customer_order_item,
            co_id: removed._co_display.co_id ?? null,
            co_no: removed._co_display.co_no,
            co_date: removed._co_display.co_date ?? null,
            customer_name: removed._co_display.customer_name,
            sl_no: removed._co_display.sl_no,
            item: removed.item ?? null,
            item_name: removed._co_display.item_name ?? null,
            purity: removed.purity ?? null,
            pcs: removed.pcs ?? null,
            approx_wt: removed.approx_wt ?? null,
            size: removed.size ?? null,
            due_date: removed.due_date ?? null,
            remarks: removed.remarks ?? null,
          },
        ]);
      }
      return prev.filter((_, i) => i !== index);
    });
  };

  const toggleSelect = (pid) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid); else next.add(pid);
      return next;
    });
  };

  const filteredPending = pendingItems.filter((p) => {
    if (!pickerSearch) return true;
    const q = pickerSearch.toLowerCase();
    return (
      (p.customer_name || "").toLowerCase().includes(q) ||
      (p.co_no || "").toLowerCase().includes(q) ||
      (p.item || "").toLowerCase().includes(q) ||
      (p.item_name || "").toLowerCase().includes(q)
    );
  });

  const addSelectedPending = () => {
    const picked = pendingItems.filter((p) => selectedIds.has(p.co_item_id));
    if (picked.length === 0) { setPickerOpen(false); return; }
    setRows((prev) => {
      const base = prev.length;
      const newRows = picked.map((p, idx) => ({
        issue_sl_no: base + idx + 1,
        design_code: "",
        item: p.item ?? "",
        purity: p.purity ?? "",
        issued_sample_items: [],
        pcs: p.pcs ?? "",
        approx_wt: p.approx_wt ?? "",
        size: p.size ?? "",
        due_date: p.due_date ?? "",
        remarks: p.remarks ?? "",
        customer_order_item: p.co_item_id,
        _co_display: {
          co_id: p.co_id,
          co_no: p.co_no,
          co_date: p.co_date,
          sl_no: p.sl_no,
          customer_name: p.customer_name,
          item_name: p.item_name,
        },
      }));
      return [...prev, ...newRows];
    });
    setPendingItems((prev) => prev.filter((p) => !selectedIds.has(p.co_item_id)));
    setSelectedIds(new Set());
    setPickerSearch("");
    setPickerOpen(false);
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
      // Sample items moved to the dedicated Sample Issue form — no longer captured here.
      table.issued_sample_items = [];
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
                  toast({ title: "Converted to unbarcoded" });
                  // Refresh the unbarcoded list inline instead of reloading the page.
                  const list = await fetchUnBarcodedList({});
                  if (list.success) {
                    setUnbarcodedList((list.data.results || list.data || []).map(
                      (u) => ({ value: u.id, label: `${u.item_desc || ''} — ${u.gw}g` })
                    ));
                  }
                } else {
                  toast({ title: "Convert failed", description: JSON.stringify(response.error), variant: "destructive" });
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
            <SearchableComboBox
              options={customers}
              value={watch("form.karigar_ldgr_name") ?? ""}
              onSelect={(opt) => {
                setValue("form.karigar_ldgr_name", opt.ac_name)
                setValue("form.karigar_ldgr", opt.id)
              }}
              placeholder="Search karigar…"
            />
            <input type="hidden" {...register("form.karigar_ldgr")} />
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
        <div className="flex items-center justify-between my-3">
          <h6 className="text-lg font-semibold">Order Item Detail</h6>
          {slip_type === "Customer Order" && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPickerOpen(true)}
              className="cursor-pointer h-8 px-3 text-xs gap-1.5"
            >
              <ShoppingCart className="size-3.5" />
              Pick from Customer Orders
              {pendingItems.length > 0 && (
                <span className="inline-flex items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-semibold px-1.5 min-w-4 h-4">
                  {pendingItems.length}
                </span>
              )}
            </Button>
          )}
        </div>
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-20 px-4 py-2 border">Option</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Design No</TableCell>
              <TableCell className="w-32 px-4 py-2 border">Main Item</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Purity</TableCell>
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
{/* Sample-issue picker moved to the dedicated Sample Issue form. */}
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
                    <SquarePen className="size-4 mr-1 cursor-pointer" onClick={() => handleEdit(index)} />

                    <Trash2 color="#d45959" className="size-4 mr-1 cursor-pointer" onClick={() => handleDelete(index)} />
                  </div>
                </TableCell>
                <TableCell className="w-32 px-4 py-2 border"> {row.design_code}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">
                  {row.item}
                </TableCell>
                <TableCell className="w-20 px-4 py-2 border">{row.purity}</TableCell>
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

      {/* Customer Order Picker Modal */}
      <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Pending Customer Order Items</DialogTitle>
          </DialogHeader>

          <Input
            placeholder="Search customer, CO #, item…"
            value={pickerSearch}
            onChange={(e) => setPickerSearch(e.target.value)}
            className="mb-1"
          />

          <div className="max-h-[55vh] overflow-auto rounded-md border border-border">
            {filteredPending.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No pending customer-order items.
              </div>
            ) : (
              <Table className="w-full text-sm">
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="w-10 px-2 py-2" />
                    <TableHead className="px-3 py-2">CO Date</TableHead>
                    <TableHead className="px-3 py-2">Customer</TableHead>
                    <TableHead className="px-3 py-2">CO #</TableHead>
                    <TableHead className="px-3 py-2 w-12">Sl</TableHead>
                    <TableHead className="px-3 py-2">Item</TableHead>
                    <TableHead className="px-3 py-2">Purity</TableHead>
                    <TableHead className="px-3 py-2 text-right">Pcs</TableHead>
                    <TableHead className="px-3 py-2 text-right">Approx Wt</TableHead>
                    <TableHead className="px-3 py-2">Size</TableHead>
                    <TableHead className="px-3 py-2">Due</TableHead>
                    <TableHead className="px-3 py-2">Remarks</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPending.map((p) => (
                    <TableRow
                      key={p.co_item_id}
                      className={`odd:bg-muted/10 cursor-pointer transition-colors duration-100 ${selectedIds.has(p.co_item_id) ? "bg-primary/5 hover:bg-primary/10" : "hover:bg-muted/20"}`}
                      onClick={() => toggleSelect(p.co_item_id)}
                    >
                      <TableCell className="px-2 py-2">
                        <Checkbox
                          checked={selectedIds.has(p.co_item_id)}
                          onCheckedChange={() => toggleSelect(p.co_item_id)}
                          onClick={(e) => e.stopPropagation()}
                          className="cursor-pointer"
                        />
                      </TableCell>
                      <TableCell className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{p.co_date || "—"}</TableCell>
                      <TableCell className="px-3 py-2 font-medium">{p.customer_name || "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-xs font-mono">{p.co_no || "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-center">{p.sl_no}</TableCell>
                      <TableCell className="px-3 py-2 font-medium">{p.item_name || p.item || "—"}</TableCell>
                      <TableCell className="px-3 py-2">{p.purity || "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-right tabular-nums">{p.pcs ?? "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-right tabular-nums">{p.approx_wt ?? "—"}</TableCell>
                      <TableCell className="px-3 py-2">{p.size || "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-xs whitespace-nowrap">{p.due_date || "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-muted-foreground">{p.remarks || "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>

          <DialogFooter className="flex items-center justify-between sm:justify-between mt-1">
            <span className="text-sm text-muted-foreground">
              {selectedIds.size > 0
                ? `${selectedIds.size} item${selectedIds.size !== 1 ? "s" : ""} selected`
                : "Click rows to select"}
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                className="cursor-pointer"
                onClick={() => { setPickerOpen(false); setSelectedIds(new Set()); }}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={addSelectedPending}
                disabled={selectedIds.size === 0}
                className="cursor-pointer"
              >
                Add Selected
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default KarigarIssue;

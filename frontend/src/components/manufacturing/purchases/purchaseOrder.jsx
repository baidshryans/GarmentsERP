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
import { fetchMainItem, fetchNextStoneBillNo, fetchPurity, fetchPackets, getLedgers, createKarigarStoneIssue, createPurchaseOrder, fetchPendingCustomerOrderItems } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchPoNoNext, fetchPurchaseOrderForEdit, updatePurchaseOrderForEdit } from "../../../services/apiService";
import { SquarePen, Trash2, ChevronRight, ShoppingCart } from "lucide-react";
import { arrayToObject, renderErrorTree } from "../../../Utils";
import { useNavigate } from "react-router";

/* ─── helpers ──────────────────────────────────────────────── */
function SectionCard({ title, children, className = "", action }) {
  return (
    <div className={`bg-white border border-border rounded-xl shadow-sm ${className}`}>
      <div className="px-5 py-3 border-b border-border bg-muted/20 flex items-center justify-between rounded-t-xl">
        <div className="flex items-center gap-2">
          <span className="w-0.5 h-4 rounded-full bg-primary inline-block" />
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{title}</h3>
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Field({ label, required, children, className = "" }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <Label className="text-xs font-medium text-muted-foreground">
        {label}{required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
    </div>
  );
}

/* ─── component ────────────────────────────────────────────── */
const PurchaseOrder = () => {
  const { toast } = useToast()
  const { id } = useParams()
  const { register, handleSubmit, control, reset, watch, setValue, getValues, setFocus } = useForm({
    defaultValues: {
      form: {
        place_of_supply: "WB",
        table: { sgst: 0, igst: 0, cgst: 0, ct: 0, gw: 0 },
        date1: new Date().toISOString().split("T")[0],
      }
    },
  });

  const tableDefaultValue = {
    slno: "", design_no: "", main_item: "", purity: "",
    pcs: "", approx_wt: "", size: "", due_date: "", remarks: "",
  };

  const navigate = useNavigate();
  const [rs, setRows] = useState([]);
const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [packets, setPackets] = useState([]);
  const [pendingItems, setPendingItems] = useState([]);
  const po_type = watch("form.po_type");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [pickerSearch, setPickerSearch] = useState("");

useEffect(() => {
    async function fetchData() {
      const [pkts, customersRes, orderNo, mainItem, purity, pending] = await Promise.all([
        fetchPackets(),
        getLedgers({ type: "VD" }),
        fetchPoNoNext(),
        fetchMainItem(),
        fetchPurity(),
        fetchPendingCustomerOrderItems(),
      ]);
      if (pkts.success) setPackets(pkts.data.results);
      if (customersRes.success) setCustomers(customersRes.data.results);
      if (orderNo.success) setValue("form.po_no", orderNo.data.billno);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
      if (pending.success) setPendingItems(pending.data);
    }
    fetchData().then(() => {
      if (id) {
        fetchPurchaseOrderForEdit(id)
          .then((response) => {
            Object.keys(response.data).forEach((key) => {
              setValue(`form.${key}`, response.data[key]);
            });
            if (response.data.purchaseorderitems_set) {
              setRows(response.data.purchaseorderitems_set);
            }
          })
          .catch((error) => console.error('Error fetching purchase order:', error));
      }
    });
  }, []);

  const onSubmit = (data) => {
    const dat = getValues('form');
    dat.purchaseorderitems_set = rs.map(({ _co_display, ...rest }) => rest);
    if (!dat.ldgr) {
      toast({ title: "Please select a vendor from the list.", variant: "destructive" });
      return;
    }
    if (rs.length === 0) {
      toast({ title: "Add at least one item." });
      return;
    }
    (id ? updatePurchaseOrderForEdit(dat, id) : createPurchaseOrder(dat))
      .then((response) => {
        if (response.success) {
          toast({ title: "Purchase order saved!" });
          setTimeout(() => navigate("/purchase/purchaseorder/list/"), 2000);
        } else {
          toast({
            title: "Save failed",
            description: renderErrorTree(response.error),
            variant: "destructive",
          });
        }
      })
      .catch(() => toast({ title: "An error occurred. Please try again later.", variant: "destructive" }));
  };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    const row = rs[index];
    reset({ form: getValues('form'), table: row });
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

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

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
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
        po_sl_no: base + idx + 1,
        design_code: "",
        item: p.item ?? "",
        purity: p.purity ?? "",
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

  const handleKeyDown = (e) => {
    if (e.key !== "Tab") return;
    const table = getValues("table");
    setRows([...rs, { ...table }]);
    reset({ form: { ...getValues('form') }, table: { ...tableDefaultValue } });
    setFocus('table.po_sl_no');
  };

  /* ─── render ─────────────────────────────────────────────── */
  return (
    <div className="w-[70%] mx-auto px-4 py-6 space-y-4">

      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <button
          type="button"
          onClick={() => navigate("/purchase/purchaseorder/list/")}
          className="hover:text-foreground transition-colors cursor-pointer"
        >
          Purchase Orders
        </button>
        <ChevronRight className="size-3" />
        <span className="text-foreground font-medium">
          {id ? watch("form.po_no") || "Edit Order" : "New Order"}
        </span>
      </div>

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground tracking-tight">
            {id ? "Edit Purchase Order" : "New Purchase Order"}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {id ? "Update order details and items below" : "Fill in the details to raise a new purchase order"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => window.history.back()}
            className="cursor-pointer"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit(onSubmit)}
            className="min-w-24 cursor-pointer"
          >
            Save Order
          </Button>
        </div>
      </div>

      <form id="orderForm" onSubmit={handleSubmit(onSubmit)} className="space-y-4">

        {/* ── Card 1: Order Reference ── */}
        <SectionCard title="Order Reference">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
            <Field label="PO No">
              <span className="inline-flex items-center px-3 h-9 rounded-md bg-primary/5 border border-primary/20 text-primary text-sm font-semibold truncate">
                {watch("form.po_no") || (
                  <span className="text-primary/50 text-xs font-normal">Auto-generating…</span>
                )}
              </span>
              <input type="hidden" {...register("form.po_no")} />
            </Field>

            <Field label="Date" required>
              <Input type="date" tabIndex={1} {...register("form.date1")} required />
            </Field>

            <Field label="PO Type">
              <Controller
                name="form.po_type"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger className="cursor-pointer" tabIndex={2}>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Customer Order">Customer Order</SelectItem>
                      <SelectItem value="Stock">Stock</SelectItem>
                      <SelectItem value="Repair">Repair</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>

            <Field label="Vendor">
              <SearchableComboBox
                options={customers}
                value={watch("form.ldgr_name") ?? ""}
                onSelect={(opt) => {
                  setValue("form.ldgr_name", opt.ac_name);
                  setValue("form.ldgr", opt.id);
                }}
                placeholder="Search vendor…"
                tabIndex={3}
              />
              <input type="hidden" {...register("form.ldgr")} />
            </Field>
          </div>
        </SectionCard>

        {/* ── Card 3: Item Details ── */}
        <SectionCard
          title="Item Details"
          action={
            <div className="flex items-center gap-3">
              {rs.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {rs.length} item{rs.length !== 1 ? "s" : ""}
                </span>
              )}
              {po_type === "Customer Order" && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPickerOpen(true)}
                  className="cursor-pointer h-7 px-2.5 text-xs gap-1.5"
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
          }
        >
          <div className="overflow-x-auto rounded-md border border-border">
            <Table className="w-full text-sm min-w-[900px]">
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  {["", "Sl No", "Design No", "Main Item", "Purity", "Pcs", "Approx Wt", "Size", "Due Date", "Remarks"].map((h, i) => (
                    <TableHead key={i} className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap first:w-16">
                      {h}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>

              <TableBody>
                {/* ── Input row ── */}
                <TableRow className="bg-primary/[0.03] border-b-2 border-primary/10 align-top">
                  <TableCell className="px-3 py-2 w-16" />
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="number" className="h-8 text-sm" tabIndex={4} {...register("table.po_sl_no")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-24">
                    <Input type="number" className="h-8 text-sm" tabIndex={5} {...register("table.design_code")} />
                  </TableCell>
                  <TableCell className="px-2 py-2">
                    <Input
                      list="item_list"
                      className="h-8 text-sm"
                      placeholder="Search item…"
                      tabIndex={6}
                      {...register("table.item")}
                    />
                    <datalist id="item_list">
                      {mainItemData.map((item, i) => (
                        <option key={i} value={item.short_code}>{item.item_name}</option>
                      ))}
                    </datalist>
                  </TableCell>
                  <TableCell className="px-2 py-2 w-28">
                    <Controller
                      name="table.purity"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value}>
                          <SelectTrigger className="h-8 text-sm cursor-pointer" tabIndex={7}>
                            <SelectValue placeholder="Purity" />
                          </SelectTrigger>
                          <SelectContent>
                            {purityData.map((item, i) => (
                              <SelectItem key={i} value={`${item.purity}`}>{item.purity}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="number" className="h-8 text-sm" tabIndex={8} {...register("table.pcs")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-24">
                    <Input type="number" className="h-8 text-sm" tabIndex={9} {...register("table.approx_wt")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="number" className="h-8 text-sm" tabIndex={10} {...register("table.size")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-32">
                    <Input type="date" className="h-8 text-sm" tabIndex={11} {...register("table.due_date")} />
                  </TableCell>
                  <TableCell className="px-2 py-2">
                    <Input
                      type="text"
                      className="h-8 text-sm"
                      placeholder="Remarks — Tab↹ to add"
                      tabIndex={12}
                      onKeyDown={handleKeyDown}
                      {...register("table.remarks")}
                    />
                  </TableCell>
                </TableRow>

                {/* ── Data rows ── */}
                {rs.map((row, index) => (
                  <TableRow key={index} className="hover:bg-muted/20 transition-colors duration-150">
                    <TableCell className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => handleEdit(index)}
                          className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors duration-150 cursor-pointer"
                          title="Edit"
                        >
                          <SquarePen className="size-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(index)}
                          className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors duration-150 cursor-pointer"
                          title="Delete"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-2 text-sm tabular-nums">
                      {row._co_display ? (
                        <div>
                          <span className="text-[10px] text-muted-foreground block leading-tight">
                            CO# {row._co_display.co_no} · Sl {row._co_display.sl_no}
                          </span>
                          <span className="font-medium">{row.po_sl_no}</span>
                        </div>
                      ) : row.po_sl_no}
                    </TableCell>
                    <TableCell className="px-3 py-2 text-sm tabular-nums">{row.design_code}</TableCell>
                    <TableCell className="px-3 py-2">
                      <span className="text-sm font-medium text-foreground">
                        {row._co_display?.item_name || row.item}
                      </span>
                      {row._co_display?.item_name && row.item && (
                        <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{row.item}</p>
                      )}
                    </TableCell>
                    <TableCell className="px-3 py-2 text-sm">{row.purity}</TableCell>
                    <TableCell className="px-3 py-2 text-sm tabular-nums text-right">{row.pcs}</TableCell>
                    <TableCell className="px-3 py-2 text-sm tabular-nums text-right">{row.approx_wt}</TableCell>
                    <TableCell className="px-3 py-2 text-sm tabular-nums">{row.size}</TableCell>
                    <TableCell className="px-3 py-2 text-sm">{row.due_date}</TableCell>
                    <TableCell className="px-3 py-2 text-sm text-muted-foreground">{row.remarks}</TableCell>
                  </TableRow>
                ))}

                {rs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={10} className="text-center py-10 text-muted-foreground text-sm">
                      <div className="flex flex-col items-center gap-1.5">
                        <span>No items added yet</span>
                        <span className="text-xs">
                          Fill the row above and press{" "}
                          <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-[10px] font-mono">Tab</kbd>{" "}
                          to add, or pick from Customer Orders above
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </SectionCard>

        {/* ── Bottom action bar ── */}
        <div className="flex items-center justify-end gap-2 pt-1 pb-6">
          <Button
            type="button"
            variant="outline"
            onClick={() => window.history.back()}
            className="cursor-pointer"
          >
            Cancel
          </Button>
          <Button type="submit" className="min-w-28 cursor-pointer">
            Save Order
          </Button>
        </div>
      </form>

      {/* ── Customer Order Picker Modal ── */}
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

export default PurchaseOrder;

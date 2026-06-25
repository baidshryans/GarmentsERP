import React, { useEffect, useState, useRef } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { fetchMainItem, fetchSlipNoNext, fetchPurity, getLedgers, createKarigarIssue, fetchPos, fetchPendingCustomerOrderItems, } from "@/services/apiService";
import { useParams, useSearchParams } from "react-router-dom";
import { FieldContainer } from "@/Utils.jsx"
import { useNavigate } from "react-router-dom";
import { fetchKarigarIssueForEdit, updateKarigarIssue } from "../../../services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";
import { SquarePen, Trash2, ShoppingCart, ChevronRight } from "lucide-react";
import { renderErrorTree } from "../../../Utils";

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


const KarigarIssue = () => {
  const { id } = useParams();
  const { toast } = useToast()
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();
  const { register, handleSubmit, control, reset, watch, setValue, getValues , setFocus, formState: { isDirty } } = useForm({
    defaultValues: {
      form: {
        issue_slip_type: 'Stock',
        date1: new Date().toISOString().split("T")[0],
      }

    },
  });
  const [karigars, setKarigars] = useState([]);
  const [rs, setRows] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [tableItemLabel, setTableItemLabel] = useState("");
  const itemComboRef = useRef(null);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [pendingItems, setPendingItems] = useState([]);
  const [saving, setSaving] = useState(false);
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [pickerSearch, setPickerSearch] = useState("");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const prefillCoId = !id ? searchParams.get("co") : null;
  // Optional explicit subset of CO item IDs picked via the quick-action modal
  // on the Customer Order list. When present, only these items are pre-loaded.
  const prefillItemIdsParam = !id ? searchParams.get("items") : null;
  const prefillItemIds = prefillItemIdsParam
    ? new Set(prefillItemIdsParam.split(",").map(s => Number(s.trim())).filter(n => !Number.isNaN(n)))
    : null;

  const tableDefaultValue = {
    design_code: "",
    item: "",
    purity: "", // or a default purity value like "916" if needed
    pcs: "", // or 0 if you prefer numeric defaults
    approx_wt: "", // or 0
    size: "",
    due_date: "", // in "YYYY-MM-DD" format if a default is needed
    remarks: "",
  }

  useEffect(() => {
    async function fetchData() {
      const [customers, orderNo, mainItem, purity, karigars, pending] = await Promise.all([
        getLedgers({ type: "KR" }),
        fetchSlipNoNext(),
        fetchMainItem({ type: "M" }),
        fetchPurity(),
        fetchPos("Job Order"),
        fetchPendingCustomerOrderItems(),
      ]);
      if (customers.success) setCustomers(customers.data.results);
      if (orderNo.success) setValue("form.issue_slip_no", orderNo.data.next_slip_no);
      if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
      if (purity.success) setPurityData(purity.data.results ?? purity.data);
      if (karigars.success) setKarigars(karigars.data.results);
      if (pending.success) {
        // If opened via +MO quick-action from a Customer Order row, auto-pull that
        // order's pending items into the grid and remove them from the picker list.
        if (prefillCoId) {
          const coIdNum = Number(prefillCoId);
          const picked = (pending.data || []).filter(p =>
            Number(p.co_id) === coIdNum &&
            (!prefillItemIds || prefillItemIds.has(Number(p.co_item_id)))
          );
          if (picked.length > 0) {
            setValue("form.issue_slip_type", "Customer Order");
            const newRows = picked.map((p, idx) => ({
              issue_sl_no: idx + 1,
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
            setRows(newRows);
            const pickedIds = new Set(picked.map(p => p.co_item_id));
            setPendingItems((pending.data || []).filter(p => !pickedIds.has(p.co_item_id)));
          } else {
            setPendingItems(pending.data);
            toast({ title: "No pending items", description: "This customer order has no items left to allocate." });
          }
        } else {
          setPendingItems(pending.data);
        }
      }


    }
    fetchData().then(() => {
      // Consume-and-clear the ?co= / ?items= prefill params so a refresh won't
      // re-populate rows the user may have since deleted.
      if (prefillCoId || prefillItemIdsParam) {
        setSearchParams({}, { replace: true });
      }
    });

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
          reset(getValues(), { keepValues: true, keepDirty: false });
          resetTableDirty();
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


    setSaving(true);
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
          setSaving(false);
          toast({
            title: "Form submission failed. Please try again.",
            description: renderErrorTree(response.error),
          });  // Error toast
        }
      })
      .catch((error) => {
        setSaving(false);
        console.error("Error submitting form:", error);
        toast({ title: "An error occurred. Please try again later." });
      });
  };

  useF4Submit(handleSubmit(onSubmit));

  // Preserve CO-linkage fields while the user edits a CO-sourced row.
  const editingMetaRef = useRef(null);

  const handleEdit = (index) => {
    const row = rs[index];
    editingMetaRef.current = row.customer_order_item
      ? { customer_order_item: row.customer_order_item, _co_display: row._co_display }
      : null;
    reset({ form: getValues('form'), table: row });
    const match = mainItemData.find(i => i.short_code === row.item);
    setTableItemLabel(match ? match.item_name : (row.item ?? ""));
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
    setTimeout(() => itemComboRef.current?.querySelector('input')?.focus(), 0);
  };

  const handleDelete = (index) => {
    markTableDirty();
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
    const existingCoItemIds = new Set(rs.map(r => r.customer_order_item).filter(Boolean));
    const picked = pendingItems
      .filter((p) => selectedIds.has(p.co_item_id))
      .filter((p) => !existingCoItemIds.has(p.co_item_id));
    if (picked.length === 0) { setPickerOpen(false); return; }
    markTableDirty();
    setRows((prev) => {
      const base = prev.length;
      const newRows = picked.map((p, idx) => ({
        issue_sl_no: base + idx + 1,
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


    if (e.key === "Tab") {
      e.preventDefault()
      const table = getValues("table");
      // Re-attach CO-linkage if this is an edit-cycle add-back.
      const merged = editingMetaRef.current ? { ...table, ...editingMetaRef.current } : table;

      // Require item, purity, and pcs — remarks is optional
      if (!merged.item) {
        toast({ title: "Main Item is required", variant: "destructive" });
        return;
      }
      if (!merged.purity) {
        toast({ title: "Purity is required", variant: "destructive" });
        return;
      }
      if (!merged.pcs && merged.pcs !== 0) {
        toast({ title: "Pcs is required", variant: "destructive" });
        return;
      }

      // Block duplicate CO items — the same customer_order_item must not appear twice.
      if (merged.customer_order_item && rs.some(r => r.customer_order_item === merged.customer_order_item)) {
        toast({
          title: "Item already in this job work",
          description: "This customer-order item is already on the grid. Edit the existing row instead.",
          variant: "destructive",
        });
        return;
      }
      const issue_sl_no = rs.length + 1
      const rowVals = {
        issue_sl_no,
        ...merged,
      }
      setRows([...rs, rowVals])
      markTableDirty();
      editingMetaRef.current = null;
      setTableItemLabel("");
      reset({form:{...getValues('form')},table:{...tableDefaultValue}})
      setFocus('table.design_code')



    }
  };

  return (
    <div className="w-[96%] max-w-[1500px] mx-auto px-4 py-6 space-y-4">

      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <button
          type="button"
          onClick={() => navigate("/manufacturing/issue/jobwork")}
          className="hover:text-foreground transition-colors cursor-pointer"
        >
          Karigar Job Work
        </button>
        <ChevronRight className="size-3" />
        <span className="text-foreground font-medium">
          {id ? watch("form.issue_slip_no") || "Edit Job Work" : "New Job Work"}
        </span>
      </div>

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground tracking-tight">
            {id ? "Edit Karigar Job Work" : "New Karigar Job Work"}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {id ? "Update job work details and items below" : "Fill in the details to raise a new karigar job work"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.history.back()} className="cursor-pointer">
            Cancel
          </Button>
          <Button size="sm" onClick={handleSubmit(onSubmit)} className="min-w-24 cursor-pointer" disabled={saving || !canSave}>
            {saving ? (id ? "Updating…" : "Saving…") : (id ? "Update Job Work" : "Save Job Work")}
          </Button>
        </div>
      </div>

      <form id="orderForm" onSubmit={handleSubmit(onSubmit)} className="space-y-4">

        {/* Card 1: Job Work Reference */}
        <SectionCard title="Job Work Reference">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">

            <Field label="Date" required>
              <Input type="date" min={fyMin} max={fyMax} {...register("form.date1")} required />
            </Field>

            <Field label="Slip No">
              <span className="inline-flex items-center px-3 h-9 rounded-md bg-primary/5 border border-primary/20 text-primary text-sm font-semibold truncate">
                {watch("form.issue_slip_no") || <span className="text-primary/50 text-xs font-normal">Auto-generating…</span>}
              </span>
              <input type="hidden" {...register("form.issue_slip_no")} />
            </Field>

            <Field label="Slip Type">
              <Controller
                name="form.issue_slip_type"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value} disabled={rs.length > 0}>
                    <SelectTrigger
                      className={`cursor-pointer ${rs.length > 0 ? 'opacity-70 cursor-not-allowed' : ''}`}
                      title={rs.length > 0 ? 'Slip Type is locked because items have been added. Remove all items to change it.' : undefined}
                    >
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
              {rs.length > 0 && (
                <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">Locked — remove all items to change type.</p>
              )}
            </Field>

            <Field label="Karigar Name" required>
              <SearchableComboBox
                options={customers}
                value={watch("form.karigar_ldgr_name") ?? ""}
                onSelect={(opt) => {
                  setValue("form.karigar_ldgr_name", opt.ac_name);
                  setValue("form.karigar_ldgr", opt.id);
                }}
                placeholder="Search karigar…"
                autoFocus={!id}
              />
              <input type="hidden" {...register("form.karigar_ldgr")} />
            </Field>

          </div>
        </SectionCard>

        {/* Card 2: Item Details */}
        <SectionCard
          title="Item Details"
          action={
            <div className="flex items-center gap-3">
              {rs.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {rs.length} item{rs.length !== 1 ? "s" : ""}
                </span>
              )}
              {slip_type === "Customer Order" && (
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
            <Table className="w-full text-sm min-w-[1100px]">
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
                {/* Input row */}
                <TableRow className="bg-primary/[0.03] border-b-2 border-primary/10 align-top">
                  <TableCell className="px-3 py-2 w-16" />
                  <TableCell className="px-2 py-2 w-16 align-middle text-xs text-muted-foreground italic">auto</TableCell>
                  <TableCell className="px-2 py-2 w-28">
                    <Input type="text" className="h-8 text-sm" {...register("table.design_code")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 min-w-[200px]">
                    <input type="hidden" {...register("table.item")} />
                    <div ref={itemComboRef}>
                      <SearchableComboBox
                        options={mainItemData}
                        labelKey="item_name"
                        searchKeys={["short_code"]}
                        value={tableItemLabel}
                        onSelect={(opt) => {
                          setValue("table.item", opt.short_code);
                          setTableItemLabel(opt.item_name);
                        }}
                        placeholder="Search item…"
                        className="h-8 text-sm"
                      />
                    </div>
                  </TableCell>
                  <TableCell className="px-2 py-2 w-28">
                    <Controller
                      name="table.purity"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value}>
                          <SelectTrigger className="h-8 text-sm cursor-pointer">
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
                    <Input type="number" className="h-8 text-sm" {...register("table.pcs")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-28">
                    <Input type="number" className="h-8 text-sm" {...register("table.approx_wt")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="text" className="h-8 text-sm" {...register("table.size")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-32">
                    <Input type="date" className="h-8 text-sm" {...register("table.due_date")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-32">
                    <Input type="text" className="h-8 text-sm" onKeyDown={(e) => handleKeyDown(e)} {...register("table.remarks")} />
                  </TableCell>
                </TableRow>

                {/* Data rows */}
                {rs.map((row, index) => (
                  <TableRow key={index} className="odd:bg-muted/10 hover:bg-muted/20 transition-colors">
                    <TableCell className="px-3 py-2">
                      <div className="flex gap-2">
                        <SquarePen className="size-4 cursor-pointer text-muted-foreground hover:text-foreground" onClick={() => handleEdit(index)} />
                        <Trash2 className="size-4 cursor-pointer text-destructive/70 hover:text-destructive" onClick={() => handleDelete(index)} />
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-2 font-semibold tabular-nums">{row.issue_sl_no ?? index + 1}</TableCell>
                    <TableCell className="px-3 py-2">{row.design_code || <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="px-3 py-2">
                      {row.item
                        ? (mainItemData.find(i => i.short_code === row.item)?.item_name ?? row.item)
                        : <span className="text-muted-foreground">—</span>}
                    </TableCell>
                    <TableCell className="px-3 py-2">{row.purity || <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="px-3 py-2 tabular-nums">{row.pcs ?? <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="px-3 py-2 tabular-nums">{row.approx_wt ?? <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="px-3 py-2">{row.size || <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="px-3 py-2">{row.due_date || <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className="px-3 py-2 text-muted-foreground">{row.remarks || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </SectionCard>

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

import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableBody, TableHead, TableHeader } from "@/components/ui/table";
import {
  fetchMainItem, fetchOrderNoNext, fetchSalesperson,
  fetchPurity, getLedgers, createCustomerOrder,
} from "@/services/apiService";
import { Link, useParams, useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { fetchCustomerOrderForEdit, getGoldRate, updateCustomerOrderForEdit, cancelCustomerOrder } from "./services/apiService";
import { useEditDirty } from "@/hooks/useEditDirty";
import { SquarePen, Trash2, Loader2, Plus, Zap, Lock, ChevronRight } from "lucide-react";
import { arrayToObject } from "./Utils";
import { renderErrorTree } from "./Utils";
import { useF4Submit } from "@/hooks/useF4Submit";

/* ─── helpers ─────────────────────────────────────────────── */
function SectionCard({ title, children, className = "", action }) {
  return (
    <div className={`bg-white border border-border rounded-xl overflow-hidden shadow-sm ${className}`}>
      <div className="px-5 py-3 border-b border-border bg-muted/20 flex items-center justify-between">
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

const DELIVERY_STATUS_LABELS = {
  pending: { label: "Pending", className: "bg-amber-50 text-amber-700 border-amber-200" },
  partially_delivered: { label: "Partial", className: "bg-blue-50 text-blue-700 border-blue-200" },
  delivered: { label: "Delivered", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  cancelled: { label: "Cancelled", className: "bg-red-50 text-red-600 border-red-200" },
};

/* ─── component ────────────────────────────────────────────── */
const CustomerOrderForm = () => {
  const defaultTableValues = {
    item_id: "", item_name: "", purity: "", pcs: 0, gw: 0,
    making: "", making_type: "", other_chg: 0, size: "", remarks: "",
  };

  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const { register, setFocus, handleSubmit, control, reset, watch, setValue, getValues, formState: { isDirty } } = useForm({
    defaultValues: {
      form: {
        rate_14kt: 0, rate_18kt: 0, rate_22kt: 0,
        est_amount: 0,
        date1: new Date().toISOString().split("T")[0],
        fix_gold_rate: false, gold_rate_date: null,
        salesman_1: null, salesman_2: null,
        nature: "new_booking", delivery_status: "pending",
      },
      table: { ...defaultTableValues },
    },
  });

  const [rs, setRows] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [fetchingRates, setFetchingRates] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });

  const party_name    = watch("form.ldgr_code_name");
  const gold_rate_date = watch("form.gold_rate_date");
  const fix_gold_rate  = watch("form.fix_gold_rate");
  const delivery_status = watch("form.delivery_status");

  /* pre-fill customer when redirected back from the ledger add page */
  useEffect(() => {
    const ldgr     = searchParams.get("ldgr");
    const ldgrName = searchParams.get("ldgr_name");
    if (ldgr && ldgrName) {
      setValue("form.ldgr", ldgr);
      setValue("form.ldgr_code_name", ldgrName);
      setCustomers((prev) => {
        const already = prev.some((c) => String(c.id) === String(ldgr));
        return already ? prev : [{ id: ldgr, ac_name: ldgrName, mobile1: "" }, ...prev];
      });
    }
  }, []);

  useEffect(() => {
    getLedgers({ type: "CO", search: party_name }).then(r => {
      if (r.success) setCustomers(r.data.results ?? []);
    });
  }, [party_name]);

  useEffect(() => {
    if (!gold_rate_date) return;
    setFetchingRates(true);
    getGoldRate(gold_rate_date).then(response => {
      if (response.success && Array.isArray(response.data) && response.data.length > 0) {
        const dict = arrayToObject(response.data, 'purity_name', 'rate');
        setValue("form.rate_14kt", dict['14K'] ?? 0);
        setValue("form.rate_18kt", dict['18K'] ?? 0);
        setValue("form.rate_22kt", dict['22K'] ?? 0);
      }
    }).finally(() => setFetchingRates(false));
  }, [gold_rate_date]);

  useEffect(() => {
    Promise.all([
      getLedgers({ type: "CO" }),
      fetchSalesperson(),
      fetchOrderNoNext(),
      fetchMainItem({ type: "M" }),
      fetchPurity(),
    ]).then(([cust, sp, orderNo, items, purity]) => {
      if (cust.success)    setCustomers(Array.isArray(cust.data.results) ? cust.data.results : cust.data ?? []);
      if (sp.success)      setSalespersonData(Array.isArray(sp.data) ? sp.data : sp.data?.results ?? []);
      if (orderNo.success) setValue("form.order_no", orderNo.data.order_no);
      if (items.success)   setMainItemData(Array.isArray(items.data) ? items.data : items.data?.results ?? []);
      if (purity.success)  setPurityData(Array.isArray(purity.data) ? purity.data : purity.data?.results ?? []);

      if (id) {
        fetchCustomerOrderForEdit(id).then(data => {
          if (data.success) {
            Object.entries(data.data).forEach(([k, v]) => {
              if (k !== 'items') setValue(`form.${k}`, v);
            });
            setRows(JSON.parse(JSON.stringify(data.data.items)));
            reset(getValues(), { keepValues: true, keepDirty: false });
            resetTableDirty();
          }
        });
      }
    });
  }, []);

  const handleFixGoldRateChange = async (checked) => {
    setValue("form.fix_gold_rate", checked);
    if (checked) {
      setFetchingRates(true);
      try {
        const response = await getGoldRate("");
        if (response.success && Array.isArray(response.data) && response.data.length > 0) {
          const dict = arrayToObject(response.data, 'purity_name', 'rate');
          setValue("form.rate_14kt", dict['14K'] ?? 0);
          setValue("form.rate_18kt", dict['18K'] ?? 0);
          setValue("form.rate_22kt", dict['22K'] ?? 0);
          const latestDate = response.data[0]?.date1;
          if (latestDate) setValue("form.gold_rate_date", latestDate.split("T")[0]);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setFetchingRates(false);
      }
    } else {
      setValue("form.rate_14kt", 0);
      setValue("form.rate_18kt", 0);
      setValue("form.rate_22kt", 0);
      setValue("form.gold_rate_date", null);
    }
  };

  const onSubmit = () => {
    if (rs.length === 0) { toast({ title: "Add at least one item." }); return; }
    const data = getValues("form");
    delete data.advance_amt; delete data.advance_reconciled; delete data.advance_available;
    if (data.salesman_2 === "__none__") data.salesman_2 = null;
    data.items = [...rs];
    setSubmitting(true);
    (id ? updateCustomerOrderForEdit(data, id) : createCustomerOrder(data))
      .then(r => {
        if (r.success) {
          toast({ title: "Customer order saved!" });
          setTimeout(() => navigate("/sales/customerorder/list/"), 1500);
        } else {
          toast({ title: "Save failed", description: renderErrorTree(r.error), variant: "destructive" });
        }
      })
      .catch(() => toast({ title: "An error occurred.", variant: "destructive" }))
      .finally(() => setSubmitting(false));
  };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    reset({ form: getValues('form'), table: rs[index] });
    setRows(prev => prev.filter((_, i) => i !== index));
    markTableDirty();
  };
  const handleDelete = (index) => { setRows(prev => prev.filter((_, i) => i !== index)); markTableDirty(); };
  const handleKeyDown = (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const row = getValues("table");
    const code = (row.item_id ?? "").trim();
    const known = mainItemData.find(
      (it) => it.short_code === code || it.item_name === code
    );
    if (!known) {
      toast({
        title: "Unknown item",
        description: code
          ? `“${code}” is not in the item master. Please pick an item from the list.`
          : "Please select an item before adding the row.",
        variant: "destructive",
      });
      setFocus("table.item_id");
      return;
    }
    setRows([...rs, {
      sl_no: rs.length + 1,
      ...row,
      item_id: known.short_code,
      item_name: known.item_name,
    }]);
    markTableDirty();
    reset({ form: getValues('form'), table: defaultTableValues });
    setFocus("table.item_id");
  };

  const statusInfo = DELIVERY_STATUS_LABELS[delivery_status] ?? DELIVERY_STATUS_LABELS.pending;

  /* ─── render ─────────────────────────────────────────────── */
  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">

      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <button
          type="button"
          onClick={() => navigate("/sales/customerorder/list/")}
          className="hover:text-foreground transition-colors cursor-pointer"
        >
          Customer Orders
        </button>
        <ChevronRight className="size-3" />
        <span className="text-foreground font-medium">
          {id ? watch("form.order_no") || "Edit Order" : "New Order"}
        </span>
        {id && (
          <span className={`ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusInfo.className}`}>
            {statusInfo.label}
          </span>
        )}
      </div>

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground tracking-tight">
            {id ? "Edit Customer Order" : "New Customer Order"}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {id ? "Update order details and items below" : "Fill in the details to create a new order"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigate("/sales/customerorder/list/")}
            className="cursor-pointer"
          >
            Close
          </Button>
          <Button
            size="sm"
            disabled={submitting || !canSave}
            onClick={handleSubmit(onSubmit)}
            className="min-w-24 cursor-pointer"
          >
            {submitting
              ? <><Loader2 className="size-3.5 mr-1.5 animate-spin" />{id ? "Updating…" : "Saving…"}</>
              : (id ? "Update Order" : "Save Order")
            }
          </Button>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

        {/* ── Card 1: Order Reference ── */}
        <SectionCard title="Order Reference">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
            <Field label="Order No">
              <span className="inline-flex items-center px-3 h-9 rounded-md bg-primary/5 border border-primary/20 text-primary text-sm font-semibold truncate">
                {watch("form.order_no") || (
                  <span className="text-primary/50 text-xs font-normal">Auto-generating…</span>
                )}
              </span>
              <input type="hidden" {...register("form.order_no")} />
            </Field>

            <Field label="Order Date" required>
              <Input type="date" {...register("form.date1")} required />
            </Field>

            <Field label="Delivery Date" required>
              <Input
                type="date"
                min={new Date(Date.now() + 86400000).toISOString().split("T")[0]}
                {...register("form.delivery_date", {
                  validate: (v) =>
                    !v || v > new Date().toISOString().split("T")[0] ||
                    "Delivery date must be after today",
                })}
                required
              />
            </Field>

            <Field label="Nature">
              <Controller
                name="form.nature"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger className="cursor-pointer"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="new_booking">New Booking</SelectItem>
                      <SelectItem value="repair">Repair</SelectItem>
                      <SelectItem value="sample">Sample</SelectItem>
                      <SelectItem value="to_be_altered">To be altered</SelectItem>
                      <SelectItem value="valuation">Valuation</SelectItem>
                      <SelectItem value="melting">Melting</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>

            <Field label="Delivery Status">
              <Controller
                name="form.delivery_status"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value ?? "pending"}>
                    <SelectTrigger className="cursor-pointer"><SelectValue placeholder="Status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="partially_delivered">Partially Delivered</SelectItem>
                      <SelectItem value="delivered">Delivered</SelectItem>
                      <SelectItem value="cancelled">Cancelled</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
          </div>
        </SectionCard>

        {/* ── Card 2: Customer & Sales ── */}
        <SectionCard title="Customer & Sales">
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
            {/* Party — spans 2 cols */}
            <div className="col-span-2">
              <Field label="Party Name" required>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <SearchableComboBox
                      options={customers}
                      labelKey="ac_name"
                      searchKeys={["mobile1", "mobile2", "phone1"]}
                      value={watch("form.ldgr_code_name") ?? ""}
                      placeholder="Search by name or phone…"
                      onInputChange={(val) => {
                        setValue("form.ldgr_code_name", val);
                        if (!val) setValue("form.ldgr", "");
                      }}
                      onSelect={(opt) => {
                        setValue("form.ldgr_code_name", opt.ac_name ?? "");
                        setValue("form.ldgr", opt.id);
                      }}
                      renderOption={(opt) => {
                        const phone = opt.mobile1 || opt.mobile2 || opt.phone1 || "";
                        const place = [opt.city, opt.state].filter(Boolean).join(", ");
                        return (
                          <div className="leading-tight">
                            <div className="text-sm text-foreground">{opt.ac_name}</div>
                            {(phone || place) && (
                              <div className="text-[11px] text-muted-foreground mt-0.5">
                                {phone}{phone && place ? " · " : ""}{place}
                              </div>
                            )}
                          </div>
                        );
                      }}
                    />
                  </div>
                  <Link
                    to={`/crm/ledger/add/?next=${encodeURIComponent(location.pathname)}`}
                    tabIndex={-1}
                  >
                    <Button type="button" size="icon" variant="outline" title="New customer" className="cursor-pointer shrink-0">
                      <Plus className="size-4" />
                    </Button>
                  </Link>
                </div>
                <input type="hidden" {...register("form.ldgr")} />
                {(() => {
                  const sel = customers.find(c => String(c.id) === String(watch("form.ldgr")));
                  if (!sel) return null;
                  const phone = [sel.mobile1, sel.mobile2, sel.phone1].filter(Boolean).join(" · ");
                  const address = [sel.add1, sel.add2, sel.city, sel.state, sel.pincode].filter(Boolean).join(", ");
                  if (!phone && !address) return null;
                  return (
                    <div className="mt-1.5 px-2.5 py-1.5 border border-border rounded-md bg-muted/30 text-[11px] text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5 leading-snug">
                      {phone && <span>📞 {phone}</span>}
                      {address && <span>📍 {address}</span>}
                    </div>
                  );
                })()}
              </Field>
            </div>

            <Field label="Salesperson 1" required>
              <Controller
                name="form.salesman_1"
                control={control}
                rules={{ required: true }}
                render={({ field, fieldState }) => (
                  <>
                    <Select onValueChange={field.onChange} value={field.value ?? ""}>
                      <SelectTrigger className={`cursor-pointer ${fieldState.error ? "border-destructive focus:ring-destructive" : ""}`}>
                        <SelectValue placeholder="Select salesperson" />
                      </SelectTrigger>
                      <SelectContent>
                        {salespersonData.map((sp, i) => (
                          <SelectItem key={i} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {fieldState.error && (
                      <p className="text-[11px] text-destructive">Required</p>
                    )}
                  </>
                )}
              />
            </Field>

            <Field label="Salesperson 2">
              <Controller
                name="form.salesman_2"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value ?? ""}>
                    <SelectTrigger className="cursor-pointer"><SelectValue placeholder="Optional" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— None —</SelectItem>
                      {salespersonData.map((sp, i) => (
                        <SelectItem key={`sp2-${i}`} value={`${sp.id}`}>{sp.salesperson_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>

            <Field label="Estimated Amount">
              <Input type="number" {...register("form.est_amount")} />
            </Field>

            <Field label="Advance (from receipts)">
              <div className="flex gap-2">
                <Input
                  type="number"
                  value={watch("form.advance_amt") || 0}
                  readOnly
                  disabled
                  className="bg-muted/50 cursor-not-allowed"
                />
                {id && watch("form.ldgr") && (
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    title="Add receipt"
                    className="cursor-pointer shrink-0"
                    onClick={() => {
                      const qs = new URLSearchParams({
                        customer_order: String(id),
                        order_no: watch("form.order_no") || "",
                        ldgr: String(watch("form.ldgr")),
                        ldgr_name: watch("form.ldgr_code_name") || "",
                      }).toString();
                      window.open(`/accounting/AddJournal/RCPT/add?${qs}`, "_blank");
                    }}
                  >
                    <Plus className="size-4" />
                  </Button>
                )}
              </div>
              {id && (
                <p className="text-[10px] text-muted-foreground">Sum of linked receipt vouchers</p>
              )}
            </Field>
          </div>
        </SectionCard>

        {/* ── Card 3: Gold Rate ── */}
        <SectionCard title="Gold Rate">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex items-center gap-2.5 h-9 px-3 rounded-md border border-border bg-muted/20 cursor-pointer select-none">
              {fetchingRates
                ? <Loader2 className="size-4 text-primary animate-spin" />
                : <Checkbox
                    id="fix_rate"
                    checked={fix_gold_rate}
                    onCheckedChange={handleFixGoldRateChange}
                    disabled={fetchingRates}
                    className="cursor-pointer"
                  />
              }
              <Label htmlFor="fix_rate" className="cursor-pointer text-sm font-medium">
                Fix Gold Rate
              </Label>
              {fix_gold_rate && !fetchingRates && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                  <Zap className="size-2.5" /> FIXED
                </span>
              )}
            </div>

            <div className={`flex flex-wrap gap-4 transition-opacity duration-200 ${fix_gold_rate ? "opacity-100" : "opacity-40 pointer-events-none"}`}>
              <Field label="Rate Date" className="w-36">
                <Input type="date" {...register("form.gold_rate_date")} disabled={!fix_gold_rate} />
              </Field>
              <Field label="14K (₹/g)" className="w-28">
                <Input type="number" disabled={!fix_gold_rate}
                  {...register("form.rate_14kt", { valueAsNumber: true })}
                />
              </Field>
              <Field label="18K (₹/g)" className="w-28">
                <Input type="number" disabled={!fix_gold_rate}
                  {...register("form.rate_18kt", { valueAsNumber: true })}
                />
              </Field>
              <Field label="22K (₹/g)" className="w-28">
                <Input type="number" disabled={!fix_gold_rate}
                  {...register("form.rate_22kt", { valueAsNumber: true })}
                />
              </Field>
            </div>
          </div>
        </SectionCard>

        {/* ── Card 4: Item Details ── */}
        <SectionCard
          title="Item Details"
          action={
            rs.length > 0 && (
              <span className="text-xs text-muted-foreground font-normal">
                {rs.length} item{rs.length !== 1 ? "s" : ""}
              </span>
            )
          }
        >
          <div className="overflow-x-auto rounded-md border border-border">
            <Table className="w-full text-sm min-w-[800px]">
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  {["", "Item", "Purity", "Pcs", "GW (g)", "Making", "Type", "Other Chg", "Size", "Remarks"].map((h, i) => (
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
                  <TableCell className="px-2 py-2">
                    <SearchableComboBox
                      options={mainItemData}
                      labelKey="short_code"
                      searchKeys={["item_name"]}
                      value={watch("table.item_id") ?? ""}
                      placeholder="Search item…"
                      className="text-sm"
                      onInputChange={(val) => {
                        setValue("table.item_id", val);
                        const match = mainItemData.find(
                          (it) => it.short_code === val || it.item_name === val
                        );
                        setValue("table.item_name", match ? match.item_name : "");
                      }}
                      onSelect={(opt) => {
                        setValue("table.item_id", opt.short_code ?? "");
                        setValue("table.item_name", opt.item_name ?? "");
                      }}
                      renderOption={(opt) => (
                        <div className="leading-tight">
                          <div className="text-sm text-foreground">{opt.item_name}</div>
                          <div className="text-[11px] text-muted-foreground mt-0.5">{opt.short_code}</div>
                        </div>
                      )}
                    />
                    <input type="hidden" {...register("table.item_name")} />
                    <input type="hidden" {...register("table.item_id")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-28">
                    <Controller
                      name="table.purity"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value || ""}>
                          <SelectTrigger className="h-8 text-sm cursor-pointer"><SelectValue placeholder="Purity" /></SelectTrigger>
                          <SelectContent>
                            {purityData.map((p, i) => (
                              <SelectItem key={i} value={`${p.purity}`}>{p.purity}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="number" className="h-8 text-sm" {...register("table.pcs")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="number" className="h-8 text-sm" {...register("table.gw")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-24">
                    <Input type="number" className="h-8 text-sm" {...register("table.making_amt")} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-32">
                    <Controller
                      name="table.making_type"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value || ""}>
                          <SelectTrigger className="h-8 text-sm cursor-pointer"><SelectValue placeholder="Type" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="per_nw">% of wt</SelectItem>
                            <SelectItem value="val">Value</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-24">
                    <Input type="number" className="h-8 text-sm" {...register("table.other_chg", { valueAsNumber: true })} />
                  </TableCell>
                  <TableCell className="px-2 py-2 w-20">
                    <Input type="text" className="h-8 text-sm" {...register("table.size")} />
                  </TableCell>
                  <TableCell className="px-2 py-2">
                    <div className="flex items-center gap-1.5">
                      <Input
                        type="text"
                        className="h-8 text-sm"
                        placeholder="Remarks — Tab↹ to add"
                        onKeyDown={handleKeyDown}
                        {...register("table.remarks")}
                      />
                    </div>
                  </TableCell>
                </TableRow>

                {/* ── Added rows ── */}
                {rs.map((row, index) => {
                  const locked = row.lock_state && row.lock_state !== 'unlocked';
                  return (
                    <TableRow
                      key={index}
                      className={`hover:bg-muted/20 transition-colors duration-150 ${locked ? "bg-amber-50/60" : ""}`}
                    >
                      <TableCell className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          {locked ? (
                            <span
                              className="p-1 rounded text-amber-500"
                              title={row.lock_reason || `Locked: ${row.lock_state}`}
                            >
                              <Lock className="size-3.5" />
                            </span>
                          ) : (
                            <>
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
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="px-3 py-2">
                        <span className="font-medium text-foreground text-sm">
                          {row.item_name || row.item_id}
                        </span>
                        {row.item_name && row.item_id && (
                          <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{row.item_id}</p>
                        )}
                      </TableCell>
                      <TableCell className="px-3 py-2 text-sm">{row.purity}</TableCell>
                      <TableCell className="px-3 py-2 text-sm text-right tabular-nums">{row.pcs}</TableCell>
                      <TableCell className="px-3 py-2 text-sm text-right tabular-nums">{row.gw}</TableCell>
                      <TableCell className="px-3 py-2 text-sm text-right tabular-nums">{row.making_amt}</TableCell>
                      <TableCell className="px-3 py-2 text-xs text-muted-foreground">{row.making_type}</TableCell>
                      <TableCell className="px-3 py-2 text-sm text-right tabular-nums">{row.other_chg}</TableCell>
                      <TableCell className="px-3 py-2 text-sm">{row.size}</TableCell>
                      <TableCell className="px-3 py-2 text-sm text-muted-foreground">{row.remarks}</TableCell>
                    </TableRow>
                  );
                })}

                {rs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={10} className="text-center py-10 text-muted-foreground text-sm">
                      <div className="flex flex-col items-center gap-1.5">
                        <span>No items added yet</span>
                        <span className="text-xs">
                          Fill the row above and press{" "}
                          <kbd className="px-1.5 py-0.5 bg-muted border border-border rounded text-[10px] font-mono">Tab</kbd>{" "}
                          to add
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
        <div className="flex items-center justify-between gap-3 pt-1 pb-6">
          <div>
            {id && watch("form.is_cancellable") && (
              <Button
                type="button"
                variant="outline"
                className="border-amber-300 text-amber-700 hover:bg-amber-50 cursor-pointer"
                onClick={async () => {
                  const warnings = [];
                  if (watch("form.has_in_production_items")) warnings.push("• Some items are still in production with a karigar or supplier.");
                  if (watch("form.has_advance"))             warnings.push("• Advance receipts will remain on the customer's ledger as a credit.");
                  const orderNo = watch("form.order_no") || id;
                  const msg = `Cancel order ${orderNo}?` + (warnings.length ? `\n\n${warnings.join("\n")}` : "");
                  if (!window.confirm(msg)) return;
                  const res = await cancelCustomerOrder(id);
                  if (res.success) {
                    toast({ title: "Order cancelled." });
                    navigate("/sales/customerorder/list/");
                  } else {
                    toast({ title: "Failed to cancel", description: String(res.error?.detail || res.error), variant: "destructive" });
                  }
                }}
              >
                Cancel Order
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/sales/customerorder/list/")}
              className="cursor-pointer"
            >
              Close
            </Button>
            <Button
              type="submit"
              disabled={submitting || !canSave}
              className="min-w-28 cursor-pointer"
            >
              {submitting
                ? <><Loader2 className="size-4 mr-2 animate-spin" />{id ? "Updating…" : "Saving…"}</>
                : (id ? "Update Order" : "Save Order")
              }
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default CustomerOrderForm;

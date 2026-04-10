import React, { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/table";
import { SquarePen, Trash2, Plus, X, Check, Percent } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter,
} from "@/components/ui/sheet";
import {
  fetchSalesperson,
  createSalesperson,
  updateSalesperson,
  deleteSalesperson,
  getRetails,
  getLedgerList,
} from "@/services/apiService";

const COMMISSION_ON_OPTIONS = [
  { value: "overall", label: "Overall Bill Value (MRP − Discount)" },
  { value: "making",  label: "Making Value Only" },
  { value: "stone",   label: "Stone Value Only" },
];

const BLANK_FORM = {
  salesperson_name: "",
  retail: "",
  ledger: "",
  commission_rate: "0",
  commission_on: "overall",
  deduct_discount: true,
  apply_on_b2b: false,
};

function SalesPersonList() {
  const { toast } = useToast();
  const [salespersons, setSalespersons] = useState([]);
  const [retails, setRetails] = useState([]);
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [sheet, setSheet] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(BLANK_FORM);
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    const [spRes, retRes, ldgrRes] = await Promise.all([
      fetchSalesperson(),
      getRetails(),
      getLedgerList(),
    ]);
    if (spRes.success)  setSalespersons(spRes.data);
    else                setError(spRes.error);
    if (retRes.success) {
      const locs = retRes.data.results?.flatMap(ul => ul.location) || [];
      setRetails(locs.filter((l, i, a) => a.findIndex(x => x.id === l.id) === i));
    }
    if (ldgrRes.success) setLedgers(Array.isArray(ldgrRes.data) ? ldgrRes.data : ldgrRes.data?.results || []);
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const setField = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const openAdd = () => {
    setEditingId(null);
    // Pre-fill retail from the currently active retail location
    const currentRetailCode = localStorage.getItem("retail_code") || "";
    const currentRetail = retails.find(r => r.retail_code === currentRetailCode);
    setForm({
      ...BLANK_FORM,
      retail: currentRetail ? String(currentRetail.id) : "",
    });
    setSheet(true);
  };

  const openEdit = (row) => {
    setEditingId(row.id);
    setForm({
      salesperson_name: row.salesperson_name,
      retail:           row.retail ? String(row.retail) : "",
      ledger:           row.ledger ? String(row.ledger) : "",
      commission_rate:  String(row.commission_rate ?? 0),
      commission_on:    row.commission_on || "overall",
      deduct_discount:  row.deduct_discount ?? true,
      apply_on_b2b:     row.apply_on_b2b   ?? false,
    });
    setSheet(true);
  };

  const handleSubmit = async () => {
    if (!form.salesperson_name.trim()) return;
    setSubmitting(true);

    const payload = {
      salesperson_name: form.salesperson_name.trim(),
      commission_rate:  parseFloat(form.commission_rate) || 0,
      commission_on:    form.commission_on,
      deduct_discount:  form.deduct_discount,
      apply_on_b2b:     form.apply_on_b2b,
    };
    if (form.retail) payload.retail = Number(form.retail);
    if (form.ledger) payload.ledger = Number(form.ledger);
    else             payload.ledger = null;

    const res = editingId
      ? await updateSalesperson(editingId, payload)
      : await createSalesperson(payload);

    if (res.success) {
      toast({ title: editingId ? "Sales person updated" : "Sales person added" });
      setSheet(false);
      loadData();
    } else {
      const msg = typeof res.error === "object"
        ? Object.values(res.error).flat().join(", ")
        : res.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  useF4Submit(handleSubmit);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this sales person?")) return;
    const res = await deleteSalesperson(id);
    if (res.success) { toast({ title: "Deleted" }); loadData(); }
    else toast({ title: "Error", description: JSON.stringify(res.error), variant: "destructive" });
  };

  const retailMap = Object.fromEntries(retails.map(r => [r.id, r.retail_name]));

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(row.original)} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </button>
          <button onClick={() => handleDelete(row.original.id)} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1 },
    { header: "Name",   accessorKey: "salesperson_name" },
    { header: "Retail", accessorKey: "retail", cell: ({ getValue }) => retailMap[getValue()] || "—" },
    {
      header: "Commission",
      cell: ({ row }) => {
        const r = row.original;
        const rate = parseFloat(r.commission_rate || 0);
        if (rate === 0) return <span className="text-muted-foreground text-xs">None</span>;
        return (
          <div className="text-xs flex flex-col gap-0.5">
            <span className="font-medium">{rate}% on {r.commission_on}</span>
            <span className="text-muted-foreground">
              {r.deduct_discount ? "After discount" : "Before discount"}
              {r.apply_on_b2b ? "" : " · Skip B2B"}
            </span>
          </div>
        );
      },
    },
    {
      header: "Payable Ledger",
      accessorKey: "ledger_name",
      cell: ({ getValue }) => getValue() || <span className="text-muted-foreground text-xs">Not set</span>,
    },
  ];

  return (
    <div className="p-4">
      <div className="flex justify-end mb-4">
        <Button onClick={openAdd}>
          <Plus className="size-4 mr-1" /> Add Sales Person
        </Button>
      </div>

      {loading ? (
        <div>{[...Array(4)].map((_, i) => <Skeleton key={i} className="w-full h-8 mb-2" />)}</div>
      ) : error ? (
        <div className="text-destructive text-sm">Error: {typeof error === "string" ? error : JSON.stringify(error)}</div>
      ) : (
        <DataTable columns={columns} data={salespersons} />
      )}

      {/* Add/Edit Sheet */}
      <Sheet open={sheet} onOpenChange={setSheet}>
        <SheetContent side="right" className="sm:max-w-md overflow-y-auto" aria-describedby={undefined}>
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Percent className="w-5 h-5 text-primary" />
              {editingId ? "Edit Sales Person" : "Add Sales Person"}
            </SheetTitle>
          </SheetHeader>

          <div className="flex flex-col gap-4 py-4">
            {/* Basic Info */}
            <div className="flex flex-col gap-1">
              <Label>Name *</Label>
              <Input
                value={form.salesperson_name}
                onChange={e => setField("salesperson_name", e.target.value)}
                placeholder="Salesperson name"
                maxLength={100}
              />
            </div>

            <div className="flex flex-col gap-1">
              <Label>Retail Location</Label>
              <Select value={form.retail} onValueChange={v => setField("retail", v)}>
                <SelectTrigger><SelectValue placeholder="Select retail" /></SelectTrigger>
                <SelectContent>
                  {retails.map(r => (
                    <SelectItem key={r.id} value={String(r.id)}>{r.retail_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1">
              <Label>Payable Ledger</Label>
              <p className="text-xs text-muted-foreground">
                {editingId
                  ? "Ledger used for commission journal vouchers"
                  : "Leave empty to auto-create a \"Commission Payable\" ledger"}
              </p>
              <Select value={form.ledger} onValueChange={v => setField("ledger", v === "__auto__" ? "" : v)}>
                <SelectTrigger><SelectValue placeholder="— Auto-create —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__auto__">— Auto-create (Sales Commission) —</SelectItem>
                  {ledgers.map(l => (
                    <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Commission Section */}
            <div className="border-t pt-4 mt-2">
              <p className="text-sm font-semibold mb-3 flex items-center gap-1">
                <Percent className="w-4 h-4 text-primary" /> Commission Configuration
              </p>

              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                  <Label>Commission Rate (%)</Label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    step="0.001"
                    value={form.commission_rate}
                    onChange={e => setField("commission_rate", e.target.value)}
                    placeholder="0"
                  />
                  <p className="text-xs text-muted-foreground">Set to 0 to disable commission for this person</p>
                </div>

                <div className="flex flex-col gap-1">
                  <Label>Apply Commission On</Label>
                  <Select value={form.commission_on} onValueChange={v => setField("commission_on", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {COMMISSION_ON_OPTIONS.map(o => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <div>
                    <p className="text-sm font-medium">Deduct Discount Before Commission</p>
                    <p className="text-xs text-muted-foreground">If checked, commission = (Value − Discount) × Rate%</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={form.deduct_discount}
                    onClick={() => setField("deduct_discount", !form.deduct_discount)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${form.deduct_discount ? "bg-primary" : "bg-muted"}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${form.deduct_discount ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>

                <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <div>
                    <p className="text-sm font-medium">Apply on B2B Sales</p>
                    <p className="text-xs text-muted-foreground">If off, commission is skipped for GST-registered customers</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={form.apply_on_b2b}
                    onClick={() => setField("apply_on_b2b", !form.apply_on_b2b)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${form.apply_on_b2b ? "bg-primary" : "bg-muted"}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${form.apply_on_b2b ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <SheetFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setSheet(false)} className="flex-1">
              <X className="size-4 mr-1" /> Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting || !form.salesperson_name.trim()}
              className="flex-1"
            >
              <Check className="size-4 mr-1" />
              {editingId ? "Update" : "Save"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default SalesPersonList;

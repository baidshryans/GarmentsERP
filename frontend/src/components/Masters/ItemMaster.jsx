import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { DataTable } from "@/table";
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchItems,
  createItem,
  updateItem,
  deleteItem,
  fetchItemGroups,
  fetchHSNs,
  getLedgers,
  fetchPurity,
} from "@/services/apiService";

const ITEM_TYPES = [
  { value: "M", label: "Metal" },
  { value: "R", label: "Raw" },
  { value: "S", label: "Stone" },
  { value: "O", label: "Other" },
  { value: "C", label: "Coin" },
];

const UOM_OPTIONS = [
  { value: "Gm", label: "Gram" },
  { value: "Pcs", label: "Pieces" },
  { value: "Ct", label: "Carat" },
];

const emptyForm = {
  short_code: "",
  item_name: "",
  grp: "",
  sub_grp: "",
  item_type: "M",
  uom: "Gm",
  hsn_no: "",
  show_in_pcs_report: false,
  purchase_ledger: "",
  sale_ledger: "",
  op_wtd_avg_rate: "0",
  default_purity: "",
};

export default function ItemMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [itemGroups, setItemGroups] = useState([]);
  const [hsns, setHsns] = useState([]);
  const [ledgers, setLedgers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [search, setSearch] = useState("");

  const toArr = (d) => (Array.isArray(d) ? d : d?.results ?? []);

  const load = async () => {
    setLoading(true);
    const [itemsRes, groupsRes, hsnRes, ledgersRes, purityRes] = await Promise.all([
      fetchItems(),
      fetchItemGroups(),
      fetchHSNs(),
      getLedgers({ type: "" }),
      fetchPurity(),
    ]);
    if (itemsRes.success) setRows(toArr(itemsRes.data));
    if (groupsRes.success) setItemGroups(toArr(groupsRes.data));
    if (hsnRes.success) setHsns(toArr(hsnRes.data));
    if (ledgersRes.success) setLedgers(toArr(ledgersRes.data));
    if (purityRes.success) setPurityData(Array.isArray(purityRes.data) ? purityRes.data : purityRes.data?.results ?? []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((f) => ({ ...f, [name]: type === "checkbox" ? checked : value }));
  };

  const handleSelect = (name, value) =>
    setForm((f) => ({ ...f, [name]: value === "__none__" ? "" : value }));

  const buildPayload = () => ({
    short_code: form.short_code.trim(),
    item_name: form.item_name.trim(),
    grp: form.grp ? Number(form.grp) : null,
    sub_grp: form.sub_grp.trim(),
    item_type: form.item_type,
    uom: form.uom,
    hsn_no: form.hsn_no ? Number(form.hsn_no) : null,
    show_in_pcs_report: form.show_in_pcs_report,
    purchase_ledger: form.purchase_ledger ? Number(form.purchase_ledger) : null,
    sale_ledger: form.sale_ledger ? Number(form.sale_ledger) : null,
    op_wtd_avg_rate: form.op_wtd_avg_rate || "0",
    default_purity: form.default_purity || "",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.short_code.trim() || !form.item_name.trim()) return;
    if (!form.purchase_ledger) {
      toast({ title: "Purchase Ledger is required", variant: "destructive" });
      setSubmitting(false);
      return;
    }
    if (!form.sale_ledger) {
      toast({ title: "Sale Ledger is required", variant: "destructive" });
      setSubmitting(false);
      return;
    }
    setSubmitting(true);
    const res = editingId
      ? await updateItem(editingId, buildPayload())
      : await createItem(buildPayload());
    if (res.success) {
      toast({ title: editingId ? "Item updated" : "Item added" });
      reset();
      load();
    } else {
      const msg =
        typeof res.error === "object"
          ? Object.values(res.error).flat().join(", ")
          : res.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  useF4Submit(handleSubmit);

  const handleEdit = (row) => {
    setForm({
      short_code: row.short_code || "",
      item_name: row.item_name || "",
      grp: row.grp?.id ? String(row.grp.id) : row.grp ? String(row.grp) : "",
      sub_grp: row.sub_grp || "",
      item_type: row.item_type || "M",
      uom: row.uom || "Gm",
      hsn_no: row.hsn_no?.id ? String(row.hsn_no.id) : row.hsn_no ? String(row.hsn_no) : "",
      show_in_pcs_report: row.show_in_pcs_report || false,
      purchase_ledger: row.purchase_ledger?.id
        ? String(row.purchase_ledger.id)
        : row.purchase_ledger ? String(row.purchase_ledger) : "",
      sale_ledger: row.sale_ledger?.id
        ? String(row.sale_ledger.id)
        : row.sale_ledger ? String(row.sale_ledger) : "",
      op_wtd_avg_rate: String(row.op_wtd_avg_rate ?? "0"),
      default_purity: row.default_purity || "",
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this item?")) return;
    const res = await deleteItem(id);
    if (res.success) {
      toast({ title: "Item deleted" });
      load();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
  };

  const reset = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
  };

  const typeMap = Object.fromEntries(ITEM_TYPES.map((t) => [t.value, t.label]));
  const groupMap = Object.fromEntries(itemGroups.map((g) => [g.id, g.item_group_name]));
  const hsnMap = Object.fromEntries(hsns.map((h) => [h.id, h.hsn_no]));

  const filtered = search
    ? rows.filter(
        (r) =>
          r.item_name?.toLowerCase().includes(search.toLowerCase()) ||
          r.short_code?.toLowerCase().includes(search.toLowerCase())
      )
    : rows;

  const columns = [
    {
      header: "Action",
      cell: ({ row }) => (
        <div className="flex gap-3">
          <button type="button" onClick={(e) => { e.stopPropagation(); handleEdit(row.original); }} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </button>
          <button type="button" onClick={(e) => { e.stopPropagation(); handleDelete(row.original.id); }} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1 },
    { header: "Code", accessorKey: "short_code" },
    { header: "Item Name", accessorKey: "item_name" },
    {
      header: "Group",
      accessorKey: "grp",
      cell: ({ getValue }) => {
        const val = getValue();
        return val ? (groupMap[val?.id ?? val] || val?.item_group_name || "-") : "-";
      },
    },
    {
      header: "Type",
      accessorKey: "item_type",
      cell: ({ getValue }) => (
        <span className="text-xs bg-muted px-1.5 py-0.5 rounded font-medium">
          {typeMap[getValue()] || getValue()}
        </span>
      ),
    },
    { header: "UOM", accessorKey: "uom" },
    {
      header: "HSN",
      accessorKey: "hsn_no",
      cell: ({ getValue }) => {
        const val = getValue();
        return val ? (hsnMap[val?.id ?? val] || val?.hsn_no || "-") : "-";
      },
    },
    {
      header: "Op. Rate",
      accessorKey: "op_wtd_avg_rate",
      cell: ({ getValue }) => Number(getValue()).toFixed(3),
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Top bar */}
      <div className="flex flex-wrap justify-between items-center gap-2">
        <Input
          placeholder="Search by name or code..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 w-64"
        />
        {!showForm && (
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Item
          </Button>
        )}
      </div>

      {/* Form card */}
      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit Item" : "Add Item"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Short Code *</Label>
                <Input
                  name="short_code"
                  value={form.short_code}
                  onChange={handleChange}
                  placeholder="e.g. AU22"
                  className="h-9"
                  autoFocus
                  maxLength={10}
                />
              </div>

              <div className="flex flex-col gap-1 sm:col-span-2">
                <Label className="text-xs">Item Name *</Label>
                <Input
                  name="item_name"
                  value={form.item_name}
                  onChange={handleChange}
                  placeholder="e.g. Gold 22K Necklace"
                  className="h-9"
                  maxLength={50}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Item Type</Label>
                <Select
                  value={form.item_type}
                  onValueChange={(v) => handleSelect("item_type", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ITEM_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">UOM</Label>
                <Select
                  value={form.uom}
                  onValueChange={(v) => handleSelect("uom", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {UOM_OPTIONS.map((u) => (
                      <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Item Group</Label>
                <Select
                  value={form.grp || "__none__"}
                  onValueChange={(v) => handleSelect("grp", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select group" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {itemGroups.map((g) => (
                      <SelectItem key={g.id} value={String(g.id)}>
                        {g.item_group_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Sub Group</Label>
                <Input
                  name="sub_grp"
                  value={form.sub_grp}
                  onChange={handleChange}
                  placeholder="e.g. Necklace"
                  className="h-9"
                  maxLength={20}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">HSN</Label>
                <Select
                  value={form.hsn_no || "__none__"}
                  onValueChange={(v) => handleSelect("hsn_no", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select HSN" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {hsns.map((h) => (
                      <SelectItem key={h.id} value={String(h.id)}>
                        {h.hsn_no} — {h.description}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Purchase Ledger <span className="text-destructive">*</span></Label>
                <Select
                  value={form.purchase_ledger || "__none__"}
                  onValueChange={(v) => handleSelect("purchase_ledger", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select ledger" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- Select --</SelectItem>
                    {ledgers.map((l) => (
                      <SelectItem key={l.id} value={String(l.id)}>
                        {l.ac_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Sale Ledger <span className="text-destructive">*</span></Label>
                <Select
                  value={form.sale_ledger || "__none__"}
                  onValueChange={(v) => handleSelect("sale_ledger", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select ledger" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- Select --</SelectItem>
                    {ledgers.map((l) => (
                      <SelectItem key={l.id} value={String(l.id)}>
                        {l.ac_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Opening Wtd. Avg. Rate</Label>
                <Input
                  name="op_wtd_avg_rate"
                  type="number"
                  step="0.001"
                  min="0"
                  value={form.op_wtd_avg_rate}
                  onChange={handleChange}
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Default Purity</Label>
                <Select
                  value={form.default_purity || "__none__"}
                  onValueChange={(v) => handleSelect("default_purity", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {purityData.map((p, i) => (
                      <SelectItem key={i} value={`${p.purity}`}>{p.purity}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2 pt-5">
                <input
                  id="show_in_pcs"
                  type="checkbox"
                  name="show_in_pcs_report"
                  checked={form.show_in_pcs_report}
                  onChange={handleChange}
                  className="size-4 accent-primary cursor-pointer"
                />
                <Label htmlFor="show_in_pcs" className="text-xs cursor-pointer">
                  Show in PCS Report
                </Label>
              </div>
            </div>

            <div className="flex gap-2 mt-4">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.short_code.trim() || !form.item_name.trim()}
              >
                <Check className="size-4 mr-1" />
                {editingId ? "Update" : "Save"}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={reset}>
                <X className="size-4 mr-1" />
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : (
        <DataTable columns={columns} data={filtered} />
      )}
    </div>
  );
}

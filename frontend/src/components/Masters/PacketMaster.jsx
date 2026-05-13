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
  fetchPackets,
  createPacket,
  updatePacket,
  deletePacket,
  fetchPacketGroups,
  fetchItems,
  fetchShapes,
  fetchColors,
} from "@/services/apiService";

const emptyForm = {
  pckt_no: "",
  packet_group: "",
  stone_item_id: "",
  cut: "",
  clarity: "",
  color: "",
  shape: "",
  seives: "",
  is_solitaire: false,
  rate_for_retail: "",
  rate_for_wholesale: "",
  is_customer_stone: false,
  op_stock_wtd_avg_rate: "0",
};

export default function PacketMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [packetGroups, setPacketGroups] = useState([]);
  const [stoneItems, setStoneItems] = useState([]);
  const [shapes, setShapes] = useState([]);
  const [colors, setColors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const toArr = (d) => (Array.isArray(d) ? d : d?.results ?? []);

  const load = async () => {
    setLoading(true);
    const [pktsRes, grpsRes, itemsRes, shapesRes, colorsRes] = await Promise.all([
      fetchPackets(),
      fetchPacketGroups(),
      fetchItems(),
      fetchShapes(),
      fetchColors(),
    ]);
    if (pktsRes.success) setRows(toArr(pktsRes.data));
    if (grpsRes.success) setPacketGroups(toArr(grpsRes.data));
    if (itemsRes.success) {
      setStoneItems(toArr(itemsRes.data).filter((i) => i.item_type === "S"));
    }
    if (shapesRes.success) setShapes(toArr(shapesRes.data));
    if (colorsRes.success) setColors(toArr(colorsRes.data));
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
    pckt_no: form.pckt_no.trim(),
    packet_group: form.packet_group ? Number(form.packet_group) : null,
    stone_item_id: form.stone_item_id ? Number(form.stone_item_id) : null,
    cut: form.cut.trim() || null,
    clarity: form.clarity.trim() || null,
    color: form.color ? Number(form.color) : null,
    shape: form.shape ? Number(form.shape) : null,
    seives: form.seives.trim() || null,
    is_solitaire: form.is_solitaire,
    rate_for_retail: Number(form.rate_for_retail) || 0,
    rate_for_wholesale: form.rate_for_wholesale ? Number(form.rate_for_wholesale) : null,
    is_customer_stone: form.is_customer_stone,
    op_stock_wtd_avg_rate: form.op_stock_wtd_avg_rate || "0",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.pckt_no.trim()) return;
    setSubmitting(true);
    const res = editingId
      ? await updatePacket(editingId, buildPayload())
      : await createPacket(buildPayload());
    if (res.success) {
      toast({ title: editingId ? "Packet updated" : "Packet added" });
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

  const fkId = (val) => val?.id ?? (typeof val === "number" ? val : undefined);

  const handleEdit = (row) => {
    setForm({
      pckt_no: row.pckt_no || "",
      packet_group: fkId(row.packet_group) ? String(fkId(row.packet_group)) : "",
      stone_item_id: fkId(row.stone_item_id) ? String(fkId(row.stone_item_id)) : "",
      cut: row.cut || "",
      clarity: row.clarity || "",
      color: fkId(row.color) ? String(fkId(row.color)) : "",
      shape: fkId(row.shape) ? String(fkId(row.shape)) : "",
      seives: row.seives || "",
      is_solitaire: row.is_solitaire || false,
      rate_for_retail: String(row.rate_for_retail ?? ""),
      rate_for_wholesale: row.rate_for_wholesale != null ? String(row.rate_for_wholesale) : "",
      is_customer_stone: row.is_customer_stone || false,
      op_stock_wtd_avg_rate: String(row.op_stock_wtd_avg_rate ?? "0"),
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this packet?")) return;
    const res = await deletePacket(id);
    if (res.success) {
      toast({ title: "Packet deleted" });
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

  const grpMap = Object.fromEntries(packetGroups.map((g) => [g.id, g.packet_group_name]));
  const stoneMap = Object.fromEntries(stoneItems.map((i) => [i.id, i.item_name]));
  const shapeMap = Object.fromEntries(shapes.map((s) => [s.id, s.shape_name]));
  const colorMap = Object.fromEntries(colors.map((c) => [c.id, c.color_name]));

  const filtered = search
    ? rows.filter((r) => r.pckt_no?.toLowerCase().includes(search.toLowerCase()))
    : rows;

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const columns = [
    {
      header: "Action",
      cell: ({ row }) => (
        <div className="flex gap-3">
          <button onClick={() => handleEdit(row.original)} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </button>
          <button onClick={() => handleDelete(row.original.id)} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1 },
    { header: "Packet No", accessorKey: "pckt_no" },
    {
      header: "Group",
      accessorKey: "packet_group",
      cell: ({ row }) => {
        const v = row.original.packet_group;
        return row.original.packet_group_name || grpMap[fkId(v)] || v?.packet_group_name || "-";
      },
    },
    {
      header: "Stone",
      accessorKey: "stone_item_id",
      cell: ({ row }) => {
        const v = row.original.stone_item_id;
        return row.original.stone_item_name || stoneMap[fkId(v)] || v?.item_name || "-";
      },
    },
    { header: "Cut", accessorKey: "cut", cell: ({ getValue }) => getValue() || "-" },
    { header: "Clarity", accessorKey: "clarity", cell: ({ getValue }) => getValue() || "-" },
    {
      header: "Shape",
      accessorKey: "shape",
      cell: ({ row }) => {
        const v = row.original.shape;
        return row.original.shape_name || shapeMap[fkId(v)] || v?.shape_name || "-";
      },
    },
    {
      header: "Color",
      accessorKey: "color",
      cell: ({ row }) => {
        const v = row.original.color;
        return row.original.color_name || colorMap[fkId(v)] || v?.color_name || "-";
      },
    },
    {
      header: "Rate (Retail)",
      accessorKey: "rate_for_retail",
      cell: ({ getValue }) =>
        Number(getValue()).toLocaleString("en-IN"),
    },
    {
      header: "Solitaire",
      accessorKey: "is_solitaire",
      cell: ({ getValue }) => (getValue() ? "Yes" : "No"),
    },
    {
      header: "Cust. Stone",
      accessorKey: "is_customer_stone",
      cell: ({ getValue }) => (getValue() ? "Yes" : "No"),
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Top bar */}
      <div className="flex flex-wrap justify-between items-center gap-2">
        <Input
          placeholder="Search by packet no..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="h-9 w-56"
        />
        {!showForm && (
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Packet
          </Button>
        )}
      </div>

      {/* Form card */}
      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit Packet" : "Add Packet"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Packet No *</Label>
                <Input
                  name="pckt_no"
                  value={form.pckt_no}
                  onChange={handleChange}
                  placeholder="e.g. DIA-001"
                  className="h-9"
                  autoFocus
                  maxLength={10}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Packet Group</Label>
                <Select
                  value={form.packet_group || "__none__"}
                  onValueChange={(v) => handleSelect("packet_group", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select group" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {packetGroups.map((g) => (
                      <SelectItem key={g.id} value={String(g.id)}>
                        {g.packet_group_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Stone Item</Label>
                <Select
                  value={form.stone_item_id || "__none__"}
                  onValueChange={(v) => handleSelect("stone_item_id", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select stone" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {stoneItems.map((i) => (
                      <SelectItem key={i.id} value={String(i.id)}>
                        {i.item_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Shape</Label>
                <Select
                  value={form.shape || "__none__"}
                  onValueChange={(v) => handleSelect("shape", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select shape" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {shapes.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.shape_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Color</Label>
                <Select
                  value={form.color || "__none__"}
                  onValueChange={(v) => handleSelect("color", v)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select color" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">-- None --</SelectItem>
                    {colors.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.color_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Cut</Label>
                <Input
                  name="cut"
                  value={form.cut}
                  onChange={handleChange}
                  placeholder="e.g. Round Brilliant"
                  className="h-9"
                  maxLength={50}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Clarity</Label>
                <Input
                  name="clarity"
                  value={form.clarity}
                  onChange={handleChange}
                  placeholder="e.g. VS1"
                  className="h-9"
                  maxLength={10}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Sieves</Label>
                <Input
                  name="seives"
                  value={form.seives}
                  onChange={handleChange}
                  placeholder="e.g. 10/12"
                  className="h-9"
                  maxLength={10}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Rate (Retail) *</Label>
                <Input
                  name="rate_for_retail"
                  type="number"
                  min="0"
                  value={form.rate_for_retail}
                  onChange={handleChange}
                  placeholder="0"
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Rate (Wholesale)</Label>
                <Input
                  name="rate_for_wholesale"
                  type="number"
                  min="0"
                  value={form.rate_for_wholesale}
                  onChange={handleChange}
                  placeholder="0"
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Op. Stock Rate</Label>
                <Input
                  name="op_stock_wtd_avg_rate"
                  type="number"
                  step="0.001"
                  min="0"
                  value={form.op_stock_wtd_avg_rate}
                  onChange={handleChange}
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-3 pt-1">
                <div className="flex items-center gap-2 pt-4">
                  <input
                    id="is_solitaire"
                    type="checkbox"
                    name="is_solitaire"
                    checked={form.is_solitaire}
                    onChange={handleChange}
                    className="size-4 accent-primary cursor-pointer"
                  />
                  <Label htmlFor="is_solitaire" className="text-xs cursor-pointer">
                    Is Solitaire
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    id="is_customer_stone"
                    type="checkbox"
                    name="is_customer_stone"
                    checked={form.is_customer_stone}
                    onChange={handleChange}
                    className="size-4 accent-primary cursor-pointer"
                  />
                  <Label htmlFor="is_customer_stone" className="text-xs cursor-pointer">
                    Customer Stone
                  </Label>
                </div>
              </div>
            </div>

            <div className="flex gap-2 mt-4">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.pckt_no.trim()}
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
        <>
          <DataTable columns={columns} data={paginated} />
          {/* Pagination controls */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {filtered.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="px-2">Page {page} of {totalPages}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

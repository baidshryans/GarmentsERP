import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Edit, Trash2, Plus, X, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchItemGroups,
  createItemGroup,
  updateItemGroup,
  deleteItemGroup,
} from "@/services/apiService";

const emptyForm = { item_group_name: "", short_code: "" };

export default function ItemGroupMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const res = await fetchItemGroups();
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.item_group_name.trim()) return;
    setSubmitting(true);
    const payload = {
      item_group_name: form.item_group_name.trim(),
      short_code: form.short_code.trim(),
    };
    const res = editingId
      ? await updateItemGroup(editingId, payload)
      : await createItemGroup(payload);
    if (res.success) {
      toast({ title: editingId ? "Item group updated" : "Item group added" });
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
    setForm({ item_group_name: row.item_group_name, short_code: row.short_code });
    setEditingId(row.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this item group?")) return;
    const res = await deleteItemGroup(id);
    if (res.success) {
      toast({ title: "Item group deleted" });
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

  const columns = [
    {
      header: "Action",
      cell: ({ row }) => (
        <div className="flex gap-3">
          <button onClick={() => handleEdit(row.original)} className="text-primary">
            <Edit className="size-4" />
          </button>
          <button onClick={() => handleDelete(row.original.id)} className="text-red-500">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1 },
    { header: "Group Name", accessorKey: "item_group_name" },
    { header: "Short Code", accessorKey: "short_code" },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Form */}
      <div className="flex justify-between items-start">
        {showForm ? (
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 w-full">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Group Name *</Label>
              <Input
                name="item_group_name"
                value={form.item_group_name}
                onChange={handleChange}
                placeholder="e.g. Gold Jewellery"
                className="h-9 w-52"
                autoFocus
                maxLength={20}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Short Code</Label>
              <Input
                name="short_code"
                value={form.short_code}
                onChange={handleChange}
                placeholder="e.g. GJ"
                className="h-9 w-28"
                maxLength={5}
              />
            </div>
            <Button type="submit" size="sm" disabled={submitting || !form.item_group_name.trim()} className="h-9">
              <Check className="size-4 mr-1" />
              {editingId ? "Update" : "Save"}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={reset} className="h-9">
              <X className="size-4 mr-1" />
              Cancel
            </Button>
          </form>
        ) : (
          <>
            <div />
            <Button size="sm" onClick={() => setShowForm(true)}>
              <Plus className="size-4 mr-1" />
              Add Item Group
            </Button>
          </>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}

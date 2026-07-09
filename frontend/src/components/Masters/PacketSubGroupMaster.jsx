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
  fetchPacketSubGroups,
  createPacketSubGroup,
  updatePacketSubGroup,
  deletePacketSubGroup,
  fetchPacketGroups,
} from "@/services/apiService";

const emptyForm = { packet_group: "", packet_sub_group_name: "" };

export default function PacketSubGroupMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [packetGroups, setPacketGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const toArr = (d) => (Array.isArray(d) ? d : d?.results ?? []);

  const load = async () => {
    setLoading(true);
    const [rowsRes, groupsRes] = await Promise.all([
      fetchPacketSubGroups(),
      fetchPacketGroups(),
    ]);
    if (rowsRes.success) setRows(toArr(rowsRes.data));
    if (groupsRes.success) setPacketGroups(toArr(groupsRes.data));
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSelect = (name, value) =>
    setForm((f) => ({ ...f, [name]: value === "__none__" ? "" : value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.packet_group || !form.packet_sub_group_name.trim()) return;
    setSubmitting(true);
    const payload = {
      packet_group: Number(form.packet_group),
      packet_sub_group_name: form.packet_sub_group_name.trim(),
    };
    const res = editingId
      ? await updatePacketSubGroup(editingId, payload)
      : await createPacketSubGroup(payload);
    if (res.success) {
      toast({ title: editingId ? "Packet sub group updated" : "Packet sub group added" });
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
      packet_group: row.packet_group != null ? String(row.packet_group) : "",
      packet_sub_group_name: row.packet_sub_group_name || "",
    });
    setEditingId(row.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this packet sub group?")) return;
    const res = await deletePacketSubGroup(id);
    if (res.success) {
      toast({ title: "Packet sub group deleted" });
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
    {
      header: "Group",
      accessorKey: "packet_group_name",
      cell: ({ getValue }) => getValue() || "-",
    },
    { header: "Sub Group Name", accessorKey: "packet_sub_group_name" },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Form */}
      <div className="flex justify-between items-start">
        {showForm ? (
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 w-full">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Packet Group *</Label>
              <Select
                value={form.packet_group || "__none__"}
                onValueChange={(v) => handleSelect("packet_group", v)}
              >
                <SelectTrigger className="h-9 w-52">
                  <SelectValue placeholder="Select group" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">-- Select --</SelectItem>
                  {packetGroups.map((g) => (
                    <SelectItem key={g.id} value={String(g.id)}>
                      {g.packet_group_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Sub Group Name *</Label>
              <Input
                value={form.packet_sub_group_name}
                onChange={(e) => setForm((f) => ({ ...f, packet_sub_group_name: e.target.value }))}
                placeholder="e.g. Small"
                className="h-9 w-52"
                autoFocus
                maxLength={10}
              />
            </div>
            <Button type="submit" size="sm" disabled={submitting || !form.packet_group || !form.packet_sub_group_name.trim()} className="h-9">
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
              Add Packet Sub Group
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

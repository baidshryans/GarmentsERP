import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchPacketGroups,
  createPacketGroup,
  updatePacketGroup,
  deletePacketGroup,
} from "@/services/apiService";

export default function PacketGroupMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formName, setFormName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const res = await fetchPacketGroups();
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formName.trim()) return;
    setSubmitting(true);
    const payload = { packet_group_name: formName.trim() };
    const res = editingId
      ? await updatePacketGroup(editingId, payload)
      : await createPacketGroup(payload);
    if (res.success) {
      toast({ title: editingId ? "Packet group updated" : "Packet group added" });
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
    setFormName(row.packet_group_name);
    setEditingId(row.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this packet group?")) return;
    const res = await deletePacketGroup(id);
    if (res.success) {
      toast({ title: "Packet group deleted" });
      load();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
  };

  const reset = () => {
    setShowForm(false);
    setEditingId(null);
    setFormName("");
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
    { header: "Packet Group Name", accessorKey: "packet_group_name" },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Form */}
      <div className="flex justify-between items-start">
        {showForm ? (
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 w-full">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Packet Group Name *</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Diamond"
                className="h-9 w-52"
                autoFocus
                maxLength={10}
              />
            </div>
            <Button type="submit" size="sm" disabled={submitting || !formName.trim()} className="h-9">
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
              Add Packet Group
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

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
import { Edit, Trash2, Plus, X, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { fetchHSNs, createHsn, updateHsn, deleteHsn } from "@/services/apiService";

const emptyForm = {
  hsn_no: "",
  hsn_type: "GD",
  cgst: "",
  sgst: "",
  igst: "",
  description: "",
};

export default function HsnMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const res = await fetchHSNs();
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
    if (!form.hsn_no.trim()) return;
    setSubmitting(true);
    const payload = {
      hsn_no: form.hsn_no.trim(),
      hsn_type: form.hsn_type,
      cgst: form.cgst || "0",
      sgst: form.sgst || "0",
      igst: form.igst || "0",
      description: form.description.trim(),
    };
    const res = editingId
      ? await updateHsn(editingId, payload)
      : await createHsn(payload);
    if (res.success) {
      toast({ title: editingId ? "HSN updated" : "HSN added" });
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
      hsn_no: row.hsn_no,
      hsn_type: row.hsn_type || "GD",
      cgst: String(row.cgst ?? ""),
      sgst: String(row.sgst ?? ""),
      igst: String(row.igst ?? ""),
      description: row.description || "",
    });
    setEditingId(row.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this HSN entry?")) return;
    const res = await deleteHsn(id);
    if (res.success) {
      toast({ title: "HSN deleted" });
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

  const hsnTypeLabel = { GD: "Goods", SR: "Services" };

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
    { header: "HSN No", accessorKey: "hsn_no" },
    {
      header: "Type",
      accessorKey: "hsn_type",
      cell: ({ getValue }) => hsnTypeLabel[getValue()] || getValue(),
    },
    { header: "CGST %", accessorKey: "cgst" },
    { header: "SGST %", accessorKey: "sgst" },
    { header: "IGST %", accessorKey: "igst" },
    { header: "Description", accessorKey: "description" },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Toggle button */}
      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add HSN
          </Button>
        </div>
      )}

      {/* Form */}
      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit HSN" : "Add HSN"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">HSN Number *</Label>
                <Input
                  name="hsn_no"
                  value={form.hsn_no}
                  onChange={handleChange}
                  placeholder="e.g. 71131920"
                  className="h-9"
                  autoFocus
                  maxLength={10}
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Type</Label>
                <Select
                  value={form.hsn_type}
                  onValueChange={(v) => setForm((f) => ({ ...f, hsn_type: v }))}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GD">Goods</SelectItem>
                    <SelectItem value="SR">Services</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">CGST %</Label>
                <Input
                  name="cgst"
                  type="number"
                  step="0.001"
                  min="0"
                  max="100"
                  value={form.cgst}
                  onChange={handleChange}
                  placeholder="0.000"
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">SGST %</Label>
                <Input
                  name="sgst"
                  type="number"
                  step="0.001"
                  min="0"
                  max="100"
                  value={form.sgst}
                  onChange={handleChange}
                  placeholder="0.000"
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">IGST %</Label>
                <Input
                  name="igst"
                  type="number"
                  step="0.001"
                  min="0"
                  max="100"
                  value={form.igst}
                  onChange={handleChange}
                  placeholder="0.000"
                  className="h-9"
                />
              </div>

              <div className="flex flex-col gap-1 sm:col-span-2">
                <Label className="text-xs">Description</Label>
                <Input
                  name="description"
                  value={form.description}
                  onChange={handleChange}
                  placeholder="e.g. Gold jewellery of precious metal"
                  className="h-9"
                  maxLength={100}
                />
              </div>
            </div>

            <div className="flex gap-2 mt-4">
              <Button type="submit" size="sm" disabled={submitting || !form.hsn_no.trim()}>
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
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}

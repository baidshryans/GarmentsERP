import { useState, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { DataTable } from "@/table"
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { fetchShapes, createShape, updateShape, deleteShape } from "@/services/apiService"

const emptyForm = { shape_name: "", shape_code: "" }

export default function ShapeMasterPage() {
  const { toast } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    const res = await fetchShapes()
    if (res.success) {
      const d = res.data
      setRows(Array.isArray(d) ? d : d?.results ?? [])
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.shape_name.trim()) return
    setSubmitting(true)
    const payload = {
      shape_name: form.shape_name.trim(),
      shape_code: form.shape_code.trim(),
    }
    const res = editingId
      ? await updateShape(editingId, payload)
      : await createShape(payload)
    if (res.success) {
      toast({ title: editingId ? "Shape updated" : "Shape added" })
      reset()
      load()
    } else {
      const msg =
        typeof res.error === "object"
          ? Object.values(res.error).flat().join(", ")
          : res.error
      toast({ title: "Error", description: msg, variant: "destructive" })
    }
    setSubmitting(false)
  }

  useF4Submit(handleSubmit)

  const handleEdit = (row) => {
    setForm({ shape_name: row.shape_name, shape_code: row.shape_code ?? "" })
    setEditingId(row.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this shape?")) return
    const res = await deleteShape(id)
    if (res.success) {
      toast({ title: "Shape deleted" })
      load()
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" })
    }
  }

  const reset = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

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
    { header: "Shape Name", accessorKey: "shape_name" },
    { header: "Shape Code", accessorKey: "shape_code" },
  ]

  return (
    <div className="p-4 flex flex-col gap-4">
      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Shape
          </Button>
        </div>
      )}

      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit Shape" : "Add Shape"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Shape Name *</Label>
                <Input
                  name="shape_name"
                  value={form.shape_name}
                  onChange={handleChange}
                  placeholder="e.g. Round, Oval, Princess"
                  className="h-9 w-48"
                  autoFocus
                  maxLength={50}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Shape Code</Label>
                <Input
                  name="shape_code"
                  value={form.shape_code}
                  onChange={handleChange}
                  placeholder="e.g. RND"
                  className="h-9 w-28"
                  maxLength={50}
                />
              </div>
              <Button
                type="submit"
                size="sm"
                className="h-9"
                disabled={submitting || !form.shape_name.trim()}
              >
                <Check className="size-4 mr-1" />
                {editingId ? "Update" : "Save"}
              </Button>
              <Button type="button" variant="outline" size="sm" className="h-9" onClick={reset}>
                <X className="size-4 mr-1" />
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  )
}

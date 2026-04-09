import { useState, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { DataTable } from "@/table"
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { fetchColors, createColor, updateColor, deleteColor } from "@/services/apiService"

const emptyForm = { color_name: "" }

export default function ColorMasterPage() {
  const { toast } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    const res = await fetchColors()
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
    if (!form.color_name.trim()) return
    setSubmitting(true)
    const payload = { color_name: form.color_name.trim() }
    const res = editingId
      ? await updateColor(editingId, payload)
      : await createColor(payload)
    if (res.success) {
      toast({ title: editingId ? "Color updated" : "Color added" })
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
    setForm({ color_name: row.color_name })
    setEditingId(row.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this color?")) return
    const res = await deleteColor(id)
    if (res.success) {
      toast({ title: "Color deleted" })
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
    { header: "Color Name", accessorKey: "color_name" },
  ]

  return (
    <div className="p-4 flex flex-col gap-4">
      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Color
          </Button>
        </div>
      )}

      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit Color" : "Add Color"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Color Name *</Label>
                <Input
                  name="color_name"
                  value={form.color_name}
                  onChange={handleChange}
                  placeholder="e.g. White, Yellow, Rose"
                  className="h-9 w-48"
                  autoFocus
                  maxLength={50}
                />
              </div>
              <Button
                type="submit"
                size="sm"
                className="h-9"
                disabled={submitting || !form.color_name.trim()}
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

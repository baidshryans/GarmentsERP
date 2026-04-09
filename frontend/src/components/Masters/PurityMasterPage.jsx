import { useState, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { DataTable } from "@/table"
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { fetchPurity, createPurity, updatePurity, deletePurity } from "@/services/apiService"

const emptyForm = { purity: "", gw_per: "" }

export default function PurityMasterPage() {
  const { toast } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    const res = await fetchPurity()
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
    if (!form.purity.trim() || !form.gw_per) return
    setSubmitting(true)
    const payload = {
      purity: form.purity.trim(),
      gw_per: form.gw_per,
    }
    const res = editingId
      ? await updatePurity(editingId, payload)
      : await createPurity(payload)
    if (res.success) {
      toast({ title: editingId ? "Purity updated" : "Purity added" })
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
    setForm({ purity: row.purity, gw_per: String(row.gw_per ?? "") })
    setEditingId(row.id)
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this purity? This may affect gold rates and manufacturing records.")) return
    const res = await deletePurity(id)
    if (res.success) {
      toast({ title: "Purity deleted" })
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
    { header: "Purity Name", accessorKey: "purity" },
    {
      header: "Fine Weight %",
      accessorKey: "gw_per",
      cell: ({ getValue }) => `${getValue()}%`,
    },
  ]

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Toggle button */}
      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Purity
          </Button>
        </div>
      )}

      {/* Form */}
      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit Purity" : "Add Purity"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Purity Name *</Label>
                <Input
                  name="purity"
                  value={form.purity}
                  onChange={handleChange}
                  placeholder="e.g. 22K, 18K, 999"
                  className="h-9 w-40"
                  autoFocus
                  maxLength={10}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Fine Weight % *</Label>
                <Input
                  name="gw_per"
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={form.gw_per}
                  onChange={handleChange}
                  placeholder="e.g. 91.67"
                  className="h-9 w-36"
                />
              </div>
              <Button
                type="submit"
                size="sm"
                className="h-9"
                disabled={submitting || !form.purity.trim() || !form.gw_per}
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

      {/* Table */}
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

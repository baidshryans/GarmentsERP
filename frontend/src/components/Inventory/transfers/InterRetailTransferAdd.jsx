import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Trash2, Save, Loader2 } from "lucide-react";
import {
  fetchRetails, fetchItems,
  createInterRetailTransfer, updateInterRetailTransfer,
  fetchInterRetailTransfer, getNextInterRetailTransferNo,
} from "@/services/apiService";

const today = new Date().toISOString().split("T")[0];

const emptyLine = () => ({ item: "", qty_pcs: "", qty_gw: "", qty_ct: "" });

export default function InterRetailTransferAdd() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = Boolean(id);

  const [retails, setRetails] = useState([]);
  const [items, setItems] = useState([]);
  const [previewNo, setPreviewNo] = useState("");

  const [form, setForm] = useState({
    transfer_date: today, from_retail: "", to_retail: "", narration: "",
    items: [emptyLine()],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchRetails().then((res) => res.success && setRetails(res.data?.results || res.data || []));
    fetchItems().then((res) => {
      if (res.success) {
        const all = res.data || [];
        setItems(all.filter((it) => ["R", "S", "M"].includes(it.item_type)));
      }
    });
    if (!isEdit) {
      getNextInterRetailTransferNo().then((res) => res.success && setPreviewNo(res.data?.next_no || ""));
    }
  }, [isEdit]);

  useEffect(() => {
    if (!isEdit) return;
    fetchInterRetailTransfer(id).then((res) => {
      if (res.success) {
        const v = res.data;
        setForm({
          transfer_date: v.transfer_date,
          from_retail: v.from_retail,
          to_retail: v.to_retail,
          narration: v.narration || "",
          items: (v.items || []).map((it) => ({
            id: it.id, item: it.item, qty_pcs: it.qty_pcs, qty_gw: it.qty_gw, qty_ct: it.qty_ct,
          })),
        });
        setPreviewNo(v.voucher_no);
      }
    });
  }, [id, isEdit]);

  const addLine = () => setForm((f) => ({ ...f, items: [...f.items, emptyLine()] }));
  const removeLine = (idx) => setForm((f) => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const updateLine = (idx, patch) =>
    setForm((f) => ({ ...f, items: f.items.map((ln, i) => (i === idx ? { ...ln, ...patch } : ln)) }));

  const itemById = useMemo(() => Object.fromEntries(items.map((it) => [it.id, it])), [items]);

  const save = async () => {
    setError("");
    if (!form.from_retail || !form.to_retail) return setError("From and To retails are required.");
    if (String(form.from_retail) === String(form.to_retail)) return setError("From and To retails must differ.");
    if (form.items.length === 0) return setError("At least one line item is required.");
    for (const [i, ln] of form.items.entries()) {
      if (!ln.item) return setError(`Row ${i + 1}: select an item.`);
    }
    setSaving(true);
    const payload = {
      transfer_date: form.transfer_date,
      from_retail: Number(form.from_retail),
      to_retail: Number(form.to_retail),
      narration: form.narration,
      items: form.items.map((ln) => ({
        ...(ln.id ? { id: ln.id } : {}),
        item: Number(ln.item),
        qty_pcs: Number(ln.qty_pcs || 0),
        qty_gw: Number(ln.qty_gw || 0),
        qty_ct: Number(ln.qty_ct || 0),
      })),
    };
    const res = isEdit
      ? await updateInterRetailTransfer(id, payload)
      : await createInterRetailTransfer(payload);
    setSaving(false);
    if (res.success) {
      navigate(`/inventory/inter-retail-transfer/${res.data.id}`);
    } else {
      const err = res.error;
      setError(typeof err === "string" ? err : JSON.stringify(err));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {isEdit ? "Edit" : "New"} Inter-Retail Transfer
          {previewNo && <span className="ml-3 text-sm text-muted-foreground font-mono">{previewNo}</span>}
        </h2>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => navigate("/inventory/inter-retail-transfer")}>Cancel</Button>
          <Button size="sm" onClick={save} disabled={saving} className="gap-1.5">
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            Save Draft
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-lg border border-border bg-muted/20">
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">Transfer Date</Label>
          <Input type="date" value={form.transfer_date}
                 onChange={(e) => setForm((f) => ({ ...f, transfer_date: e.target.value }))} className="h-9" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">From Retail</Label>
          <select value={form.from_retail}
                  onChange={(e) => setForm((f) => ({ ...f, from_retail: e.target.value }))}
                  className="h-9 rounded-md border border-border bg-background px-2 text-sm">
            <option value="">Select…</option>
            {retails.map((r) => <option key={r.id} value={r.id}>{r.retail_name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">To Retail</Label>
          <select value={form.to_retail}
                  onChange={(e) => setForm((f) => ({ ...f, to_retail: e.target.value }))}
                  className="h-9 rounded-md border border-border bg-background px-2 text-sm">
            <option value="">Select…</option>
            {retails.filter((r) => String(r.id) !== String(form.from_retail)).map((r) =>
              <option key={r.id} value={r.id}>{r.retail_name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1.5 md:col-span-4">
          <Label className="text-xs">Narration</Label>
          <Input value={form.narration}
                 onChange={(e) => setForm((f) => ({ ...f, narration: e.target.value }))}
                 className="h-9" placeholder="Optional note" />
        </div>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left w-12">#</th>
              <th className="px-3 py-2 text-left">Item</th>
              <th className="px-3 py-2 text-right w-28">Pcs</th>
              <th className="px-3 py-2 text-right w-32">GW</th>
              <th className="px-3 py-2 text-right w-32">CT</th>
              <th className="px-3 py-2 text-right w-12"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {form.items.map((ln, i) => {
              const it = itemById[ln.item];
              return (
                <tr key={i}>
                  <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                  <td className="px-3 py-2">
                    <select value={ln.item}
                            onChange={(e) => updateLine(i, { item: e.target.value })}
                            className="h-8 w-full rounded-md border border-border bg-background px-2 text-sm">
                      <option value="">Select item…</option>
                      {items.map((opt) => (
                        <option key={opt.id} value={opt.id}>
                          [{opt.item_type}] {opt.item_name}
                        </option>
                      ))}
                    </select>
                    {it && <p className="mt-1 text-[10px] text-muted-foreground">Primary: {it.item_type === "S" ? "CT" : "GW"}</p>}
                  </td>
                  <td className="px-3 py-2">
                    <Input type="number" step="0.01" value={ln.qty_pcs}
                           onChange={(e) => updateLine(i, { qty_pcs: e.target.value })}
                           className="h-8 text-right" />
                  </td>
                  <td className="px-3 py-2">
                    <Input type="number" step="0.0001" value={ln.qty_gw}
                           onChange={(e) => updateLine(i, { qty_gw: e.target.value })}
                           className="h-8 text-right" />
                  </td>
                  <td className="px-3 py-2">
                    <Input type="number" step="0.0001" value={ln.qty_ct}
                           onChange={(e) => updateLine(i, { qty_ct: e.target.value })}
                           className="h-8 text-right" />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => removeLine(i)}
                            disabled={form.items.length === 1}>
                      <Trash2 className="size-3.5 text-destructive" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Button size="sm" variant="outline" onClick={addLine} className="self-start gap-1.5">
        <Plus className="size-4" /> Add Row
      </Button>

      <p className="text-xs text-muted-foreground">
        Rate will be snapshotted on save from the source retail&apos;s weighted-average rate on the transfer date.
      </p>
    </div>
  );
}

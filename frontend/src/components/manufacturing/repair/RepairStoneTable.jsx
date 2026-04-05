import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Trash2, PlusCircle } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";

export default function RepairStoneTable({ rows, setRows, readOnly }) {
  const addRow = () =>
    setRows((prev) => [
      ...prev,
      { _key: Date.now(), description: "", pcs: "", ct: "", remarks: "", returned: false },
    ]);

  const update = (idx, field, value) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));

  const remove = (idx) => setRows((prev) => prev.filter((_, i) => i !== idx));

  const handleTabOnRemarks = (e, idx) => {
    if (e.key === "Tab" && !e.shiftKey && idx === rows.length - 1) {
      e.preventDefault();
      addRow();
    }
  };

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[1fr_70px_80px_1fr_70px_36px] gap-2 text-xs font-medium text-muted-foreground px-1">
        <span>Description</span>
        <span>Pcs</span>
        <span>Carats</span>
        <span>Remarks</span>
        <span className="text-center">Returned</span>
        <span />
      </div>

      {rows.map((row, idx) => (
        <div key={row._key ?? row.id ?? idx} className="grid grid-cols-[1fr_70px_80px_1fr_70px_36px] gap-2 items-center">
          <Input
            className="h-8 text-xs"
            value={row.description}
            onChange={(e) => update(idx, "description", e.target.value)}
            disabled={readOnly}
          />

          <Input
            className="h-8 text-xs text-right"
            type="number"
            min="0"
            value={row.pcs}
            onChange={(e) => update(idx, "pcs", e.target.value)}
            disabled={readOnly}
          />

          <Input
            className="h-8 text-xs text-right"
            type="number"
            step="0.001"
            value={row.ct}
            onChange={(e) => update(idx, "ct", e.target.value)}
            disabled={readOnly}
          />

          <Input
            className="h-8 text-xs"
            value={row.remarks}
            onChange={(e) => update(idx, "remarks", e.target.value)}
            onKeyDown={(e) => handleTabOnRemarks(e, idx)}
            disabled={readOnly}
          />

          <div className="flex justify-center">
            <Checkbox
              checked={!!row.returned}
              onCheckedChange={(val) => update(idx, "returned", val)}
              disabled={readOnly}
            />
          </div>

          {!readOnly && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 text-destructive hover:text-destructive"
              onClick={() => remove(idx)}
            >
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      ))}

      {!readOnly && (
        <Button type="button" variant="outline" size="sm" className="h-7 text-xs gap-1.5" onClick={addRow}>
          <PlusCircle className="size-3.5" />
          Add Stone
        </Button>
      )}
    </div>
  );
}

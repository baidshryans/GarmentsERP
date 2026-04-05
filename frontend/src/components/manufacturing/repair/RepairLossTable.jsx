import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Trash2, PlusCircle } from "lucide-react";

const LOSS_TYPES = [
  { value: "POLISH",  label: "Polish Loss"       },
  { value: "FILING",  label: "Filing Loss"        },
  { value: "MELTING", label: "Melting Loss"       },
  { value: "STONE",   label: "Stone Setting Loss" },
  { value: "OTHER",   label: "Other"              },
];

export default function RepairLossTable({ rows, setRows, readOnly }) {
  const addRow = () =>
    setRows((prev) => [...prev, { _key: Date.now(), loss_type: "POLISH", loss_wt: "", remarks: "" }]);

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
      <div className="grid grid-cols-[160px_120px_1fr_36px] gap-2 text-xs font-medium text-muted-foreground px-1">
        <span>Loss Type</span>
        <span>Weight (g)</span>
        <span>Remarks</span>
        <span />
      </div>

      {rows.map((row, idx) => (
        <div key={row._key ?? row.id ?? idx} className="grid grid-cols-[160px_120px_1fr_36px] gap-2 items-center">
          <Select
            value={row.loss_type}
            onValueChange={(val) => update(idx, "loss_type", val)}
            disabled={readOnly}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LOSS_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value} className="text-xs">
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            className="h-8 text-xs text-right"
            type="number"
            step="0.001"
            value={row.loss_wt}
            onChange={(e) => update(idx, "loss_wt", e.target.value)}
            disabled={readOnly}
          />

          <Input
            className="h-8 text-xs"
            value={row.remarks}
            onChange={(e) => update(idx, "remarks", e.target.value)}
            onKeyDown={(e) => handleTabOnRemarks(e, idx)}
            disabled={readOnly}
          />

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
          Add Loss
        </Button>
      )}
    </div>
  );
}

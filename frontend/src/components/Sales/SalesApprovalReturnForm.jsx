import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

/**
 * Shared return form — used inside the Sheet (list page) and
 * inside SalesApprovalReturnPage (standalone page).
 *
 * Props:
 *   approval  — full approval object from GET /api/sale-approval/:id/
 *   onSave    — async fn(returnedIds: number[]) called on submit
 *   saving    — boolean, disables the button while request is in flight
 */
const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function SalesApprovalReturnForm({ approval, onSave, saving }) {
  const items = approval?.items ?? [];

  // Track which NOT-yet-returned items the user has ticked
  const [selected, setSelected] = useState(new Set());

  const toggle = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const handleSave = () => {
    // Include already-returned IDs too (idempotent on backend)
    const alreadyReturned = items
      .filter((it) => it.ret_status)
      .map((it) => it.id);
    onSave([...alreadyReturned, ...selected]);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Approval header */}
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <span className="text-muted-foreground">Bill No</span>
          <p className="font-semibold">{approval?.billno}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Date</span>
          <p className="font-semibold">
            {approval?.date1
              ? new Date(approval.date1).toLocaleDateString("en-GB").replaceAll("/", "-")
              : "—"}
          </p>
        </div>
        <div>
          <span className="text-muted-foreground">Customer</span>
          <p className="font-semibold">{approval?.ldgr_name ?? "—"}</p>
        </div>
      </div>

      {/* Item table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-muted text-muted-foreground">
              <th className="px-2 py-1.5 text-left border">Barcode</th>
              <th className="px-2 py-1.5 text-left border">Item</th>
              <th className="px-2 py-1.5 text-right border">GW</th>
              <th className="px-2 py-1.5 text-right border">Purity</th>
              <th className="px-2 py-1.5 text-right border">Amount</th>
              <th className="px-2 py-1.5 text-center border">Return</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const alreadyReturned = item.ret_status;
              const checked = alreadyReturned || selected.has(item.id);
              return (
                <tr
                  key={item.id}
                  className={alreadyReturned ? "opacity-50" : ""}
                >
                  <td className="px-2 py-1.5 border font-mono">
                    {item.barcode}
                  </td>
                  <td className="px-2 py-1.5 border">
                    {item.item_name ?? item.item}
                  </td>
                  <td className="px-2 py-1.5 border text-right">
                    {Number(item.gw || 0).toFixed(3)}
                  </td>
                  <td className="px-2 py-1.5 border text-right">
                    {item.purity ?? "—"}
                  </td>
                  <td className="px-2 py-1.5 border text-right tabular-nums">
                    {fmt(item.amount)}
                  </td>
                  <td className="px-2 py-1.5 border text-center">
                    <Checkbox
                      checked={checked}
                      disabled={alreadyReturned}
                      onCheckedChange={() => toggle(item.id)}
                    />
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-2 py-4 text-center text-muted-foreground">
                  No items on this approval.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Button
        onClick={handleSave}
        disabled={saving || selected.size === 0}
        className="self-start"
      >
        {saving ? "Saving…" : "Save Returns"}
      </Button>
    </div>
  );
}

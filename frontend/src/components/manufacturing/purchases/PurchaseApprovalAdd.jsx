import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { FieldContainer } from "@/Utils.jsx";
import { formatNumber } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useActiveFiscalYear } from "@/hooks/useActiveFiscalYear";
import { useLedgers, useItems, usePurities, usePackets } from "@/hooks/queries/masters";
import { fetchPapNoNext, fetchPurchaseApproval, savePurchaseApproval } from "@/services/apiService";

const today = () => new Date().toISOString().split("T")[0];
const num = (v) => parseFloat(v || 0) || 0;
const blankSub = () => ({ sub_item: "", sub_item_name: "", packet: "", metal_purity: "", sub_pcs: "", sub_ct: "", sub_gw: "", rate: "", value: 0 });
const blankLine = () => ({
  item: "", item_name: "", pcs: "", gw: "", purity: "", making_type: "", making_value: "", remarks: "", details: [],
});
const errText = (e) => {
  if (!e) return "Request failed";
  if (typeof e === "string") return e;
  if (e.detail) return String(e.detail);
  return Object.entries(e)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join("; ");
};

// Same rule as the purchase voucher: stones price on carats, everything else on weight.
const subValue = (sub, uomOf) => {
  const base = (uomOf(sub.sub_item) || "").toLowerCase() === "ct" ? num(sub.sub_ct) : num(sub.sub_gw);
  return Math.round(base * num(sub.rate) * 100) / 100;
};
const lineAmount = (l) =>
  l.details.reduce((s, d) => s + num(d.value), 0) + (l.making_type === "val" ? num(l.making_value) : 0);

function PurchaseApprovalAdd() {
  const { id } = useParams();
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { min: fyMin, max: fyMax } = useActiveFiscalYear();

  const vendorsQuery = useLedgers({ type: "VD,KR" });
  const itemsQuery = useItems();
  const mainItemsQuery = useItems({ type: "M" });
  const puritiesQuery = usePurities();
  const packetsQuery = usePackets();
  const vendors = useMemo(() => vendorsQuery.data ?? [], [vendorsQuery.data]);
  const items = useMemo(() => itemsQuery.data ?? [], [itemsQuery.data]);
  const mainItems = useMemo(() => mainItemsQuery.data ?? [], [mainItemsQuery.data]);
  const purities = useMemo(() => puritiesQuery.data ?? [], [puritiesQuery.data]);
  const packets = useMemo(() => packetsQuery.data ?? [], [packetsQuery.data]);
  const uomOf = (ref) => items.find((i) => i.short_code === ref || i.id === ref)?.uom;

  const [billno, setBillno] = useState("");
  const [date1, setDate1] = useState(today());
  const [vendor, setVendor] = useState({ id: "", name: "" });
  const [narration, setNarration] = useState("");
  const [lines, setLines] = useState([blankLine()]);
  const [locked, setLocked] = useState(false); // some line already bought/returned
  const [saving, setSaving] = useState(false);

  // New approval: show the number the server will assign (it is authoritative on save).
  useEffect(() => {
    if (id) return;
    fetchPapNoNext().then((r) => r.success && setBillno(r.data.billno));
  }, [id]);

  // Edit: load the saved approval.
  useEffect(() => {
    if (!id) return;
    fetchPurchaseApproval(id).then((r) => {
      if (!r.success) return toast({ title: "Could not load approval", description: errText(r.error), variant: "destructive" });
      const d = r.data;
      setBillno(d.billno);
      setDate1(d.date1);
      setVendor({ id: d.ldgr, name: d.ldgr_name });
      setNarration(d.narration || "");
      setLocked(d.items.some((i) => i.status !== "pending"));
      setLines(d.items.map((i) => ({
        item: i.item, item_name: i.item_name, pcs: i.pcs, gw: i.gw, purity: i.purity || "",
        making_type: i.making_type || "", making_value: i.making_value, remarks: i.remarks || "",
        details: (i.details || []).map((s) => ({
          sub_item: s.sub_item, sub_item_name: s.sub_item_name, packet: s.packet || "",
          metal_purity: s.metal_purity || "", sub_pcs: s.sub_pcs, sub_ct: s.sub_ct, sub_gw: s.sub_gw,
          rate: s.rate, value: num(s.value),
        })),
      })));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const setLine = (li, patch) => setLines((prev) => prev.map((l, i) => (i === li ? { ...l, ...patch } : l)));
  const removeLine = (li) => setLines((prev) => (prev.length === 1 ? [blankLine()] : prev.filter((_, i) => i !== li)));
  const setSub = (li, si, patch) =>
    setLines((prev) => prev.map((l, i) => {
      if (i !== li) return l;
      const details = l.details.map((d, j) => {
        if (j !== si) return d;
        const next = { ...d, ...patch };
        return { ...next, value: subValue(next, uomOf) };
      });
      return { ...l, details };
    }));
  const addSub = (li) => setLine(li, { details: [...lines[li].details, blankSub()] });
  const removeSub = (li, si) => setLine(li, { details: lines[li].details.filter((_, j) => j !== si) });

  const subGwOf = (l) => l.details.reduce((s, d) => s + num(d.sub_gw), 0);
  const mismatch = (l) => l.details.length > 0 && Math.abs(subGwOf(l) - num(l.gw)) > 0.01;
  const totalGw = lines.reduce((s, l) => s + num(l.gw), 0);
  const totalAmt = lines.reduce((s, l) => s + lineAmount(l), 0);

  const handleSave = async () => {
    if (!vendor.id) return toast({ title: "Choose a vendor", variant: "destructive" });
    const filled = lines.filter((l) => l.item);
    if (!filled.length) return toast({ title: "Add at least one item", variant: "destructive" });
    const bad = filled.find(mismatch);
    if (bad) {
      return toast({
        title: `Weight mismatch for "${bad.item_name || bad.item}"`,
        description: `Sub-items total ${subGwOf(bad).toFixed(3)}g but item GW is ${num(bad.gw).toFixed(3)}g. Please reconcile.`,
        variant: "destructive",
      });
    }
    const payload = {
      date1,
      ldgr: vendor.id,
      narration,
      items: filled.map((l) => ({
        item: l.item,
        pcs: parseInt(l.pcs || 0, 10),
        gw: l.gw || 0,
        purity: l.purity || null,
        making_type: l.making_type || "",
        making: l.making_type === "val" ? num(l.making_value) : 0,
        making_value: l.making_type === "val" ? num(l.making_value) : 0,
        amount: lineAmount(l),
        remarks: l.remarks || "",
        details: l.details.filter((d) => d.sub_item).map((d) => ({
          sub_item: d.sub_item,
          packet: d.packet || null,
          metal_purity: d.metal_purity || null,
          sub_pcs: parseInt(d.sub_pcs || 0, 10),
          sub_ct: d.sub_ct || 0,
          sub_gw: d.sub_gw || 0,
          rate: d.rate || 0,
          value: d.value || 0,
        })),
      })),
    };
    setSaving(true);
    const res = await savePurchaseApproval(payload, id);
    setSaving(false);
    if (!res.success) {
      return toast({ title: "Could not save approval", description: errText(res.error), variant: "destructive" });
    }
    queryClient.invalidateQueries({ queryKey: ["purchaseApprovals"] });
    toast({ title: id ? "Purchase approval updated" : `Purchase approval ${res.data.billno} saved` });
    navigate("/purchase/purchaseapproval/list/");
  };

  useF4Submit(handleSave);

  const purityPicker = (value, onChange, disabled) => (
    <Select value={value || ""} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger><SelectValue placeholder="Purity" /></SelectTrigger>
      <SelectContent>
        {purities.map((p) => (
          <SelectItem key={p.id ?? p.purity} value={String(p.purity)}>{p.purity}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );

  return (
    <div className="p-4 flex flex-col gap-4">
      {locked && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Some lines on this approval are already bought or returned, so it can no longer be edited.
          Undo the returns from the list to change it.
        </div>
      )}
      <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
        Saving adds these items to stock, like a purchase voucher, but posts no accounting entry.
        Buying a line later moves it onto a purchase voucher; returning it takes it back out of stock.
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <FieldContainer>
          <Label>Approval No</Label>
          <Input value={billno} readOnly placeholder="Assigned on save" />
        </FieldContainer>
        <FieldContainer>
          <Label>Date</Label>
          <Input type="date" value={date1} min={fyMin} max={fyMax} onChange={(e) => setDate1(e.target.value)} disabled={locked} />
        </FieldContainer>
        <FieldContainer>
          <Label>Vendor</Label>
          <SearchableComboBox
            options={vendors}
            labelKey="ac_name"
            searchKeys={["ac_name"]}
            value={vendor.name}
            placeholder="Search vendor…"
            disabled={locked}
            onSelect={(v) => setVendor({ id: v.id, name: v.ac_name })}
          />
        </FieldContainer>
        <FieldContainer>
          <Label>Narration</Label>
          <Input value={narration} maxLength={100} onChange={(e) => setNarration(e.target.value)} disabled={locked} />
        </FieldContainer>
      </div>

      {lines.map((l, li) => (
        <div key={li} className="border rounded-md">
          <div className="flex items-center justify-between bg-muted/50 px-3 py-2">
            <span className="text-sm font-semibold">Item {li + 1}</span>
            {!locked && (
              <button onClick={() => removeLine(li)} className="p-1.5 rounded text-red-500 hover:bg-red-50" title="Remove item">
                <Trash2 className="size-4" />
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-7 gap-3 p-3">
            <div className="col-span-2"><FieldContainer>
              <Label>Main item</Label>
              <SearchableComboBox
                options={mainItems}
                labelKey="item_name"
                searchKeys={["item_name", "short_code"]}
                value={l.item_name}
                placeholder="Search item…"
                disabled={locked}
                onSelect={(it) => setLine(li, { item: it.id, item_name: it.item_name })}
              />
            </FieldContainer></div>
            <FieldContainer>
              <Label>Pcs</Label>
              <Input type="number" min="0" value={l.pcs} disabled={locked} onChange={(e) => setLine(li, { pcs: e.target.value })} />
            </FieldContainer>
            <FieldContainer>
              <Label>Gross wt</Label>
              <Input type="number" step="0.001" min="0" value={l.gw} disabled={locked} onChange={(e) => setLine(li, { gw: e.target.value })} />
            </FieldContainer>
            <FieldContainer>
              <Label>Purity</Label>
              {purityPicker(l.purity, (v) => setLine(li, { purity: v }), locked)}
            </FieldContainer>
            <FieldContainer>
              <Label>Making</Label>
              <div className="flex gap-2">
                <Select value={l.making_type || "none"} disabled={locked}
                  onValueChange={(v) => setLine(li, { making_type: v === "none" ? "" : v, making_value: v === "val" ? l.making_value : "" })}>
                  <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    <SelectItem value="val">Value</SelectItem>
                  </SelectContent>
                </Select>
                {l.making_type === "val" && (
                  <Input type="number" step="0.01" min="0" value={l.making_value} disabled={locked}
                    onChange={(e) => setLine(li, { making_value: e.target.value })} />
                )}
              </div>
            </FieldContainer>
            <FieldContainer>
              <Label>Item value</Label>
              <Input value={formatNumber(lineAmount(l))} readOnly />
            </FieldContainer>
          </div>

          <div className="px-3 pb-3">
            {l.details.length > 0 && (
              <div className="border rounded-md overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-accent-50 text-left text-xs uppercase text-primary">
                    <tr>
                      <th className="p-2 w-36">Packet</th>
                      <th className="p-2 min-w-48">Sub item</th>
                      <th className="p-2 w-20">Pcs</th>
                      <th className="p-2 w-24">Ct</th>
                      <th className="p-2 w-28">Gross wt</th>
                      <th className="p-2 w-28">Purity</th>
                      <th className="p-2 w-28">Rate</th>
                      <th className="p-2 w-28">Value</th>
                      <th className="p-2 w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {l.details.map((d, si) => (
                      <tr key={si} className="border-t align-top">
                        <td className="p-2">
                          <SearchableComboBox
                            options={packets}
                            labelKey="pckt_no"
                            searchKeys={["pckt_no", "stone_item_name"]}
                            value={d.packet}
                            placeholder="Packet"
                            disabled={locked}
                            onSelect={(p) => setSub(li, si, {
                              packet: p.pckt_no,
                              sub_item: p.stone_item_short_code || d.sub_item,
                              sub_item_name: p.stone_item_name || d.sub_item_name,
                            })}
                          />
                        </td>
                        <td className="p-2">
                          <SearchableComboBox
                            options={items}
                            labelKey="item_name"
                            searchKeys={["item_name", "short_code"]}
                            value={d.sub_item_name}
                            placeholder="Search item…"
                            disabled={locked}
                            onSelect={(it) => setSub(li, si, { sub_item: it.id, sub_item_name: it.item_name })}
                          />
                        </td>
                        <td className="p-2"><Input type="number" min="0" value={d.sub_pcs} disabled={locked} onChange={(e) => setSub(li, si, { sub_pcs: e.target.value })} /></td>
                        <td className="p-2"><Input type="number" step="0.001" min="0" value={d.sub_ct} disabled={locked} onChange={(e) => setSub(li, si, { sub_ct: e.target.value })} /></td>
                        <td className="p-2"><Input type="number" step="0.001" min="0" value={d.sub_gw} disabled={locked} onChange={(e) => setSub(li, si, { sub_gw: e.target.value })} /></td>
                        <td className="p-2">{purityPicker(d.metal_purity, (v) => setSub(li, si, { metal_purity: v }), locked)}</td>
                        <td className="p-2"><Input type="number" step="0.01" min="0" value={d.rate} disabled={locked} onChange={(e) => setSub(li, si, { rate: e.target.value })} /></td>
                        <td className="p-2"><Input value={formatNumber(d.value)} readOnly /></td>
                        <td className="p-2">
                          {!locked && (
                            <button onClick={() => removeSub(li, si)} className="p-1.5 rounded text-red-500 hover:bg-red-50">
                              <Trash2 className="size-4" />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex items-center justify-between pt-2">
              {!locked ? (
                <Button variant="outline" size="sm" className="gap-1.5" onClick={() => addSub(li)}>
                  <Plus className="size-4" /> Add sub item
                </Button>
              ) : <span />}
              {l.details.length > 0 && (
                <span className={`text-xs ${mismatch(l) ? "text-red-600 font-semibold" : "text-muted-foreground"}`}>
                  Sub-items {formatNumber(subGwOf(l), { decimals: 3 })}g of {formatNumber(num(l.gw), { decimals: 3 })}g
                </span>
              )}
            </div>
          </div>
        </div>
      ))}

      <div className="flex items-center justify-between">
        {!locked ? (
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setLines((p) => [...p, blankLine()])}>
            <Plus className="size-4" /> Add item
          </Button>
        ) : <span />}
        <div className="text-sm font-semibold">
          Total {formatNumber(totalGw, { decimals: 3 })}g · {formatNumber(totalAmt)}
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate("/purchase/purchaseapproval/list/")}>Cancel</Button>
        <Button onClick={handleSave} disabled={saving || locked}>{saving ? "Saving…" : id ? "Update" : "Save"}</Button>
      </div>
    </div>
  );
}

export default PurchaseApprovalAdd;

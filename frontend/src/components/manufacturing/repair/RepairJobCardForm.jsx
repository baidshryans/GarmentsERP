import { useState, useEffect, useCallback } from "react";
import { getFormatConfig } from "@/lib/format";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  fetchRepairJobCardNextNo,
  fetchRepairJobCardById,
  createRepairJobCard,
  updateRepairJobCard,
  updateRepairJobCardStatus,
  getLedgers,
  fetchMainItem,
  fetchPurity,
} from "@/services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import RepairLossTable    from "./RepairLossTable";
import RepairStoneTable   from "./RepairStoneTable";
import RepairWeightSummary from "./RepairWeightSummary";
import { ArrowLeft, ExternalLink, Printer } from "lucide-react";
import { openAndPrint } from "@/services/print/utils";
import RepairJobCardPrint from "@/services/print/RepairJobCard";

const today = () => new Date().toISOString().split("T")[0];

const STATUS_LABELS = {
  RCV:  "Received from Customer",
  ISS:  "Issued to Karigar",
  RECV: "Received from Karigar",
  RDY:  "Ready for Delivery",
  DLV:  "Delivered",
};

const STATUS_COLOR = {
  RCV:  "bg-blue-100 text-blue-700",
  ISS:  "bg-amber-100 text-amber-700",
  RECV: "bg-purple-100 text-primary",
  RDY:  "bg-green-100 text-green-700",
  DLV:  "bg-gray-100 text-gray-600",
};

export default function RepairJobCardForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const isNew = !id;

  // Master data
  const [purities, setPurities] = useState([]);
  const [items,    setItems]    = useState([]);
  const [customers, setCustomers] = useState([]);
  const [customerSearch, setCustomerSearch] = useState("");

  // Form fields
  const [rjcNo,             setRjcNo]            = useState("");
  const [date1,             setDate1]             = useState(today());
  const [customerId,        setCustomerId]        = useState("");
  const [status,            setStatus]            = useState("RCV");
  const [itemId,            setItemId]            = useState("");
  const [purityId,          setPurityId]          = useState("");
  const [description,       setDescription]       = useState("");
  const [receivedGw,        setReceivedGw]        = useState("");
  const [receivedNw,        setReceivedNw]        = useState("");
  const [expectedDelivery,  setExpectedDelivery]  = useState("");
  const [estimatedMaking,   setEstimatedMaking]   = useState("");
  const [remarks,           setRemarks]           = useState("");

  // Child rows
  const [losses, setLosses] = useState([]);
  const [stones, setStones] = useState([]);

  // Karigar links (read-only display)
  const [karigarLinks, setKarigarLinks] = useState([]);

  // From API: returned weight (sum of karigar receive items)
  const [returnedGw, setReturnedGw] = useState(0);

  const [saving, setSaving] = useState(false);
  const [retailName, setRetailName] = useState("");

  // ── Load master data ──────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([fetchMainItem(), fetchPurity()]).then(([itemRes, purRes]) => {
      if (itemRes.success) {
        const arr = Array.isArray(itemRes.data) ? itemRes.data : itemRes.data?.results ?? [];
        setItems(arr);
      }
      if (purRes.success) {
        const arr = Array.isArray(purRes.data) ? purRes.data : purRes.data?.results ?? [];
        setPurities(arr);
      }
    });
  }, []);

  // ── Load customers (debounced search) ────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(async () => {
      const res = await getLedgers({ type: "CO", search: customerSearch });
      if (res.success) {
        const arr = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        setCustomers(arr);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [customerSearch]);

  // ── Load existing card (edit mode) ───────────────────────────────────────
  useEffect(() => {
    if (isNew) {
      fetchRepairJobCardNextNo().then((res) => {
        if (res.success) setRjcNo(res.data?.rjc_no ?? "");
      });
    } else {
      fetchRepairJobCardById(id).then((res) => {
        if (!res.success) { toast({ title: "Failed to load", variant: "destructive" }); return; }
        const d = res.data;
        setRjcNo(d.rjc_no);
        setDate1(d.date1);
        setCustomerId(String(d.customer));
        setCustomerSearch(d.customer_name ?? "");
        setStatus(d.status);
        setItemId(d.item   ? String(d.item)   : "");
        setPurityId(d.purity ? String(d.purity) : "");
        setDescription(d.description ?? "");
        setReceivedGw(d.received_gw ?? "");
        setReceivedNw(d.received_nw ?? "");
        setExpectedDelivery(d.expected_delivery_date ?? "");
        setEstimatedMaking(d.estimated_making ?? "");
        setRemarks(d.remarks ?? "");
        setReturnedGw(parseFloat(d.returned_gw) || 0);
        setLosses((d.losses ?? []).map((l) => ({ ...l, _key: l.id })));
        setStones((d.stones ?? []).map((s) => ({ ...s, _key: s.id })));
        setKarigarLinks(d.karigar_links ?? []);
        setRetailName(d.retail_name ?? "");
      });
    }
  }, [id]);

  // ── Save ─────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!customerId) { toast({ title: "Customer is required." }); return; }
    setSaving(true);

    const payload = {
      date1,
      customer: parseInt(customerId),
      item:     itemId   ? parseInt(itemId)   : null,
      purity:   purityId ? parseInt(purityId) : null,
      description,
      received_gw:            parseFloat(receivedGw)       || 0,
      received_nw:            parseFloat(receivedNw)       || 0,
      expected_delivery_date: expectedDelivery || null,
      estimated_making:       parseFloat(estimatedMaking)  || 0,
      remarks,
      losses: losses.map(({ id: lid, loss_type, loss_wt, remarks: r }) => ({
        ...(lid ? { id: lid } : {}),
        loss_type,
        loss_wt: parseFloat(loss_wt) || 0,
        remarks: r,
      })),
      stones: stones.map(({ id: sid, description: desc, pcs, ct, remarks: r, returned }) => ({
        ...(sid ? { id: sid } : {}),
        description: desc,
        pcs:      parseInt(pcs)  || 0,
        ct:       parseFloat(ct) || 0,
        remarks:  r,
        returned: !!returned,
      })),
    };

    const res = isNew
      ? await createRepairJobCard(payload)
      : await updateRepairJobCard(id, payload);

    if (res.success) {
      toast({ title: isNew ? "Job card created." : "Saved." });
      if (isNew) navigate(`/manufacturing/repair/${res.data.id}`);
    } else {
      const msg =
        typeof res.error === "string"
          ? res.error
          : JSON.stringify(res.error);
      toast({ title: msg, variant: "destructive" });
    }
    setSaving(false);
  };

  // ── Status change ─────────────────────────────────────────────────────────
  const handleStatusChange = async (newStatus) => {
    if (!id) return;
    const res = await updateRepairJobCardStatus(id, newStatus);
    if (res.success) {
      setStatus(newStatus);
      toast({ title: `Status updated to ${STATUS_LABELS[newStatus]}.` });
    } else {
      toast({ title: "Failed to update status.", variant: "destructive" });
    }
  };

  // ── Issue to Karigar URL ──────────────────────────────────────────────────
  const issueUrl = id
    ? `/manufacturing/issue/jobwork/new?type=Repair&rjc=${id}&rjc_no=${encodeURIComponent(rjcNo)}&received_gw=${receivedGw}`
    : null;

  const handlePrint = () => {
    const printData = {
      rjc_no: rjcNo,
      date1,
      customer_name: customerSearch,
      customer_mobile: customers.find((c) => String(c.id) === customerId)?.mobile1 ?? "",
      status,
      item_name:  items.find((it) => String(it.id) === itemId)?.item_name ?? "",
      purity_name: purities.find((p) => String(p.id) === purityId)?.purity ?? "",
      description,
      received_gw: receivedGw,
      received_nw: receivedNw,
      returned_gw: returnedGw,
      expected_delivery_date: expectedDelivery,
      estimated_making: estimatedMaking,
      remarks,
      retail_name: retailName,
      losses,
      stones,
      karigar_links: karigarLinks,
    };
    openAndPrint(<RepairJobCardPrint data={printData} />);
  };

  return (
    <div className="p-4 max-w-5xl space-y-6">
      {/* Back + title */}
      <div className="flex items-center gap-3">
        <Link to="/manufacturing/repair/list/" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" />
        </Link>
        <h1 className="text-lg font-semibold">
          {isNew ? "New Repair Job Card" : `Repair Job Card — ${rjcNo}`}
        </h1>
        {!isNew && (
          <span className={`ml-2 px-2 py-0.5 rounded-full text-[11px] font-medium ${STATUS_COLOR[status] ?? ""}`}>
            {STATUS_LABELS[status] ?? status}
          </span>
        )}
      </div>

      {/* ── Section 1: Header ─────────────────────────────────────────── */}
      <Section title="Job Details">
        <div className="grid grid-cols-3 gap-4">
          <Field label="RJC No">
            <Input value={rjcNo} readOnly className="bg-muted/30" />
          </Field>
          <Field label="Date">
            <Input type="date" value={date1} onChange={(e) => setDate1(e.target.value)} />
          </Field>
          <Field label="Expected Delivery">
            <Input
              type="date"
              value={expectedDelivery}
              onChange={(e) => setExpectedDelivery(e.target.value)}
            />
          </Field>
        </div>

        {/* Customer — searchable */}
        <div className="grid grid-cols-3 gap-4 mt-4">
          <div className="col-span-2">
            <Field label="Customer *">
              <Input
                placeholder="Search customer…"
                value={customerSearch}
                onChange={(e) => { setCustomerSearch(e.target.value); setCustomerId(""); }}
              />
              {customers.length > 0 && !customerId && customerSearch && (
                <div className="border rounded-md shadow-sm mt-1 bg-background z-10 max-h-48 overflow-y-auto absolute w-80">
                  {customers.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                      onClick={() => { setCustomerId(String(c.id)); setCustomerSearch(c.ac_name); setCustomers([]); }}
                    >
                      {c.ac_name}
                    </button>
                  ))}
                </div>
              )}
            </Field>
          </div>
          <Field label={`Estimated Making (${getFormatConfig().symbol})`}>
            <Input
              type="number"
              step="0.01"
              value={estimatedMaking}
              onChange={(e) => setEstimatedMaking(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-4">
          <Field label="Item">
            <Select value={itemId || "__none__"} onValueChange={(v) => setItemId(v === "__none__" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="Select item" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">— None —</SelectItem>
                {items.map((it) => (
                  <SelectItem key={it.id} value={String(it.id)}>{it.item_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Purity">
            <Select value={purityId || "__none__"} onValueChange={(v) => setPurityId(v === "__none__" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="Select purity" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">— None —</SelectItem>
                {purities.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.purity}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>

        <div className="mt-4">
          <Field label="Repair Instructions / Description">
            <Textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the repair work required…"
            />
          </Field>
        </div>

        <div className="mt-4">
          <Field label="Internal Remarks">
            <Textarea
              rows={1}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
            />
          </Field>
        </div>
      </Section>

      {/* ── Section 2: Gold Received ───────────────────────────────────── */}
      <Section title="Gold Received from Customer">
        <div className="grid grid-cols-4 gap-4">
          <Field label="Gross Weight (g)">
            <Input
              type="number"
              step="0.001"
              value={receivedGw}
              onChange={(e) => setReceivedGw(e.target.value)}
            />
          </Field>
          <Field label="Net Weight (g)">
            <Input
              type="number"
              step="0.001"
              value={receivedNw}
              onChange={(e) => setReceivedNw(e.target.value)}
            />
          </Field>
        </div>
      </Section>

      {/* ── Section 3: Stones ─────────────────────────────────────────── */}
      <Section title="Customer-Owned Stones">
        <RepairStoneTable rows={stones} setRows={setStones} readOnly={false} />
      </Section>

      {/* ── Section 4: Karigar Activity (only in edit mode) ───────────── */}
      {!isNew && (
        <Section title="Karigar Activity">
          {karigarLinks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No karigar links yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground border-b">
                  <th className="text-left pb-1">Issue No</th>
                  <th className="text-left pb-1">Karigar</th>
                  <th className="text-left pb-1">Receive No</th>
                  <th className="text-left pb-1">Returned GW</th>
                </tr>
              </thead>
              <tbody>
                {karigarLinks.map((lk) => (
                  <tr key={lk.id} className="border-b last:border-0">
                    <td className="py-1 font-mono">{lk.karigar_issue_no ?? "—"}</td>
                    <td className="py-1">{lk.karigar_name ?? "—"}</td>
                    <td className="py-1 font-mono">{lk.karigar_receive_no ?? "—"}</td>
                    <td className="py-1 tabular-nums">{lk.returned_gw ? parseFloat(lk.returned_gw).toFixed(3) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="mt-3">
            <a
              href={issueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
            >
              Issue to Karigar →
              <ExternalLink className="size-3.5" />
            </a>
          </div>
        </Section>
      )}

      {/* ── Section 5: Named Losses ───────────────────────────────────── */}
      <Section title="Named Losses">
        {!["RECV", "RDY", "DLV"].includes(status) && (
          <p className="text-xs text-muted-foreground">
            Loss entry is available once the karigar returns the piece (status: Received from Karigar).
          </p>
        )}
        <RepairLossTable
          rows={losses}
          setRows={setLosses}
          readOnly={!["RECV", "RDY", "DLV"].includes(status)}
        />
      </Section>

      {/* ── Section 6: Weight Reconciliation ─────────────────────────── */}
      <Section title="Weight Reconciliation">
        <RepairWeightSummary
          receivedGw={receivedGw}
          returnedGw={returnedGw}
          losses={losses}
        />
      </Section>

      {/* ── Section 7: Status controls (edit only) ───────────────────── */}
      {!isNew && (
        <Section title="Status">
          <div className="flex gap-2 flex-wrap">
            {status === "RECV" && (
              <Button variant="outline" size="sm" onClick={() => handleStatusChange("RDY")}>
                Mark Ready for Delivery
              </Button>
            )}
            {status === "RDY" && (
              <Button variant="default" size="sm" onClick={() => handleStatusChange("DLV")}>
                Mark Delivered
              </Button>
            )}
            {status === "DLV" && (
              <span className="text-sm text-muted-foreground">Job delivered.</span>
            )}
          </div>
        </Section>
      )}

      {/* ── Save button ───────────────────────────────────────────────── */}
      <div className="flex gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : isNew ? "Create Job Card" : "Save Changes"}
        </Button>
        {!isNew && (
          <Button variant="outline" onClick={handlePrint} className="gap-1.5">
            <Printer className="size-4" />
            Print Receipt
          </Button>
        )}
        <Button variant="outline" onClick={() => navigate("/manufacturing/repair/list/")}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="space-y-1 relative">
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

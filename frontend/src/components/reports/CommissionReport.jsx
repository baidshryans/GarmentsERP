import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/table";
import { useToast } from "@/hooks/use-toast";
import { BookCheck, AlertCircle, FileText } from "lucide-react";
import { fetchCommissionReport, createCommissionJV } from "@/services/apiService";

function CommissionReport() {
  const { toast } = useToast();

  // Filters
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [fromDate, setFromDate]     = useState(firstOfMonth);
  const [toDate, setToDate]         = useState(today);
  const [spFilter, setSpFilter]     = useState("");
  const [inclJv, setInclJv]         = useState(false);

  // Data
  const [rows, setRows]             = useState([]);
  const [salespersons, setSalespersons] = useState([]);
  const [ldgrConfigured, setLdgrConfigured] = useState(false);
  const [totalCommission, setTotalCommission] = useState(0);
  const [totalReversal, setTotalReversal]     = useState(0);
  const [totalNet, setTotalNet]               = useState(0);
  const [loading, setLoading]       = useState(false);
  const [selected, setSelected]     = useState(new Set()); // Set of row keys "voucherId_spId"
  const [creatingJV, setCreatingJV] = useState(false);

  const rowKey = (r) => `${r.voucher_id}_${r.salesperson_id}`;

  const load = useCallback(async () => {
    setLoading(true);
    setSelected(new Set());
    const params = { from_date: fromDate, to_date: toDate };
    if (spFilter) params.salesperson = spFilter;
    if (inclJv)   params.include_jv_created = "true";

    const res = await fetchCommissionReport(params);
    if (res.success) {
      setRows(res.data.rows || []);
      setSalespersons(res.data.salespersons || []);
      setLdgrConfigured(res.data.commission_ledger_configured);
      setTotalCommission(res.data.total_commission || 0);
      setTotalReversal(res.data.total_reversal || 0);
      setTotalNet(res.data.total_net_commission || 0);
    } else {
      toast({ title: "Error loading report", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setLoading(false);
  }, [fromDate, toDate, spFilter, inclJv]);

  useEffect(() => { load(); }, [load]);

  const toggleRow = (key) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const isEligible = (r) => !r.jv_created && r.has_sp_ledger && Number(r.net_commission) > 0;

  const toggleAll = () => {
    const eligible = rows.filter(isEligible);
    if (selected.size === eligible.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(eligible.map(rowKey)));
    }
  };

  const handleCreateJV = async () => {
    if (!ldgrConfigured) {
      toast({
        title: "Commission Ledger not configured",
        description: "Go to Settings → Salesperson Commission and set a commission expense ledger first.",
        variant: "destructive",
      });
      return;
    }
    if (selected.size === 0) {
      toast({ title: "No rows selected", description: "Select at least one row to create JVs.", variant: "destructive" });
      return;
    }

    const entries = rows
      .filter(r => selected.has(rowKey(r)))
      .map(r => ({
        voucher_id:     r.voucher_id,
        salesperson_id: r.salesperson_id,
        // Use net_commission (after any return reversals) as the JV amount
        commission_amt: r.net_commission,
        base_amount:    r.base_amount,
        rate:           r.rate,
      }));

    setCreatingJV(true);
    const res = await createCommissionJV(entries);
    setCreatingJV(false);

    if (res.success) {
      const { created, skipped, jvs } = res.data;
      toast({
        title: `${created} Journal Voucher${created !== 1 ? "s" : ""} created`,
        description: skipped > 0
          ? `${skipped} skipped (no payable ledger or already journalised)`
          : jvs.map(j => j.voucher_no).join(", "),
      });
      load();
    } else {
      toast({ title: "Error creating JVs", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  const eligibleCount = rows.filter(isEligible).length;
  const selectedCount = selected.size;

  const columns = [
    {
      id: "select",
      header: () => {
        const eligible = rows.filter(isEligible);
        return (
          <input
            type="checkbox"
            checked={eligible.length > 0 && selected.size === eligible.length}
            onChange={toggleAll}
            title="Select all eligible rows"
          />
        );
      },
      cell: ({ row }) => {
        const r = row.original;
        const key = rowKey(r);
        const eligible = isEligible(r);
        return (
          <input
            type="checkbox"
            checked={selected.has(key)}
            disabled={!eligible}
            onChange={() => eligible && toggleRow(key)}
            title={
              r.jv_created ? "JV already created" :
              !r.has_sp_ledger ? "No payable ledger assigned to salesperson" :
              Number(r.net_commission) <= 0 ? "Fully reversed by returns — no commission payable" :
              "Select for JV creation"
            }
          />
        );
      },
    },
    {
      header: "Date",
      accessorKey: "date",
      cell: ({ getValue }) => {
        const d = new Date(getValue());
        return d.toLocaleDateString("en-GB").replaceAll("/", "-");
      },
    },
    { header: "Bill No",    accessorKey: "billno" },
    { header: "Party",      accessorKey: "party_name" },
    {
      header: "B2B",
      accessorKey: "is_b2b",
      cell: ({ getValue }) => getValue()
        ? <span className="text-xs bg-blue-100 text-blue-700 rounded px-1">B2B</span>
        : <span className="text-xs text-muted-foreground">B2C</span>,
    },
    { header: "Salesperson", accessorKey: "salesperson_name" },
    {
      header: "Commission On",
      accessorKey: "commission_on",
    },
    {
      header: "Base Amount",
      accessorKey: "base_amount",
      cell: ({ getValue }) => "₹" + Number(getValue()).toLocaleString("en-IN", { minimumFractionDigits: 2 }),
    },
    {
      header: "Rate %",
      accessorKey: "rate",
      cell: ({ getValue }) => getValue() + "%",
    },
    {
      header: "Commission",
      accessorKey: "commission_amt",
      cell: ({ getValue }) => (
        <span className="font-semibold text-primary">
          ₹{Number(getValue()).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </span>
      ),
    },
    {
      header: "Reversal",
      accessorKey: "reversal_amt",
      cell: ({ row }) => {
        const r = row.original;
        if (!r.has_reversal) return <span className="text-xs text-muted-foreground">—</span>;
        return (
          <div className="flex flex-col gap-0.5">
            <span className="text-red-600 font-medium text-xs">
              −₹{Number(r.reversal_amt).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
            {r.has_reversal_jv && (
              <span className="text-[10px] text-green-700 bg-green-50 rounded px-1">JV posted</span>
            )}
            {!r.has_reversal_jv && r.jv_created && (
              <span className="text-[10px] text-amber-700 bg-amber-50 rounded px-1">No reversal JV</span>
            )}
          </div>
        );
      },
    },
    {
      header: "Net Commission",
      accessorKey: "net_commission",
      cell: ({ row }) => {
        const r = row.original;
        const net = Number(r.net_commission);
        return (
          <span className={`font-bold text-sm ${net <= 0 ? "text-muted-foreground line-through" : "text-foreground"}`}>
            ₹{net.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </span>
        );
      },
    },
    {
      header: "JV Status",
      cell: ({ row }) => {
        const r = row.original;
        if (r.jv_created) {
          return <span className="text-xs bg-green-100 text-green-700 rounded px-1.5 py-0.5">✓ JV Created</span>;
        }
        if (!r.has_sp_ledger) {
          return <span className="text-xs bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">No Ledger</span>;
        }
        return <span className="text-xs bg-muted text-muted-foreground rounded px-1.5 py-0.5">Pending</span>;
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Warning if commission ledger not set */}
      {!ldgrConfigured && !loading && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Commission ledger not configured</p>
            <p className="mt-0.5">
              Journal voucher creation is disabled. Go to{" "}
              <strong>Settings → Salesperson Commission</strong> and assign a commission expense ledger.
            </p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Salesperson</Label>
          <Select value={spFilter} onValueChange={v => setSpFilter(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All salespersons" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All salespersons</SelectItem>
              {salespersons.map(s => (
                <SelectItem key={s.id} value={String(s.id)}>{s.salesperson_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2 pb-1">
          <input
            type="checkbox"
            id="inclJv"
            checked={inclJv}
            onChange={e => setInclJv(e.target.checked)}
          />
          <Label htmlFor="inclJv" className="text-xs cursor-pointer">Show already journalised</Label>
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 items-center">
          <span>{rows.length} bill{rows.length !== 1 ? "s" : ""}</span>
          <span>
            Gross:{" "}
            <span className="font-semibold text-foreground">
              ₹{Number(totalCommission).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </span>
          {totalReversal > 0 && (
            <span>
              Reversed:{" "}
              <span className="font-semibold text-red-600">
                −₹{Number(totalReversal).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </span>
          )}
          <span>
            Net:{" "}
            <span className="font-semibold text-primary">
              ₹{Number(totalNet).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </span>
          {selectedCount > 0 && (
            <span className="text-primary font-medium">{selectedCount} selected</span>
          )}
        </div>
        <Button
          onClick={handleCreateJV}
          disabled={creatingJV || selectedCount === 0 || !ldgrConfigured}
          className="gap-1.5"
        >
          <BookCheck className="w-4 h-4" />
          {creatingJV ? "Creating…" : `Create Journal Voucher${selectedCount !== 1 ? "s" : ""}`}
          {selectedCount > 0 && ` (${selectedCount})`}
        </Button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="w-full h-10" />)}
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <FileText className="w-10 h-10" />
          <p className="text-sm">No commission records found for the selected period.</p>
          <p className="text-xs">Make sure salespersons have a commission rate configured.</p>
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}

export default CommissionReport;

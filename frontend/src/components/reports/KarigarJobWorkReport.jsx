import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import { DataTable } from "@/table";
import { useToast } from "@/hooks/use-toast";
import { fetchJobStatusReport } from "@/services/apiService";
import apiClient from "@/services/apiClient";
import { Hammer, Clock, CheckCircle2, AlertTriangle } from "lucide-react";
import { isValidDateRange } from "@/lib/dateRange";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtDate(d) {
  if (!d) return "�";
  const dt = new Date(d);
  return dt.toLocaleDateString("en-GB").replaceAll("/", "-");
}

function isOverdue(dueDateStr) {
  if (!dueDateStr) return false;
  return new Date(dueDateStr) < new Date(new Date().toDateString());
}

function DaysChip({ dueDate, completed }) {
  if (!dueDate) return <span className="text-muted-foreground text-xs">No due date</span>;
  const today = new Date(new Date().toDateString());
  const due   = new Date(dueDate);
  const diff  = Math.round((due - today) / 86400000); // days

  if (completed) {
    return <span className="text-xs text-muted-foreground">�</span>;
  }
  if (diff < 0) {
    return (
      <span className="text-xs font-semibold text-red-600 flex items-center gap-0.5">
        <AlertTriangle className="size-3" />{Math.abs(diff)}d overdue
      </span>
    );
  }
  if (diff === 0) {
    return <span className="text-xs font-semibold text-amber-600">Due today</span>;
  }
  return <span className="text-xs text-muted-foreground">{diff}d left</span>;
}

// ── Main Component ─────────────────────────────────────────────────────────────

function KarigarJobWorkReport() {
  const { toast } = useToast();

  // Filters
  const today        = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [fromDate, setFromDate]   = useState(firstOfMonth);
  const [toDate, setToDate]       = useState(today);
  const [statusFilter, setStatus] = useState("all");   // "all" | "false" | "true"
  const [karigarFilter, setKarigar] = useState("");

  // Data
  const [rows, setRows]         = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [loading, setLoading]   = useState(false);

  // Load karigar list once
  useEffect(() => {
    apiClient.get("/contacts/api/ledger/?role=KR&page_size=500")
      .then(res => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setKarigars(list);
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    setLoading(true);
    const params = { from_date: fromDate, to_date: toDate };
    if (statusFilter !== "all") params.rec_status = statusFilter;
    if (karigarFilter)          params.karigar     = karigarFilter;

    const res = await fetchJobStatusReport(params);
    if (res.success) {
      const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setRows(list);
    } else {
      toast({ title: "Error loading report", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setLoading(false);
  }, [fromDate, toDate, statusFilter, karigarFilter]);

  useEffect(() => { load(); }, [load]);

  // ── Summary counts ────────────────────────────────────────────────────────
  const isFinished = (r) => r.stage === 'FINISHED';
  const total     = rows.length;
  const pending   = rows.filter(r => !isFinished(r)).length;
  const completed = rows.filter(r => isFinished(r)).length;
  const overdue   = rows.filter(r => !isFinished(r) && isOverdue(r.due_date)).length;

  // ── Columns ───────────────────────────────────────────────────────────────
  const columns = [
    {
      header: "#",
      cell: ({ row }) => (
        <span className="text-muted-foreground text-xs">{row.index + 1}</span>
      ),
    },
    {
      header: "Issue Slip",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="flex flex-col gap-0.5">
            <span className="font-medium text-sm">{r.issue_slip?.issue_slip_no ?? "�"}</span>
            <span className="text-xs text-muted-foreground">{r.issue_slip?.issue_slip_type ?? ""}</span>
          </div>
        );
      },
    },
    {
      header: "Date",
      cell: ({ row }) => fmtDate(row.original.issue_slip?.date1),
    },
    {
      header: "Karigar",
      cell: ({ row }) => (
        <span className="text-sm">{row.original.issue_slip?.karigar_ldgr_name ?? "�"}</span>
      ),
    },
    {
      header: "Item",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="flex flex-col gap-0.5">
            <span className="text-sm">{r.item?.item_name ?? "�"}</span>
            {r.design_code && (
              <span className="text-xs text-muted-foreground font-mono">{r.design_code}</span>
            )}
          </div>
        );
      },
    },
    {
      header: "Purity",
      cell: ({ row }) => (
        <span className="text-xs font-medium">{row.original.purity?.purity_name ?? "�"}</span>
      ),
    },
    {
      header: "Pcs",
      accessorKey: "pcs",
      cell: ({ getValue }) => (
        <span className="text-sm font-medium">{getValue()}</span>
      ),
    },
    {
      header: "Approx Wt (g)",
      accessorKey: "approx_wt",
      cell: ({ getValue }) => {
        const v = getValue();
        return v ? <span className="text-sm">{Number(v).toFixed(3)}</span> : <span className="text-muted-foreground text-xs">�</span>;
      },
    },
    {
      header: "Size",
      accessorKey: "size",
      cell: ({ getValue }) => getValue() || <span className="text-muted-foreground text-xs">�</span>,
    },
    {
      header: "Due Date",
      cell: ({ row }) => {
        const r = row.original;
        const due = r.due_date;
        if (!due) return <span className="text-muted-foreground text-xs">�</span>;
        const finished = r.stage === 'FINISHED';
        const over = !finished && isOverdue(due);
        return (
          <div className="flex flex-col gap-0.5">
            <span className={`text-xs font-medium ${over ? "text-red-600" : ""}`}>
              {fmtDate(due)}
            </span>
            <DaysChip dueDate={due} completed={finished} />
          </div>
        );
      },
    },
    {
      header: "Status",
      cell: ({ row }) => {
        const r = row.original;
        const stage = r.stage || (r.rec_status ? 'FINISHED' : 'ISSUED');
        if (stage === 'FINISHED') {
          return (
            <span className="inline-flex items-center gap-1 text-xs bg-green-100 text-green-700 rounded-full px-2 py-0.5 font-medium">
              <CheckCircle2 className="size-3" />Completed
            </span>
          );
        }
        if (stage === 'SEMI_FINISHED_RECEIVED') {
          return (
            <span className="inline-flex items-center gap-1 text-xs bg-blue-100 text-blue-700 rounded-full px-2 py-0.5 font-medium">
              <CheckCircle2 className="size-3" />Semi-Finished
            </span>
          );
        }
        if (stage === 'REISSUED') {
          return (
            <span className="inline-flex items-center gap-1 text-xs bg-violet-100 text-violet-700 rounded-full px-2 py-0.5 font-medium">
              <Hammer className="size-3" />Re-Issued
            </span>
          );
        }
        if (isOverdue(r.due_date)) {
          return (
            <span className="inline-flex items-center gap-1 text-xs bg-red-100 text-red-700 rounded-full px-2 py-0.5 font-medium">
              <AlertTriangle className="size-3" />Overdue
            </span>
          );
        }
        return (
          <span className="inline-flex items-center gap-1 text-xs bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 font-medium">
            <Clock className="size-3" />Pending
          </span>
        );
      },
    },
    {
      header: "Remarks",
      accessorKey: "remarks",
      cell: ({ getValue }) => (
        <span className="text-xs text-muted-foreground">{getValue() || "�"}</span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} max={toDate || undefined} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} min={fromDate || undefined} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Karigar</Label>
          <Select value={karigarFilter} onValueChange={v => setKarigar(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-52">
              <SelectValue placeholder="All karigars" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All karigars</SelectItem>
              {karigars.map(k => (
                <SelectItem key={k.id} value={String(k.id)}>{k.ac_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Status</Label>
          <Select value={statusFilter} onValueChange={setStatus}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="false">Pending</SelectItem>
              <SelectItem value="true">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          {loading ? "Loading�" : "Refresh"}
        </Button>
      </div>

      {/* Summary Cards */}
      {!loading && rows.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <SummaryCard
            icon={<Hammer className="size-4 text-primary" />}
            label="Total Jobs"
            value={total}
            color="violet"
          />
          <SummaryCard
            icon={<Clock className="size-4 text-amber-500" />}
            label="Pending"
            value={pending}
            color="amber"
          />
          <SummaryCard
            icon={<CheckCircle2 className="size-4 text-green-500" />}
            label="Completed"
            value={completed}
            color="green"
          />
          <SummaryCard
            icon={<AlertTriangle className="size-4 text-red-500" />}
            label="Overdue"
            value={overdue}
            color="red"
          />
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(7)].map((_, i) => <Skeleton key={i} className="w-full h-10" />)}
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <Hammer className="size-10" />
          <p className="text-sm">No job work records found for the selected filters.</p>
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}

function SummaryCard({ icon, label, value, color }) {
  const colorMap = {
    violet: "bg-violet-50 border-violet-100",
    amber:  "bg-amber-50  border-amber-100",
    green:  "bg-green-50  border-green-100",
    red:    "bg-red-50    border-red-100",
  };
  const textMap = {
    violet: "text-primary",
    amber:  "text-amber-700",
    green:  "text-green-700",
    red:    "text-red-700",
  };
  return (
    <div className={`rounded-lg border p-3 flex items-center gap-3 ${colorMap[color]}`}>
      <div className="shrink-0">{icon}</div>
      <div>
        <p className={`text-xl font-bold leading-none ${textMap[color]}`}>{value}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
      </div>
    </div>
  );
}

export default KarigarJobWorkReport;

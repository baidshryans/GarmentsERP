import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Plus, Search, Printer, RefreshCw, XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import {
  fetchCreditDebitNotes, cancelCreditDebitNote, fetchCNDNPrintData,
} from "@/services/apiService";
import { openAndPrint } from "@/services/print/utils";
import CreditDebitNotePrint from "@/services/print/CreditDebitNote";

const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function CreditDebitNoteList() {
  const { toast } = useToast();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const load = async () => {
    if (notes.length === 0) setLoading(true);
    else setTransitioning(true);
    const res = await fetchCreditDebitNotes(typeFilter);
    if (res.success) {
      setNotes(Array.isArray(res.data) ? res.data : res.data.results || []);
    } else {
      toast({ title: "Error", description: "Failed to load notes", variant: "destructive" });
    }
    setLoading(false);
    setTransitioning(false);
  };

  useEffect(() => { load(); }, [typeFilter]);

  const filtered = notes.filter((n) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (n.note_no || "").toLowerCase().includes(q) ||
      (n.ldgr_name || "").toLowerCase().includes(q) ||
      (n.reason || "").toLowerCase().includes(q)
    );
  });

  const handlePrint = async (id) => {
    const res = await fetchCNDNPrintData(id);
    if (res.success) {
      openAndPrint(<CreditDebitNotePrint data={res.data} />);
    } else {
      toast({ title: "Error", description: "Failed to load print data", variant: "destructive" });
    }
  };

  const handleCancel = async (id) => {
    if (!confirm("Cancel this note? This will reverse the accounting entry.")) return;
    const res = await cancelCreditDebitNote(id);
    if (res.success) {
      toast({ title: "Cancelled", description: "Note cancelled successfully." });
      load();
    } else {
      toast({ title: "Error", description: res.error?.error || "Failed to cancel", variant: "destructive" });
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex-1 min-w-[240px] max-w-sm relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            placeholder="Search note no, party, reason�"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex rounded-md overflow-hidden border border-border">
          {[
            { k: "",   lbl: "All" },
            { k: "CN", lbl: "Credit Notes" },
            { k: "DN", lbl: "Debit Notes" },
          ].map((t) => (
            <button
              key={t.k}
              onClick={() => setTypeFilter(t.k)}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                typeFilter === t.k
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              {t.lbl}
            </button>
          ))}
        </div>
        <Button size="sm" onClick={load} className="h-9 gap-2" disabled={loading || transitioning}>
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
        <Link to="/accounting/credit-debit-notes/add" className="ml-auto">
          <Button size="sm" className="h-9 gap-2">
            <Plus className="size-4" /> New Note
          </Button>
        </Link>
      </div>

      {/* Table */}
      <div className={`rounded-lg border border-border overflow-hidden ${transitioning ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}`}>
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Note No</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Type</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Date</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Party</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Against</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Reason</th>
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wider">Amount</th>
              <th className="text-center px-4 py-2 text-xs font-semibold uppercase tracking-wider w-28">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(4)].map((_, i) => (
                <tr key={i}>
                  <td colSpan={8} className="px-4 py-2">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </tr>
              ))}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-muted-foreground py-8 text-sm">
                  No credit/debit notes found.
                </td>
              </tr>
            )}
            {!loading &&
              filtered.map((n) => (
                <tr key={n.id} className="border-t border-border hover:bg-muted/20">
                  <td className="px-4 py-2 font-mono font-medium">{n.note_no}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                        n.note_type === "CN"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {n.note_type === "CN" ? "Credit Note" : "Debit Note"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{n.date}</td>
                  <td className="px-4 py-2">{n.ldgr_name}</td>
                  <td className="px-4 py-2 font-mono text-muted-foreground">
                    {n.ref_bill_no || "�"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground truncate max-w-[200px]">
                    {n.reason}
                  </td>
                  <td className="px-4 py-2 text-right font-medium">
                    ₹{fmt(n.amount)}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <div className="flex space-x-4 justify-center">
                      <button
                        onClick={() => handlePrint(n.id)}
                        className="p-1.5 rounded text-emerald-600 hover:bg-emerald-50 transition-colors flex items-center"
                        title="Print"
                      >
                        <Printer className="size-4" />
                      </button>
                      <button
                        onClick={() => handleCancel(n.id)}
                        className="p-1.5 rounded text-amber-600 hover:bg-amber-50 transition-colors flex items-center"
                        title="Cancel Note"
                      >
                        <XCircle className="size-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

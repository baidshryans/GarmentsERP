import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { ChevronDown, ChevronRight } from "lucide-react";

const today = new Date().toISOString().split("T")[0];

const BUCKETS = [
  { key: "0_30", label: "0�30 days" },
  { key: "31_60", label: "31�60 days" },
  { key: "61_90", label: "61�90 days" },
  { key: "above_90", label: "90+ days" },
];

export default function OutstandingReport() {
  const [reportType, setReportType] = useState("debtor");
  const [asOfDate, setAsOfDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState({});

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    try {
      const res = await apiClient.get(
        `/accounting/api/outstanding/?type=${reportType}&as_of_date=${asOfDate}`
      );
      setReport(res.data);
      setExpanded({});
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load report.");
    }
    setLoading(false);
  };

  const toggle = (name) => setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
  const fmt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2 });

  const bucketColor = (key) => {
    if (key === "0_30") return "text-emerald-700";
    if (key === "31_60") return "text-primary";
    if (key === "61_90") return "text-orange-600";
    return "text-rose-600";
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Report Type</Label>
          <div className="flex rounded-md overflow-hidden border border-border">
            {["debtor", "creditor"].map((t) => (
              <button
                key={t}
                onClick={() => setReportType(t)}
                className={`px-4 py-1.5 text-sm font-medium capitalize transition-colors ${
                  reportType === t
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-muted-foreground hover:bg-muted"
                }`}
              >
                {t === "debtor" ? "Debtors (Receivable)" : "Creditors (Payable)"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">As of Date</Label>
          <Input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} className="h-9 w-36" />
        </div>
        <Button size="sm" onClick={fetchReport} className="h-9">Show</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <div className="flex flex-col gap-3">
          {/* Summary strip */}
          <div className="grid grid-cols-5 gap-2">
            {[{ key: "total", label: "Total Outstanding" }, ...BUCKETS].map(({ key, label }) => (
              <div key={key} className="rounded-lg border border-border p-3 bg-background">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className={`text-sm font-bold mt-0.5 ${key === "total" ? "text-foreground" : bucketColor(key)}`}>
                  ₹{fmt(report.summary[key] ?? 0)}
                </p>
              </div>
            ))}
          </div>

          {/* Party rows */}
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 text-left font-semibold">Party</th>
                  <th className="px-4 py-2.5 text-right font-semibold">0�30</th>
                  <th className="px-4 py-2.5 text-right font-semibold">31�60</th>
                  <th className="px-4 py-2.5 text-right font-semibold">61�90</th>
                  <th className="px-4 py-2.5 text-right font-semibold">90+</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {report.parties.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-10 text-muted-foreground">
                      No outstanding {reportType === "debtor" ? "receivables" : "payables"}.
                    </td>
                  </tr>
                )}
                {report.parties.map((party, i) => (
                  <>
                    <tr
                      key={party.name}
                      className={`border-t border-border cursor-pointer hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/20" : ""}`}
                      onClick={() => toggle(party.name)}
                    >
                      <td className="px-4 py-2.5 flex items-center gap-2">
                        {expanded[party.name]
                          ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                          : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
                        <span className="font-medium">{party.name}</span>
                      </td>
                      <td className={`px-4 py-2.5 text-right ${bucketColor("0_30")}`}>{Number(party["0_30"]) > 0 ? fmt(party["0_30"]) : "�"}</td>
                      <td className={`px-4 py-2.5 text-right ${bucketColor("31_60")}`}>{Number(party["31_60"]) > 0 ? fmt(party["31_60"]) : "�"}</td>
                      <td className={`px-4 py-2.5 text-right ${bucketColor("61_90")}`}>{Number(party["61_90"]) > 0 ? fmt(party["61_90"]) : "�"}</td>
                      <td className={`px-4 py-2.5 text-right ${bucketColor("above_90")}`}>{Number(party["above_90"]) > 0 ? fmt(party["above_90"]) : "�"}</td>
                      <td className="px-4 py-2.5 text-right font-semibold">{fmt(party.total)}</td>
                    </tr>
                    {expanded[party.name] && party.bills.map((bill, j) => (
                      <tr key={j} className="border-t border-border/40 bg-muted/10 text-xs">
                        <td className="px-8 py-1.5 text-muted-foreground">{bill.bill_no}</td>
                        <td colSpan={4} className="px-4 py-1.5 text-muted-foreground">
                          {bill.date} � {bill.age_days} days old � Bill: ₹{fmt(bill.total_amount)}
                        </td>
                        <td className="px-4 py-1.5 text-right font-medium">₹{fmt(bill.due_amount)}</td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

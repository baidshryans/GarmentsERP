import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { AlertTriangle, Play, Eye, Database, CheckCircle2 } from "lucide-react";
import {
  carryForwardPreview,
  carryForwardExecute,
  getCarryForwardLog,
  getRetails,
} from "@/services/apiService";

export default function CarryForwardPage() {
  const { toast } = useToast();
  const [cutoffDate, setCutoffDate] = useState("");
  const [retailId, setRetailId] = useState("all");
  const [retails, setRetails] = useState([]);
  const [previewOutput, setPreviewOutput] = useState("");
  const [executeOutput, setExecuteOutput] = useState("");
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    loadRetails();
    loadLogs();
  }, []);

  async function loadRetails() {
    const res = await getRetails();
    if (res.success) {
      const list = res.data.results?.[0]?.location || [];
      setRetails(list);
    }
  }

  async function loadLogs() {
    const res = await getCarryForwardLog();
    if (res.success) setLogs(res.data);
  }

  async function handlePreview() {
    if (!cutoffDate) {
      toast({ variant: "destructive", title: "Select a cutoff date" });
      return;
    }
    setLoading(true);
    setPreviewOutput("");
    setExecuteOutput("");
    setConfirming(false);
    const res = await carryForwardPreview({
      cutoff_date: cutoffDate,
      retail_id: retailId === "all" ? null : retailId,
    });
    setLoading(false);
    if (res.success && res.data.returncode === 0) {
      setPreviewOutput(res.data.output);
    } else {
      const err = res.data?.errors || res.data?.output || res.error;
      toast({ variant: "destructive", title: "Preview failed", description: String(err).slice(0, 200) });
      setPreviewOutput(res.data?.output || "");
    }
  }

  async function handleExecute() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setLoading(true);
    setExecuteOutput("");
    const res = await carryForwardExecute({
      cutoff_date: cutoffDate,
      retail_id: retailId === "all" ? null : retailId,
    });
    setLoading(false);
    setConfirming(false);
    if (res.success && res.data.success) {
      setExecuteOutput(res.data.output);
      toast({ title: "Carry-forward complete", description: "Database has been replaced. Please refresh the application." });
      loadLogs();
    } else {
      const err = res.data?.errors || res.data?.output || res.error;
      toast({ variant: "destructive", title: "Carry-forward failed", description: String(err).slice(0, 200) });
      setExecuteOutput(res.data?.output || "");
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Controls */}
      <div className="border rounded-lg p-4 space-y-4 bg-card">
        <h3 className="font-semibold flex items-center gap-2">
          <Database className="size-4" /> Database Carry-Forward
        </h3>
        <p className="text-sm text-muted-foreground">
          Create a fresh database carrying forward only master data, opening balances, and pending work.
          All completed transactions (sales, purchases, vouchers) will be discarded. The old database is
          saved as a backup file on disk.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="cutoff-date">Cutoff Date</Label>
            <Input
              id="cutoff-date"
              type="date"
              value={cutoffDate}
              onChange={(e) => { setCutoffDate(e.target.value); setConfirming(false); }}
            />
          </div>
          <div>
            <Label htmlFor="retail-select">Retail</Label>
            <Select value={retailId} onValueChange={(v) => { setRetailId(v); setConfirming(false); }}>
              <SelectTrigger id="retail-select">
                <SelectValue placeholder="All Retails" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Retails</SelectItem>
                {retails.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>
                    {r.retail_code} - {r.retail_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end gap-2">
            <Button variant="outline" onClick={handlePreview} disabled={loading}>
              <Eye className="size-4 mr-1" /> Preview
            </Button>
            {!confirming ? (
              <Button variant="destructive" onClick={handleExecute} disabled={loading || !previewOutput}>
                <Play className="size-4 mr-1" /> Execute
              </Button>
            ) : (
              <Button variant="destructive" onClick={handleExecute} disabled={loading}>
                <AlertTriangle className="size-4 mr-1" /> Confirm Execute
              </Button>
            )}
          </div>
        </div>

        {confirming && (
          <div className="bg-destructive/10 border border-destructive/30 rounded p-3 text-sm">
            <strong>Warning:</strong> This will replace the current database with a fresh one.
            Completed transactions will no longer be accessible. The old database will be saved
            as a backup file. Click "Confirm Execute" to proceed.
          </div>
        )}
      </div>

      {/* Preview / Execute Output */}
      {(previewOutput || executeOutput) && (
        <div className="border rounded-lg p-4 bg-card">
          <h4 className="font-semibold mb-2">
            {executeOutput ? "Execution Result" : "Preview"}
          </h4>
          <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-96 whitespace-pre-wrap">
            {executeOutput || previewOutput}
          </pre>
        </div>
      )}

      {/* History */}
      {logs.length > 0 && (
        <div className="border rounded-lg p-4 bg-card">
          <h4 className="font-semibold mb-2">Carry-Forward History</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2 pr-3">Date</th>
                  <th className="py-2 pr-3">Cutoff</th>
                  <th className="py-2 pr-3">Retail</th>
                  <th className="py-2 pr-3">New FY</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Master</th>
                  <th className="py-2 pr-3">Live</th>
                  <th className="py-2">OB Ledgers</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b">
                    <td className="py-2 pr-3">{new Date(log.created_at).toLocaleDateString()}</td>
                    <td className="py-2 pr-3">{log.cutoff_date}</td>
                    <td className="py-2 pr-3">{log.retail__retail_code || "All"}</td>
                    <td className="py-2 pr-3">{log.new_fy_code}</td>
                    <td className="py-2 pr-3">
                      {log.status === "success" ? (
                        <span className="text-green-600 flex items-center gap-1">
                          <CheckCircle2 className="size-3" /> Success
                        </span>
                      ) : (
                        <span className="text-red-600">{log.status}</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">{log.master_rows_copied}</td>
                    <td className="py-2 pr-3">{log.live_rows_copied}</td>
                    <td className="py-2">{log.ledgers_with_opening}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

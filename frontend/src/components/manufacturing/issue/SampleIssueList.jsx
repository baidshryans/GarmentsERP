import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { fetchSampleIssues, deleteSampleIssue } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";
import { Trash2, SquarePen } from "lucide-react";

export default function SampleIssueList() {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState("");
  const { toast } = useToast();

  const load = async () => {
    const res = await fetchSampleIssues({ search });
    if (res.success) {
      setRows(Array.isArray(res.data) ? res.data : res.data.results || []);
    }
  };

  useEffect(() => { load(); }, []);

  const onDelete = async (id) => {
    if (!window.confirm("Delete this Sample Issue?")) return;
    const res = await deleteSampleIssue(id);
    if (res.success) { toast({ title: "Deleted" }); load(); }
    else toast({ title: "Delete failed", variant: "destructive" });
  };

  return (
    <div className="p-4 space-y-3">
      <div className="flex gap-2 items-center">
        <h2 className="text-xl font-semibold flex-1">Sample Issues</h2>
        <Input placeholder="Search billno / karigar" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
        <Button onClick={load} variant="secondary">Search</Button>
        <Button asChild><Link to="/manufacturing/issue/sample-issue/new">+ New</Link></Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Bill No</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Karigar</TableHead>
            <TableHead>Items</TableHead>
            <TableHead>Remarks</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell>{r.billno}</TableCell>
              <TableCell>{r.date1}</TableCell>
              <TableCell>{r.karigar_ldgr_name}</TableCell>
              <TableCell>{r.items?.length || 0}</TableCell>
              <TableCell>{r.remarks}</TableCell>
              <TableCell className="flex gap-2">
                <Link to={`/manufacturing/issue/sample-issue/${r.id}`}><SquarePen size={16} /></Link>
                <button onClick={() => onDelete(r.id)}><Trash2 size={16} /></button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

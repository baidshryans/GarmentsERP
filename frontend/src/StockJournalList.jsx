import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { openAndPrint } from "@/services/print/utils";
import { fetchStockJournal, deleteStockJournal, fetchStockJournalForEdit } from "./services/apiService";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from "react-router-dom";

// ── Print template rendered inside the new window ───────────────────────────
function StockJournalPrintView({ data }) {
  const rows    = data.stockjournaldetail_set ?? [];
  const retail  = localStorage.getItem("retail_name") || "";

  const totals = ["Issue", "Receive"].map(type => {
    const filtered = rows.filter(r => r.doc_type === type);
    if (!filtered.length) return null;
    return {
      type,
      pcs:  filtered.reduce((s, r) => s + Number(r.pcs  || 0), 0),
      ct:   filtered.reduce((s, r) => s + Number(r.ct   || 0), 0),
      gw:   filtered.reduce((s, r) => s + Number(r.gw   || 0), 0),
      loss: filtered.reduce((s, r) => s + Number(r.loss || 0), 0),
    };
  }).filter(Boolean);

  const tdStyle  = { border: "1px solid #999", padding: "4px 7px" };
  const thStyle  = { ...tdStyle, background: "#e8e8e8", fontWeight: "bold", textAlign: "center" };
  const totStyle = { ...tdStyle, background: "#f0f0f0", fontWeight: "bold" };

  return (
    <div style={{ fontFamily: "serif", padding: "16px", fontSize: 12 }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 14 }}>
        {retail && <p style={{ margin: 0, fontSize: 15, fontWeight: "bold" }}>{retail}</p>}
        <p style={{ margin: "4px 0", fontSize: 20, fontWeight: "bold", letterSpacing: 1 }}>STOCK JOURNAL</p>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
          <span><strong>Bill No:</strong> {data.billno}</span>
          <span><strong>Date:</strong> {data.date ? new Date(data.date).toLocaleDateString("en-GB").replaceAll("/", "-") : ""}</span>
        </div>
        {data.remarks && (
          <p style={{ marginTop: 4, textAlign: "left" }}><strong>Remarks:</strong> {data.remarks}</p>
        )}
      </div>

      {/* Table */}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
        <thead>
          <tr>
            {["#", "Doc Type", "Packet", "Item", "Purity", "Pcs", "CT", "GW", "Loss"].map(h => (
              <th key={h} style={thStyle}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#fafafa" }}>
              <td style={{ ...tdStyle, textAlign: "center" }}>{i + 1}</td>
              <td style={{ ...tdStyle, textAlign: "center" }}>{r.doc_type}</td>
              <td style={{ ...tdStyle, textAlign: "center" }}>{r.packet || "—"}</td>
              <td style={{ ...tdStyle, textAlign: "center" }}>{r.item || "—"}</td>
              <td style={{ ...tdStyle, textAlign: "center" }}>{r.metal_purity || "—"}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{r.pcs ?? "—"}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{r.ct  != null ? parseFloat(r.ct).toFixed(3) : "—"}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{r.gw  != null ? parseFloat(r.gw).toFixed(3) : "—"}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>{r.loss != null ? parseFloat(r.loss).toFixed(3) : 0}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          {totals.map(t => (
            <tr key={t.type}>
              <td colSpan={5} style={{ ...totStyle, textAlign: "right" }}>{t.type} Total:</td>
              <td style={{ ...totStyle, textAlign: "right" }}>{t.pcs}</td>
              <td style={{ ...totStyle, textAlign: "right" }}>{t.ct.toFixed(3)}</td>
              <td style={{ ...totStyle, textAlign: "right" }}>{t.gw.toFixed(3)}</td>
              <td style={{ ...totStyle, textAlign: "right" }}>{t.loss.toFixed(3)}</td>
            </tr>
          ))}
        </tfoot>
      </table>

      <p style={{ marginTop: 24, fontSize: 10, textAlign: "right", color: "#555" }}>
        Printed on {new Date().toLocaleString("en-IN")}
      </p>
    </div>
  );
}

// ── List Component ───────────────────────────────────────────────────────────
const StockJournalList = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const search = params.get("search") || "";
  const sortby = params.get("sortby") || "";

  useEffect(() => {
    const fetchLedgers = async () => {
      if (ledgers.length === 0) setLoading(true);
      else setTransitioning(true);
      const result = await fetchStockJournal({ search, page, ordering: sortby });
      if (result.success) {
        setLedgers(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
      setTransitioning(false);
    };
    fetchLedgers();
  }, [search, page, sortby]);

  const handlePrint = async (id) => {
    const res = await fetchStockJournalForEdit(id);
    if (!res.success) {
      toast({ title: "Could not load journal for printing", variant: "destructive" });
      return;
    }
    openAndPrint(<StockJournalPrintView data={res.data} />);
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center space-x-3">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => deleteStockJournal(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="size-4" />
          </button>
          <button
            onClick={() => handlePrint(row.original.id)}
            className="text-blue-500 hover:text-blue-700"
            title="Print"
          >
            <Printer className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) =>
        new Date(getValue()).toLocaleDateString("en-GB").replaceAll("/", "-"),
    },
    {
      header: "Bill No",
      accessorKey: "billno",
    },
  ];

  return (
    <div className="p-4">
      <div className="flex justify-between mb-4">
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({ search: e.target.value, sortby })}
          placeholder="Search..."
          className="max-w-sm"
        />
        <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
          <SelectTrigger className="max-w-sm">
            <span>Sort By</span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date1">(Old) Date</SelectItem>
            <SelectItem value="-date1">(New) Date</SelectItem>
            <SelectItem value="billno">(Asc) Bill No</SelectItem>
            <SelectItem value="-billno">(Desc) Bill No</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div>
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="w-full h-8 mb-2" />
          ))}
        </div>
      ) : error ? (
        <div>Error: {error}</div>
      ) : (
        <>
          <div className={transitioning ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
          <DataTable columns={columns} data={ledgers} />
          </div>

          <div className="flex justify-between items-center mt-4">
            <Button
              variant="outline"
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1 || transitioning}
            >
              Previous
            </Button>
            <span>Page {page} of {totalPages}</span>
            <Button
              variant="outline"
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page === totalPages || transitioning}
            >
              Next
            </Button>
          </div>

          <div className="flex justify-end mt-4">
            <Link to="add/">
              <Button>Add New</Button>
            </Link>
          </div>
        </>
      )}
    </div>
  );
};

export default StockJournalList;

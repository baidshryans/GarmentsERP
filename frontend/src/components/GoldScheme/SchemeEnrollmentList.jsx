import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Plus, Eye, CreditCard, Gift } from "lucide-react";
import { fetchSchemeEnrollments } from "@/services/apiService";

const STATUS_COLORS = {
  ACTIVE: "bg-green-100 text-green-800",
  MATURED: "bg-blue-100 text-blue-800",
  REDEEMED: "bg-purple-100 text-purple-800",
  FORFEITED: "bg-red-100 text-red-800",
  CANCELLED: "bg-gray-100 text-gray-800",
};

export default function SchemeEnrollmentList() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("__all__");

  const load = async () => {
    setLoading(true);
    const params = {};
    if (statusFilter && statusFilter !== "__all__") params.status = statusFilter;
    const res = await fetchSchemeEnrollments(params);
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [statusFilter]);

  const columns = [
    { accessorKey: "enrollment_no", header: "Enrollment #" },
    { accessorKey: "customer_name", header: "Customer" },
    { accessorKey: "scheme_name", header: "Scheme" },
    { accessorKey: "scheme_type", header: "Type",
      cell: ({ row }) => {
        const t = row.original.scheme_type;
        return t === "INSTALLMENT" ? "Monthly" : t === "ACCUMULATION" ? "Gold Accum." : "Lump Sum";
      }
    },
    { accessorKey: "installment_amount", header: "Installment",
      cell: ({ row }) => `₹${Number(row.original.installment_amount).toLocaleString("en-IN")}`
    },
    { accessorKey: "total_paid", header: "Total Paid",
      cell: ({ row }) => `₹${Number(row.original.total_paid).toLocaleString("en-IN")}`
    },
    { accessorKey: "payments_made", header: "Payments" },
    { accessorKey: "gold_accumulated_wt", header: "Gold (g)",
      cell: ({ row }) => {
        const wt = Number(row.original.gold_accumulated_wt);
        return wt > 0 ? `${wt.toFixed(3)}g` : "-";
      }
    },
    { accessorKey: "maturity_date", header: "Maturity" },
    { accessorKey: "status", header: "Status",
      cell: ({ row }) => (
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[row.original.status] || ""}`}>{row.original.status}</span>
      )
    },
    { accessorKey: "applicable_benefit", header: "Benefit",
      cell: ({ row }) => {
        const b = row.original.applicable_benefit;
        return b ? `${b.lc_discount_pct}% off LC` : "-";
      }
    },
    {
      id: "actions", header: "",
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" title="View Statement"
            onClick={() => navigate(`/scheme/enrollments/${row.original.id}/statement`)}
          ><Eye className="h-4 w-4" /></Button>
          {row.original.status === "ACTIVE" && (
            <Button variant="ghost" size="icon" title="Record Payment"
              onClick={() => navigate(`/scheme/enrollments/${row.original.id}/pay`)}
            ><CreditCard className="h-4 w-4 text-green-600" /></Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Scheme Enrollments</h2>
        <div className="flex gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40"><SelectValue placeholder="All statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All</SelectItem>
              <SelectItem value="ACTIVE">Active</SelectItem>
              <SelectItem value="MATURED">Matured</SelectItem>
              <SelectItem value="REDEEMED">Redeemed</SelectItem>
              <SelectItem value="CANCELLED">Cancelled</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => navigate("/scheme/enrollments/add")}><Plus className="h-4 w-4 mr-1" /> New Enrollment</Button>
        </div>
      </div>

      {loading ? <Skeleton className="h-64" /> : <DataTable columns={columns} data={rows} />}
    </div>
  );
}

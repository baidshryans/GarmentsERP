import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Users, IndianRupee, Clock, AlertTriangle } from "lucide-react";
import { fetchSchemeSummary, fetchOverduePayments, fetchMaturityCalendar } from "@/services/apiService";

export default function SchemeDashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [overdue, setOverdue] = useState([]);
  const [maturing, setMaturing] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const today = new Date();
      const thirtyDays = new Date(today);
      thirtyDays.setDate(thirtyDays.getDate() + 30);

      const [sRes, oRes, mRes] = await Promise.all([
        fetchSchemeSummary(),
        fetchOverduePayments(),
        fetchMaturityCalendar({
          from_date: today.toISOString().split("T")[0],
          to_date: thirtyDays.toISOString().split("T")[0],
        }),
      ]);
      if (sRes.success) setSummary(sRes.data);
      if (oRes.success) setOverdue(Array.isArray(oRes.data) ? oRes.data : []);
      if (mRes.success) setMaturing(Array.isArray(mRes.data) ? mRes.data : []);
      setLoading(false);
    };
    load();
  }, []);

  const inr = (v) => `₹${Number(v || 0).toLocaleString("en-IN")}`;

  if (loading) return <Skeleton className="h-96" />;

  const kpis = [
    { label: "Active Enrollments", value: summary?.active_enrollments || 0, icon: Users, color: "text-green-600" },
    { label: "Total Collection", value: inr(summary?.total_collection), icon: IndianRupee, color: "text-blue-600" },
    { label: "Maturing in 30 Days", value: summary?.maturing_in_30_days || 0, icon: Clock, color: "text-orange-600" },
    { label: "Matured (Pending Redeem)", value: summary?.matured_enrollments || 0, icon: AlertTriangle, color: "text-purple-600" },
  ];

  const overdueColumns = [
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "scheme", header: "Scheme" },
    { accessorKey: "missed_payments", header: "Missed" },
    { accessorKey: "total_overdue", header: "Overdue Amount", cell: ({ row }) => inr(row.original.total_overdue) },
  ];

  const maturityColumns = [
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "scheme", header: "Scheme" },
    { accessorKey: "maturity_date", header: "Maturity Date" },
    { accessorKey: "total_paid", header: "Total Paid", cell: ({ row }) => inr(row.original.total_paid) },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Gold Scheme Dashboard</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="pt-4">
              <div className="flex items-center gap-3">
                <kpi.icon className={`h-8 w-8 ${kpi.color}`} />
                <div>
                  <p className="text-2xl font-bold">{kpi.value}</p>
                  <p className="text-sm text-muted-foreground">{kpi.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Overdue Payments */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Overdue Payments</CardTitle>
          </CardHeader>
          <CardContent>
            {overdue.length > 0 ? (
              <DataTable columns={overdueColumns} data={overdue.slice(0, 10)} />
            ) : (
              <p className="text-sm text-muted-foreground">No overdue payments</p>
            )}
          </CardContent>
        </Card>

        {/* Upcoming Maturities */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Upcoming Maturities (30 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            {maturing.length > 0 ? (
              <DataTable columns={maturityColumns} data={maturing.slice(0, 10)} />
            ) : (
              <p className="text-sm text-muted-foreground">No upcoming maturities</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Navigation */}
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => navigate("/scheme/master")}>Manage Schemes</Button>
        <Button variant="outline" onClick={() => navigate("/scheme/enrollments")}>All Enrollments</Button>
      </div>
    </div>
  );
}

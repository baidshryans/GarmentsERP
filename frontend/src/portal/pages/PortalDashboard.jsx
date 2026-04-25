import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Gem, IndianRupee, Clock } from "lucide-react";
import { portalFetchDashboard } from "../api/portalApiService";
import EnrollmentCard from "../components/EnrollmentCard";
import OrderTracker from "../components/OrderTracker";

const inr = (v) => `₹${Number(v || 0).toLocaleString("en-IN")}`;

export default function PortalDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const customerName = sessionStorage.getItem("portalCustomerName") || "Customer";

  useEffect(() => {
    portalFetchDashboard().then((res) => {
      if (res.success) setData(res.data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-3 gap-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (!data) {
    return <p className="text-center text-muted-foreground py-8">Unable to load data. Please try again.</p>;
  }

  const { summary, enrollments } = data;

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-semibold">Hello, {customerName}</h1>

      {/* Order Tracking */}
      <div>
        <h2 className="text-sm font-semibold text-foreground mb-3">Order Status</h2>
        <OrderTracker />
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="pt-3 pb-3 text-center">
            <Gem className="size-5 mx-auto text-primary mb-1" />
            <p className="text-xl font-bold">{summary.total_schemes}</p>
            <p className="text-[11px] text-muted-foreground">Schemes</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-3 text-center">
            <IndianRupee className="size-5 mx-auto text-green-600 mb-1" />
            <p className="text-xl font-bold">{inr(summary.total_invested)}</p>
            <p className="text-[11px] text-muted-foreground">Invested</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-3 text-center">
            <Clock className="size-5 mx-auto text-orange-600 mb-1" />
            <p className="text-xl font-bold">{summary.active_schemes}</p>
            <p className="text-[11px] text-muted-foreground">Active</p>
          </CardContent>
        </Card>
      </div>

      {/* Enrollment cards */}
      {enrollments.length === 0 ? (
        <div className="text-center py-12">
          <Gem className="size-12 mx-auto text-muted-foreground/30 mb-3" />
          <p className="text-muted-foreground">No scheme enrollments found.</p>
          <p className="text-sm text-muted-foreground mt-1">Contact the shop to enroll in a gold scheme.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Your Schemes</h2>
          {enrollments.map((e) => (
            <EnrollmentCard key={e.enrollment_no} enrollment={e} />
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, CreditCard } from "lucide-react";
import { portalFetchEnrollment } from "../api/portalApiService";
import PaymentTimeline from "../components/PaymentTimeline";

const STATUS_COLORS = {
  ACTIVE: "bg-green-100 text-green-800",
  MATURED: "bg-blue-100 text-blue-800",
  REDEEMED: "bg-purple-100 text-purple-800",
  FORFEITED: "bg-red-100 text-red-800",
  CANCELLED: "bg-gray-100 text-gray-800",
};

const inr = (v) => `₹${Number(v || 0).toLocaleString("en-IN")}`;

export default function PortalEnrollment() {
  const { enrollmentNo } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    portalFetchEnrollment(enrollmentNo).then((res) => {
      if (res.success) setData(res.data);
      setLoading(false);
    });
  }, [enrollmentNo]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!data) {
    return <p className="text-center text-muted-foreground py-8">Enrollment not found.</p>;
  }

  const e = data.enrollment;
  const payments = data.payments || [];
  const benefit = data.benefit;
  const totalInstallments = e.payments_made + e.remaining_installments;

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate("/portal/")}>
        <ArrowLeft className="h-4 w-4 mr-1" /> Back
      </Button>

      {/* Enrollment header */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-base">{e.scheme_name}</CardTitle>
              <p className="text-xs text-muted-foreground">{e.enrollment_no}</p>
            </div>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[e.status] || ""}`}>
              {e.status}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <div>
              <span className="text-muted-foreground text-xs">Scheme Type</span>
              <p className="font-medium">{e.scheme_type}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-xs">Installment</span>
              <p className="font-medium">{inr(e.installment_amount)}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-xs">Total Paid</span>
              <p className="font-medium text-green-700">{inr(e.total_paid)}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-xs">Progress</span>
              <p className="font-medium">{e.payments_made} / {totalInstallments}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-xs">Start Date</span>
              <p className="font-medium">{e.start_date}</p>
            </div>
            <div>
              <span className="text-muted-foreground text-xs">Maturity Date</span>
              <p className="font-medium">{e.maturity_date}</p>
            </div>
            {Number(e.gold_accumulated_wt) > 0 && (
              <div>
                <span className="text-muted-foreground text-xs">Gold Accumulated</span>
                <p className="font-medium text-yellow-700">{Number(e.gold_accumulated_wt).toFixed(3)}g</p>
              </div>
            )}
            {e.locked_gold_rate && (
              <div>
                <span className="text-muted-foreground text-xs">Locked Rate</span>
                <p className="font-medium">{inr(e.locked_gold_rate)}/g</p>
              </div>
            )}
          </div>

          {/* Progress bar */}
          {totalInstallments > 0 && (
            <div className="mt-4">
              <div className="flex justify-between text-xs text-muted-foreground mb-1">
                <span>Payment Progress</span>
                <span>{Math.round((e.payments_made / totalInstallments) * 100)}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${Math.min(100, (e.payments_made / totalInstallments) * 100)}%` }}
                />
              </div>
            </div>
          )}

          {/* Benefit */}
          {benefit?.gold_benefit && (
            <div className="mt-4 p-3 bg-green-50 rounded-lg border border-green-200">
              <p className="text-sm font-medium text-green-800">
                Current Benefit: {benefit.gold_benefit.lc_discount_pct}% off Making Charges
              </p>
              {benefit.diamond_benefit && (
                <p className="text-xs text-green-700 mt-1">
                  Diamond: {benefit.diamond_benefit.lc_discount_pct}% off LC + {benefit.diamond_benefit.value_discount_pct}% off value
                </p>
              )}
            </div>
          )}
          {!benefit?.gold_benefit && e.months_completed < 6 && e.status === "ACTIVE" && (
            <p className="mt-4 text-xs text-muted-foreground">
              Benefits unlock after 6 months of regular payments.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Payment History */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Payment History</CardTitle>
        </CardHeader>
        <CardContent>
          <PaymentTimeline payments={payments} />
        </CardContent>
      </Card>

      {/* Sticky pay button */}
      {e.status === "ACTIVE" && e.remaining_installments > 0 && (
        <div className="sticky bottom-4">
          <Button
            className="w-full shadow-lg"
            onClick={() => navigate(`/portal/pay/${e.enrollment_no}`)}
          >
            <CreditCard className="h-4 w-4 mr-1" />
            Pay Installment #{e.payments_made + 1} — {inr(e.installment_amount)}
          </Button>
        </div>
      )}
    </div>
  );
}

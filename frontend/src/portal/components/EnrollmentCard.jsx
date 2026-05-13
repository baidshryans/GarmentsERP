import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CreditCard, ChevronRight } from "lucide-react";

const STATUS_COLORS = {
  ACTIVE: "bg-green-100 text-green-800",
  MATURED: "bg-blue-100 text-blue-800",
  REDEEMED: "bg-purple-100 text-purple-800",
  FORFEITED: "bg-red-100 text-red-800",
  CANCELLED: "bg-gray-100 text-gray-800",
};

const inr = (v) => `₹${Number(v || 0).toLocaleString("en-IN")}`;

export default function EnrollmentCard({ enrollment }) {
  const navigate = useNavigate();
  const e = enrollment;
  const totalInstallments = e.payments_made + e.remaining_installments;

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => navigate(`/portal/enrollment/${e.enrollment_no}`)}
    >
      <CardContent className="pt-4 pb-3">
        <div className="flex items-start justify-between mb-2">
          <div>
            <p className="font-medium">{e.scheme_name}</p>
            <p className="text-xs text-muted-foreground">{e.enrollment_no}</p>
          </div>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[e.status] || ""}`}>
            {e.status}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mt-3">
          <div>
            <span className="text-muted-foreground text-xs">Total Paid</span>
            <p className="font-medium text-green-700">{inr(e.total_paid)}</p>
          </div>
          <div>
            <span className="text-muted-foreground text-xs">Installment</span>
            <p className="font-medium">{inr(e.installment_amount)}</p>
          </div>
          <div>
            <span className="text-muted-foreground text-xs">Progress</span>
            <p className="font-medium">{e.payments_made} / {totalInstallments}</p>
          </div>
          <div>
            <span className="text-muted-foreground text-xs">Maturity</span>
            <p className="font-medium">{e.maturity_date}</p>
          </div>
        </div>

        {/* Progress bar */}
        {totalInstallments > 0 && (
          <div className="mt-3 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all"
              style={{ width: `${Math.min(100, (e.payments_made / totalInstallments) * 100)}%` }}
            />
          </div>
        )}

        {Number(e.gold_accumulated_wt) > 0 && (
          <p className="text-xs text-yellow-700 mt-2">
            Gold accumulated: {Number(e.gold_accumulated_wt).toFixed(3)}g
          </p>
        )}

        {e.status === "ACTIVE" && e.remaining_installments > 0 && (
          <Button
            size="sm"
            className="w-full mt-3"
            onClick={(ev) => {
              ev.stopPropagation();
              navigate(`/portal/pay/${e.enrollment_no}`);
            }}
          >
            <CreditCard className="h-3.5 w-3.5 mr-1" /> Pay Next Installment
          </Button>
        )}

        {e.status === "MATURED" && (
          <p className="text-xs text-blue-700 font-medium mt-2 text-center">
            Ready for Redemption � Visit the shop
          </p>
        )}
      </CardContent>
    </Card>
  );
}

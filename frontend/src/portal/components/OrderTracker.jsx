import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ShoppingCart, Clock, CheckCircle2, AlertTriangle, Hammer, XCircle } from "lucide-react";
import { portalFetchOrders } from "../api/portalApiService";

const STATUS_CONFIG = {
  pending: { icon: Clock, color: "text-amber-600", bg: "bg-amber-50", label: "Pending" },
  ready: { icon: ShoppingCart, color: "text-blue-600", bg: "bg-blue-50", label: "Ready for Delivery" },
  delivered: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50", label: "Delivered" },
  cancelled: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", label: "Cancelled" },
};

const PIPELINE_STEPS = [
  { key: "pending",   label: "Order Placed",       icon: Clock,         activeColor: "text-amber-600",   bg: "bg-amber-50",   ring: "ring-amber-200" },
  { key: "ready",     label: "Ready for Delivery", icon: Hammer,        activeColor: "text-blue-600",    bg: "bg-blue-50",    ring: "ring-blue-200" },
  { key: "delivered", label: "Delivered",          icon: CheckCircle2,  activeColor: "text-emerald-600", bg: "bg-emerald-50", ring: "ring-emerald-200" },
];

const STAGE_INDEX = { pending: 0, ready: 1, delivered: 2 };

function OrderPipeline({ status }) {
  if (status === "cancelled") {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-red-50 border border-red-200 text-xs text-red-700">
        <XCircle size={14} />
        <span className="font-medium">Order cancelled</span>
      </div>
    );
  }

  const currentIdx = STAGE_INDEX[status] ?? 0;

  return (
    <div className="flex items-start justify-between gap-1 mt-2">
      {PIPELINE_STEPS.map((step, idx) => {
        const isCompleted = idx < currentIdx;
        const isCurrent = idx === currentIdx;
        const isFuture = idx > currentIdx;
        const Icon = step.icon;

        const circleClasses = isFuture
          ? "bg-gray-100 text-gray-300"
          : isCurrent
          ? `${step.bg} ${step.activeColor} ring-2 ${step.ring}`
          : "bg-emerald-50 text-emerald-600";

        const labelClasses = isFuture
          ? "text-gray-400"
          : isCurrent
          ? `${step.activeColor} font-semibold`
          : "text-gray-600";

        const connectorClasses = idx < currentIdx
          ? "bg-emerald-300"
          : "bg-gray-200";

        return (
          <div key={step.key} className="flex-1 flex flex-col items-center min-w-0">
            <div className="flex items-center w-full">
              <div className={`flex-1 h-0.5 ${idx === 0 ? "bg-transparent" : connectorClasses}`} />
              <div className={`flex items-center justify-center w-8 h-8 rounded-full shrink-0 ${circleClasses}`}>
                {isCompleted ? <CheckCircle2 size={16} /> : <Icon size={15} />}
              </div>
              <div className={`flex-1 h-0.5 ${idx === PIPELINE_STEPS.length - 1 ? "bg-transparent" : (idx < currentIdx ? "bg-emerald-300" : "bg-gray-200")}`} />
            </div>
            <p className={`text-[10px] mt-1 text-center leading-tight ${labelClasses}`}>
              {step.label}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function OrderCard({ order }) {
  const statusConfig = STATUS_CONFIG[order.delivery_status] || STATUS_CONFIG.pending;
  const Icon = statusConfig.icon;

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <p className="font-semibold text-sm">{order.order_no}</p>
          <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${statusConfig.bg} ${statusConfig.color}`}>
            <Icon size={14} />
            {statusConfig.label}
          </span>
        </div>

        <div className="space-y-1 text-xs text-muted-foreground mb-3">
          <p>
            <span className="font-medium">Items:</span> {order.item_count || 0}
          </p>
          {order.delivery_date && (
            <p>
              <span className="font-medium">Due Date:</span>{" "}
              {new Date(order.delivery_date).toLocaleDateString("en-GB")}
            </p>
          )}
          {order.est_amount && (
            <p>
              <span className="font-medium">Amount:</span> ₹
              {Number(order.est_amount).toLocaleString("en-IN")}
            </p>
          )}
        </div>

        <OrderPipeline status={order.delivery_status} />

        {order.is_overdue && (
          <div className="flex items-center gap-1.5 px-2 py-1.5 mt-3 rounded bg-red-50 border border-red-200 text-xs text-red-700">
            <AlertTriangle size={13} />
            {order.days_overdue} days overdue
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function OrderTracker() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    portalFetchOrders().then((res) => {
      if (res.success) setOrders(res.data || []);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="text-center py-8">
        <ShoppingCart className="size-12 mx-auto text-muted-foreground/30 mb-3" />
        <p className="text-muted-foreground">No orders found.</p>
      </div>
    );
  }

  const pendingOrders = orders.filter((o) => o.delivery_status === "pending");
  const readyOrders = orders.filter((o) => o.delivery_status === "ready");
  const deliveredOrders = orders.filter((o) => o.delivery_status === "delivered");

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="pt-3 pb-3 text-center">
            <Clock className="size-5 mx-auto text-amber-600 mb-1" />
            <p className="text-xl font-bold">{pendingOrders.length}</p>
            <p className="text-[11px] text-muted-foreground">Pending</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-3 text-center">
            <ShoppingCart className="size-5 mx-auto text-blue-600 mb-1" />
            <p className="text-xl font-bold">{readyOrders.length}</p>
            <p className="text-[11px] text-muted-foreground">Ready</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-3 pb-3 text-center">
            <CheckCircle2 className="size-5 mx-auto text-emerald-600 mb-1" />
            <p className="text-xl font-bold">{deliveredOrders.length}</p>
            <p className="text-[11px] text-muted-foreground">Delivered</p>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">Your Orders</h3>
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} />
        ))}
      </div>
    </div>
  );
}

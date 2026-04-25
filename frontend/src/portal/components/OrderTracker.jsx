import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ShoppingCart, Clock, Truck, CheckCircle2, AlertTriangle } from "lucide-react";
import { portalFetchOrders } from "../api/portalApiService";

const STATUS_CONFIG = {
  pending: { icon: Clock, color: "text-amber-600", bg: "bg-amber-50", label: "Pending" },
  ready: { icon: ShoppingCart, color: "text-blue-600", bg: "bg-blue-50", label: "Ready for Delivery" },
  delivered: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50", label: "Delivered" },
  cancelled: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", label: "Cancelled" },
};

function OrderCard({ order }) {
  const statusConfig = STATUS_CONFIG[order.delivery_status] || STATUS_CONFIG.pending;
  const Icon = statusConfig.icon;

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
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

            {order.is_overdue && (
              <div className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-red-50 border border-red-200 text-xs text-red-700">
                <AlertTriangle size={13} />
                {order.days_overdue} days overdue
              </div>
            )}
          </div>
        </div>
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

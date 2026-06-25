import React, { useEffect, useState } from "react";
import { formatNumber, formatDate } from "@/lib/format";
import { fetchAllApps } from "@/services/apiService";
import {
  Package, Heart, Hammer, ShoppingCart, ReceiptText, Calculator,
  Sparkles, Settings, Users, DollarSign, ShieldCheck, AppWindow,
} from "lucide-react";

/* Map icon name strings from AppRegistry to Lucide components */
const ICON_MAP = {
  Settings,
  Users,
  Heart,
  DollarSign,
  Hammer,
  ShoppingCart,
  ReceiptText,
  Package,
  Calculator,
  Sparkles,
  ShieldCheck,
};

function getIcon(iconName) {
  return ICON_MAP[iconName] || AppWindow;
}

export default function AppsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAllApps().then((res) => {
      if (res.success) setData(res.data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="p-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-40 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-center text-gray-500">
        Failed to load apps. Please try again later.
      </div>
    );
  }

  const { subscription, apps } = data;
  const installedApps = apps.filter((a) => a.is_licensed);
  const availableApps = apps.filter((a) => !a.is_licensed);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      {/* Subscription banner */}
      {subscription && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 flex items-center justify-between shadow-sm">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Your Subscription</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Status:{" "}
              <span
                className={`font-medium ${
                  subscription.status === "active"
                    ? "text-emerald-600"
                    : subscription.status === "trial"
                    ? "text-amber-600"
                    : "text-red-500"
                }`}
              >
                {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
              </span>
              {" · "}
              Valid until{" "}
              <span className="font-medium text-gray-700">
                {formatDate(subscription.end_date, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-800">{installedApps.length}</p>
            <p className="text-xs text-gray-500">Apps Installed</p>
          </div>
        </div>
      )}

      {/* Installed Apps */}
      <section>
        <h3 className="text-base font-semibold text-gray-700 mb-3">Installed Apps</h3>
        {installedApps.length === 0 ? (
          <p className="text-sm text-gray-400">No apps installed yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {installedApps.map((app) => (
              <AppCard key={app.code} app={app} installed />
            ))}
          </div>
        )}
      </section>

      {/* Available Apps */}
      {availableApps.length > 0 && (
        <section>
          <h3 className="text-base font-semibold text-gray-700 mb-3">Available Apps</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {availableApps.map((app) => (
              <AppCard key={app.code} app={app} installed={false} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function AppCard({ app, installed }) {
  const Icon = getIcon(app.icon);

  return (
    <div
      className={`rounded-xl border p-5 flex flex-col gap-3 transition-shadow ${
        installed
          ? "bg-white border-gray-200 shadow-sm hover:shadow-md"
          : "bg-gray-50 border-dashed border-gray-300 opacity-75"
      }`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
            installed ? "bg-accent-100 text-primary" : "bg-gray-200 text-gray-400"
          }`}
        >
          <Icon className="size-5" />
        </div>
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-gray-800 truncate">{app.name}</h4>
          {app.is_core && (
            <span className="text-[10px] font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded-full">
              Core
            </span>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">
        {app.description || "No description available."}
      </p>

      <div className="mt-auto flex items-center justify-between pt-2 border-t border-gray-100">
        {app.monthly_price > 0 ? (
          <span className="text-xs font-medium text-gray-600">
            ₹{formatNumber(app.monthly_price)}/mo
          </span>
        ) : (
          <span className="text-xs text-gray-400">Free</span>
        )}
        {installed ? (
          <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">
            Installed
          </span>
        ) : (
          <span className="text-[10px] font-medium text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
            Contact Vendor
          </span>
        )}
      </div>
    </div>
  );
}

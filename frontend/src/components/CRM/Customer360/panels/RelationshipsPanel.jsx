// Everything else the customer has open with us: orders, schemes, approvals.
import React from "react";

import { EmptyNote, Money } from "../badges";

function Card({ title, children, count }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="font-medium text-slate-800">
        {title}
        {count > 0 && (
          <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
            {count}
          </span>
        )}
      </h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default function RelationshipsPanel({ profile }) {
  const orders = profile.pending_orders || [];
  const schemes = profile.schemes || [];
  const approvals = profile.approvals || [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Pending orders" count={orders.length}>
        {orders.length ? (
          <ul className="space-y-2 text-sm">
            {orders.map((o) => (
              <li key={o.id} className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-700">{o.order_no}</div>
                  <div className="text-xs text-slate-500">
                    Ordered {o.date}
                    {o.delivery_date ? ` · due ${o.delivery_date}` : ""}
                  </div>
                </div>
                <div className="text-right">
                  <span className="rounded bg-blue-50 px-2 py-0.5 text-xs capitalize text-blue-700">
                    {o.delivery_status}
                  </span>
                  {Number(o.advance_amt) > 0 && (
                    <div className="mt-1 text-xs text-slate-500">
                      Advance <Money value={o.advance_amt} />
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyNote>No open orders.</EmptyNote>
        )}
      </Card>

      <Card title="Savings schemes" count={schemes.length}>
        {schemes.length ? (
          <ul className="space-y-2 text-sm">
            {schemes.map((s) => (
              <li key={s.id} className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-700">{s.scheme || s.enrollment_no}</div>
                  <div className="text-xs text-slate-500">
                    {s.payments_made} paid · matures {s.maturity_date || "—"}
                  </div>
                </div>
                <div className="text-right">
                  <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs capitalize text-emerald-700">
                    {s.status}
                  </span>
                  <div className="mt-1 text-xs text-slate-500">
                    <Money value={s.total_paid} /> paid
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyNote>Not enrolled in any scheme.</EmptyNote>
        )}
      </Card>

      <Card title="Out on approval" count={approvals.length}>
        {approvals.length ? (
          <ul className="space-y-2 text-sm">
            {approvals.map((a) => (
              <li key={a.id} className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-700">{a.item || a.barcode}</div>
                  <div className="text-xs text-slate-500">
                    {a.approval_no} · issued {a.date}
                  </div>
                </div>
                <div className="text-right">
                  {a.days_outstanding != null && (
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        a.days_outstanding > 30
                          ? "bg-red-50 text-red-700"
                          : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {a.days_outstanding} days out
                    </span>
                  )}
                  <div className="mt-1 text-xs text-slate-500">
                    <Money value={a.amount} />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyNote>Nothing out on approval.</EmptyNote>
        )}
      </Card>

      <Card title="Portal account">
        <p className="text-sm text-slate-600">
          {profile.has_portal_account
            ? "This customer can sign in to the customer portal."
            : "No customer portal account linked."}
        </p>
      </Card>
    </div>
  );
}

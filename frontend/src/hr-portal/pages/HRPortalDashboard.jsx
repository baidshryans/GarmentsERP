import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { hrPortalFetchSlips } from "../hrPortalApiService";

const MONTHS = ["", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

const STATUS_COLORS = {
  APPROVED: "bg-blue-100 text-blue-800",
  PAID: "bg-green-100 text-green-800",
};

export default function HRPortalDashboard() {
  const navigate = useNavigate();
  const emp = JSON.parse(localStorage.getItem("hrPortalEmployee") || "{}");
  const [slips, setSlips] = useState([]);

  useEffect(() => {
    hrPortalFetchSlips().then(r => r.success && setSlips(r.data.slice(0, 6)));
  }, []);

  const latest = slips[0];

  return (
    <div className="space-y-6">
      <div className="rounded-lg border bg-card p-5">
        <h2 className="text-lg font-semibold">Welcome, {emp.full_name || "Employee"}</h2>
        <p className="text-sm text-muted-foreground mt-1">{emp.designation} {emp.department ? `· ${emp.department}` : ""}</p>
        <p className="text-xs text-muted-foreground mt-0.5">Employee Code: {emp.employee_code}</p>
      </div>

      {latest && (
        <div className="rounded-lg border bg-card p-5 space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Latest Payslip</h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">{MONTHS[latest.month]} {latest.year}</p>
              <p className="text-sm text-muted-foreground">Net: ₹{Number(latest.net_salary).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[latest.status] || ""}`}>
                {latest.status}
              </span>
              <button
                onClick={() => navigate(`/hr-portal/slip/${latest.month}/${latest.year}`)}
                className="text-xs text-primary underline"
              >
                View
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-lg border bg-card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Recent Payslips</h3>
          <button onClick={() => navigate("/hr-portal/slips")} className="text-xs text-primary underline">View All</button>
        </div>
        {slips.length === 0 && <p className="text-sm text-muted-foreground">No payslips available yet.</p>}
        <div className="space-y-2">
          {slips.map(s => (
            <div key={s.id} className="flex items-center justify-between py-1 border-b last:border-0">
              <span className="text-sm">{MONTHS[s.month]} {s.year}</span>
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">₹{Number(s.net_salary).toLocaleString("en-IN")}</span>
                <button
                  onClick={() => navigate(`/hr-portal/slip/${s.month}/${s.year}`)}
                  className="text-xs text-primary underline"
                >
                  View
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

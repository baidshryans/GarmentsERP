import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/format";
import { useNavigate } from "react-router-dom";
import { hrPortalFetchSlips } from "../hrPortalApiService";

const MONTHS = ["", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

export default function HRPortalSlipList() {
  const navigate = useNavigate();
  const now = new Date();
  const [year, setYear] = useState(String(now.getFullYear()));
  const [slips, setSlips] = useState([]);

  useEffect(() => {
    hrPortalFetchSlips(year).then(r => r.success && setSlips(r.data));
  }, [year]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">My Payslips</h2>
        <input
          type="number"
          className="border rounded px-2 py-1 text-sm bg-background w-24"
          value={year}
          onChange={e => setYear(e.target.value)}
        />
      </div>

      {slips.length === 0 && (
        <p className="text-sm text-muted-foreground">No payslips found for {year}.</p>
      )}

      <div className="space-y-2">
        {slips.map(s => (
          <div key={s.id} className="rounded-lg border bg-card p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">{MONTHS[s.month]} {s.year}</p>
              <p className="text-sm text-muted-foreground">
                Gross: ₹{formatNumber(s.gross_salary)} &nbsp;·&nbsp;
                Net: ₹{formatNumber(s.net_salary)}
              </p>
            </div>
            <button
              onClick={() => navigate(`/hr-portal/slip/${s.month}/${s.year}`)}
              className="text-sm text-primary underline"
            >
              View Slip
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

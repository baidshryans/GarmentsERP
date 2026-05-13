import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { hrPortalFetchSlip } from "../hrPortalApiService";
import SalarySlipView from "../../components/HR/SalarySlipView";

export default function HRPortalSlipDetail() {
  const { month, year } = useParams();
  const [slip, setSlip]     = useState(null);
  const [error, setError]   = useState("");

  useEffect(() => {
    hrPortalFetchSlip(Number(month), Number(year)).then(r => {
      if (r.success) setSlip(r.data);
      else setError(r.error?.detail || "Slip not found.");
    });
  }, [month, year]);

  if (error) return <p className="text-sm text-destructive p-4">{error}</p>;
  if (!slip) return <p className="text-sm text-muted-foreground p-4">Loading�</p>;

  return <SalarySlipView slip={slip} />;
}

/**
 * Pure presentational salary slip � accepts `slip` and `company` props.
 * Shared between the ERP (SalaryProcessingPage) and the HR Employee Portal.
 */
import { Button } from "@/components/ui/button";
import { Printer } from "lucide-react";

const MONTHS = ["", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

function Row({ label, value }) {
  return (
    <tr>
      <td className="py-0.5 pr-4 text-sm text-muted-foreground">{label}</td>
      <td className="py-0.5 text-sm text-right font-medium">₹{Number(value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
    </tr>
  );
}

export default function SalarySlipView({ slip, company }) {
  if (!slip) return null;

  const period = `${MONTHS[slip.month]} ${slip.year}`;

  return (
    <div>
      <div className="flex justify-end mb-3 print:hidden">
        <Button variant="outline" size="sm" onClick={() => window.print()}>
          <Printer className="size-4 mr-1" /> Print
        </Button>
      </div>

      <div id="salary-slip-print" className="bg-white text-black p-6 rounded border max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center border-b pb-3 mb-4">
          <h1 className="text-xl font-bold">{company?.name || "Company"}</h1>
          {company?.address && <p className="text-xs text-gray-500">{company.address}</p>}
          <h2 className="mt-1 text-base font-semibold">Salary Slip � {period}</h2>
        </div>

        {/* Employee Details */}
        <div className="grid grid-cols-2 gap-1 mb-4 text-sm">
          <div><span className="text-gray-500">Employee Code:</span> <span className="font-medium">{slip.employee_code}</span></div>
          <div><span className="text-gray-500">Name:</span> <span className="font-medium">{slip.employee_name}</span></div>
          <div><span className="text-gray-500">Working Days:</span> <span className="font-medium">{slip.working_days}</span></div>
          <div><span className="text-gray-500">Days Worked:</span> <span className="font-medium">{slip.days_worked}</span></div>
        </div>

        {/* Earnings + Deductions table */}
        <div className="grid grid-cols-2 gap-6">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">Earnings</h3>
            <table className="w-full">
              <tbody>
                <Row label="Basic"              value={slip.basic_earned} />
                <Row label="HRA"               value={slip.hra_earned} />
                <Row label="DA"                value={slip.da_earned} />
                <Row label="Conveyance"        value={slip.conveyance_earned} />
                <Row label="Medical Allowance" value={slip.medical_earned} />
                <Row label="Special Allowance" value={slip.special_allowance_earned} />
              </tbody>
              <tfoot>
                <tr className="border-t font-bold">
                  <td className="pt-1 pr-4 text-sm">Gross Salary</td>
                  <td className="pt-1 text-sm text-right">₹{Number(slip.gross_salary || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">Deductions</h3>
            <table className="w-full">
              <tbody>
                {Number(slip.pf_employee) > 0 && <Row label="PF (Employee)"    value={slip.pf_employee} />}
                {Number(slip.pf_employer) > 0 && <Row label="PF (Employer)"    value={slip.pf_employer} />}
                {Number(slip.esi_employee) > 0 && <Row label="ESI (Employee)"  value={slip.esi_employee} />}
                {Number(slip.esi_employer) > 0 && <Row label="ESI (Employer)"  value={slip.esi_employer} />}
                {Number(slip.professional_tax) > 0 && <Row label="Prof. Tax"   value={slip.professional_tax} />}
                {Number(slip.tds_deducted) > 0 && <Row label="TDS"             value={slip.tds_deducted} />}
                {Number(slip.advance_recovery) > 0 && <Row label="Advance Recovery" value={slip.advance_recovery} />}
              </tbody>
              <tfoot>
                <tr className="border-t font-bold">
                  <td className="pt-1 pr-4 text-sm">Total Deductions</td>
                  <td className="pt-1 text-sm text-right">₹{Number(slip.total_deductions || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Net Salary */}
        <div className="mt-4 border-t pt-3 flex justify-between items-center">
          <span className="font-bold text-base">Net Salary</span>
          <span className="font-bold text-lg">₹{Number(slip.net_salary || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
        </div>

        <p className="mt-4 text-xs text-gray-400 text-center">This is a computer-generated salary slip and does not require a signature.</p>
      </div>
    </div>
  );
}

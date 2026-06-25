import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/format";
import { useParams } from "react-router-dom";
import { useF4Submit } from "@/hooks/useF4Submit";
import { fetchDuePayments, fetchDuePaymentsSale } from "@/services/apiService";

const fmtDate = (d) => {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-GB").replaceAll("/", "-");
};

const fmtAmt = (n) => {
  const v = parseFloat(n) || 0;
  return formatNumber(v, { decimals: 2 });
};

const Account = () => {
  const { type, id } = useParams();
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);

  const isReceipt = type === "RECEIPT" || type === "RCPT";

  useEffect(() => {
    setLoading(true);
    const fetcher = isReceipt ? fetchDuePaymentsSale(id) : fetchDuePayments(id);
    fetcher
      .then((res) => {
        if (res.success) {
          const data = Array.isArray(res.data)
            ? res.data
            : res.data?.results ?? [];
          setBills(
            data.map((b) => ({
              ...b,
              bill_no: b.bill_no || b.billno || "",
              date: b.date1 || b.date || "",
              total: parseFloat(b.total_incl_gst || b.total_bill_value || 0),
              due: parseFloat(b.due_amt || 0),
              payment: "",
            }))
          );
        }
      })
      .finally(() => setLoading(false));
  }, [id, type]);

  const setPayment = (idx, value) => {
    setBills((prev) =>
      prev.map((b, i) => (i === idx ? { ...b, payment: value } : b))
    );
  };

  const handlePayAll = () => {
    setBills((prev) => prev.map((b) => ({ ...b, payment: String(b.due) })));
  };

  const handleSubmit = () => {
    const selected = bills
      .filter((b) => parseFloat(b.payment) > 0)
      .map((b) => {
        const amt = parseFloat(b.payment) || 0;
        return {
          bill_no: b.bill_no,
          // For receipts: customer account is debited in the entry, amount goes to credit
          // For payments: vendor account is credited, amount goes to debit
          debit: isReceipt ? amt : amt,
          credit: isReceipt ? 0 : 0,
        };
      });

    if (selected.length === 0) {
      alert("Enter payment amount for at least one bill.");
      return;
    }

    if (window.opener && window.opener.loadInvoices) {
      window.opener.loadInvoices(selected);
    }
    window.close();
  };

  useF4Submit(handleSubmit);

  const totalDue = bills.reduce((s, b) => s + b.due, 0);
  const totalPayment = bills.reduce(
    (s, b) => s + (parseFloat(b.payment) || 0),
    0
  );

  return (
    <div
      style={{
        fontFamily: "Inter, system-ui, sans-serif",
        padding: "24px",
        maxWidth: "800px",
        margin: "0 auto",
      }}
    >
      <h2
        style={{
          fontSize: "16px",
          fontWeight: 600,
          marginBottom: "16px",
          borderBottom: "2px solid hsl(var(--primary))",
          paddingBottom: "8px",
        }}
      >
        {isReceipt
          ? "Select Sale Bills to Receive Against"
          : "Select Purchase Bills to Pay Against"}
      </h2>

      {loading ? (
        <p style={{ color: "#888", fontSize: "14px" }}>Loading outstanding bills…</p>
      ) : bills.length === 0 ? (
        <p style={{ color: "#888", fontSize: "14px" }}>
          No outstanding bills found for this party.
        </p>
      ) : (
        <>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13px",
            }}
          >
            <thead>
              <tr style={{ background: "#f4f4f5", borderBottom: "2px solid #e4e4e7" }}>
                <Th>#</Th>
                <Th align="left">Bill No</Th>
                <Th align="left">Date</Th>
                <Th align="right">Bill Amount</Th>
                <Th align="right">Due Amount</Th>
                <Th align="right">
                  {isReceipt ? "Receipt Amt" : "Payment Amt"}
                </Th>
              </tr>
            </thead>
            <tbody>
              {bills.map((b, i) => (
                <tr
                  key={b.bill_no || i}
                  style={{ borderBottom: "1px solid #e4e4e7" }}
                >
                  <Td>{i + 1}</Td>
                  <Td align="left" bold>
                    {b.bill_no}
                  </Td>
                  <Td align="left">{fmtDate(b.date)}</Td>
                  <Td align="right">{fmtAmt(b.total)}</Td>
                  <Td align="right" bold color="#dc2626">
                    {fmtAmt(b.due)}
                  </Td>
                  <Td align="right">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max={b.due}
                      value={b.payment}
                      onChange={(e) => setPayment(i, e.target.value)}
                      style={{
                        width: "110px",
                        padding: "4px 8px",
                        border: "1px solid #d4d4d8",
                        borderRadius: "4px",
                        textAlign: "right",
                        fontSize: "13px",
                        outline: "none",
                      }}
                      onFocus={(e) => (e.target.style.borderColor = "hsl(var(--primary))")}
                      onBlur={(e) => (e.target.style.borderColor = "#d4d4d8")}
                    />
                  </Td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr
                style={{
                  borderTop: "2px solid #e4e4e7",
                  background: "#fafafa",
                  fontWeight: 600,
                }}
              >
                <td colSpan={4} style={{ padding: "8px", textAlign: "right" }}>
                  Total
                </td>
                <td style={{ padding: "8px", textAlign: "right", color: "#dc2626" }}>
                  {fmtAmt(totalDue)}
                </td>
                <td style={{ padding: "8px", textAlign: "right", color: "#16a34a" }}>
                  {fmtAmt(totalPayment)}
                </td>
              </tr>
            </tfoot>
          </table>

          <div
            style={{
              display: "flex",
              gap: "8px",
              marginTop: "16px",
              justifyContent: "flex-end",
            }}
          >
            <button
              onClick={handlePayAll}
              style={{
                padding: "6px 16px",
                fontSize: "13px",
                border: "1px solid #d4d4d8",
                borderRadius: "6px",
                background: "#fff",
                cursor: "pointer",
              }}
            >
              Pay All Dues
            </button>
            <button
              onClick={handleSubmit}
              style={{
                padding: "6px 20px",
                fontSize: "13px",
                border: "none",
                borderRadius: "6px",
                background: "hsl(var(--primary))",
                color: "#fff",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {isReceipt ? "Apply Receipts" : "Apply Payments"}
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default Account;

// ── tiny helpers for inline styles ──

function Th({ children, align = "center" }) {
  return (
    <th
      style={{
        padding: "8px",
        textAlign: align,
        fontWeight: 600,
        fontSize: "12px",
        color: "#71717a",
        textTransform: "uppercase",
        letterSpacing: "0.5px",
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, align = "center", bold, color }) {
  return (
    <td
      style={{
        padding: "8px",
        textAlign: align,
        fontWeight: bold ? 600 : 400,
        color: color || "inherit",
      }}
    >
      {children}
    </td>
  );
}

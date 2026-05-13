import { useNavigate } from "react-router-dom";
import { ArrowDownLeft, ArrowUpRight, ArrowLeftRight, BookOpen } from "lucide-react";

const VOUCHER_TYPES = [
  {
    type: "RCPT",
    label: "Receipt",
    shortcut: "R",
    icon: ArrowDownLeft,
    description: "Record money received from customers. Link against outstanding sale invoices.",
    color: "text-emerald-600",
    bg: "bg-emerald-50 hover:bg-emerald-100 border-emerald-200",
    iconBg: "bg-emerald-100",
  },
  {
    type: "PMNT",
    label: "Payment",
    shortcut: "P",
    icon: ArrowUpRight,
    description: "Record payments made to suppliers. Link against outstanding purchase bills.",
    color: "text-rose-600",
    bg: "bg-rose-50 hover:bg-rose-100 border-rose-200",
    iconBg: "bg-rose-100",
  },
  {
    type: "CONTRA",
    label: "Contra",
    shortcut: "C",
    icon: ArrowLeftRight,
    description: "Transfer funds between cash and bank accounts, or between two bank accounts.",
    color: "text-primary",
    bg: "bg-violet-50 hover:bg-violet-100 border-violet-200",
    iconBg: "bg-violet-100",
  },
  {
    type: "JRNL",
    label: "Journal",
    shortcut: "J",
    icon: BookOpen,
    description: "General accounting entries — adjustments, provisions, depreciation, and corrections.",
    color: "text-primary",
    bg: "bg-violet-50 hover:bg-violet-100 border-violet-200",
    iconBg: "bg-violet-100",
  },
];

export default function VoucherTypeSelector() {
  const navigate = useNavigate();

  const handleSelect = (type) => {
    navigate(`/accounting/${type}/add`);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground">New Accounting Voucher</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Select the type of transaction you want to record.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {VOUCHER_TYPES.map(({ type, label, shortcut, icon: Icon, description, color, bg, iconBg }) => (
          <button
            key={type}
            onClick={() => handleSelect(type)}
            className={`flex items-start gap-4 p-5 rounded-xl border text-left transition-colors cursor-pointer ${bg}`}
          >
            <div className={`flex items-center justify-center w-11 h-11 rounded-lg shrink-0 ${iconBg}`}>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className={`font-semibold text-base ${color}`}>{label}</span>
                <kbd className="text-xs font-mono bg-white/70 border border-current/20 rounded px-1.5 py-0.5 text-muted-foreground">
                  Alt+{shortcut}
                </kbd>
              </div>
              <p className="text-sm text-muted-foreground mt-1 leading-snug">{description}</p>
            </div>
          </button>
        ))}
      </div>

      <p className="text-xs text-muted-foreground text-center mt-6">
        To view existing vouchers, use the Financial Accounting menu in the sidebar.
      </p>
    </div>
  );
}

import React from "react";
import { useLocation, Link } from "react-router-dom";
import { Home } from "lucide-react";
import {
  SidebarTrigger,
} from "@/components/ui/sidebar";
import RetailSelection from "./loginpage";
import { navData } from "@/config/navData";

// ── Build URL → label map from navData (walks nested items) ──────────────
const URL_LABEL_MAP = (() => {
  const map = {};
  const walk = (items) => {
    if (!Array.isArray(items)) return;
    items.forEach((it) => {
      if (it.url && it.url !== "#") map[it.url.replace(/\/$/, "")] = it.title;
      if (it.items) walk(it.items);
    });
  };
  Object.values(navData || {}).forEach(walk);
  return map;
})();

// ── Known segment labels (covers common URL fragments) ───────────────────
const SEGMENT_LABEL_OVERRIDES = {
  gstinputregister: "GST Input Register",
  gstoutputregister: "GST Output Register",
  gstr1: "GSTR-1",
  gstr3b: "GSTR-3B",
  gstin: "GSTIN",
  tds: "TDS",
  tcs: "TCS",
  pnl: "P&L",
  hsn: "HSN",
  rcm: "RCM",
  kyc: "KYC",
  erp: "ERP",
  ai: "AI",
  crm: "CRM",
  pos: "POS",
  api: "API",
  id: "ID",
  ui: "UI",
  sku: "SKU",
  po: "PO",
  pv: "PV",
  sv: "SV",
  // Compound slugs that don't split cleanly from the dictionary
  goldrate: "Gold Rate",
  hmissue: "Hallmark Issue",
  karigarstonetxns: "Karigar Stone Transactions",
  finisheditemrec: "Finished Item Receive",
  profitlosscal: "Profit Loss Calculation",
  idgen: "ID Generation",
  joborder: "Job Order",
  rawsalesvoucher: "Raw Sales Voucher",
  stockvalue: "Stock Value",
  rfid: "RFID",
  tagassign: "Tag Assignment",
  "tag-assign": "Tag Assignment",
};

// Dictionary used to split glued lowercase slugs like "customerpurchase"
const DICT = [
  "accounting", "accounts", "advanced", "advance", "approval", "attachment", "audit", "balance", "bank",
  "barcode", "book", "branch", "bulk", "card", "carriage", "cash", "category",
  "chart", "closing", "color", "commission", "company", "contacts", "conversion", "customer",
  "dashboard", "data", "debit", "details", "discount", "enrollment", "enrollments", "estimate", "exhibition",
  "expenses", "fiscal", "generation", "gold", "group", "hallmark", "history",
  "import", "input", "inventory", "invoice", "issue", "item", "items", "job",
  "journal", "karigar", "ledger", "licensing", "loss", "list", "log", "machine", "main",
  "making", "manage", "management", "manufacturing", "market", "master",
  "masters", "material", "memo", "menu", "merge", "metal", "mobile", "module",
  "new", "note", "number", "occasion", "office", "old", "opening", "order",
  "other", "output", "pack", "packet", "page", "payment", "people", "person",
  "point", "preview", "price", "print", "process", "profit", "purchase",
  "purity", "quotation", "quotations", "rate", "rates", "raw", "receive", "refinery", "refinary", "register", "repair",
  "report", "reports", "retail", "return", "returns", "role", "roles", "salary", "sale", "sales",
  "scheme", "schemes", "section", "sections",
  "semi", "setup", "sheet", "shape", "stage", "standard", "statement", "stock",
  "stone", "store", "summary", "tax", "test", "tracking", "transfer", "trial",
  "type", "unit", "update", "upload", "user", "value", "vendor", "voucher",
  "vouchers", "wise", "work", "year", "years", "zone",
  "cal", "demo", "finished", "gen", "split", "rec",
  "rfid", "count", "assign", "tag",
];
const DICT_SET = new Set(DICT.sort((a, b) => b.length - a.length));

// Greedy longest-match word splitter for lowercase glued strings
function splitGlued(s) {
  const lower = s.toLowerCase();
  const out = [];
  let i = 0;
  let anyDictMatch = false;
  while (i < lower.length) {
    let matched = null;
    for (const w of DICT_SET) {
      if (lower.startsWith(w, i)) {
        matched = w;
        break;
      }
    }
    if (matched) {
      out.push(matched);
      anyDictMatch = true;
      i += matched.length;
    } else {
      // fallback: take one char
      out.push(lower[i]);
      i += 1;
    }
  }
  // If no dictionary word was matched at all, the word is unknown � return as-is
  // so it title-cases cleanly instead of producing garbled pairs like "Qu Ot At Io N"
  if (!anyDictMatch) return [lower];
  // merge lone chars
  const merged = [];
  out.forEach((w) => {
    if (w.length === 1 && merged.length && merged[merged.length - 1].length === 1) {
      merged[merged.length - 1] += w;
    } else {
      merged.push(w);
    }
  });
  return merged;
}

const titleCase = (w) => {
  const key = w.toLowerCase();
  if (SEGMENT_LABEL_OVERRIDES[key]) return SEGMENT_LABEL_OVERRIDES[key];
  return w.charAt(0).toUpperCase() + w.slice(1);
};

// Humanise a single URL segment
const humanise = (seg) => {
  let s = decodeURIComponent(seg);
  const key = s.toLowerCase();
  if (SEGMENT_LABEL_OVERRIDES[key]) return SEGMENT_LABEL_OVERRIDES[key];
  // camelCase / kebab / snake → already word-separated
  if (/[A-Z]/.test(s) || /[-_]/.test(s)) {
    return s
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/[-_]/g, " ")
      .split(/\s+/)
      .map(titleCase)
      .join(" ");
  }
  // pure lowercase glued word → dictionary split
  if (/^[a-z]+$/.test(s) && s.length > 4) {
    return splitGlued(s).map(titleCase).join(" ");
  }
  return titleCase(s);
};

const Header = ({ heading, children }) => {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  return (
    <>
      {/* ── Main header bar ──────────────────────────────────── */}
      <header className="relative flex items-center justify-between w-full px-4 h-14 bg-white border-b border-gray-100 shadow-[0_1px_8px_0_rgba(0,0,0,0.06)]">

        {/* Left cluster */}
        <div className="flex items-center gap-3 min-w-0">

          {/* Sidebar toggle */}
          <SidebarTrigger className="text-gray-500 hover:text-primary transition-colors" />

          {/* Slim divider */}
          <div className="h-5 w-px bg-gray-200" />

          {/* Page title */}
          {heading && (
            <div className="flex items-center gap-2">
              <span className="block w-[3px] h-4 rounded-full bg-primary" />
              <h1 className="text-sm font-bold text-gray-800 tracking-tight whitespace-nowrap">
                {heading}
              </h1>
            </div>
          )}

          {/* Breadcrumb path */}
          {segments.length > 0 && (
            <nav
              aria-label="breadcrumb"
              className="flex items-center gap-1 bg-gray-100/70 rounded-full px-3 py-1 ml-1 border border-gray-200/60"
            >
              {/* Home icon */}
              <Link
                to="/"
                className="text-gray-400 hover:text-primary transition-colors flex items-center"
              >
                <Home className="size-3" />
              </Link>

              {segments.map((seg, idx) => {
                const url  = `/${segments.slice(0, idx + 1).join("/")}`;
                const last = idx === segments.length - 1;
                const label = URL_LABEL_MAP[url] || humanise(seg);

                // Skip this segment if the next segment's label already starts with
                // this label (e.g. "Sales Approval" before "Sales Approval List")
                if (!last) {
                  const nextUrl = `/${segments.slice(0, idx + 2).join("/")}`;
                  const nextLabel = URL_LABEL_MAP[nextUrl] || humanise(segments[idx + 1]);
                  if (nextLabel.toLowerCase().startsWith(label.toLowerCase())) return null;
                }

                return (
                  <React.Fragment key={url}>
                    {/* Separator */}
                    <span className="text-gray-300 text-xs select-none font-light">/</span>

                    {/* Segment */}
                    {last ? (
                      <span className="text-xs font-semibold text-primary tracking-wide">
                        {label}
                      </span>
                    ) : (
                      <Link
                        to={url}
                        className="text-xs text-gray-500 hover:text-primary transition-colors font-medium"
                      >
                        {label}
                      </Link>
                    )}
                  </React.Fragment>
                );
              })}
            </nav>
          )}
        </div>

        {/* Right: retail selector */}
        <RetailSelection />

        {/* Violet accent line at bottom */}
        <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-violet-400/0 via-violet-400/40 to-violet-400/0 pointer-events-none" />
      </header>

      <div className="flex flex-col gap-4 p-4 pt-4">
        {children}
      </div>
    </>
  );
};

export default Header;

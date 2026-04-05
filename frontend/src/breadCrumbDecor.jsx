import React from "react";
import { useLocation, Link } from "react-router-dom";
import { Home } from "lucide-react";
import {
  SidebarTrigger,
} from "@/components/ui/sidebar";
import RetailSelection from "./loginpage";

// Capitalise and humanise a URL segment, e.g. "customerpurchase" → "Customer Purchase"
const humanise = (seg) =>
  decodeURIComponent(seg)
    .replace(/([a-z])([A-Z])/g, "$1 $2")   // camelCase → words
    .replace(/[-_]/g, " ")                  // kebab/snake → words
    .replace(/\b\w/g, (c) => c.toUpperCase()); // title case

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
          <SidebarTrigger className="text-gray-500 hover:text-violet-600 transition-colors" />

          {/* Slim divider */}
          <div className="h-5 w-px bg-gray-200" />

          {/* Page title */}
          {heading && (
            <div className="flex items-center gap-2">
              <span className="block w-[3px] h-4 rounded-full bg-violet-500" />
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
                className="text-gray-400 hover:text-violet-600 transition-colors flex items-center"
              >
                <Home className="w-3 h-3" />
              </Link>

              {segments.map((seg, idx) => {
                const url  = `/${segments.slice(0, idx + 1).join("/")}`;
                const last = idx === segments.length - 1;
                const label = humanise(seg);

                return (
                  <React.Fragment key={url}>
                    {/* Separator */}
                    <span className="text-gray-300 text-xs select-none font-light">/</span>

                    {/* Segment */}
                    {last ? (
                      <span className="text-xs font-semibold text-violet-600 tracking-wide">
                        {label}
                      </span>
                    ) : (
                      <Link
                        to={url}
                        className="text-xs text-gray-500 hover:text-violet-600 transition-colors font-medium"
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

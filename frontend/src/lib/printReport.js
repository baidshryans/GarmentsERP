/**
 * Opens a new browser window with a clean A4-formatted report and triggers
 * the browser print dialog (which allows saving as PDF).
 *
 * @param {Object}  opts
 * @param {string}  opts.title       � Report heading printed at the top
 * @param {string}  [opts.subtitle]  � Optional line below the title (e.g. date range)
 * @param {string}  opts.html        � The inner HTML of the report body (usually a <table>)
 * @param {boolean} [opts.landscape] � If true, prints in landscape orientation (default: portrait)
 * @param {string}  [opts.company]   � Company name shown above the title (falls back to blank if not provided)
 * @param {string}  [opts.extraCss]  � Additional CSS injected into the print stylesheet
 */
export function printReport({ title, subtitle, html, landscape = false, company = "", extraCss = "" }) {
  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) {
    alert("Please allow popups for this site to print reports.");
    return;
  }

  const orientation = landscape ? "landscape" : "portrait";

  win.document.write(/* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${title}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@200..800&display=swap');

    @page {
      size: A4 ${orientation};
      margin: 8mm 10mm;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html, body {
      font-family: 'Assistant', system-ui, -apple-system, sans-serif;
      font-size: 11px;
      line-height: 1.4;
      color: #1a1a1a;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }

    /* ── Header ──────────────────────────────────────────── */
    .report-header {
      text-align: center;
      margin-bottom: 10px;
      padding-bottom: 8px;
      border-bottom: 2px solid #6965db;
    }
    .report-header h1 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: #1a1a1a;
      margin-bottom: 2px;
    }
    .report-header .subtitle {
      font-size: 11px;
      color: #64748b;
    }
    .report-header .company {
      font-size: 12px;
      font-weight: 600;
      color: #6965db;
      letter-spacing: 1px;
      text-transform: uppercase;
      margin-bottom: 2px;
    }

    /* ── Tables ─────────────────────────────────────────── */
    table {
      width: 100%;
      border-collapse: collapse;
      page-break-inside: auto;
    }
    thead {
      display: table-header-group;
    }
    tr {
      page-break-inside: avoid;
      page-break-after: auto;
    }
    th, td {
      padding: 4px 6px;
      text-align: left;
      vertical-align: top;
      font-size: 10.5px;
    }
    th {
      font-weight: 700;
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      color: #475569;
      background: #f8f7ff !important;
      border-bottom: 1.5px solid #cbd5e1;
    }
    td {
      border-bottom: 0.5px solid #e2e8f0;
    }

    /* Right-align numeric cells */
    .text-right, td[style*="text-align: right"], td[style*="text-align:right"] {
      text-align: right;
    }
    .tabular-nums {
      font-variant-numeric: tabular-nums;
    }
    .font-semibold, .font-bold {
      font-weight: 700;
    }
    .font-medium {
      font-weight: 600;
    }
    .font-mono {
      font-family: 'Courier New', monospace;
    }

    /* Group / section header rows */
    tr.group-header td,
    tr.section-header td {
      background: #f1f0fb !important;
      font-weight: 700;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      color: #475569;
      padding: 6px;
    }

    /* Totals row */
    tfoot tr td, tfoot tr th,
    tr.totals-row td {
      font-weight: 700;
      border-top: 2px solid #94a3b8;
      background: #f8f7ff !important;
      padding: 5px 6px;
    }

    /* Alternating rows */
    tbody tr:nth-child(even) {
      background: #fafafa;
    }

    /* Indent helper */
    .pl-8 { padding-left: 24px; }
    .pl-10 { padding-left: 32px; }

    /* ── Footer ─────────────────────────────────────────── */
    .report-footer {
      margin-top: 12px;
      padding-top: 6px;
      border-top: 1px solid #e2e8f0;
      font-size: 9px;
      color: #94a3b8;
      display: flex;
      justify-content: space-between;
    }

    /* Hide background colors that don't translate well */
    .bg-muted\\/50, .bg-muted\\/30, .bg-muted\\/20, .bg-muted\\/15,
    .bg-muted\\/40, .bg-muted\\/10,
    .bg-accent\\/30, .bg-accent\\/40, .bg-accent\\/20 {
      background: transparent !important;
    }

    /* Badge styles */
    .badge {
      display: inline-block;
      padding: 1px 5px;
      border-radius: 3px;
      font-size: 9px;
      font-weight: 600;
      background: #f1f0fb;
      color: #6965db;
    }

    /* Closing stock special: tint section column headers */
    th[class*="bg-violet"]  { background: #f5f3ff !important; }
    th[class*="bg-green"]   { background: #f0fdf4 !important; }
    th[class*="bg-orange"]  { background: #fff7ed !important; }
    th[class*="bg-red"]     { background: #fef2f2 !important; }
    th[class*="bg-teal"]    { background: #f0fdfa !important; }
    th[class*="bg-purple"]  { background: #faf5ff !important; }
    th[class*="bg-primary"] { background: #f8f7ff !important; }

    /* Utility: hide screen-only elements */
    .print-hide, .no-print { display: none !important; }

    ${extraCss}
  </style>
</head>
<body>
  <div class="report-header">
    ${company ? `<div class="company">${company}</div>` : ""}
    <h1>${title}</h1>
    ${subtitle ? `<div class="subtitle">${subtitle}</div>` : ""}
  </div>

  <div class="report-body">
    ${html}
  </div>

  <div class="report-footer">
    <span>Printed on ${new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })} at ${new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span>
    <span>Jewel India ERP</span>
  </div>
</body>
</html>`);

  win.document.close();

  // Wait for fonts to load, then print
  win.onload = () => {
    setTimeout(() => {
      win.focus();
      win.print();
      // Don't auto-close � let user review / re-print
    }, 400);
  };
}

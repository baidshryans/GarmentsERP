import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { fetchBarcodeList } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Printer } from "lucide-react";

/**
 * BarcodePrint � Printable label sheet for one or more barcodes.
 *
 * Usage:
 *   /inventory/barcode-print?ids=1,2,3   → print multiple labels
 *   /inventory/barcode-print?ids=42      → print single label
 *
 * Each label shows:
 *   - QR code image  (top)
 *   - Barcode number (bold, monospace)
 *   - Item, Purity, GW, NW, Pcs, HUID
 */

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";

function qrSrc(path) {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE_URL.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;
}

function Label({ b }) {
  return (
    <div
      className="barcode-label"
      style={{
        width: "8cm",
        minHeight: "4cm",
        border: "1px solid #ccc",
        borderRadius: "6px",
        padding: "10px 12px",
        display: "flex",
        gap: "10px",
        alignItems: "flex-start",
        pageBreakInside: "avoid",
        background: "#fff",
        margin: "4px",
        boxSizing: "border-box",
      }}
    >
      {/* QR Code */}
      {b.qr_code ? (
        <img
          src={qrSrc(b.qr_code)}
          alt="QR"
          style={{ width: "2.4cm", height: "2.4cm", objectFit: "contain", flexShrink: 0, border: "1px solid #eee" }}
        />
      ) : (
        <div
          style={{
            width: "2.4cm",
            height: "2.4cm",
            background: "#f5f5f5",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "9px",
            color: "#aaa",
            flexShrink: 0,
            border: "1px solid #eee",
          }}
        >
          No QR
        </div>
      )}

      {/* Text details */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Barcode number */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: "13px",
            fontWeight: "bold",
            letterSpacing: "1px",
            marginBottom: "4px",
            wordBreak: "break-all",
          }}
        >
          {b.barcode}
        </div>

        <table style={{ fontSize: "9px", width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {(b.item_desc || b.item_name) && (
              <tr>
                <td style={{ color: "#888", paddingRight: "4px", whiteSpace: "nowrap" }}>Item</td>
                <td style={{ fontWeight: 500 }}>{b.item_desc || b.item_name}</td>
              </tr>
            )}
            {(b.purity_name || b.purity) && (
              <tr>
                <td style={{ color: "#888", paddingRight: "4px", whiteSpace: "nowrap" }}>Purity</td>
                <td>{b.purity_name || b.purity}</td>
              </tr>
            )}
            <tr>
              <td style={{ color: "#888", paddingRight: "4px" }}>GW / NW</td>
              <td>
                {parseFloat(b.gw || 0).toFixed(3)} g / {parseFloat(b.nw || 0).toFixed(3)} g
              </td>
            </tr>
            {b.pcs && (
              <tr>
                <td style={{ color: "#888", paddingRight: "4px" }}>Pcs</td>
                <td>{b.pcs}</td>
              </tr>
            )}
            {b.huid && (
              <tr>
                <td style={{ color: "#888", paddingRight: "4px" }}>HUID</td>
                <td style={{ fontFamily: "monospace", fontSize: "8px" }}>{b.huid}</td>
              </tr>
            )}
            {b.design_code && (
              <tr>
                <td style={{ color: "#888", paddingRight: "4px" }}>Design</td>
                <td>{b.design_code}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function BarcodePrint() {
  const [searchParams] = useSearchParams();
  const idsParam = searchParams.get("ids") || "";
  const ids = idsParam.split(",").map((s) => s.trim()).filter(Boolean);

  const [barcodes, setBarcodes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ids.length) { setLoading(false); return; }
    // Fetch with id filter � backend supports ?ids=1,2,3 or individual fetches
    // We use the list endpoint with id__in filter
    fetchBarcodeList({ ids: ids.join(","), page_size: ids.length + 10 }).then((res) => {
      if (res.success) {
        const results = res.data?.results ?? (Array.isArray(res.data) ? res.data : []);
        // Filter to only the requested IDs (in case backend doesn't support id filter)
        const idSet = new Set(ids.map(Number));
        const filtered = results.filter((b) => idSet.has(b.id));
        setBarcodes(filtered.length > 0 ? filtered : results.slice(0, ids.length));
      }
      setLoading(false);
    });
  }, [idsParam]);

  if (loading) {
    return (
      <div className="p-8 flex flex-col gap-3">
        {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 w-80" />)}
      </div>
    );
  }

  if (!barcodes.length) {
    return (
      <div className="p-8 text-muted-foreground text-sm">
        No barcodes found for the given IDs.
      </div>
    );
  }

  return (
    <>
      {/* Print-only styles */}
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { margin: 0; }
          .print-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 8px;
          }
        }
        @media screen {
          .print-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            padding: 24px;
          }
        }
      `}</style>

      {/* Toolbar � hidden on print */}
      <div className="no-print flex items-center gap-3 px-6 py-3 border-b border-border bg-muted/30">
        <span className="text-sm font-medium">
          {barcodes.length} label{barcodes.length !== 1 ? "s" : ""} ready to print
        </span>
        <Button
          size="sm"
          className="bg-primary hover:bg-primary text-white"
          onClick={() => window.print()}
        >
          <Printer className="size-4 mr-1.5" />
          Print Labels
        </Button>
        <Button size="sm" variant="outline" onClick={() => window.history.back()}>
          Back
        </Button>
      </div>

      {/* Label grid */}
      <div className="print-grid">
        {barcodes.map((b) => (
          <Label key={b.id} b={b} />
        ))}
      </div>
    </>
  );
}

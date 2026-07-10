import { useState, useEffect } from "react";
import { formatMoney } from "@/lib/format";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Package, Printer, Loader2 } from "lucide-react";
import { fetchCatalogDetail, fetchBarcodeDetailOnly } from "@/services/apiService";
import { openAndPrint } from "@/services/print/utils";
import { MultiEstimatePrint } from "@/components/Sales/salesPrintEstimate";
import { useToast } from "@/hooks/use-toast";
import StoneSwapPanel from "./StoneSwapPanel";

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const imgSrc = (p) =>
  !p ? null : p.startsWith("http") ? p
    : `${BASE_URL.replace(/\/$/, "")}${p.startsWith("/") ? "" : "/"}${p}`;
const inr = (n) => formatMoney(n, { decimals: 0, space: false });

export default function CatalogDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [sp] = useSearchParams();
  const [d, setD] = useState(null);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(true);
  const [printing, setPrinting] = useState(null);   // barcode currently being printed

  // Open the estimate print window for a single barcode — without leaving the
  // catalog page (reuses the Sales Estimate print view).
  const printEstimate = async (barcode) => {
    setPrinting(barcode);
    try {
      const res = await fetchBarcodeDetailOnly(barcode);
      if (res.success && res.data) {
        openAndPrint(<MultiEstimatePrint items={[{ ...res.data, _key: barcode }]} />);
      } else {
        toast({
          title: "Could not load barcode",
          description: typeof res.error === "string" ? res.error : barcode,
          variant: "destructive",
        });
      }
    } catch {
      toast({ title: "Failed to print estimate", variant: "destructive" });
    }
    setPrinting(null);
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      const qs = sp.toString() ? `?${sp.toString()}` : "";
      const res = await fetchCatalogDetail(id, qs);
      if (res.success) setD(res.data);
      setLoading(false);
    })();
  }, [id]);

  if (loading) return <div className="py-20 text-center text-muted-foreground">Loading…</div>;
  if (!d) return <div className="py-20 text-center text-muted-foreground">Design not found.</div>;

  const p = d.price || {};
  const images = d.images || [];

  return (
    <div className="mt-4 space-y-4">
      <Button variant="ghost" size="sm" className="gap-2" onClick={() => navigate(-1)}>
        <ArrowLeft className="size-4" /> Back to catalog
      </Button>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Gallery */}
        <div>
          <div className="aspect-square rounded-lg border bg-muted/30 flex items-center justify-center overflow-hidden">
            {images[active]?.image ? (
              <img src={imgSrc(images[active].image)} alt={d.design_no} className="w-full h-full object-cover" />
            ) : (
              <Package className="size-16 text-muted-foreground" />
            )}
          </div>
          {images.length > 1 && (
            <div className="flex gap-2 mt-3 flex-wrap">
              {images.map((im, i) => (
                <button key={im.id} onClick={() => setActive(i)}
                  className={`size-16 rounded border overflow-hidden ${i === active ? "ring-2 ring-primary" : ""}`}>
                  <img src={imgSrc(im.image)} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Details */}
        <div className="space-y-4">
          <div>
            <h1 className="text-2xl font-bold font-mono">{d.design_no}{d.variation_suffix ? `-${d.variation_suffix}` : ""}</h1>
            <p className="text-muted-foreground">{d.item_name} — {d.item_desc}</p>
            <span className={`inline-block mt-2 rounded-full px-2 py-0.5 text-xs font-medium ${d.in_stock_count > 0 ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`}>
              {d.in_stock_count > 0 ? `${d.in_stock_count} in stock` : "Made to order"}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 text-sm">
            <Spec label="Pieces" value={d.pcs} />
            <Spec label="Gross wt" value={`${d.gw} g`} />
            <Spec label="Net wt" value={`${d.nw} g`} />
            <Spec label="Purity" value={p.gold_purity || "—"} />
            <Spec label="Making" value={d.making_type || "—"} />
          </div>

          {/* Price breakdown */}
          <div className="rounded-lg border bg-card p-4">
            <div className="text-xs font-semibold text-muted-foreground mb-2">PRICE BREAKDOWN</div>
            <div className="space-y-1 text-sm">
              {(p.component_lines || []).map((c, i) => (
                <Row key={i} label={c.name + (c.ct ? ` (${c.ct} ct)` : "")} value={inr(c.amount)} />
              ))}
              <div className="border-t my-2" />
              <Row label="Taxable" value={inr(p.taxable)} />
              <Row label={`GST (${p.gst_pct || 0}%)`} value={inr(p.gst)} />
              <div className="border-t my-2" />
              <div className="flex justify-between text-base font-bold">
                <span>Total</span><span>{inr(p.total_price)}</span>
              </div>
            </div>
          </div>

          <StoneSwapPanel
            design={d}
            tier={sp.get("tier") || "retail"}
            pricelist={sp.get("pricelist") || null}
          />

          {/* Available barcodes */}
          {d.barcodes?.length > 0 && (
            <div className="rounded-lg border bg-card p-4">
              <div className="text-xs font-semibold text-muted-foreground mb-2">
                PIECES ({d.in_stock_count} in stock) — click to print an estimate
              </div>
              <div className="flex flex-wrap gap-2">
                {d.barcodes.map((b) => (
                  <button
                    key={b.barcode}
                    type="button"
                    title={`Print estimate for ${b.barcode}`}
                    disabled={printing === b.barcode}
                    onClick={() => printEstimate(b.barcode)}
                    className={`group inline-flex items-center gap-1.5 font-mono text-xs rounded px-2 py-1 border transition-colors hover:border-primary hover:text-primary disabled:opacity-60 ${b.in_stock ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-muted text-muted-foreground"}`}
                  >
                    {printing === b.barcode
                      ? <Loader2 className="size-3.5 animate-spin" />
                      : <Printer className="size-3.5 opacity-60 group-hover:opacity-100" />}
                    {b.barcode}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Spec({ label, value }) {
  return (
    <div className="rounded border bg-muted/20 px-3 py-2">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}

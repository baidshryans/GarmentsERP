import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Package, FileDown, ChevronLeft, ChevronRight } from "lucide-react";
import { fetchPublicCatalog } from "@/services/apiService";

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const imgSrc = (p) =>
  !p ? null : p.startsWith("http") ? p
    : `${BASE_URL.replace(/\/$/, "")}${p.startsWith("/") ? "" : "/"}${p}`;
const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function PublicCatalog() {
  const { token } = useParams();
  const [rows, setRows] = useState([]);
  const [label, setLabel] = useState("Catalog");
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res = await fetchPublicCatalog(token, `?page=${page}&page_size=12`);
      if (res.success) {
        setRows(res.data?.results ?? []);
        setLabel(res.data?.catalog_label ?? "Catalog");
        setCount(res.data?.count ?? 0);
        setTotalPages(res.data?.total_pages ?? 1);
      } else if (res.status === 404) {
        setGone(true);
      }
      setLoading(false);
    })();
  }, [token, page]);

  const pdfUrl = `${BASE_URL.replace(/\/$/, "")}/inventory/api/catalog-share/${token}/pdf/?fmt=summary`;

  if (gone) {
    return (
      <div className="min-h-screen flex items-center justify-center text-center px-6">
        <div>
          <Package className="size-10 mx-auto text-muted-foreground mb-3" />
          <h1 className="text-lg font-semibold">This catalog link is no longer available</h1>
          <p className="text-sm text-muted-foreground">Please contact the store for an updated link.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 bg-background/95 backdrop-blur z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <h1 className="text-lg font-semibold">{label}</h1>
          <span className="text-sm text-muted-foreground">{count} designs</span>
          <div className="flex-1" />
          <Button asChild variant="outline" size="sm" className="gap-2">
            <a href={pdfUrl} target="_blank" rel="noreferrer"><FileDown className="size-4" /> PDF</a>
          </Button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {loading ? (
          <div className="py-20 text-center text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="py-20 text-center text-muted-foreground">No items to show.</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {rows.map((d) => (
              <div key={d.id} className="rounded-lg border bg-card shadow-sm overflow-hidden">
                <div className="aspect-square bg-muted/30 flex items-center justify-center overflow-hidden">
                  {d.cover_image ? (
                    <img src={imgSrc(d.cover_image)} alt={d.design_no} className="w-full h-full object-cover" />
                  ) : (
                    <Package className="size-10 text-muted-foreground" />
                  )}
                </div>
                <div className="p-3 space-y-1">
                  <div className="font-mono text-sm font-medium">{d.design_no}</div>
                  <div className="text-xs text-muted-foreground truncate">{d.item_name || ""}</div>
                  <div className="text-xs text-muted-foreground">{d.nw} g · {d.gold_purity || "—"}</div>
                  <div className="text-base font-semibold">{inr(d.price)}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 mt-6">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="size-4" /> Prev
            </Button>
            <span className="text-sm text-muted-foreground">Page {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next <ChevronRight className="size-4" />
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}

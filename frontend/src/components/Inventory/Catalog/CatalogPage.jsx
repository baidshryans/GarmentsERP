import { useState, useEffect, useMemo } from "react";
import { formatMoney } from "@/lib/format";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import { Package, ChevronLeft, ChevronRight, FileDown, Share2, Copy, Trash2, Link as LinkIcon } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import {
  fetchCatalog, fetchPurity, fetchB2BPricelists, fetchRetailDiscountPricelists,
  downloadCatalogPdf, fetchCatalogShares, createCatalogShare, deleteCatalogShare,
  fetchMainItem,
} from "@/services/apiService";

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const imgSrc = (p) =>
  !p ? null : p.startsWith("http") ? p
    : `${BASE_URL.replace(/\/$/, "")}${p.startsWith("/") ? "" : "/"}${p}`;
const inr = (n) => formatMoney(n, { decimals: 0, space: false });

export default function CatalogPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [count, setCount] = useState(0);

  const [q, setQ] = useState("");
  const [item, setItem] = useState("");
  const [purity, setPurity] = useState("");
  const [minW, setMinW] = useState("");
  const [maxW, setMaxW] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [inStock, setInStock] = useState(false);
  const [tier, setTier] = useState("retail");          // "retail" | "retail:<id>" | "b2b:<id>"

  const [purities, setPurities] = useState([]);
  const [items, setItems] = useState([]);
  const [b2bLists, setB2bLists] = useState([]);
  const [retailLists, setRetailLists] = useState([]);

  useEffect(() => {
    (async () => {
      const [pu, b2b, rt, it] = await Promise.all([
        fetchPurity(), fetchB2BPricelists(), fetchRetailDiscountPricelists(),
        fetchMainItem({ type: "M", page_size: 10000 }),
      ]);
      if (pu.success) setPurities(pu.data?.results ?? pu.data ?? []);
      if (b2b.success) setB2bLists(b2b.data?.results ?? b2b.data ?? []);
      if (rt.success) setRetailLists(rt.data?.results ?? rt.data ?? []);
      if (it.success) setItems(it.data?.results ?? it.data ?? []);
    })();
  }, []);

  const tierParams = useMemo(() => {
    if (tier.startsWith("b2b:")) return `&tier=b2b&pricelist=${tier.slice(4)}`;
    if (tier.startsWith("retail:")) return `&tier=retail&pricelist=${tier.slice(7)}`;
    return "&tier=retail";
  }, [tier]);

  const filterQS = () => {
    let p = `${tierParams}`;
    if (q.trim()) p += `&search=${encodeURIComponent(q.trim())}`;
    if (item) p += `&item=${encodeURIComponent(item)}`;
    if (purity) p += `&purity=${purity}`;
    if (minW) p += `&min_weight=${minW}`;
    if (maxW) p += `&max_weight=${maxW}`;
    if (minPrice) p += `&min_price=${minPrice}`;
    if (maxPrice) p += `&max_price=${maxPrice}`;
    if (inStock) p += `&in_stock=1`;
    return p;
  };

  // Current filters as a plain object + the tier/pricelist split — for share links.
  const filterObj = () => {
    const f = {};
    if (q.trim()) f.search = q.trim();
    if (item) f.item = item;
    if (purity) f.purity = purity;
    if (minW) f.min_weight = minW;
    if (maxW) f.max_weight = maxW;
    if (minPrice) f.min_price = minPrice;
    if (maxPrice) f.max_price = maxPrice;
    if (inStock) f.in_stock = "1";
    return f;
  };
  const tierParts = () => {
    if (tier.startsWith("b2b:")) return { tier: "b2b", pricelist_id: Number(tier.slice(4)) };
    if (tier.startsWith("retail:")) return { tier: "retail", pricelist_id: Number(tier.slice(7)) };
    return { tier: "retail", pricelist_id: null };
  };

  const exportPdf = async (fmt) => {
    toast({ title: `Generating ${fmt} PDF…` });
    const res = await downloadCatalogPdf(`?fmt=${fmt}${filterQS()}`);
    if (!res.success) { toast({ title: "PDF export failed", variant: "destructive" }); return; }
    const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url; a.download = `catalog_${fmt}.pdf`; a.click();
    URL.revokeObjectURL(url);
  };

  const load = async (pg = page) => {
    setLoading(true);
    const p = `?page=${pg}&page_size=12${filterQS()}`;
    const res = await fetchCatalog(p);
    if (res.success) {
      setRows(res.data?.results ?? []);
      setTotalPages(res.data?.total_pages ?? 1);
      setCount(res.data?.count ?? 0);
    }
    setLoading(false);
  };

  // Reload on filter changes (reset to page 1); debounce the search box.
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); load(1); }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, item, purity, minW, maxW, minPrice, maxPrice, inStock, tier]);

  useEffect(() => { load(page); /* eslint-disable-next-line */ }, [page]);

  const goDetail = (d) => navigate(`/inventory/catalog/${d.id}?${tierParams.replace(/^&/, "")}`);

  return (
    <div className="mt-4 flex gap-6">
      {/* Filters */}
      <aside className="w-60 shrink-0 space-y-4">
        <div>
          <Label className="text-xs font-semibold text-muted-foreground">SEARCH</Label>
          <Input placeholder="Design no / item…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <Label className="text-xs font-semibold text-muted-foreground">PRICING TIER</Label>
          <Select value={tier} onValueChange={setTier}>
            <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="retail">Retail (list)</SelectItem>
              {retailLists.map((r) => (
                <SelectItem key={`r${r.id}`} value={`retail:${r.id}`}>Retail · {r.name}</SelectItem>
              ))}
              {b2bLists.map((b) => (
                <SelectItem key={`b${b.id}`} value={`b2b:${b.id}`}>B2B · {b.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs font-semibold text-muted-foreground">ITEM</Label>
          <SearchableComboBox
            options={[{ item_name: "All items", short_code: "" }, ...items]}
            labelKey="item_name"
            searchKeys={["short_code"]}
            value={item ? (items.find((i) => i.short_code === item)?.item_name || item) : ""}
            onSelect={(opt) => setItem(opt.short_code || "")}
            renderOption={(o) => (o.short_code ? `${o.item_name} (${o.short_code})` : o.item_name)}
            placeholder="All items"
            className="h-9"
          />
        </div>
        <div>
          <Label className="text-xs font-semibold text-muted-foreground">PURITY</Label>
          <Select value={purity || "all"} onValueChange={(v) => setPurity(v === "all" ? "" : v)}>
            <SelectTrigger className="h-9"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {purities.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.purity}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs font-semibold text-muted-foreground">NET WEIGHT (g)</Label>
          <div className="flex gap-2">
            <Input type="number" placeholder="Min" value={minW} onChange={(e) => setMinW(e.target.value)} />
            <Input type="number" placeholder="Max" value={maxW} onChange={(e) => setMaxW(e.target.value)} />
          </div>
        </div>
        <div>
          <Label className="text-xs font-semibold text-muted-foreground">PRICE (₹)</Label>
          <div className="flex gap-2">
            <Input type="number" placeholder="Min" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} />
            <Input type="number" placeholder="Max" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} />
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <Checkbox checked={inStock} onCheckedChange={(v) => setInStock(!!v)} />
          <span className="text-sm">In stock only</span>
        </label>
      </aside>

      {/* Grid */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center mb-3">
          <h2 className="text-lg font-semibold">Catalog</h2>
          <span className="ml-2 text-sm text-muted-foreground">{count} designs</span>
          <div className="flex-1" />
          <ShareDialog filterObj={filterObj} tierParts={tierParts} toast={toast} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2 ml-2">
                <FileDown className="size-4" /> Export PDF
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => exportPdf("summary")}>Summary (image grid)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportPdf("detailed")}>Detailed (breakdown)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportPdf("quotation")}>Quotation (table)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {loading ? (
          <div className="py-20 text-center text-muted-foreground">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="py-20 text-center text-muted-foreground">No designs match these filters.</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
            {rows.map((d) => (
              <button
                key={d.id}
                onClick={() => goDetail(d)}
                className="text-left rounded-lg border bg-card shadow-sm overflow-hidden hover:shadow-md hover:border-primary/40 transition-all"
              >
                <div className="aspect-square bg-muted/30 flex items-center justify-center overflow-hidden">
                  {d.cover_image ? (
                    <img src={imgSrc(d.cover_image)} alt={d.design_no} className="w-full h-full object-cover" />
                  ) : (
                    <Package className="size-10 text-muted-foreground" />
                  )}
                </div>
                <div className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-medium">{d.design_no}</span>
                    <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${d.in_stock_count > 0 ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`}>
                      {d.in_stock_count > 0 ? `${d.in_stock_count} in stock` : "made to order"}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground truncate">{d.item_name || d.item}</div>
                  <div className="text-xs text-muted-foreground">{d.nw} g · {d.price?.gold_purity || "—"}</div>
                  <div className="text-base font-semibold">{inr(d.price?.total_price)}</div>
                </div>
              </button>
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
      </div>
    </div>
  );
}

function shareUrl(token) {
  return `${window.location.origin}/share/${token}`;
}

function ShareDialog({ filterObj, tierParts, toast }) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [shares, setShares] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await fetchCatalogShares();
    if (res.success) setShares(res.data?.results ?? res.data ?? []);
  };
  useEffect(() => { if (open) load(); }, [open]);

  const create = async () => {
    setBusy(true);
    const { tier, pricelist_id } = tierParts();
    const res = await createCatalogShare({ label, tier, pricelist_id, filters: filterObj() });
    setBusy(false);
    if (res.success) {
      toast({ title: "Share link created." });
      setLabel("");
      await navigator.clipboard?.writeText(shareUrl(res.data.token)).catch(() => {});
      load();
    } else {
      toast({ title: "Could not create link", variant: "destructive" });
    }
  };

  const copy = (token) => {
    navigator.clipboard?.writeText(shareUrl(token));
    toast({ title: "Link copied." });
  };

  const revoke = async (id) => {
    const res = await deleteCatalogShare(id);
    if (res.success) { toast({ title: "Link revoked." }); setShares((p) => p.filter((s) => s.id !== id)); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Share2 className="size-4" /> Share
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Share this catalog</DialogTitle>
          <DialogDescription>
            Creates a public link that shows the current filters &amp; pricing tier. Anyone with the link
            can view it — sale price only. Revoke any time.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2">
          <Input placeholder="Label (e.g. Diwali Collection)" value={label} onChange={(e) => setLabel(e.target.value)} />
          <Button onClick={create} disabled={busy} className="gap-2 shrink-0">
            <LinkIcon className="size-4" /> Create link
          </Button>
        </div>

        <div className="mt-2 max-h-72 overflow-y-auto divide-y">
          {shares.length === 0 && <p className="text-sm text-muted-foreground py-4 text-center">No share links yet.</p>}
          {shares.map((s) => (
            <div key={s.id} className="flex items-center gap-2 py-2">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate">{s.label || "Catalog"}</div>
                <div className="text-[11px] text-muted-foreground truncate font-mono">{shareUrl(s.token)}</div>
              </div>
              <span className="text-[10px] uppercase rounded px-1.5 py-0.5 bg-muted">{s.tier}</span>
              <Button size="icon" variant="ghost" className="size-7" title="Copy" onClick={() => copy(s.token)}>
                <Copy className="size-4" />
              </Button>
              <Button size="icon" variant="ghost" className="size-7 text-destructive" title="Revoke" onClick={() => revoke(s.id)}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

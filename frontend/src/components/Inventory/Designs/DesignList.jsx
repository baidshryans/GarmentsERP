import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import { Plus, Pencil, Trash2, ImageIcon, Package } from "lucide-react";
import { fetchDesigns, deleteDesign } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";
import DesignImages from "./DesignImages";

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const imgSrc = (p) =>
  !p ? null : p.startsWith("http") ? p
    : `${BASE_URL.replace(/\/$/, "")}${p.startsWith("/") ? "" : "/"}${p}`;

export default function DesignList() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [photo, setPhoto] = useState({ open: false, id: null, text: "" });

  const load = async () => {
    setLoading(true);
    const res = await fetchDesigns("?page_size=500");
    if (res.success) setRows(res.data?.results ?? res.data ?? []);
    else toast({ title: "Failed to load designs.", variant: "destructive" });
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const onDelete = async (d) => {
    if (!window.confirm(`Delete design ${d.design_no}? This also removes its photos and detail rows.`)) return;
    const res = await deleteDesign(d.id);
    if (res.success) {
      toast({ title: "Design deleted." });
      setRows((p) => p.filter((x) => x.id !== d.id));
    } else {
      toast({ title: "Delete failed.", variant: "destructive" });
    }
  };

  const filtered = rows.filter((d) => {
    const s = q.trim().toLowerCase();
    if (!s) return true;
    return (
      (d.design_no || "").toLowerCase().includes(s) ||
      (d.item_desc || "").toLowerCase().includes(s) ||
      (d.item_name || "").toLowerCase().includes(s)
    );
  });

  return (
    <div className="mt-4 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">Designs</h2>
        <span className="text-sm text-muted-foreground">{filtered.length} of {rows.length}</span>
        <div className="flex-1" />
        <Input
          placeholder="Search design no / item…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-xs"
        />
        <Button className="gap-2" onClick={() => navigate("/inventory/designs/add/")}>
          <Plus className="size-4" /> Add Design
        </Button>
      </div>

      <div className="rounded-lg border bg-card shadow-sm overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Photo</TableHead>
              <TableHead>Design No</TableHead>
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Pcs</TableHead>
              <TableHead className="text-right">GW</TableHead>
              <TableHead className="text-right">NW</TableHead>
              <TableHead>Making</TableHead>
              <TableHead className="text-center">In stock</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={9} className="text-center py-10 text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {!loading && filtered.length === 0 && (
              <TableRow><TableCell colSpan={9} className="text-center py-10 text-muted-foreground">No designs found.</TableCell></TableRow>
            )}
            {!loading && filtered.map((d) => (
              <TableRow key={d.id}>
                <TableCell>
                  {d.cover_image ? (
                    <img src={imgSrc(d.cover_image)} alt={d.design_no} className="size-12 rounded object-cover border" />
                  ) : (
                    <div className="size-12 rounded border bg-muted/30 flex items-center justify-center">
                      <Package className="size-5 text-muted-foreground" />
                    </div>
                  )}
                </TableCell>
                <TableCell className="font-mono font-medium">{d.design_no}{d.variation_suffix ? `-${d.variation_suffix}` : ""}</TableCell>
                <TableCell>{d.item_name || d.item}<div className="text-xs text-muted-foreground">{d.item_desc}</div></TableCell>
                <TableCell className="text-right">{d.pcs}</TableCell>
                <TableCell className="text-right">{d.gw}</TableCell>
                <TableCell className="text-right">{d.nw}</TableCell>
                <TableCell>{d.making_type}</TableCell>
                <TableCell className="text-center">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${d.in_stock_count > 0 ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`}>
                    {d.in_stock_count}/{d.total_barcodes}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button size="icon" variant="ghost" title="Photos"
                      onClick={() => setPhoto({ open: true, id: d.id, text: d.design_no })}>
                      <ImageIcon className="size-4" />
                    </Button>
                    <Button size="icon" variant="ghost" title="Edit"
                      onClick={() => navigate(`/inventory/designs/${d.id}`)}>
                      <Pencil className="size-4" />
                    </Button>
                    <Button size="icon" variant="ghost" title="Delete"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDelete(d)}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <DesignImages
        designId={photo.id}
        designText={photo.text}
        open={photo.open}
        onOpenChange={(v) => setPhoto((p) => ({ ...p, open: v }))}
      />
    </div>
  );
}

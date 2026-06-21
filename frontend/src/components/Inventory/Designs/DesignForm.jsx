import { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import { Plus, Trash2, ImageIcon } from "lucide-react";
import { FieldContainer } from "@/Utils";
import { useToast } from "@/hooks/use-toast";
import {
  fetchMainItem, fetchPurity, fetchKarigarIssues, fetchPackets,
  createDesign, updateDesign, fetchDesignForEdit, uploadDesignImages,
} from "@/services/apiService";
import DesignImages from "./DesignImages";

const num = (v) => (v === "" || v === null || v === undefined ? 0 : Number(v));

// Short code of the base gold item — its wt_gm is always = NW (auto-filled, read-only)
const GOLD_CODE = "Gold";

// Cache dropdown data in sessionStorage — these master lists don't change mid-session
const SESSION_TTL = 10 * 60 * 1000; // 10 minutes
function cachedFetch(key, fetcher) {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw) {
      const { ts, data } = JSON.parse(raw);
      if (Date.now() - ts < SESSION_TTL) return Promise.resolve({ success: true, data });
    }
  } catch {}
  return fetcher().then((res) => {
    if (res.success) {
      try { sessionStorage.setItem(key, JSON.stringify({ ts: Date.now(), data: res.data })); } catch {}
    }
    return res;
  });
}

export default function DesignForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [items, setItems] = useState([]);
  const [purities, setPurities] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [packets, setPackets] = useState([]);
  const [photoOpen, setPhotoOpen] = useState(false);
  const [stagedPhotos, setStagedPhotos] = useState([]);

  const { register, control, handleSubmit, reset, getValues, setValue, watch } = useForm({
    defaultValues: {
      design_no: "", variation_suffix: "", item: "", item_desc: "",
      pcs: 1, gw: 0, nw: 0, making: 0, making_type: "", kr_code: null,
      making_rate: 0, design_details: [],
    },
  });

  // NW (gold weight) = GW − Σ(non-gold wt_gm) − Σ(ct / 5)
  // Gold row wt_gm is excluded from the sum and auto-filled with NW.
  // Conversion: 5 ct = 1 gm, so ct_to_gm = ct / 5
  const recalcNWFromDetails = (gwRaw) => {
    const gw = parseFloat(gwRaw ?? getValues("gw")) || 0;
    const details = getValues("design_details") || [];
    const totalWtGm = details.reduce(
      (s, d) => (d.sub_item === GOLD_CODE ? s : s + (parseFloat(d.wt_gm) || 0)), 0
    );
    const totalCtAsGm = details.reduce((s, d) => s + (parseFloat(d.ct) || 0) / 5, 0);
    const nw = parseFloat(Math.max(0, gw - totalWtGm - totalCtAsGm).toFixed(3));
    setValue("nw", nw);
    // Write NW back into every gold sub-item row
    details.forEach((d, idx) => {
      if (d.sub_item === GOLD_CODE) setValue(`design_details.${idx}.wt_gm`, nw);
    });
  };
  const { fields, append, remove } = useFieldArray({ control, name: "design_details" });

  const detailValues = watch("design_details");

  useEffect(() => {
    (async () => {
      const [it, pu, kr, pk] = await Promise.all([
        cachedFetch("df_items", () => fetchMainItem({ page_size: 10000 })),
        cachedFetch("df_purities", fetchPurity),
        cachedFetch("df_karigars", () => fetchKarigarIssues({ page_size: 1000 })),
        cachedFetch("df_packets", fetchPackets),
      ]);
      if (it.success) setItems(it.data?.results ?? it.data ?? []);
      if (pu.success) setPurities(pu.data?.results ?? pu.data ?? []);
      if (kr.success) setKarigars(kr.data?.results ?? kr.data ?? []);
      if (pk.success) setPackets(pk.data?.results ?? pk.data ?? []);

      if (id) {
        const res = await fetchDesignForEdit(id);
        if (res.success) {
          const d = res.data;
          reset({
            design_no: d.design_no ?? "",
            variation_suffix: d.variation_suffix ?? "",
            item: d.item ?? "",
            item_desc: d.item_desc ?? "",
            pcs: d.pcs ?? 0, gw: d.gw ?? 0, nw: d.nw ?? 0,
            making: d.making ?? 0, making_type: d.making_type ?? "",
            kr_code: d.kr_code ?? null,
            making_rate: d.making_rate ?? 0,
            design_details: (d.design_details ?? []).map((x) => ({
              sub_item: x.sub_item, metal_purity: x.metal_purity,
              packet: x.packet ?? "",
              pcs: x.pcs, ct: x.ct, wt_gm: x.wt_gm ?? 0, rate: x.rate, amt: x.amt,
            })),
          });
          // Auto-fill gold wt_gm after reset settles
          setTimeout(() => recalcNWFromDetails(), 0);
        } else {
          toast({ title: "Failed to load design.", variant: "destructive" });
        }
      }
    })();
  }, [id]);

  const onSubmit = async (v) => {
    const payload = {
      design_no: v.design_no,
      variation_suffix: v.variation_suffix || null,
      item: v.item,
      item_desc: v.item_desc || "",
      pcs: num(v.pcs), gw: num(v.gw), nw: num(v.nw),
      making: num(v.making), making_type: v.making_type || "",
      kr_code: v.kr_code || null,
      making_rate: num(v.making_rate),
      design_details: (v.design_details || []).map((d) => ({
        sub_item: d.sub_item,
        metal_purity: d.metal_purity,
        packet: d.packet || null,
        pcs: num(d.pcs), ct: num(d.ct), wt_gm: num(d.wt_gm), rate: num(d.rate), amt: num(d.amt),
      })),
    };

    const res = id ? await updateDesign(payload, id) : await createDesign(payload);
    if (!res.success) {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
      return;
    }
    let extra = "";
    if (!id && stagedPhotos.length && res.data?.id) {
      const up = await uploadDesignImages(res.data.id, stagedPhotos);
      extra = up.success ? ` + ${stagedPhotos.length} photo${stagedPhotos.length > 1 ? "s" : ""}` : " (photos failed)";
    }
    toast({ title: `Design saved${extra}.` });
    setTimeout(() => navigate("/inventory/designs/"), 800);
  };

  return (
    <div className="mt-4">
      <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-muted-foreground">{id ? "Edit Design" : "New Design"}</h3>
            <Button type="button" variant="outline" size="sm" className="gap-2" onClick={() => setPhotoOpen(true)}>
              <ImageIcon className="size-4" /> Photos
              {!id && stagedPhotos.length > 0 && (
                <span className="ml-1 rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">
                  {stagedPhotos.length}
                </span>
              )}
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-3">
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">DESIGN NO</Label>
              <Input className="font-mono" {...register("design_no", { required: true })} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">VARIATION</Label>
              <Input {...register("variation_suffix")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">ITEM</Label>
              <Controller name="item" control={control} rules={{ required: true }} render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value || ""}>
                  <SelectTrigger className="h-9"><SelectValue placeholder="Select item" /></SelectTrigger>
                  <SelectContent>
                    {items.map((i) => (
                      <SelectItem key={i.short_code} value={i.short_code}>{i.item_name} ({i.short_code})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">DESCRIPTION</Label>
              <Input {...register("item_desc")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">PCS</Label>
              <Input type="number" {...register("pcs")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">GROSS WT</Label>
              <Input
                type="number" step="0.001"
                {...register("gw", {
                  onChange: (e) => recalcNWFromDetails(e.target.value),
                })}
              />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">
                NET WT <span className="text-[10px] text-muted-foreground/60 font-normal">(gold wt)</span>
              </Label>
              <Input type="number" step="0.001" {...register("nw")} className="bg-muted/30" />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">MAKING</Label>
              <Input type="number" step="0.001" {...register("making")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">MAKING TYPE</Label>
              <Input {...register("making_type")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">MAKING RATE</Label>
              <Input type="number" step="0.01" {...register("making_rate")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">KARIGAR</Label>
              <Controller name="kr_code" control={control} render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value ? String(field.value) : ""}>
                  <SelectTrigger className="h-9"><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent>
                    {karigars.map((k) => (
                      <SelectItem key={k.id} value={String(k.id)}>{k.ledger_name || k.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )} />
            </FieldContainer>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-muted-foreground">Components</h3>
            <Button type="button" variant="outline" size="sm" className="gap-2"
              onClick={() => append({ sub_item: "", metal_purity: "", packet: "", pcs: 0, ct: 0, wt_gm: 0, rate: 0, amt: 0 })}>
              <Plus className="size-4" /> Add row
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8"></TableHead>
                <TableHead>Sub-item</TableHead>
                <TableHead>Purity</TableHead>
                <TableHead>Packet</TableHead>
                <TableHead className="text-right">Pcs</TableHead>
                <TableHead className="text-right">Ct</TableHead>
                <TableHead className="text-right">Wt (g)</TableHead>
                <TableHead className="text-right">Rate</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {fields.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground py-4 text-sm">
                    No components. Add rows as needed.
                  </TableCell>
                </TableRow>
              )}
              {fields.map((f, idx) => {
                const rowItem = items.find(i => i.short_code === detailValues?.[idx]?.sub_item);
                const hasPurity = rowItem?.item_type === 'R';
                return (
                <TableRow key={f.id}>
                  <TableCell className="w-8 pr-0">
                    <Button type="button" size="icon" variant="ghost" className="size-7 text-destructive" onClick={() => remove(idx)}>
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                  <TableCell className="min-w-48">
                    <Controller name={`design_details.${idx}.sub_item`} control={control} render={({ field }) => {
                      const isPacketOwned = !!detailValues?.[idx]?.packet;
                      if (isPacketOwned) {
                        return (
                          <div className="h-8 flex items-center px-2 text-sm bg-muted/30 rounded-md border border-input text-muted-foreground">
                            {items.find(i => i.short_code === field.value)?.item_name || field.value || "—"}
                          </div>
                        );
                      }
                      return (
                        <Select
                          onValueChange={(val) => {
                            field.onChange(val);
                            if (val === GOLD_CODE) setTimeout(() => recalcNWFromDetails(), 0);
                          }}
                          value={field.value || ""}
                        >
                          <SelectTrigger className="h-8"><SelectValue placeholder="Item" /></SelectTrigger>
                          <SelectContent>
                            {items.map((i) => (
                              <SelectItem key={i.short_code} value={i.short_code}>{i.item_name} ({i.short_code})</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      );
                    }} />
                  </TableCell>
                  <TableCell className="min-w-28">
                    {hasPurity ? (
                      <Controller name={`design_details.${idx}.metal_purity`} control={control} render={({ field }) => (
                        <Select
                          onValueChange={(v) => field.onChange(Number(v))}
                          value={field.value ? String(field.value) : ""}
                        >
                          <SelectTrigger className="h-8"><SelectValue placeholder="—" /></SelectTrigger>
                          <SelectContent>
                            {purities.map((p) => (
                              <SelectItem key={p.id} value={String(p.id)}>{p.purity}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )} />
                    ) : (
                      <span className="text-muted-foreground/50 px-2 text-sm">—</span>
                    )}
                  </TableCell>
                  <TableCell className="min-w-32">
                    <Controller name={`design_details.${idx}.packet`} control={control} render={({ field }) => (
                      <Select
                        onValueChange={(val) => {
                          const resolved = val === "__none__" ? "" : val;
                          field.onChange(resolved);
                          if (resolved) {
                            const pkt = packets.find(p => p.pckt_no === resolved);
                            if (pkt?.stone_item_short_code) {
                              setValue(`design_details.${idx}.sub_item`, pkt.stone_item_short_code);
                              if (pkt.stone_item_short_code === GOLD_CODE) setTimeout(() => recalcNWFromDetails(), 0);
                            }
                          }
                        }}
                        value={field.value || ""}
                      >
                        <SelectTrigger className="h-8"><SelectValue placeholder="—" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__">— None</SelectItem>
                          {packets.map((p) => (
                            <SelectItem key={p.pckt_no} value={p.pckt_no}>{p.pckt_no}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )} />
                  </TableCell>
                  <TableCell><Input type="number" className="h-8 text-right" {...register(`design_details.${idx}.pcs`)} /></TableCell>
                  <TableCell><Input type="number" step="0.001" className="h-8 text-right"
                    {...register(`design_details.${idx}.ct`, {
                      onChange: () => recalcNWFromDetails(),
                    })} /></TableCell>
                  <TableCell>
                    {detailValues?.[idx]?.sub_item === GOLD_CODE ? (
                      <Input type="number" step="0.001" className="h-8 text-right bg-muted/30"
                        readOnly tabIndex={-1}
                        {...register(`design_details.${idx}.wt_gm`)} />
                    ) : (
                      <Input type="number" step="0.001" className="h-8 text-right"
                        {...register(`design_details.${idx}.wt_gm`, {
                          onChange: () => recalcNWFromDetails(),
                        })} />
                    )}
                  </TableCell>
                  <TableCell><Input type="number" className="h-8 text-right" {...register(`design_details.${idx}.rate`)} /></TableCell>
                  <TableCell><Input type="number" className="h-8 text-right" {...register(`design_details.${idx}.amt`)} /></TableCell>
                </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" className="px-6">Save</Button>
          <Button type="button" variant="outline" onClick={() => navigate("/inventory/designs/")}>Cancel</Button>
        </div>
      </form>

      <DesignImages
        designId={id || undefined}
        designText={watch("design_no") || "New Design"}
        open={photoOpen}
        onOpenChange={setPhotoOpen}
        staged={!id}
        stagedFiles={stagedPhotos}
        onStagedChange={setStagedPhotos}
      />
    </div>
  );
}

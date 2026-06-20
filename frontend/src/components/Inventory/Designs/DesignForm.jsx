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
  fetchMainItem, fetchPurity, fetchKarigarIssues,
  createDesign, updateDesign, fetchDesignForEdit, uploadDesignImages,
} from "@/services/apiService";
import DesignImages from "./DesignImages";

const num = (v) => (v === "" || v === null || v === undefined ? 0 : Number(v));

export default function DesignForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [items, setItems] = useState([]);
  const [purities, setPurities] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [photoOpen, setPhotoOpen] = useState(false);
  const [stagedPhotos, setStagedPhotos] = useState([]);

  const { register, control, handleSubmit, reset, getValues, watch } = useForm({
    defaultValues: {
      design_no: "", variation_suffix: "", item: "", item_desc: "",
      pcs: 1, gw: 0, nw: 0, making: 0, making_type: "", kr_code: null,
      loss_rate: 0, making_rate: 0, design_details: [],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "design_details" });

  useEffect(() => {
    (async () => {
      const [it, pu, kr] = await Promise.all([
        fetchMainItem({ page_size: 10000 }),
        fetchPurity(),
        fetchKarigarIssues({ page_size: 1000 }),
      ]);
      if (it.success) setItems(it.data?.results ?? it.data ?? []);
      if (pu.success) setPurities(pu.data?.results ?? pu.data ?? []);
      if (kr.success) setKarigars(kr.data?.results ?? kr.data ?? []);

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
            loss_rate: d.loss_rate ?? 0, making_rate: d.making_rate ?? 0,
            design_details: (d.design_details ?? []).map((x) => ({
              sub_item: x.sub_item, metal_purity: x.metal_purity,
              pcs: x.pcs, ct: x.ct, rate: x.rate, amt: x.amt,
            })),
          });
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
      loss_rate: num(v.loss_rate), making_rate: num(v.making_rate),
      design_details: (v.design_details || []).map((d) => ({
        sub_item: d.sub_item,
        metal_purity: d.metal_purity,
        pcs: num(d.pcs), ct: num(d.ct), rate: num(d.rate), amt: num(d.amt),
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
              <Input type="number" step="0.001" {...register("gw")} />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-xs font-semibold text-muted-foreground">NET WT</Label>
              <Input type="number" step="0.001" {...register("nw")} />
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
              <Label className="text-xs font-semibold text-muted-foreground">LOSS RATE</Label>
              <Input type="number" step="0.01" {...register("loss_rate")} />
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

        {/* Components / details */}
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-muted-foreground">Components</h3>
            <Button type="button" variant="outline" size="sm" className="gap-2"
              onClick={() => append({ sub_item: "", metal_purity: "", pcs: 0, ct: 0, rate: 0, amt: 0 })}>
              <Plus className="size-4" /> Add row
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sub-item</TableHead>
                <TableHead>Purity</TableHead>
                <TableHead className="text-right">Pcs</TableHead>
                <TableHead className="text-right">Ct</TableHead>
                <TableHead className="text-right">Rate</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {fields.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-4 text-sm">No components. Add gold / stone lines as needed.</TableCell></TableRow>
              )}
              {fields.map((f, idx) => (
                <TableRow key={f.id}>
                  <TableCell className="min-w-48">
                    <Controller name={`design_details.${idx}.sub_item`} control={control} render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <SelectTrigger className="h-8"><SelectValue placeholder="Item" /></SelectTrigger>
                        <SelectContent>
                          {items.map((i) => (
                            <SelectItem key={i.short_code} value={i.short_code}>{i.item_name} ({i.short_code})</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )} />
                  </TableCell>
                  <TableCell className="min-w-28">
                    <Controller name={`design_details.${idx}.metal_purity`} control={control} render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value ? String(field.value) : ""}>
                        <SelectTrigger className="h-8"><SelectValue placeholder="Purity" /></SelectTrigger>
                        <SelectContent>
                          {purities.map((p) => (
                            <SelectItem key={p.id} value={String(p.id)}>{p.purity}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )} />
                  </TableCell>
                  <TableCell><Input type="number" className="h-8 text-right" {...register(`design_details.${idx}.pcs`)} /></TableCell>
                  <TableCell><Input type="number" step="0.001" className="h-8 text-right" {...register(`design_details.${idx}.ct`)} /></TableCell>
                  <TableCell><Input type="number" className="h-8 text-right" {...register(`design_details.${idx}.rate`)} /></TableCell>
                  <TableCell><Input type="number" className="h-8 text-right" {...register(`design_details.${idx}.amt`)} /></TableCell>
                  <TableCell>
                    <Button type="button" size="icon" variant="ghost" className="size-7 text-destructive" onClick={() => remove(idx)}>
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
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

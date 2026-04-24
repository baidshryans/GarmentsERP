import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import UnbarcodedPicker from "../shared/UnbarcodedPicker";
import {
  getLedgers,
  createSampleIssue,
  updateSampleIssue,
  fetchSampleIssueForEdit,
  fetchSampleIssueNextBillno,
} from "@/services/apiService";
import { default as Select } from "react-select";

const blankRow = {
  id: undefined,
  sl_no: 0,
  piece: null,
  piece_label: "",
  piece_gw: 0,
  piece_pcs: 0,
  piece_purity: "",
  piece_item_name: "",
  piece_design_code: "",
  instructions: "",
  due_date: "",
  remarks: "",
};

export default function SampleIssue() {
  const { id } = useParams();
  const { toast } = useToast();
  const navigate = useNavigate();

  const { register, handleSubmit, control, reset, watch, setValue } = useForm({
    defaultValues: {
      billno: "",
      date1: new Date().toISOString().split("T")[0],
      karigar_ldgr: null,
      remarks: "",
      items: [ { ...blankRow, sl_no: 1 } ],
    },
  });

  const { fields, append, remove, update } = useFieldArray({ control, name: "items" });
  const [karigars, setKarigars] = useState([]);
  const karigarId = watch("karigar_ldgr");

  useEffect(() => {
    (async () => {
      const res = await getLedgers("manufacturer");
      if (res.success) {
        setKarigars(res.data.map((k) => ({ value: k.id, label: k.ac_name })));
      }
    })();
  }, []);

  useEffect(() => {
    if (id) {
      (async () => {
        const res = await fetchSampleIssueForEdit(id);
        if (res.success) {
          reset({
            billno: res.data.billno,
            date1: res.data.date1,
            karigar_ldgr: res.data.karigar_ldgr,
            remarks: res.data.remarks || "",
            items: res.data.items.length ? res.data.items : [{ ...blankRow, sl_no: 1 }],
          });
        }
      })();
    } else {
      (async () => {
        const res = await fetchSampleIssueNextBillno({});
        if (res.success && res.data?.next_billno) {
          setValue("billno", res.data.next_billno);
        }
      })();
    }
  }, [id, reset, setValue]);

  const onSubmit = async (data) => {
    if (!data.karigar_ldgr) {
      toast({ title: "Karigar required", variant: "destructive" });
      return;
    }
    const payload = {
      billno: data.billno,
      date1: data.date1,
      karigar_ldgr: data.karigar_ldgr,
      remarks: data.remarks || "",
      items: data.items
        .filter((it) => it.piece)
        .map((it, idx) => ({
          id: it.id,
          sl_no: idx + 1,
          piece: it.piece,
          instructions: it.instructions || "",
          due_date: it.due_date || null,
          remarks: it.remarks || "",
        })),
    };
    if (payload.items.length === 0) {
      toast({ title: "Add at least one piece", variant: "destructive" });
      return;
    }
    const res = id ? await updateSampleIssue(id, payload) : await createSampleIssue(payload);
    if (res.success) {
      toast({ title: id ? "Updated" : "Created" });
      navigate("/manufacturing/sample-issue");
    } else {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="p-4 space-y-4">
      <h2 className="text-xl font-semibold">Sample Issue / Reissue</h2>

      <div className="grid grid-cols-4 gap-4">
        <div>
          <Label>Bill No</Label>
          <Input {...register("billno")} />
        </div>
        <div>
          <Label>Date</Label>
          <Input type="date" {...register("date1")} />
        </div>
        <div>
          <Label>Karigar</Label>
          <Controller
            control={control}
            name="karigar_ldgr"
            render={({ field }) => (
              <Select
                options={karigars}
                value={karigars.find((k) => k.value === field.value) || null}
                onChange={(opt) => field.onChange(opt?.value || null)}
              />
            )}
          />
        </div>
        <div>
          <Label>Remarks</Label>
          <Input {...register("remarks")} />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Sl</TableHead>
            <TableHead className="min-w-[280px]">Piece</TableHead>
            <TableHead>Item</TableHead>
            <TableHead>Purity</TableHead>
            <TableHead>Pcs</TableHead>
            <TableHead>GW</TableHead>
            <TableHead>Instructions</TableHead>
            <TableHead>Due</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fields.map((row, idx) => (
            <TableRow key={row.id || idx}>
              <TableCell>{idx + 1}</TableCell>
              <TableCell>
                <UnbarcodedPicker
                  karigarId={karigarId}
                  value={row.piece}
                  onChange={(opt) => {
                    update(idx, {
                      ...row,
                      piece: opt?.value || null,
                      piece_label: opt?.label || "",
                      piece_gw: opt?.gw || 0,
                      piece_pcs: opt?.pcs || 0,
                      piece_purity: opt?.purity || "",
                      piece_item_name: opt?.item || "",
                      piece_design_code: opt?.design_code || "",
                    });
                  }}
                />
              </TableCell>
              <TableCell>{row.piece_item_name}</TableCell>
              <TableCell>{row.piece_purity}</TableCell>
              <TableCell>{row.piece_pcs}</TableCell>
              <TableCell>{row.piece_gw}</TableCell>
              <TableCell>
                <Input {...register(`items.${idx}.instructions`)} />
              </TableCell>
              <TableCell>
                <Input type="date" {...register(`items.${idx}.due_date`)} />
              </TableCell>
              <TableCell>
                <Button type="button" variant="ghost" onClick={() => remove(idx)}>
                  <Trash2 size={16} />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex gap-2">
        <Button type="button" variant="secondary" onClick={() => append({ ...blankRow, sl_no: fields.length + 1 })}>
          + Add row
        </Button>
        <Button type="submit">{id ? "Update" : "Save"}</Button>
      </div>
    </form>
  );
}

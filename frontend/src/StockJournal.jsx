import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableRow, TableCell, TableHead, TableBody, TableHeader,
} from "@/components/ui/table";
import {
  fetchMainItem, fetchPurity, fetchPackets,
  fetchNextStockJournalNo, fetchStockJournalForEdit,
  updateStockJournalForEdit, createStockJournal,
} from "@/services/apiService";
import { Link, useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { Edit, Trash2, Save, X } from "lucide-react";

// ── Main Component ─────────────────────────────────────────────────────────────
const StockJournal = () => {
  const { toast }  = useToast();
  const { id }     = useParams();
  const navigate   = useNavigate();

  const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {
      form: {
        date1:    new Date().toISOString().split("T")[0],
        billno:  "",
        remarks: "",
      },
      table: {
        packet:       "",
        item:         "",
        metal_purity: "",
        doc_type:     "",
        pcs:          "",
        ct:           "",
        gw:           "",
        loss:         "",
      },
    },
  });

  const [rows,        setRows]        = useState([]);
  const [purityData,  setPurityData]  = useState([]);
  const [packets,     setPackets]     = useState([]);
  const [rawItems,    setRawItems]    = useState([]);   // type=R items
  const [packetActive, setPacketActive] = useState(false); // packet is selected → item locked
  const [itemActive,   setItemActive]   = useState(false); // item typed manually → packet locked

  useEffect(() => {

    async function fetchData() {
      const [packetsRes, purityRes, orderNoRes, itemsRes] = await Promise.all([
        fetchPackets(),
        fetchPurity(),
        fetchNextStockJournalNo(),
        fetchMainItem({ type: "R" }),
      ]);

      if (packetsRes.success) {
        const list = Array.isArray(packetsRes.data)
          ? packetsRes.data
          : (packetsRes.data?.results ?? []);
        setPackets(list);
      }
      if (purityRes.success)  setPurityData(purityRes.data);
      if (orderNoRes.success && !id) setValue("form.billno", orderNoRes.data.bill_no);
      if (itemsRes.success) {
        const list = Array.isArray(itemsRes.data)
          ? itemsRes.data
          : (itemsRes.data?.results ?? []);
        setRawItems(list);
      }
    }

    fetchData().then(() => {
      if (id) {
        fetchStockJournalForEdit(id)
          .then(res => {
            if (!res.success) return;
            const d = res.data;
            setValue("form.date1",    d.date1    || "");
            setValue("form.billno",  d.billno  || "");
            setValue("form.remarks", d.remarks || "");
            if (d.stockjournaldetail_set) setRows(d.stockjournaldetail_set);
          })
          .catch(err => console.error("Error fetching stock journal:", err));
      }
    });
  }, []);

  // ── Packet ↔ Item mutual lock ──────────────────────────────────────────────

  const tablePacket = watch("table.packet");
  const tableItem   = watch("table.item");

  // When packet field changes, auto-fill item and lock item input
  const handlePacketChange = (e) => {
    const val    = e.target.value.trim();
    const found  = packets.find(p => p.pckt_no === val);
    if (found) {
      const itemName = found.stone_item_id?.item_name ?? found.stone_item_id?.short_code ?? "";
      setValue("table.item", itemName);
      setValue("table.metal_purity", "");   // purity not applicable in packet mode
      setPacketActive(true);
      setItemActive(false);
    } else if (!val) {
      // Cleared — unlock everything
      setValue("table.item", "");
      setPacketActive(false);
      setItemActive(false);
    }
  };

  // When item field is manually typed (without a packet), lock packet input
  const handleItemChange = (e) => {
    const val = e.target.value.trim();
    if (val && !packetActive) {
      setValue("table.packet", "");  // packet not applicable in item mode
      setValue("table.pcs", "");     // stone pcs not applicable for type-R items
      setItemActive(true);
    } else if (!val) {
      setItemActive(false);
    }
  };

  // ── Row management ────────────────────────────────────────────────────────

  const handleAddRow = () => {
    const newItem = getValues("table");
    const hasData = Object.values(newItem).some(v => v !== "" && v !== null && v !== undefined);
    if (!hasData) return;

    // Clear fields that are hidden/not applicable for the current mode
    if (packetActive) {
      newItem.metal_purity = "";
    }
    if (itemActive) {
      newItem.packet = "";
      newItem.pcs    = "";
    }

    setRows(prev => [...prev, { ...newItem }]);
    setValue("table", {
      packet: "", item: "", metal_purity: "", doc_type: "",
      pcs: "", ct: "", gw: "", loss: "",
    });
    setPacketActive(false);
    setItemActive(false);
  };

  const handleEdit = (index) => {
    const row = rows[index];
    Object.keys(row).forEach(key => setValue(`table.${key}`, row[key]));
    // Restore lock state based on whether this row had a packet
    if (row.packet) {
      setPacketActive(true);
      setItemActive(false);
    } else if (row.item) {
      setItemActive(true);
      setPacketActive(false);
    }
    setRows(prev => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows(prev => prev.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      handleAddRow();
    }
  };

  // ── Submit ────────────────────────────────────────────────────────────────

  const onSubmit = () => {
    const Issue   = rows.filter(r => r.doc_type === "Issue").reduce(
      (a, c) => ({ pcs: a.pcs + +c.pcs, ct: a.ct + +c.ct, gw: a.gw + +c.gw }), { pcs: 0, ct: 0, gw: 0 }
    );
    const Receive = rows.filter(r => r.doc_type === "Receive").reduce(
      (a, c) => ({ pcs: a.pcs + +c.pcs, ct: a.ct + +c.ct, gw: a.gw + +c.gw }), { pcs: 0, ct: 0, gw: 0 }
    );

    if (Issue.pcs !== Receive.pcs || Issue.ct !== Receive.ct || Issue.gw !== Receive.gw) {
      toast({
        title: "Values don't match",
        description: "The sum of Pcs, CT, and GW must match between Issue and Receive rows.",
        variant: "destructive",
      });
      return;
    }

    const form = { ...getValues("form") };
    form.stockjournaldetail_set = [...rows];

    const op = id ? updateStockJournalForEdit(form, id) : createStockJournal(form);
    op.then(res => {
      if (res.success) {
        toast({ title: "Stock journal saved successfully!" });
        setTimeout(() => navigate("/inventory/stockjournal/"), 1500);
      } else {
        toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
      }
    }).catch(() => {
      toast({ title: "An error occurred. Please try again.", variant: "destructive" });
    });
  };

  // ── Summary totals ─────────────────────────────────────────────────────────

  const totals = ["Issue", "Receive"].reduce((acc, type) => {
    const filtered = rows.filter(r => r.doc_type === type);
    acc[type] = {
      pcs:  filtered.reduce((s, r) => s + Number(r.pcs  || 0), 0),
      ct:   filtered.reduce((s, r) => s + Number(r.ct   || 0), 0),
      gw:   filtered.reduce((s, r) => s + Number(r.gw   || 0), 0),
      loss: filtered.reduce((s, r) => s + Number(r.loss || 0), 0),
    };
    return acc;
  }, {});

  return (
    <>
      <div className="mt-4">
        <form
          className="p-6 shadow-lg rounded-xl bg-white border space-y-6"
          id="orderForm"
          onSubmit={handleSubmit(onSubmit)}
        >
          {/* ── Title ── */}
          <div className="text-center font-bold text-violet-900 text-lg tracking-wide">
            ADD / LESS STOCK JOURNAL
          </div>

          {/* ── Header Row: Date + Bill No ── */}
          <div className="grid grid-cols-2 gap-6">
            <FieldContainer>
              <Label className="text-nowrap">Date</Label>
              <Input type="date" {...register("form.date1")} required />
            </FieldContainer>
            <FieldContainer>
              <Label className="text-nowrap">Bill No</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="text"
                  {...register("form.billno")}
                  readOnly
                  className="bg-muted font-mono font-semibold cursor-not-allowed"
                />
                <span className="text-xs whitespace-nowrap text-violet-700 border border-violet-200 rounded px-1.5 py-0.5">
                  Auto
                </span>
              </div>
            </FieldContainer>
          </div>

          {/* ── Table ── */}
          <div className="overflow-x-auto rounded-lg border">
            <Table className="w-full border-collapse text-sm">
              <TableHeader>
                <TableRow className="bg-violet-50">
                  <TableHead className="px-2 py-2 border text-center w-20">Actions</TableHead>
                  <TableHead className="px-3 py-2 border text-center">Packet</TableHead>
                  <TableHead className="px-3 py-2 border text-center">Item</TableHead>
                  <TableHead className="px-3 py-2 border text-center">Metal Purity</TableHead>
                  <TableHead className="px-3 py-2 border text-center">Doc Type</TableHead>
                  <TableHead className="px-3 py-2 border text-center">Stone Pcs</TableHead>
                  <TableHead className="px-3 py-2 border text-center">CT</TableHead>
                  <TableHead className="px-3 py-2 border text-center">GW</TableHead>
                  <TableHead className="px-3 py-2 border text-center">Loss</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* ── Input Row ── */}
                <TableRow className="bg-blue-50/40">
                  <TableCell className="px-2 py-1.5 border" />

                  {/* Packet — hidden when item (type R) is active */}
                  <TableCell className="px-2 py-1.5 border min-w-[120px]">
                    {itemActive ? (
                      <span className="text-xs text-muted-foreground italic px-1">N/A (item mode)</span>
                    ) : (
                      <>
                        <Input
                          list="packet_list"
                          {...register("table.packet", { onChange: handlePacketChange })}
                          placeholder="Packet…"
                        />
                        <datalist id="packet_list">
                          {packets.map((p, i) => (
                            <option key={i} value={p.pckt_no}>{p.pckt_no}</option>
                          ))}
                        </datalist>
                      </>
                    )}
                  </TableCell>

                  {/* Item */}
                  <TableCell className="px-2 py-1.5 border min-w-[120px]">
                    <Input
                      list="item_list"
                      {...register("table.item", { onChange: handleItemChange })}
                      disabled={packetActive}
                      placeholder={packetActive ? "(auto-filled)" : "Item…"}
                      className={packetActive ? "opacity-50 cursor-not-allowed" : ""}
                    />
                    {!packetActive && (
                      <datalist id="item_list">
                        {rawItems.map((item, i) => (
                          <option key={i} value={item.item_name} />
                        ))}
                      </datalist>
                    )}
                  </TableCell>

                  {/* Metal Purity — hidden when packet is active */}
                  <TableCell className="px-2 py-1.5 border min-w-[130px]">
                    {packetActive ? (
                      <span className="text-xs text-muted-foreground italic px-1">N/A (packet mode)</span>
                    ) : (
                      <Controller
                        name="table.metal_purity"
                        control={control}
                        render={({ field }) => (
                          <Select onValueChange={field.onChange} value={field.value}>
                            <SelectTrigger>
                              <SelectValue placeholder="Purity" />
                            </SelectTrigger>
                            <SelectContent>
                              {purityData.map((p, i) => (
                                <SelectItem key={i} value={p.purity}>{p.purity}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    )}
                  </TableCell>

                  {/* Doc Type */}
                  <TableCell className="px-2 py-1.5 border min-w-[120px]">
                    <Controller
                      name="table.doc_type"
                      control={control}
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value}>
                          <SelectTrigger>
                            <SelectValue placeholder="Type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Issue">Issue</SelectItem>
                            <SelectItem value="Receive">Receive</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </TableCell>

                  {/* Stone Pcs — hidden when item (type R) is active */}
                  <TableCell className="px-2 py-1.5 border w-24">
                    {itemActive ? (
                      <span className="text-xs text-muted-foreground italic px-1">N/A</span>
                    ) : (
                      <Input type="number" min="0" {...register("table.pcs")} placeholder="0" />
                    )}
                  </TableCell>

                  {/* CT */}
                  <TableCell className="px-2 py-1.5 border w-24">
                    <Input type="number" step="0.001" min="0" {...register("table.ct")} placeholder="0.000" />
                  </TableCell>

                  {/* GW */}
                  <TableCell className="px-2 py-1.5 border w-24">
                    <Input
                      type="number"
                      step="0.001"
                      min="0"
                      {...register("table.gw")}
                      placeholder="0.000"
                    />
                  </TableCell>

                  {/* Loss */}
                  <TableCell className="px-2 py-1.5 border w-24">
                    <Input
                      type="number"
                      step="0.001"
                      min="0"
                      {...register("table.loss")}
                      placeholder="0.000"
                      onKeyDown={handleKeyDown}
                    />
                  </TableCell>
                </TableRow>

                {/* ── Add Row trigger row ── */}
                <TableRow>
                  <TableCell colSpan={9} className="border px-3 py-1.5">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="text-violet-700 hover:text-violet-900 hover:bg-violet-50 text-xs h-7 gap-1"
                      onClick={handleAddRow}
                    >
                      + Add Row
                    </Button>
                  </TableCell>
                </TableRow>

                {/* ── Data Rows ── */}
                {rows.map((item, index) => (
                  <TableRow
                    key={index}
                    className={item.doc_type === "Issue" ? "bg-red-50/40" : "bg-green-50/40"}
                  >
                    <TableCell className="px-2 py-1.5 border">
                      <div className="flex justify-center items-center gap-1.5">
                        <Edit
                          size={15}
                          className="cursor-pointer text-violet-600 hover:text-violet-800"
                          onClick={() => handleEdit(index)}
                        />
                        <Trash2
                          size={15}
                          className="cursor-pointer text-red-500 hover:text-red-700"
                          onClick={() => handleDelete(index)}
                        />
                      </div>
                    </TableCell>
                    <TableCell className="px-3 py-1.5 border text-center font-mono text-xs">{item.packet || "—"}</TableCell>
                    <TableCell className="px-3 py-1.5 border text-center font-mono text-xs">{item.item || "—"}</TableCell>
                    <TableCell className="px-3 py-1.5 border text-center text-xs">{item.metal_purity || "—"}</TableCell>
                    <TableCell className="px-3 py-1.5 border text-center">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                        item.doc_type === "Issue"
                          ? "bg-red-100 text-red-700"
                          : "bg-green-100 text-green-700"
                      }`}>
                        {item.doc_type}
                      </span>
                    </TableCell>
                    <TableCell className="px-3 py-1.5 border text-center tabular-nums">{item.pcs || "—"}</TableCell>
                    <TableCell className="px-3 py-1.5 border text-center tabular-nums">{item.ct  || "—"}</TableCell>
                    <TableCell className="px-3 py-1.5 border text-center tabular-nums font-semibold">{item.gw   || "—"}</TableCell>
                    <TableCell className="px-3 py-1.5 border text-center tabular-nums text-orange-600">{item.loss || "—"}</TableCell>
                  </TableRow>
                ))}

                {/* ── Summary totals ── */}
                {rows.length > 0 && ["Issue", "Receive"].map(type => (
                  totals[type]?.pcs > 0 || totals[type]?.gw > 0 ? (
                    <TableRow key={type} className="bg-muted/40 font-semibold text-xs">
                      <TableCell className="border px-2" />
                      <TableCell colSpan={4} className="border px-3 py-1.5 text-right text-muted-foreground uppercase tracking-wide">
                        {type} Total
                      </TableCell>
                      <TableCell className="border px-3 py-1.5 text-center tabular-nums">{totals[type].pcs}</TableCell>
                      <TableCell className="border px-3 py-1.5 text-center tabular-nums">{totals[type].ct.toFixed(3)}</TableCell>
                      <TableCell className="border px-3 py-1.5 text-center tabular-nums">{totals[type].gw.toFixed(3)}</TableCell>
                      <TableCell className="border px-3 py-1.5 text-center tabular-nums text-orange-600">{totals[type].loss.toFixed(3)}</TableCell>
                    </TableRow>
                  ) : null
                ))}
              </TableBody>
            </Table>
          </div>

          {/* ── Remarks (below table) ── */}
          <FieldContainer>
            <Label className="text-nowrap">Remarks</Label>
            <Input
              type="text"
              {...register("form.remarks")}
              placeholder="Enter any remarks or narration…"
              className="max-w-xl"
            />
          </FieldContainer>

          {/* ── Action Buttons ── */}
          <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
            <Button type="button" variant="outline" onClick={() => window.history.back()} className="gap-2">
              <X className="w-4 h-4" /> Cancel
            </Button>
            <Button type="submit" className="gap-2 bg-violet-700 hover:bg-violet-800 text-white">
              <Save className="w-4 h-4" /> Save
            </Button>
          </div>
        </form>
      </div>
    </>
  );
};

export default StockJournal;

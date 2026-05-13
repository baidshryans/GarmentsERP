import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableRow, TableCell, TableHead, TableBody, TableHeader } from "@/components/ui/table";
import { fetchSubcontractorLedger, getLedgers } from "@/services/apiService";
import Select from "react-select";

/**
 * Subcontractor Ledger � three stacked accounts for a karigar:
 *   1. Finished / Semi-finished account  (pieces out vs receive in, weight-based)
 *   2. Raw Gold account                   (gold issued vs incremental returned, pure-wt)
 *   3. Labour summary                     (making charges per receive)
 */
export default function SubcontractorLedger() {
  const [karigars, setKarigars] = useState([]);
  const [karigar, setKarigar] = useState(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      const res = await getLedgers("manufacturer");
      if (res.success) setKarigars(res.data.map((k) => ({ value: k.id, label: k.ac_name })));
    })();
  }, []);

  const run = async () => {
    if (!karigar) return;
    setLoading(true);
    const res = await fetchSubcontractorLedger({ karigar, start, end });
    setLoading(false);
    if (res.success) setData(res.data);
  };

  const fa = data?.finished_account;
  const rg = data?.raw_gold_account;
  const lab = data?.labour_summary;

  return (
    <div className="p-4 space-y-6 print:p-2">
      <div className="flex gap-3 items-end print:hidden">
        <div className="min-w-[260px]">
          <Label>Karigar</Label>
          <Select
            options={karigars}
            value={karigars.find((k) => k.value === karigar) || null}
            onChange={(opt) => setKarigar(opt?.value || null)}
          />
        </div>
        <div>
          <Label>From</Label>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div>
          <Label>To</Label>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        <Button onClick={run} disabled={!karigar || loading}>{loading ? "Loading�" : "Run"}</Button>
        <Button variant="secondary" onClick={() => window.print()}>Print</Button>
      </div>

      {data && (
        <>
          <section>
            <h3 className="font-semibold text-lg mb-2">Finished / Semi-finished Account (weight)</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Slip</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>Pcs</TableHead>
                  <TableHead className="text-right">In (g)</TableHead>
                  <TableHead className="text-right">Out (g)</TableHead>
                  <TableHead>Ref</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow className="font-medium bg-muted/50">
                  <TableCell colSpan={4}>Opening</TableCell>
                  <TableCell>{fa.opening.pcs}</TableCell>
                  <TableCell className="text-right">{fa.opening.gw.toFixed(3)}</TableCell>
                  <TableCell />
                  <TableCell />
                </TableRow>
                {fa.rows.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.date}</TableCell>
                    <TableCell>{r.slip}</TableCell>
                    <TableCell>{r.kind}</TableCell>
                    <TableCell>{r.item}</TableCell>
                    <TableCell>{r.pcs}</TableCell>
                    <TableCell className="text-right">{r.in_gw.toFixed(3)}</TableCell>
                    <TableCell className="text-right">{r.out_gw.toFixed(3)}</TableCell>
                    <TableCell>{r.ref}</TableCell>
                  </TableRow>
                ))}
                <TableRow className="font-semibold">
                  <TableCell colSpan={5}>Totals</TableCell>
                  <TableCell className="text-right">{fa.totals.in_gw.toFixed(3)}</TableCell>
                  <TableCell className="text-right">{fa.totals.out_gw.toFixed(3)}</TableCell>
                  <TableCell>Closing: {fa.totals.closing_gw.toFixed(3)}g</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </section>

          <section>
            <h3 className="font-semibold text-lg mb-2">Raw Gold Account (pure weight)</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Slip</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>Purity</TableHead>
                  <TableHead className="text-right">Issued (g)</TableHead>
                  <TableHead className="text-right">Conv wt</TableHead>
                  <TableHead className="text-right">Received pure (g)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow className="font-medium bg-muted/50">
                  <TableCell colSpan={7}>Opening</TableCell>
                  <TableCell className="text-right">{rg.opening.gw_pure.toFixed(3)}</TableCell>
                </TableRow>
                {rg.rows.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.date}</TableCell>
                    <TableCell>{r.slip}</TableCell>
                    <TableCell>{r.kind}</TableCell>
                    <TableCell>{r.item}</TableCell>
                    <TableCell>{r.metal_purity}</TableCell>
                    <TableCell className="text-right">{r.issued_gw.toFixed(3)}</TableCell>
                    <TableCell className="text-right">{r.conv_wt.toFixed(3)}</TableCell>
                    <TableCell className="text-right">{r.received_gw.toFixed(3)}</TableCell>
                  </TableRow>
                ))}
                <TableRow className="font-semibold">
                  <TableCell colSpan={5}>Totals</TableCell>
                  <TableCell className="text-right">{rg.totals.issued_pure.toFixed(3)}</TableCell>
                  <TableCell className="text-right">{rg.totals.received_pure.toFixed(3)}</TableCell>
                  <TableCell className="text-right">Closing: {rg.totals.closing_pure.toFixed(3)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </section>

          <section>
            <h3 className="font-semibold text-lg mb-2">Labour Summary</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Receive Slip</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Incr. GW (g)</TableHead>
                  <TableHead className="text-right">Rate</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Auto?</TableHead>
                  <TableHead className="text-right">Loss (g)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lab.rows.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.receive_slip}</TableCell>
                    <TableCell>{r.date}</TableCell>
                    <TableCell className="text-right">{r.incremental_gw.toFixed(3)}</TableCell>
                    <TableCell className="text-right">{r.making_rate.toFixed(2)}</TableCell>
                    <TableCell className="text-right">{r.making_amount}</TableCell>
                    <TableCell>{r.auto ? "✓" : ""}</TableCell>
                    <TableCell className="text-right">{r.loss_gw.toFixed(3)}</TableCell>
                  </TableRow>
                ))}
                <TableRow className="font-semibold">
                  <TableCell colSpan={4}>Total Making</TableCell>
                  <TableCell className="text-right">{lab.totals.making_amount}</TableCell>
                  <TableCell colSpan={2} />
                </TableRow>
              </TableBody>
            </Table>
          </section>
        </>
      )}
    </div>
  );
}

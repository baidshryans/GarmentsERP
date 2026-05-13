import React, { useState, useEffect, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { DataTable } from '@/table';
import { fetchRfidTagList, assignRfidTag } from '@/services/apiService';

/**
 * RfidTagAssign � Link RFID EPC tags to barcode items.
 *
 * Workflow:
 *  1. Search for a barcode by barcode number or item name.
 *  2. Select a row in the table.
 *  3. Type (or scan) the RFID tag EPC into the Tag field.
 *  4. Click Assign. To unlink, clear the tag field and click Assign.
 */
export default function RfidTagAssign() {
  const [search, setSearch] = useState('');
  const [assignedFilter, setAssignedFilter] = useState('');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null); // barcode row
  const [tagInput, setTagInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null); // { type: 'success'|'error', text }
  const tagRef = useRef(null);

  const load = async () => {
    setLoading(true);
    setMessage(null);
    const res = await fetchRfidTagList({ search, assigned: assignedFilter });
    if (res.success) setRows(res.data.results);
    setLoading(false);
  };

  useEffect(() => { load(); }, [search, assignedFilter]);

  const handleSelect = (row) => {
    setSelected(row);
    setTagInput(row.rfid_tag || '');
    setMessage(null);
    setTimeout(() => tagRef.current?.focus(), 50);
  };

  const handleAssign = async () => {
    if (!selected) return;
    setSaving(true);
    setMessage(null);
    const res = await assignRfidTag(selected.barcode, tagInput.trim());
    if (res.success) {
      setMessage({ type: 'success', text: tagInput.trim() ? `Tag assigned to ${selected.barcode}` : `Tag cleared from ${selected.barcode}` });
      setSelected(null);
      setTagInput('');
      load();
    } else {
      const detail = res.error?.rfid_tag?.[0] || res.error?.barcode?.[0] || JSON.stringify(res.error);
      setMessage({ type: 'error', text: detail });
    }
    setSaving(false);
  };

  const columns = [
    { header: 'Barcode', accessorKey: 'barcode' },
    { header: 'Item', accessorKey: 'item' },
    { header: 'Purity', accessorKey: 'purity' },
    { header: 'GW (g)', accessorKey: 'gw' },
    {
      header: 'RFID Tag',
      accessorKey: 'rfid_tag',
      cell: ({ getValue }) => getValue() ? (
        <span className="font-mono text-xs text-green-700">{getValue()}</span>
      ) : (
        <span className="text-muted-foreground text-xs">�</span>
      ),
    },
  ];

  return (
    <div className="p-4 space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <Input
          placeholder="Search barcode or item..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={assignedFilter}
          onChange={(e) => setAssignedFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All items</option>
          <option value="true">Tagged only</option>
          <option value="false">Untagged only</option>
        </select>
        <Button variant="outline" onClick={load} disabled={loading}>Refresh</Button>
      </div>

      {/* Assignment panel */}
      {selected && (
        <div className="border rounded p-4 bg-muted/30 flex flex-wrap gap-4 items-end">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Selected barcode</p>
            <p className="font-mono font-semibold">{selected.barcode}</p>
            <p className="text-sm text-muted-foreground">{selected.item} � {selected.purity}</p>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-muted-foreground block mb-1">RFID Tag (EPC) � scan or type</label>
            <Input
              ref={tagRef}
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAssign()}
              placeholder="e.g. E28011700000020FA2B45678"
              className="font-mono"
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={handleAssign} disabled={saving}>
              {saving ? 'Saving...' : tagInput.trim() ? 'Assign Tag' : 'Clear Tag'}
            </Button>
            <Button variant="outline" onClick={() => { setSelected(null); setTagInput(''); }}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Status message */}
      {message && (
        <p className={`text-sm font-medium ${message.type === 'success' ? 'text-green-700' : 'text-red-600'}`}>
          {message.text}
        </p>
      )}

      {/* Table */}
      {loading ? (
        [...Array(5)].map((_, i) => <Skeleton key={i} className="w-full h-8 mb-2" />)
      ) : (
        <div className="cursor-pointer">
          <p className="text-xs text-muted-foreground mb-2">Click a row to assign/update its RFID tag.</p>
          <DataTable
            columns={columns}
            data={rows}
            onRowClick={handleSelect}
          />
          {rows.length === 0 && <p className="text-center text-muted-foreground py-6">No items found.</p>}
        </div>
      )}
    </div>
  );
}

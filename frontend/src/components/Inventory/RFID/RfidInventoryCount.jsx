import React, { useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { submitRfidCount } from '@/services/apiService';

/**
 * RfidInventoryCount — RFID bulk inventory count session.
 *
 * Workflow:
 *  1. Paste tag IDs from your RFID reader software (one per line or comma-separated),
 *     OR connect a USB HID RFID reader that types tag IDs followed by Enter.
 *  2. Click "Run Count" — the system compares scanned tags against current stock.
 *  3. Review Matched / Missing / Unexpected tabs.
 *  4. Optionally save the session for audit trail.
 */
export default function RfidInventoryCount() {
  const [tagText, setTagText] = useState('');
  const [liveTag, setLiveTag] = useState('');
  const [note, setNote] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('matched');
  const [saved, setSaved] = useState(false);

  // Parse tags from the textarea (one per line or comma-separated)
  const parseTags = (text) => {
    return [...new Set(
      text.split(/[\n,]+/).map(t => t.trim()).filter(Boolean)
    )];
  };

  // Handle live USB HID reader: each scan types the EPC + Enter
  const handleLiveInput = (e) => {
    if (e.key === 'Enter' && liveTag.trim()) {
      setTagText(prev => prev ? prev + '\n' + liveTag.trim() : liveTag.trim());
      setLiveTag('');
    }
  };

  const handleCount = async (saveSession = false) => {
    const tags = parseTags(tagText);
    if (tags.length === 0) {
      setError('No tags entered. Paste tag IDs or scan with a USB reader.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    const res = await submitRfidCount({ tags, save_session: saveSession, note });
    if (res.success) {
      setResult(res.data);
      setSaved(saveSession && !!res.data.session_id);
    } else {
      setError(typeof res.error === 'string' ? res.error : JSON.stringify(res.error));
    }
    setLoading(false);
  };

  const tabs = result ? [
    { key: 'matched', label: `Matched (${result.matched_count})`, color: 'text-green-700' },
    { key: 'missing', label: `Missing (${result.missing_count})`, color: 'text-orange-600' },
    { key: 'unexpected', label: `Unexpected (${result.unexpected_count})`, color: 'text-red-600' },
  ] : [];

  const tableData = result ? result[activeTab] : [];

  return (
    <div className="p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Live reader input */}
        <div>
          <label className="text-xs text-muted-foreground block mb-1">
            USB HID Reader — focus here and scan tags one by one
          </label>
          <Input
            value={liveTag}
            onChange={(e) => setLiveTag(e.target.value)}
            onKeyDown={handleLiveInput}
            placeholder="Scan tag here (reads EPC + Enter)..."
            className="font-mono"
            autoComplete="off"
          />
        </div>

        {/* Session note */}
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Session note (optional)</label>
          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Counter check after closing"
          />
        </div>
      </div>

      {/* Bulk paste area */}
      <div>
        <label className="text-xs text-muted-foreground block mb-1">
          Tag list — paste from reader software (one per line or comma-separated)
        </label>
        <Textarea
          value={tagText}
          onChange={(e) => setTagText(e.target.value)}
          placeholder={"E28011700000020FA2B45678\nE28011700000020FA2B45679\n..."}
          rows={6}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground mt-1">
          {parseTags(tagText).length} unique tag(s) ready
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <Button onClick={() => handleCount(false)} disabled={loading}>
          {loading ? 'Running...' : 'Run Count'}
        </Button>
        <Button
          variant="outline"
          onClick={() => handleCount(true)}
          disabled={loading || saved}
        >
          {saved ? 'Session Saved' : 'Run & Save Session'}
        </Button>
        {result && (
          <Button variant="ghost" onClick={() => { setResult(null); setTagText(''); setSaved(false); }}>
            Clear
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Results */}
      {result && (
        <div className="border rounded-lg overflow-hidden">
          {/* Summary bar */}
          <div className="bg-muted px-4 py-2 flex flex-wrap gap-6 text-sm">
            <span>Total scanned: <strong>{result.total_scanned}</strong></span>
            <span className="text-green-700">Matched: <strong>{result.matched_count}</strong></span>
            <span className="text-orange-600">Missing: <strong>{result.missing_count}</strong></span>
            <span className="text-red-600">Unexpected: <strong>{result.unexpected_count}</strong></span>
            {result.session_no && (
              <span className="text-muted-foreground">Session: <strong>{result.session_no}</strong></span>
            )}
          </div>

          {/* Tabs */}
          <div className="flex border-b">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === t.key
                    ? `border-primary ${t.color}`
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            {tableData.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No items in this category.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left px-3 py-2">RFID Tag</th>
                    {activeTab !== 'unexpected' && (
                      <>
                        <th className="text-left px-3 py-2">Barcode</th>
                        <th className="text-left px-3 py-2">Item</th>
                        <th className="text-left px-3 py-2">Purity</th>
                        <th className="text-right px-3 py-2">GW (g)</th>
                      </>
                    )}
                    {activeTab === 'matched' && (
                      <th className="text-left px-3 py-2">Stock Status</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((row, i) => (
                    <tr key={i} className="border-t hover:bg-muted/30">
                      <td className="px-3 py-2 font-mono text-xs">{row.rfid_tag}</td>
                      {activeTab !== 'unexpected' && (
                        <>
                          <td className="px-3 py-2 font-mono">{row.barcode}</td>
                          <td className="px-3 py-2">{row.item || '—'}</td>
                          <td className="px-3 py-2">{row.purity || '—'}</td>
                          <td className="px-3 py-2 text-right">{row.gw?.toFixed(3)}</td>
                        </>
                      )}
                      {activeTab === 'matched' && (
                        <td className="px-3 py-2">
                          <span className={`text-xs font-medium ${row.stk_status ? 'text-green-700' : 'text-red-600'}`}>
                            {row.stk_status ? 'In Stock' : 'Sold/Out'}
                          </span>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

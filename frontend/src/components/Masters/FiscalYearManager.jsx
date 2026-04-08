import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { useF4Submit } from '@/hooks/useF4Submit';
import {
  getFiscalYears,
  createFiscalYear,
  setActiveFiscalYear,
  closeFiscalYear,
  reopenFiscalYear,
} from '@/services/apiService';
import {
  CalendarDays,
  Check,
  Lock,
  Unlock,
  Plus,
  Star,
} from 'lucide-react';

function FiscalYearManager() {
  const { toast } = useToast();
  const [fiscalYears, setFiscalYears] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ fy_code: '', fy_start: '', fy_end: '' });
  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    const result = await getFiscalYears();
    if (result.success) {
      setFiscalYears(result.data);
    } else {
      toast({ title: 'Error', description: 'Failed to load fiscal years', variant: 'destructive' });
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  // Auto-fill dates when fy_code changes (e.g., "25-26" → Apr 2025 – Mar 2026)
  const handleFyCodeChange = (value) => {
    setFormData(prev => ({ ...prev, fy_code: value }));
    const match = value.match(/^(\d{2})-(\d{2})$/);
    if (match) {
      const startYear = 2000 + parseInt(match[1]);
      const endYear = 2000 + parseInt(match[2]);
      setFormData(prev => ({
        ...prev,
        fy_code: value,
        fy_start: `${startYear}-04-01`,
        fy_end: `${endYear}-03-31`,
      }));
    }
  };

  const handleCreate = async () => {
    if (!formData.fy_code || !formData.fy_start || !formData.fy_end) {
      toast({ title: 'Validation', description: 'All fields are required', variant: 'destructive' });
      return;
    }
    setSubmitting(true);
    const result = await createFiscalYear(formData);
    if (result.success) {
      toast({ title: 'Success', description: `Fiscal year ${formData.fy_code} created` });
      setShowForm(false);
      setFormData({ fy_code: '', fy_start: '', fy_end: '' });
      fetchData();
    } else {
      toast({ title: 'Error', description: JSON.stringify(result.error), variant: 'destructive' });
    }
    setSubmitting(false);
  };

  useF4Submit(handleCreate);

  const handleSetActive = async (id, fyCode) => {
    const result = await setActiveFiscalYear(id);
    if (result.success) {
      toast({ title: 'Success', description: `FY ${fyCode} is now active` });
      fetchData();
    } else {
      toast({ title: 'Error', description: JSON.stringify(result.error), variant: 'destructive' });
    }
  };

  const handleClose = async (id, fyCode) => {
    if (!window.confirm(`Are you sure you want to close FY ${fyCode}? Only journal entries will be allowed after closing.`)) return;
    const result = await closeFiscalYear(id);
    if (result.success) {
      toast({ title: 'Success', description: `FY ${fyCode} has been closed` });
      fetchData();
    } else {
      toast({ title: 'Error', description: JSON.stringify(result.error), variant: 'destructive' });
    }
  };

  const handleReopen = async (id, fyCode) => {
    if (!window.confirm(`Reopen FY ${fyCode}? This will allow all types of transactions again.`)) return;
    const result = await reopenFiscalYear(id);
    if (result.success) {
      toast({ title: 'Success', description: `FY ${fyCode} has been reopened` });
      fetchData();
    } else {
      toast({ title: 'Error', description: JSON.stringify(result.error), variant: 'destructive' });
    }
  };

  // Suggest next FY code
  const suggestNextFyCode = () => {
    const now = new Date();
    const startYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
    const code = `${String(startYear).slice(-2)}-${String(startYear + 1).slice(-2)}`;
    // Check if this FY already exists
    if (fiscalYears.some(fy => fy.fy_code === code)) {
      const nextYear = startYear + 1;
      return `${String(nextYear).slice(-2)}-${String(nextYear + 1).slice(-2)}`;
    }
    return code;
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Fiscal Years</h1>
          <p className="text-sm text-gray-400 mt-1">
            Manage accounting periods. Bill numbers reset for each fiscal year.
          </p>
        </div>
        <Button
          onClick={() => {
            const code = suggestNextFyCode();
            handleFyCodeChange(code);
            setShowForm(true);
          }}
          className="gap-1.5 bg-primary hover:bg-primary"
        >
          <Plus className="w-4 h-4" /> New Fiscal Year
        </Button>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="rounded-xl border border-violet-100 bg-violet-50 p-6 mb-6 space-y-4">
          <p className="text-sm font-semibold text-primary uppercase tracking-widest">Create Fiscal Year</p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label className="text-xs text-gray-500">FY Code (e.g., 25-26)</Label>
              <Input
                value={formData.fy_code}
                onChange={(e) => handleFyCodeChange(e.target.value)}
                placeholder="25-26"
                maxLength={5}
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs text-gray-500">Start Date</Label>
              <Input
                type="date"
                value={formData.fy_start}
                onChange={(e) => setFormData(prev => ({ ...prev, fy_start: e.target.value }))}
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs text-gray-500">End Date</Label>
              <Input
                type="date"
                value={formData.fy_end}
                onChange={(e) => setFormData(prev => ({ ...prev, fy_end: e.target.value }))}
                className="mt-1"
              />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={handleCreate} disabled={submitting} className="bg-primary hover:bg-primary">
              {submitting ? 'Creating...' : 'Create'}
            </Button>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Fiscal Year List */}
      {loading ? (
        <div className="text-sm text-gray-400">Loading...</div>
      ) : fiscalYears.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <CalendarDays className="w-10 h-10 mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No fiscal years created yet.</p>
          <p className="text-xs mt-1">Click "New Fiscal Year" to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {fiscalYears.map((fy) => (
            <div
              key={fy.id}
              className={`flex items-center justify-between rounded-xl border p-5 transition-colors ${
                fy.is_active
                  ? 'border-violet-300 bg-violet-50 shadow-sm'
                  : fy.is_closed
                  ? 'border-gray-200 bg-gray-50'
                  : 'border-gray-200 bg-white hover:border-violet-200'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`flex items-center justify-center w-12 h-12 rounded-full font-bold text-lg ${
                  fy.is_active
                    ? 'bg-primary text-white'
                    : fy.is_closed
                    ? 'bg-gray-300 text-gray-600'
                    : 'bg-violet-100 text-primary'
                }`}>
                  {fy.fy_code}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900">FY {fy.fy_code}</span>
                    {fy.is_active && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-200 text-primary uppercase tracking-wider">
                        Active
                      </span>
                    )}
                    {fy.is_closed && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 uppercase tracking-wider">
                        Closed
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(fy.fy_start).toLocaleDateString('en-GB')} — {new Date(fy.fy_end).toLocaleDateString('en-GB')}
                    {fy.closed_at && (
                      <span className="ml-2 text-red-400">
                        (Closed on {new Date(fy.closed_at).toLocaleDateString('en-GB')})
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {!fy.is_active && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleSetActive(fy.id, fy.fy_code)}
                    className="gap-1 text-primary border-violet-300 hover:bg-violet-50"
                  >
                    <Star className="w-3.5 h-3.5" /> Set Active
                  </Button>
                )}
                {!fy.is_closed ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleClose(fy.id, fy.fy_code)}
                    className="gap-1 text-red-600 border-red-200 hover:bg-red-50"
                  >
                    <Lock className="w-3.5 h-3.5" /> Close
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleReopen(fy.id, fy.fy_code)}
                    className="gap-1 text-green-600 border-green-200 hover:bg-green-50"
                  >
                    <Unlock className="w-3.5 h-3.5" /> Reopen
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default FiscalYearManager;

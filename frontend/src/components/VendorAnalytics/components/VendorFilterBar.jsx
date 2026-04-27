import React, { useState, useEffect } from 'react';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { getLedgers, fetchPurity, fetchRetails } from '@/services/apiService';

const ITEM_TYPE_OPTIONS = [
  { value: '__all__', label: 'All' },
  { value: 'M', label: 'Making' },
  { value: 'R', label: 'Raw' },
  { value: 'S', label: 'Studded' },
  { value: 'O', label: 'Other' },
  { value: 'C', label: 'Casting' },
];

/** Returns YYYY-MM-DD string for the start of the current Indian fiscal year (April 1). */
function fyStartDate() {
  const today = new Date();
  const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
  return `${year}-04-01`;
}

/** Returns YYYY-MM-DD string for today. */
function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

export default function VendorFilterBar({ onApply, loading = false }) {
  const [filters, setFilters] = useState({
    vendor_id: '',
    from_date: fyStartDate(),
    to_date: todayDate(),
    item_type: '',
    purity_id: '',
    design_code: '',
    retail_id: '',
  });

  const [vendors, setVendors] = useState([]);
  const [purities, setPurities] = useState([]);
  const [retails, setRetails] = useState([]);

  useEffect(() => {
    getLedgers({ type: 'VD', page_size: 200 }).then((res) => {
      if (res?.success && res?.data?.results) {
        setVendors(res.data.results);
      }
    });

    fetchPurity().then((res) => {
      if (res?.success) setPurities(res.data?.results ?? res.data ?? []);
    });

    fetchRetails().then((res) => {
      if (res?.success) {
        const data = res.data;
        setRetails(Array.isArray(data) ? data : (data?.results ?? []));
      }
    });
  }, []);

  const handleChange = (field, value) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleApply = () => {
    if (!filters.vendor_id) {
      alert('Please select a vendor');
      return;
    }
    const clean = Object.fromEntries(
      Object.entries(filters).map(([k, v]) => [k, v === '__all__' ? '' : v])
    );
    onApply(clean);
  };

  return (
    <div className="flex flex-wrap gap-3 items-end p-4 bg-white border rounded-lg shadow-sm">
      {/* Vendor */}
      <div className="flex flex-col gap-1">
        <Label>Vendor</Label>
        <Select
          value={filters.vendor_id}
          onValueChange={(val) => handleChange('vendor_id', val)}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Select vendor…" />
          </SelectTrigger>
          <SelectContent>
            {vendors.map((v) => (
              <SelectItem key={v.id} value={String(v.id)}>
                {v.ac_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* From Date */}
      <div className="flex flex-col gap-1">
        <Label>From Date</Label>
        <Input
          type="date"
          className="w-36"
          value={filters.from_date}
          onChange={(e) => handleChange('from_date', e.target.value)}
        />
      </div>

      {/* To Date */}
      <div className="flex flex-col gap-1">
        <Label>To Date</Label>
        <Input
          type="date"
          className="w-36"
          value={filters.to_date}
          onChange={(e) => handleChange('to_date', e.target.value)}
        />
      </div>

      {/* Item Type */}
      <div className="flex flex-col gap-1">
        <Label>Item Type</Label>
        <Select
          value={filters.item_type || '__all__'}
          onValueChange={(val) => handleChange('item_type', val)}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            {ITEM_TYPE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Purity */}
      <div className="flex flex-col gap-1">
        <Label>Purity</Label>
        <Select
          value={filters.purity_id || '__all__'}
          onValueChange={(val) => handleChange('purity_id', val)}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All</SelectItem>
            {purities.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.purity_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Design Code */}
      <div className="flex flex-col gap-1">
        <Label>Design Code</Label>
        <Input
          type="text"
          placeholder="Design Code"
          className="w-36"
          value={filters.design_code}
          onChange={(e) => handleChange('design_code', e.target.value)}
        />
      </div>

      {/* Branch */}
      <div className="flex flex-col gap-1">
        <Label>Branch</Label>
        <Select
          value={filters.retail_id || '__all__'}
          onValueChange={(val) => handleChange('retail_id', val)}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All Branches" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Branches</SelectItem>
            {retails.map((r) => (
              <SelectItem key={r.id} value={String(r.id)}>
                {r.retail_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Apply */}
      <Button onClick={handleApply} disabled={loading}>
        {loading ? 'Loading...' : 'Apply'}
      </Button>
    </div>
  );
}

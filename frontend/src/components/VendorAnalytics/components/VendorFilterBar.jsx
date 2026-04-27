import { useEffect, useState } from 'react';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { getLedgers, fetchPurity } from '@/services/apiService';

const ITEM_TYPE_OPTIONS = [
  { value: '__all__', label: 'All' },
  { value: 'M', label: 'Making' },
  { value: 'R', label: 'Raw' },
  { value: 'S', label: 'Studded' },
  { value: 'O', label: 'Other' },
  { value: 'C', label: 'Casting' },
];

export default function VendorFilterBar({ filters, onChange, onApply, loading }) {
  const [vendors, setVendors] = useState([]);
  const [purities, setPurities] = useState([]);

  useEffect(() => {
    getLedgers({ type: 'VD', page_size: 200 }).then((res) => {
      if (res?.success && res?.data?.results) {
        setVendors(res.data.results);
      }
    });

    fetchPurity().then((res) => {
      if (res) {
        setPurities(Array.isArray(res) ? res : res?.data ?? []);
      }
    });
  }, []);

  const handleChange = (field, value) => {
    onChange({ ...filters, [field]: value });
  };

  return (
    <div className="flex flex-wrap gap-3 items-end p-4 bg-white border rounded-lg shadow-sm">
      {/* Vendor */}
      <div className="flex flex-col gap-1">
        <Label>Vendor</Label>
        <Select
          value={filters.vendor_id ?? '__all__'}
          onValueChange={(val) => handleChange('vendor_id', val === '__all__' ? '' : val)}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="All Vendors" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Vendors</SelectItem>
            {vendors.map((v) => (
              <SelectItem key={v.id} value={String(v.id)}>
                {v.name}
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
          value={filters.from_date ?? ''}
          onChange={(e) => handleChange('from_date', e.target.value)}
        />
      </div>

      {/* To Date */}
      <div className="flex flex-col gap-1">
        <Label>To Date</Label>
        <Input
          type="date"
          className="w-36"
          value={filters.to_date ?? ''}
          onChange={(e) => handleChange('to_date', e.target.value)}
        />
      </div>

      {/* Item Type */}
      <div className="flex flex-col gap-1">
        <Label>Item Type</Label>
        <Select
          value={filters.item_type || '__all__'}
          onValueChange={(val) => handleChange('item_type', val === '__all__' ? '' : val)}
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
          value={filters.purity_id ?? '__all__'}
          onValueChange={(val) => handleChange('purity_id', val === '__all__' ? '' : val)}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All</SelectItem>
            {purities.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.purity_name ?? p.name}
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
          value={filters.design_code ?? ''}
          onChange={(e) => handleChange('design_code', e.target.value)}
        />
      </div>

      {/* Apply */}
      <Button onClick={onApply} disabled={loading}>
        {loading ? 'Loading...' : 'Apply'}
      </Button>
    </div>
  );
}

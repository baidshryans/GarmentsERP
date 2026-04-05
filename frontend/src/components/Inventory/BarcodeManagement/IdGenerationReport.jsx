import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";
import {
  fetchIDGenerationReportAPI,
  fetchArtisanDataAPI,
  fetchItemDataAPI,
  fetchPurity,
  fetchUserDataAPI
} from "@/services/apiService";

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString("en-GB");
}

export default function IDGenerationReport() {
  const [data, setData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [artisanData, setArtisanData] = useState([]);
  const [filteredArtisanData, setFilteredArtisanData] = useState([]);
  const [itemData, setItemData] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [userData, setUserData] = useState([]);
  const [artisanSearchTerm, setArtisanSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    artisan: { all: true, selected: [] },
    item: { all: true, selected: [] },
    purity: { all: true, selected: [] },
    user: { all: true, selected: [] },
    fromDate: "2024-02-01",
    toDate: "2025-07-30",
    reportType: "FROM",
    month: "SELECT",
    year: "SELECT"
  });

  useEffect(() => {
    const loadArtisanData = async () => {
      try {
        const result = await fetchArtisanDataAPI();
        if (result.success) {
          setArtisanData(result.data);
          setFilteredArtisanData(result.data);
          setFilters(prev => ({
            ...prev,
            artisan: { all: true, selected: result.data.map(a => a.id) }
          }));
        } else {
          setError("Failed to load artisan data");
        }
      } catch {
        setError("Failed to load artisan data");
      }
    };
    loadArtisanData();
  }, []);

  useEffect(() => {
    const loadFilterData = async () => {
      try {
        const [itemResult, purityResult, userResult] = await Promise.all([
          fetchItemDataAPI(),
          fetchPurity(),
          fetchUserDataAPI()
        ]);
        if (itemResult.success) setItemData(itemResult.data);
        if (purityResult.success) setPurityData(purityResult.data);
        if (userResult.success) setUserData(userResult.data);

        setFilters(prev => ({
          ...prev,
          item: { all: true, selected: itemResult.success ? itemResult.data.map(i => i.id) : [] },
          purity: { all: true, selected: purityResult.success ? purityResult.data.map(p => p.id) : [] },
          user: { all: true, selected: userResult.success ? userResult.data.map(u => u.id) : [] }
        }));
      } catch {
        setError("Failed to load filter data");
      }
    };
    loadFilterData();
  }, []);

  useEffect(() => {
    const searchArtisans = async () => {
      try {
        const result = await fetchArtisanDataAPI(artisanSearchTerm);
        if (result.success) setFilteredArtisanData(result.data);
      } catch {
        // ignore search errors
      }
    };
    const id = setTimeout(searchArtisans, 300);
    return () => clearTimeout(id);
  }, [artisanSearchTerm]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchIDGenerationReportAPI({
          from_date: "2024-02-01",
          to_date: "2025-07-30"
        });
        if (result.success) {
          setData(result.data);
          setFilteredData(result.data);
        } else {
          setError(result.error || "Failed to load initial data");
        }
      } catch {
        setError("Failed to load initial data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleFilterChange = (filterType, id, checked) => {
    if (id === 'all') {
      const currentData = filterType === 'artisan' ? artisanData
        : filterType === 'item' ? itemData
        : filterType === 'purity' ? purityData : userData;
      setFilters(prev => ({
        ...prev,
        [filterType]: { all: checked, selected: checked ? currentData.map(item => item.id) : [] }
      }));
    } else {
      setFilters(prev => {
        const currentData = filterType === 'artisan' ? artisanData
          : filterType === 'item' ? itemData
          : filterType === 'purity' ? purityData : userData;
        const newSelected = checked
          ? [...prev[filterType].selected, id]
          : prev[filterType].selected.filter(sid => sid !== id);
        return {
          ...prev,
          [filterType]: { all: newSelected.length === currentData.length, selected: newSelected }
        };
      });
    }
  };

  const handleSearch = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchIDGenerationReportAPI({
        from_date: filters.fromDate,
        to_date: filters.toDate,
        artisan_ids: filters.artisan.all ? [] : filters.artisan.selected,
        item_ids: filters.item.all ? [] : filters.item.selected,
        purity_ids: filters.purity.all ? [] : filters.purity.selected,
        user_ids: filters.user.all ? [] : filters.user.selected
      });
      if (result.success) {
        setData(result.data);
        setFilteredData(result.data);
      } else {
        setError(result.error || "Failed to fetch data");
      }
    } catch {
      setError("Failed to fetch filtered data");
    } finally {
      setLoading(false);
    }
  };

  const totals = filteredData.reduce((acc, item) => {
    acc.totalPcs += item.pcs || 0;
    acc.totalGw += item.gw || 0;
    acc.totalNw += item.nw || 0;
    item.stone_details?.forEach(s => {
      acc.stonePcs += s.pcs || 0;
      acc.stoneGw += s.gw || 0;
    });
    return acc;
  }, { totalPcs: 0, totalGw: 0, totalNw: 0, stonePcs: 0, stoneGw: 0 });

  // ── Filter panel column ─────────────────────────────────────────────────────
  const FilterColumn = ({ label, children, last = false }) => (
    <div className={`flex flex-col${last ? '' : ' border-r border-border'}`}>
      <div className="px-3 py-2 bg-muted/70 border-b border-border">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      </div>
      <div className="p-2 flex-1 overflow-y-auto max-h-48">
        {children}
      </div>
    </div>
  );

  const CheckList = ({ filterType, items, labelKey }) => (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <Checkbox
          id={`${filterType}-all`}
          checked={filters[filterType].all}
          onCheckedChange={(checked) => handleFilterChange(filterType, 'all', checked)}
        />
        <label htmlFor={`${filterType}-all`} className="text-xs cursor-pointer">All</label>
      </div>
      {items.map((item) => (
        <div key={item.id} className="flex items-center gap-2">
          <Checkbox
            id={`${filterType}-${item.id}`}
            checked={filters[filterType].selected.includes(item.id)}
            onCheckedChange={(checked) => handleFilterChange(filterType, item.id, checked)}
          />
          <label htmlFor={`${filterType}-${item.id}`} className="text-xs cursor-pointer truncate">
            {item[labelKey] || item.name || item.id}
          </label>
        </div>
      ))}
    </div>
  );

  return (
    <div className="flex flex-col gap-5">

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* ── Filters ─────────────────────────────────────────────────────────── */}
      <div className="rounded-lg border border-border overflow-hidden">
        <div className="grid grid-cols-5">
          {/* Artisan */}
          <FilterColumn label="Artisan">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="artisan-all"
                  checked={filters.artisan.all}
                  onCheckedChange={(checked) => handleFilterChange('artisan', 'all', checked)}
                />
                <label htmlFor="artisan-all" className="text-xs cursor-pointer">All</label>
              </div>
              {filteredArtisanData.slice(0, 10).map((artisan) => (
                <div key={artisan.id} className="flex items-center gap-2">
                  <Checkbox
                    id={`artisan-${artisan.id}`}
                    checked={filters.artisan.selected.includes(artisan.id)}
                    onCheckedChange={(checked) => handleFilterChange('artisan', artisan.id, checked)}
                  />
                  <label htmlFor={`artisan-${artisan.id}`} className="text-xs cursor-pointer truncate">
                    {artisan.ac_name || artisan.name}
                  </label>
                </div>
              ))}
              {filteredArtisanData.length > 10 && (
                <p className="text-xs text-muted-foreground">+{filteredArtisanData.length - 10} more</p>
              )}
            </div>
            <Input
              placeholder="Search artisan..."
              className="mt-2 h-7 text-xs"
              value={artisanSearchTerm}
              onChange={(e) => setArtisanSearchTerm(e.target.value)}
            />
          </FilterColumn>

          {/* Item */}
          <FilterColumn label="Item">
            <CheckList filterType="item" items={itemData} labelKey="short_code" />
          </FilterColumn>

          {/* Purity */}
          <FilterColumn label="Purity">
            <CheckList filterType="purity" items={purityData} labelKey="purity" />
          </FilterColumn>

          {/* User */}
          <FilterColumn label="User">
            <CheckList filterType="user" items={userData} labelKey="name" />
          </FilterColumn>

          {/* Date / Controls */}
          <div className="p-3 flex flex-col gap-3 bg-muted/20">
            <div>
              <Label className="text-xs mb-1 block">Report Type</Label>
              <RadioGroup
                value={filters.reportType}
                onValueChange={(value) => setFilters(prev => ({ ...prev, reportType: value }))}
                className="flex gap-4"
              >
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem value="FROM" id="from" />
                  <label htmlFor="from" className="text-xs cursor-pointer">Date Range</label>
                </div>
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem value="MONTH" id="month" />
                  <label htmlFor="month" className="text-xs cursor-pointer">Month</label>
                </div>
              </RadioGroup>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">From</Label>
                <Input
                  type="date"
                  value={filters.fromDate}
                  onChange={(e) => setFilters(prev => ({ ...prev, fromDate: e.target.value }))}
                  className="h-8 text-xs"
                  style={{ colorScheme: 'light' }}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">To</Label>
                <Input
                  type="date"
                  value={filters.toDate}
                  onChange={(e) => setFilters(prev => ({ ...prev, toDate: e.target.value }))}
                  className="h-8 text-xs"
                  style={{ colorScheme: 'light' }}
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Select value={filters.month} onValueChange={(value) => setFilters(prev => ({ ...prev, month: value }))}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["SELECT","January","February","March","April","May","June",
                    "July","August","September","October","November","December"].map(m => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="flex items-center gap-2">
                <Label className="text-xs shrink-0">Year</Label>
                <Select value={filters.year} onValueChange={(value) => setFilters(prev => ({ ...prev, year: value }))}>
                  <SelectTrigger className="h-8 text-xs flex-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["SELECT","2023","2024","2025","2026"].map(y => (
                      <SelectItem key={y} value={y}>{y}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button size="sm" onClick={handleSearch} disabled={loading} className="w-full h-8">
              <Search className="w-3.5 h-3.5 mr-1" />
              {loading ? "Loading..." : "Show"}
            </Button>
          </div>
        </div>
      </div>

      {/* ── Loading skeletons ────────────────────────────────────────────────── */}
      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      )}

      {/* ── Table ───────────────────────────────────────────────────────────── */}
      {!loading && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground px-1">
            {filteredData.length} record(s) — {formatDate(filters.fromDate)} to {formatDate(filters.toDate)}
          </p>

          <div className="rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-muted/50 text-muted-foreground">
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Date</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Barcode</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Pty.</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Pcs</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Gw</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Nw</th>
                    <th colSpan={5} className="px-2 py-2 border border-border font-semibold uppercase tracking-wider text-center bg-violet-100/80 text-violet-800">Stone</th>
                    <th colSpan={5} className="px-2 py-2 border border-border font-semibold uppercase tracking-wider text-center bg-sky-100/80 text-sky-800">Other</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Making</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Other Chg</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Order No.</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Inv. No</th>
                    <th className="px-2 py-2 border border-border font-semibold uppercase tracking-wider" rowSpan={2}>Inv. Dt.</th>
                  </tr>
                  <tr className="bg-muted/50 text-muted-foreground">
                    <th className="px-2 py-1.5 border border-border font-semibold bg-violet-100/60 text-violet-800">Code</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-violet-100/60 text-violet-800">Sub</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-violet-100/60 text-violet-800">Pcs</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-violet-100/60 text-violet-800">Wt</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-violet-100/60 text-violet-800">Rate</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-sky-100/60 text-sky-800">Code</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-sky-100/60 text-sky-800">Pcs</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-sky-100/60 text-sky-800">Pty</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-sky-100/60 text-sky-800">Wt</th>
                    <th className="px-2 py-1.5 border border-border font-semibold bg-sky-100/60 text-sky-800">Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredData.length === 0 ? (
                    <tr>
                      <td colSpan={21} className="px-3 py-10 text-center text-muted-foreground border border-border">
                        No data found matching the selected filters.
                      </td>
                    </tr>
                  ) : (
                    filteredData.map((item, index) => {
                      const stoneDetailsCount = item.stone_details?.length || 0;
                      const otherDetailsCount = item.other_details?.length || 0;
                      const needsRowspan = stoneDetailsCount > 1 || otherDetailsCount > 1;

                      const rowBase = `border border-border hover:bg-accent/20 transition-colors`;

                      if (!needsRowspan) {
                        const stoneDetail = item.stone_details?.[0] || {};
                        const otherDetail = item.other_details?.[0] || {};
                        return (
                          <tr key={item.id || index} className={rowBase}>
                            <td className="px-2 py-1.5 border border-border text-center">{formatDate(item.created_date)}</td>
                            <td className="px-2 py-1.5 border border-border text-center font-mono">{item.barcode}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.purity}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.pcs}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.gw?.toFixed(3) || "0.000"}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.nw?.toFixed(3) || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{stoneDetail.item || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{stoneDetail.packet || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{stoneDetail.pcs || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{stoneDetail.gw?.toFixed(3) || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{stoneDetail.rate || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{otherDetail.item || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{otherDetail.pcs || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{otherDetail.purity || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{otherDetail.gw?.toFixed(3) || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{otherDetail.rate || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.making_val ? `${item.making_val}%` : ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.other_chg?.toFixed(2) || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.invoice_no || ""}</td>
                            <td className="px-2 py-1.5 border border-border text-center">{item.invoice_date ? formatDate(item.invoice_date) : ""}</td>
                          </tr>
                        );
                      }

                      // Multiple details — rowspan logic
                      const allDetails = [];
                      item.stone_details?.forEach((s, i) => allDetails.push({ type: 'stone', data: s, index: i }));
                      item.other_details?.forEach((o, i) => allDetails.push({ type: 'other', data: o, index: i }));
                      if (allDetails.length === 0) allDetails.push({ type: 'empty', data: {}, index: 0 });

                      return allDetails.map((detail, di) => (
                        <tr key={`${item.id || index}-${di}`} className={rowBase}>
                          {di === 0 && (
                            <>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{formatDate(item.created_date)}</td>
                              <td className="px-2 py-1.5 border border-border text-center font-mono" rowSpan={allDetails.length}>{item.barcode}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.purity}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.pcs}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.gw?.toFixed(3) || "0.000"}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.nw?.toFixed(3) || ""}</td>
                            </>
                          )}
                          {detail.type === 'stone' ? (
                            <>
                              <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{detail.data.item || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{detail.data.packet || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{detail.data.pcs || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{detail.data.gw?.toFixed(3) || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-violet-50/60">{detail.data.rate || ""}</td>
                            </>
                          ) : (
                            <>
                              <td className="border border-border bg-violet-50/60" />
                              <td className="border border-border bg-violet-50/60" />
                              <td className="border border-border bg-violet-50/60" />
                              <td className="border border-border bg-violet-50/60" />
                              <td className="border border-border bg-violet-50/60" />
                            </>
                          )}
                          {detail.type === 'other' ? (
                            <>
                              <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{detail.data.item || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{detail.data.pcs || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{detail.data.purity || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{detail.data.gw?.toFixed(3) || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center bg-sky-50/60">{detail.data.rate || ""}</td>
                            </>
                          ) : (
                            <>
                              <td className="border border-border bg-sky-50/60" />
                              <td className="border border-border bg-sky-50/60" />
                              <td className="border border-border bg-sky-50/60" />
                              <td className="border border-border bg-sky-50/60" />
                              <td className="border border-border bg-sky-50/60" />
                            </>
                          )}
                          {di === 0 && (
                            <>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.making_val ? `${item.making_val}%` : ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.other_chg?.toFixed(2) || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.invoice_no || ""}</td>
                              <td className="px-2 py-1.5 border border-border text-center" rowSpan={allDetails.length}>{item.invoice_date ? formatDate(item.invoice_date) : ""}</td>
                            </>
                          )}
                        </tr>
                      ));
                    }).flat()
                  )}
                </tbody>
                {filteredData.length > 0 && (
                  <tfoot>
                    <tr className="bg-muted/50 font-semibold text-foreground border-t-2 border-border">
                      <td colSpan={3} className="px-2 py-2 border border-border text-sm">Totals</td>
                      <td className="px-2 py-2 border border-border text-center text-sm">{totals.totalPcs}</td>
                      <td className="px-2 py-2 border border-border text-center text-sm">{totals.totalGw.toFixed(3)}</td>
                      <td className="px-2 py-2 border border-border text-center text-sm">{totals.totalNw.toFixed(3)}</td>
                      <td colSpan={2} className="border border-border bg-violet-50/60" />
                      <td className="px-2 py-2 border border-border text-center text-sm bg-violet-50/60">{totals.stonePcs}</td>
                      <td className="px-2 py-2 border border-border text-center text-sm bg-violet-50/60">{totals.stoneGw.toFixed(3)}</td>
                      <td className="border border-border bg-violet-50/60" />
                      <td colSpan={10} className="border border-border" />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

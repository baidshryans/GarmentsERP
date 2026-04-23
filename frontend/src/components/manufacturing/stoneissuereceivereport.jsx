import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
    fetchStoneWorkOrderReportAPI,
    fetchArtisanDataAPI,
    fetchGroupDataAPI,
    fetchShapeDataAPI
} from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-GB");
}

export default function StoneWorkOrderReport() {
    const [data, setData] = useState([]);
    const [filteredData, setFilteredData] = useState([]);
    const [karigarData, setKarigarData] = useState([]);
    const [filteredKarigarData, setFilteredKarigarData] = useState([]);
    const [groupData, setGroupData] = useState([]);
    const [shapeData, setShapeData] = useState([]);
    const [karigarSearchTerm, setKarigarSearchTerm] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState({
        karigar: {
            all: true,
            selected: []
        },
        group: {
            all: true,
            selected: []
        },
        shape: {
            all: true,
            selected: []
        },
        fromDate: "2024-04-01",
        toDate: "2025-03-14",
        reportType: "Issue", // Make sure this is always set
        month: "MAR",
        year: "2025"
    });

    // Load karigar data on component mount
    useEffect(() => {
        const loadKarigarData = async () => {
            try {
                const result = await fetchArtisanDataAPI();
                if (result.success) {
                    setKarigarData(result.data);
                    setFilteredKarigarData(result.data);

                    setFilters(prev => ({
                        ...prev,
                        karigar: {
                            all: true,
                            selected: result.data.map(k => k.id)
                        }
                    }));
                } else {
                    setError("Failed to load karigar data");
                }
            } catch (error) {
                console.error("Error loading karigar data:", error);
                setError("Failed to load karigar data");
            }
        };
        loadKarigarData();
    }, []);

    // Load other filter data
    useEffect(() => {
        const loadFilterData = async () => {
            try {
                const [groupResult, shapeResult] = await Promise.all([
                    fetchGroupDataAPI(),
                    fetchShapeDataAPI()
                ]);

                console.log("Group Result:", groupResult); // Add debug line
                console.log("Shape Result:", shapeResult); // Add debug line

                if (groupResult.success) {
                    console.log("Group Data:", groupResult.data); // Add debug line
                    setGroupData(groupResult.data);
                }

                if (shapeResult.success) {
                    console.log("Shape Data:", shapeResult.data); // Add debug line
                    setShapeData(shapeResult.data);
                }

                setFilters(prev => ({
                    ...prev,
                    group: {
                        all: true,
                        selected: groupResult.success ? groupResult.data.map(g => g.id) : []
                    },
                    shape: {
                        all: true,
                        selected: shapeResult.success ? shapeResult.data.map(s => s.id) : []
                    }
                }));
            } catch (error) {
                console.error("Error loading filter data:", error);
                setError("Failed to load filter data");
            }
        };
        loadFilterData();
    }, []);

    // Search karigar with debounce
    useEffect(() => {
        const searchKarigar = async () => {
            try {
                const result = await fetchArtisanDataAPI(karigarSearchTerm);
                if (result.success) {
                    setFilteredKarigarData(result.data);
                }
            } catch (error) {
                console.error("Error searching karigar data:", error);
            }
        };

        const timeoutId = setTimeout(() => {
            searchKarigar();
        }, 300);

        return () => clearTimeout(timeoutId);
    }, [karigarSearchTerm]);

    // Update the handleSearch function to include karigar filtering
    const handleSearch = async () => {
        if (!isValidDateRange(filters.fromDate, filters.toDate)) {
            setError("From date cannot be after To date.");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const filterParams = {
                from_date: filters.fromDate,
                to_date: filters.toDate,
                karigar_ids: filters.karigar.all ? [] : filters.karigar.selected,
                group_ids: filters.group.all ? [] : filters.group.selected,
                shape_ids: filters.shape.all ? [] : filters.shape.selected
            };

            console.log("Filter params being sent:", filterParams); // Debug line

            const result = await fetchStoneWorkOrderReportAPI(filterParams);
            if (result.success) {
                setData(result.data);
                // Process data based on current report type and apply client-side filtering
                const processed = processReportData(result.data, filters.reportType);
                const filtered = applyKarigarFilter(processed);
                setFilteredData(filtered);
            } else {
                setError(result.error || "Failed to fetch data");
            }
        } catch (error) {
            console.error("Error fetching filtered data:", error);
            setError("Failed to fetch filtered data");
        } finally {
            setLoading(false);
        }
    };

    // Add a function to apply karigar filtering on the client side
    const applyKarigarFilter = (processedData) => {
        if (filters.karigar.all) {
            return processedData;
        }

        // Get selected karigar names
        const selectedKarigarNames = filteredKarigarData
            .filter(karigar => filters.karigar.selected.includes(karigar.id))
            .map(karigar => karigar.ac_name || karigar.name);

        console.log("Selected karigar names:", selectedKarigarNames); // Debug line

        // Filter the processed data by selected karigars
        const filtered = processedData.filter(item =>
            selectedKarigarNames.includes(item.karigar_name)
        );

        console.log("Filtered data by karigar:", filtered); // Debug line
        return filtered;
    };

    // Initial data load
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            setError(null);
            try {
                const result = await fetchStoneWorkOrderReportAPI({
                    from_date: "2024-02-01",
                    to_date: "2025-07-30"
                });
                if (result.success) {
                    setData(result.data);
                    // Process data based on current report type and apply karigar filtering
                    const processed = processReportData(result.data, filters.reportType);
                    const filtered = applyKarigarFilter(processed);
                    setFilteredData(filtered);
                } else {
                    setError(result.error || "Failed to load initial data");
                }
            } catch (error) {
                console.error("Error loading initial data:", error);
                setError("Failed to load initial data");
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, []);

    // Handle report type change
    const handleReportTypeChange = (value) => {
        console.log("Report type changing to:", value); // Debug line
        setFilters(prev => ({ ...prev, reportType: value }));

        // Re-process existing data with new report type and apply karigar filtering
        if (data && data.length > 0) {
            const processed = processReportData(data, value);
            const filtered = applyKarigarFilter(processed);
            setFilteredData(filtered);
            console.log("Processed data for", value, ":", filtered); // Debug line
        }
    };

    // Function to flatten the data based on report type
    const processReportData = (data, reportType) => {
        console.log("Processing data for report type:", reportType);
        const processedData = [];

        if (!data || !Array.isArray(data)) {
            console.log("Data is not valid array:", data);
            return processedData;
        }

        data.forEach(slip => {
            if (!slip || !slip.items || !Array.isArray(slip.items)) {
                console.log("Slip or items not valid:", slip);
                return;
            }

            slip.items.forEach(item => {
                if (reportType === "Issue" && item.stone_issue && Array.isArray(item.stone_issue) && item.stone_issue.length > 0) {
                    // Process stone issue data - group by slip
                    const slipData = {
                        id: `issue-slip-${slip.issue_slip_no}`,
                        date1: slip.date1,
                        karigar_name: slip.karigar_ldgr_name,
                        design_no: item.design_code,
                        set_name: item.item_name,
                        slip_no: slip.issue_slip_no,
                        type: "Issue",
                        stones: []
                    };

                    item.stone_issue.forEach(stoneIssue => {
                        slipData.stones.push({
                            id: `issue-${slip.issue_slip_no}-${stoneIssue.id}`,
                            particulars: stoneIssue.item,
                            pcs: stoneIssue.pcs,
                            wt_cts: stoneIssue.ct,
                            wt_gms: stoneIssue.gw,
                            packet: stoneIssue.packet
                        });
                    });

                    processedData.push(slipData);
                } else if (reportType === "Receive") {
                    // Process stone receive data - group by slip
                    const slipData = {
                        id: `receive-slip-${slip.issue_slip_no}`,
                        date1: slip.date1,
                        karigar_name: slip.karigar_ldgr_name,
                        design_no: item.design_code,
                        set_name: item.item_name,
                        slip_no: slip.issue_slip_no,
                        type: "Receive",
                        stones: []
                    };

                    // Process karigarreceiveitem_set
                    if (item.karigarreceiveitem_set && Array.isArray(item.karigarreceiveitem_set)) {
                        item.karigarreceiveitem_set.forEach(receiveItem => {
                            if (receiveItem.karigarreceiveitemdetails_set && Array.isArray(receiveItem.karigarreceiveitemdetails_set)) {
                                receiveItem.karigarreceiveitemdetails_set.forEach(detail => {
                                    if (detail.return_pcs > 0 || detail.balance_pcs > 0 || detail.return_ct > 0 || detail.balance_ct > 0) {
                                        slipData.stones.push({
                                            id: `receive-detail-${slip.issue_slip_no}-${detail.id}`,
                                            particulars: detail.item === "DI" ? "Diamond" : detail.item === "GOLD" ? "Gold" : detail.item,
                                            pcs: detail.return_pcs || detail.balance_pcs || 0,
                                            wt_cts: detail.return_ct || detail.balance_ct || 0,
                                            wt_gms: detail.return_gw || detail.balance_gw || 0,
                                            packet: detail.packet
                                        });
                                    }
                                });
                            }
                        });
                    }

                    // Also process direct stone_receive data if available
                    if (item.stone_receive && Array.isArray(item.stone_receive) && item.stone_receive.length > 0) {
                        item.stone_receive.forEach(stoneReceive => {
                            slipData.stones.push({
                                id: `receive-direct-${slip.issue_slip_no}-${stoneReceive.id}`,
                                particulars: stoneReceive.item_name || stoneReceive.item,
                                pcs: stoneReceive.return_pcs || stoneReceive.balance_pcs || 0,
                                wt_cts: stoneReceive.return_ct || stoneReceive.balance_ct || 0,
                                wt_gms: stoneReceive.return_gw || stoneReceive.balance_gw || 0,
                                packet: stoneReceive.packet
                            });
                        });
                    }

                    if (slipData.stones.length > 0) {
                        processedData.push(slipData);
                    }
                }
            });
        });

        console.log("Processed data result:", processedData);
        return processedData;
    };

    const handleFilterChange = (filterType, id, checked) => {
        if (id === 'all') {
            const currentData = filterType === 'karigar' ? karigarData :
                filterType === 'group' ? groupData : shapeData;

            setFilters(prev => ({
                ...prev,
                [filterType]: {
                    all: checked,
                    selected: checked ? currentData.map(item => item.id) : []
                }
            }));
        } else {
            setFilters(prev => {
                const currentData = filterType === 'karigar' ? karigarData :
                    filterType === 'group' ? groupData : shapeData;

                const newSelected = checked
                    ? [...prev[filterType].selected, id]
                    : prev[filterType].selected.filter(selectedId => selectedId !== id);

                const allSelected = newSelected.length === currentData.length;

                return {
                    ...prev,
                    [filterType]: {
                        all: allSelected,
                        selected: newSelected
                    }
                };
            });
        }

        // If karigar filter changed and we have data, reapply filtering
        if (filterType === 'karigar' && data && data.length > 0) {
            setTimeout(() => {
                const processed = processReportData(data, filters.reportType);
                const filtered = applyKarigarFilter(processed);
                setFilteredData(filtered);
            }, 100); // Small delay to ensure state has updated
        }
    };

    return (
        <div className="p-4 bg-gray-50 min-h-screen">
            {/* Header */}
            <div className="text-center mb-6">
                <h1 className="text-xl font-bold text-primary underline">
                    KARIGAR ISSUE/RECEIVE REGISTER
                </h1>
            </div>

            {/* Error Message */}
            {error && (
                <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                    {error}
                </div>
            )}

            {/* Filters Section */}
            <div className="bg-white border border-gray-300 mb-6">
                <div className="grid grid-cols-4 h-64">
                    {/* Karigar Filter */}
                    <div className="border-r border-gray-300">
                        <div className="bg-gray-100 p-2 border-b border-gray-300">
                            <Label className="font-semibold text-sm">Karigar</Label>
                        </div>
                        <div className="p-2 h-52 overflow-y-auto">
                            <div className="space-y-1">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="karigar-all"
                                        checked={filters.karigar.all}
                                        onCheckedChange={(checked) => handleFilterChange('karigar', 'all', checked)}
                                    />
                                    <label htmlFor="karigar-all" className="text-sm">All</label>
                                </div>
                                {filteredKarigarData.slice(0, 10).map((karigar) => (
                                    <div key={karigar.id} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`karigar-${karigar.id}`}
                                            checked={filters.karigar.selected.includes(karigar.id)}
                                            onCheckedChange={(checked) => handleFilterChange('karigar', karigar.id, checked)}
                                        />
                                        <label htmlFor={`karigar-${karigar.id}`} className="text-sm truncate">
                                            {karigar.ac_name || karigar.name}
                                        </label>
                                    </div>
                                ))}
                                {filteredKarigarData.length > 10 && (
                                    <div className="text-xs text-gray-300">
                                        ... and {filteredKarigarData.length - 10} more
                                    </div>
                                )}
                            </div>
                        </div>
                        <Input
                            placeholder="Select By Name"
                            className="mt-2"
                            value={karigarSearchTerm}
                            onChange={(e) => setKarigarSearchTerm(e.target.value)}
                        />
                    </div>

                    {/* Group Filter */}
                    <div className="border-r border-gray-300">
                        <div className="bg-gray-100 p-2 border-b border-gray-300">
                            <Label className="font-semibold text-sm">Group</Label>
                        </div>
                        <div className="p-2 h-52 overflow-y-auto">
                            <div className="space-y-1">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="group-all"
                                        checked={filters.group.all}
                                        onCheckedChange={(checked) => handleFilterChange('group', 'all', checked)}
                                    />
                                    <label htmlFor="group-all" className="text-sm">All</label>
                                </div>
                                {groupData && groupData.length > 0 ? (
                                    groupData.map((group) => (
                                        <div key={group.id} className="flex items-center space-x-2">
                                            <Checkbox
                                                id={`group-${group.id}`}
                                                checked={filters.group.selected.includes(group.id)}
                                                onCheckedChange={(checked) => handleFilterChange('group', group.id, checked)}
                                            />
                                            <label htmlFor={`group-${group.id}`} className="text-sm">
                                                {group.name || group.group_name || group.item_group_name || group.description || `Group ${group.id}`}
                                            </label>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-xs text-gray-300">
                                        No groups available
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                    <div className="border-r border-gray-300">
                        <div className="bg-gray-100 p-2 border-b border-gray-300">
                            <Label className="font-semibold text-sm">Shape</Label>
                        </div>
                        <div className="p-2 h-52 overflow-y-auto">
                            <div className="space-y-1">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="shape-all"
                                        checked={filters.shape.all}
                                        onCheckedChange={(checked) => handleFilterChange('shape', 'all', checked)}
                                    />
                                    <label htmlFor="shape-all" className="text-sm">All</label>
                                </div>
                                {shapeData.map((shape) => (
                                    <div key={shape.id} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`shape-${shape.id}`}
                                            checked={filters.shape.selected.includes(shape.id)}
                                            onCheckedChange={(checked) => handleFilterChange('shape', shape.id, checked)}
                                        />
                                        <label htmlFor={`shape-${shape.id}`} className="text-sm">
                                            {shape.name || shape.shape_name || shape.description}
                                        </label>
                                    </div>
                                ))}
                                {shapeData.length === 0 && (
                                    <div className="text-xs text-gray-300">
                                        No shapes available
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Date and Controls Section */}
                    <div className="p-2">
                        <div className="space-y-4">
                            {/* Issue/Receive Checkboxes */}
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="report-issue"
                                        checked={filters.reportType === "Issue"}
                                        onCheckedChange={(checked) => {
                                            if (checked) {
                                                handleReportTypeChange("Issue");
                                            } else if (filters.reportType === "Issue") {
                                                handleReportTypeChange(null);
                                            }
                                        }}
                                    />
                                    <label htmlFor="report-issue" className="text-sm font-medium">Issue</label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="report-receive"
                                        checked={filters.reportType === "Receive"}
                                        onCheckedChange={(checked) => {
                                            if (checked) {
                                                handleReportTypeChange("Receive");
                                            } else if (filters.reportType === "Receive") {
                                                handleReportTypeChange(null);
                                            }
                                        }}
                                    />
                                    <label htmlFor="report-receive" className="text-sm font-medium">Receive</label>
                                </div>
                            </div>

                            {/* Date Inputs */}
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Label className="text-sm">FROM</Label>
                                    <Input
                                        type="date"
                                        value={filters.fromDate}
                                        onChange={(e) => setFilters(prev => ({ ...prev, fromDate: e.target.value }))}
                                        max={filters.toDate || undefined}
                                        className="w-full text-sm"
                                    />
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Label className="text-sm">TO</Label>
                                    <Input
                                        type="date"
                                        value={filters.toDate}
                                        onChange={(e) => setFilters(prev => ({ ...prev, toDate: e.target.value }))}
                                        min={filters.fromDate || undefined}
                                        className="w-full text-sm"
                                    />
                                </div>
                            </div>

                            {/* Month and Year Selects */}
                            <div className="space-y-2">
                                <div className="flex items-center space-x-2">
                                    <Label className="text-sm">MONTH</Label>
                                    <Select value={filters.month} onValueChange={(value) => setFilters(prev => ({ ...prev, month: value }))}>
                                        <SelectTrigger className="flex-1">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="MAR">MAR</SelectItem>
                                            <SelectItem value="JAN">JAN</SelectItem>
                                            <SelectItem value="FEB">FEB</SelectItem>
                                            <SelectItem value="APR">APR</SelectItem>
                                            <SelectItem value="MAY">MAY</SelectItem>
                                            <SelectItem value="JUN">JUN</SelectItem>
                                            <SelectItem value="JUL">JUL</SelectItem>
                                            <SelectItem value="AUG">AUG</SelectItem>
                                            <SelectItem value="SEP">SEP</SelectItem>
                                            <SelectItem value="OCT">OCT</SelectItem>
                                            <SelectItem value="NOV">NOV</SelectItem>
                                            <SelectItem value="DEC">DEC</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="flex items-center space-x-2">
                                    <Label className="text-sm">YEAR</Label>
                                    <Select value={filters.year} onValueChange={(value) => setFilters(prev => ({ ...prev, year: value }))}>
                                        <SelectTrigger className="flex-1">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="2023">2023</SelectItem>
                                            <SelectItem value="2024">2024</SelectItem>
                                            <SelectItem value="2025">2025</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            {/* GO Button */}
                            <Button
                                onClick={handleSearch}
                                disabled={loading}
                                className="w-full bg-primary hover:bg-primary text-white rounded"
                            >
                                {loading ? "Loading..." : "GO"}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Summary Info */}
            <div className="text-center mb-4 text-sm">
                <span className="font-semibold">
                    Karigar Wise {filters.reportType || "Issue"} Register Between {filters.fromDate} and {filters.toDate}
                    {!filters.karigar.all && (
                        <span className="block text-xs text-gray-600 mt-1">
                            Filtered by: {filters.karigar.selected.length} selected karigar(s)
                        </span>
                    )}
                </span>
            </div>

            {/* Table */}
            <div className="bg-white border border-gray-300 overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-gray-100">
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Date</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Karigar</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Design No</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Set Name</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Slip No</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Particulars</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Pcs</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Wt(Cts)</TableHead>
                            <TableHead className="border border-gray-300 text-center font-semibold text-xs">Wt(gms)</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={9} className="text-center py-8">
                                    Loading...
                                </TableCell>
                            </TableRow>
                        ) : filteredData.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={9} className="text-center py-8">
                                    No {filters.reportType ? filters.reportType.toLowerCase() : "data"} found matching the selected filters
                                </TableCell>
                            </TableRow>
                        ) : (
                            filteredData.map((slipGroup, slipIndex) => {
                                if (!slipGroup.stones || slipGroup.stones.length === 0) {
                                    return (
                                        <TableRow key={slipGroup.id || slipIndex}>
                                            <TableCell className="border border-gray-300 text-xs text-center">
                                                {formatDate(slipGroup.date1)}
                                            </TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">
                                                {slipGroup.karigar_name || ""}
                                            </TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">
                                                {slipGroup.design_no || ""}
                                            </TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">
                                                {slipGroup.set_name || ""}
                                            </TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">
                                                {slipGroup.slip_no || ""}
                                            </TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">
                                                No stones found
                                            </TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">-</TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">-</TableCell>
                                            <TableCell className="border border-gray-300 text-xs text-center">-</TableCell>
                                        </TableRow>
                                    );
                                }

                                return slipGroup.stones.map((stone, stoneIndex) => (
                                    <TableRow key={`${slipGroup.id}-${stone.id || stoneIndex}`}>
                                        {stoneIndex === 0 && (
                                            <>
                                                <TableCell
                                                    rowSpan={slipGroup.stones.length}
                                                    className="border border-gray-300 text-xs text-center align-top"
                                                >
                                                    {formatDate(slipGroup.date1)}
                                                </TableCell>
                                                <TableCell
                                                    rowSpan={slipGroup.stones.length}
                                                    className="border border-gray-300 text-xs text-center align-top"
                                                >
                                                    {slipGroup.karigar_name || ""}
                                                </TableCell>
                                                <TableCell
                                                    rowSpan={slipGroup.stones.length}
                                                    className="border border-gray-300 text-xs text-center align-top"
                                                >
                                                    {slipGroup.design_no || ""}
                                                </TableCell>
                                                <TableCell
                                                    rowSpan={slipGroup.stones.length}
                                                    className="border border-gray-300 text-xs text-center align-top"
                                                >
                                                    {slipGroup.set_name || ""}
                                                </TableCell>
                                                <TableCell
                                                    rowSpan={slipGroup.stones.length}
                                                    className="border border-gray-300 text-xs text-center align-top"
                                                >
                                                    {slipGroup.slip_no || ""}
                                                </TableCell>
                                            </>
                                        )}
                                        <TableCell className="border border-gray-300 text-xs text-center">
                                            {stone.particulars || ""}
                                            {stone.packet && (
                                                <div className="text-xs text-gray-500">({stone.packet})</div>
                                            )}
                                        </TableCell>
                                        <TableCell className="border border-gray-300 text-xs text-center">
                                            {stone.pcs || ""}
                                        </TableCell>
                                        <TableCell className="border border-gray-300 text-xs text-center">
                                            {stone.wt_cts ? stone.wt_cts.toFixed(3) : ""}
                                        </TableCell>
                                        <TableCell className="border border-gray-300 text-xs text-center">
                                            {stone.wt_gms ? stone.wt_gms.toFixed(3) : ""}
                                        </TableCell>
                                    </TableRow>
                                ));
                            })
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Export Links */}
            <div className="flex justify-end mt-4 space-x-4 text-sm">
                <span className="text-primary cursor-pointer hover:underline">[EXCEL]</span>
                <span className="text-primary cursor-pointer hover:underline">[PRINT]</span>
            </div>
        </div>
    );
}
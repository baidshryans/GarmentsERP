
import React, { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Custom Table components to match your original design
const Table = ({ children }) => (
    <div className="w-full overflow-auto">
        <table className="w-full caption-bottom text-sm border-collapse">
            {children}
        </table>
    </div>
);

const TableHeader = ({ children }) => (
    <thead className="[&_tr]:border-b bg-muted/50">
        {children}
    </thead>
);

const TableBody = ({ children }) => (
    <tbody className="[&_tr:last-child]:border-0">
        {children}
    </tbody>
);

const TableRow = ({ children }) => (
    <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
        {children}
    </tr>
);

const TableHead = ({ children, className = "" }) => (
    <th className={`h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 border border-gray-300 bg-gray-50 ${className}`}>
        {children}
    </th>
);

const TableCell = ({ children, colSpan, className = "" }) => (
    <td colSpan={colSpan} className={`p-4 align-middle [&:has([role=checkbox])]:pr-0 border border-gray-300 ${className}`}>
        {children}
    </td>
);

// Real API functions
async function fetchHallMarkIssueReport(filterParams = {}) {
    try {
        const queryParams = new URLSearchParams();

        // Fixed parameter names to match Django view
        if (filterParams.karigar_ids && filterParams.karigar_ids.length > 0) {
            queryParams.append('ledger_ids', filterParams.karigar_ids.join(','));
        }

        if (filterParams.purity && filterParams.purity.length > 0) {
            queryParams.append('purity_id', filterParams.purity.join(','));
        }

        if (filterParams.from_date) {
            queryParams.append('start_date', filterParams.from_date);
        }

        if (filterParams.to_date) {
            queryParams.append('end_date', filterParams.to_date);
        }

        const url = `http://127.0.0.1:8000/manufacturing/api/hallmark-issue-report${queryParams.toString() ? '?' + queryParams.toString() : ''}`;

        const response = await fetch(url, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return {
            success: true,
            data: data
        };
    } catch (error) {
        console.error("Error fetching hallmark issue report:", error);
        return {
            success: false,
            data: [],
            error: error.message
        };
    }
}

async function fetchLedgerData() {
    try {
        const response = await fetch("http://127.0.0.1:8000/contacts/api/ledger/");

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data.results || data;
    } catch (error) {
        console.error("Error fetching ledger data:", error);
        return [];
    }
}

async function fetchPurityData() {
    try {
        const response = await fetch("http://127.0.0.1:8000/goldrates/api/purity/");

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching purity data:", error);
        return [];
    }
}

// New function to fetch item data
async function fetchItemData() {
    try {
        const response = await fetch("http://127.0.0.1:8000/items/api/items/");

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data.results || data;
    } catch (error) {
        console.error("Error fetching item data:", error);
        return [];
    }
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-GB");
}

export default function HallmarkIssueReport() {
    const [data, setData] = useState([]);
    const [filteredData, setFilteredData] = useState([]);
    const [ledgerData, setLedgerData] = useState([]);
    const [filteredLedgerData, setFilteredLedgerData] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [itemData, setItemData] = useState([]);
    const [searchTerm, setSearchTerm] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState({
        karigar: {
            all: true,
            selected: []
        },
        purity: {
            all: true,
            selected: []
        },
        fromDate: "2024-04-01",
        toDate: "2025-12-31",
        dateFilter: "FROM",
        month: "",
        year: "SELECT"
    });

    // Load item data on component mount
    useEffect(() => {
        const loadItemData = async () => {
            try {
                const items = await fetchItemData();
                setItemData(items);
            } catch (error) {
                console.error("Error loading item data:", error);
                setError("Failed to load item data");
            }
        };
        loadItemData();
    }, []);

    // Load ledger data on component mount
    useEffect(() => {
        const loadLedgerData = async () => {
            try {
                const ledgers = await fetchLedgerData();
                setLedgerData(ledgers);
                setFilteredLedgerData(ledgers);

                // Initialize karigar filter with all IDs
                setFilters(prev => ({
                    ...prev,
                    karigar: {
                        all: true,
                        selected: ledgers.map(l => l.id)
                    }
                }));
            } catch (error) {
                console.error("Error loading ledger data:", error);
                setError("Failed to load ledger data");
            }
        };
        loadLedgerData();
    }, []);

    // Load purity data on component mount
    useEffect(() => {
        const loadPurityData = async () => {
            try {
                const purities = await fetchPurityData();
                setPurityData(purities);

                // Initialize purity filter with all IDs
                setFilters(prev => ({
                    ...prev,
                    purity: {
                        all: true,
                        selected: purities.map(p => p.purity)
                    }
                }));
            } catch (error) {
                console.error("Error loading purity data:", error);
                setError("Failed to load purity data");
            }
        };
        loadPurityData();
    }, []);

    // Filter ledger data based on search term
    useEffect(() => {
        if (searchTerm) {
            const filtered = ledgerData.filter(ledger =>
                ledger.ac_name.toLowerCase().includes(searchTerm.toLowerCase())
            );
            setFilteredLedgerData(filtered);
        } else {
            setFilteredLedgerData(ledgerData);
        }
    }, [searchTerm, ledgerData]);

    // Helper functions to get data by ID
    const getItemById = (itemId) => {
        return itemData.find(item => item.id === itemId) || {};
    };

    const getPurityById = (purityId) => {
        const purity = purityData.find(p => p.id === purityId);
        return purity ? purity.purity : 'N/A';
    };

    const getLedgerById = (ledgerId) => {
        const ledger = ledgerData.find(l => l.id === ledgerId);
        return ledger ? ledger.ac_name : 'N/A';
    };

    // Simplified applyFilters function - API handles most filtering
    const applyFilters = (rawData) => {
        // Since API handles filtering, just return the data
        // You can add client-side filtering here if needed
        return rawData;
    };

    const handleKarigarChange = (ledgerId, checked) => {
        if (ledgerId === 'all') {
            setFilters(prev => ({
                ...prev,
                karigar: {
                    all: checked,
                    selected: checked ? ledgerData.map(l => l.id) : []
                }
            }));
        } else {
            setFilters(prev => {
                const newSelected = checked
                    ? [...prev.karigar.selected, ledgerId]
                    : prev.karigar.selected.filter(id => id !== ledgerId);

                const allSelected = newSelected.length === ledgerData.length;

                return {
                    ...prev,
                    karigar: {
                        all: allSelected,
                        selected: newSelected
                    }
                };
            });
        }
    };

    const handlePurityChange = (purityValue, checked) => {
        if (purityValue === 'all') {
            setFilters(prev => ({
                ...prev,
                purity: {
                    all: checked,
                    selected: checked ? purityData.map(p => p.purity) : []
                }
            }));
        } else {
            setFilters(prev => {
                const newSelected = checked
                    ? [...prev.purity.selected, purityValue]
                    : prev.purity.selected.filter(p => p !== purityValue);

                const allSelected = newSelected.length === purityData.length;

                return {
                    ...prev,
                    purity: {
                        all: allSelected,
                        selected: newSelected
                    }
                };
            });
        }
    };

    const handleSearch = async () => {
        setLoading(true);
        setError(null);
        try {
            // Prepare filter parameters for API call
            const filterParams = {
                karigar_ids: filters.karigar.all ? [] : filters.karigar.selected,
                purity: filters.purity.all ? [] : filters.purity.selected,
                from_date: filters.fromDate,
                to_date: filters.toDate,
            };

            console.log("Filter params being sent:", filterParams);

            const report = await fetchHallMarkIssueReport(filterParams);
            if (report.success) {
                console.log("API Response:", report.data);
                setData(report.data);
                
                // Apply any additional client-side filtering
                const filteredResult = applyFilters(report.data);
                console.log("After client filtering:", filteredResult);
                setFilteredData(filteredResult);
            } else {
                setError(report.error || "Failed to fetch data");
            }
        } catch (error) {
            console.error("Error fetching filtered data:", error);
            setError("Failed to fetch filtered data");
        } finally {
            setLoading(false);
        }
    };

    // Simplified useEffect - just set data directly since API handles filtering
    useEffect(() => {
        if (data.length > 0) {
            setFilteredData(data);
        }
    }, [data]);

    // Initial data load
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            setError(null);
            try {
                const report = await fetchHallMarkIssueReport();
                if (report.success) {
                    setData(report.data);
                    setFilteredData(report.data);
                } else {
                    setError(report.error || "Failed to load initial data");
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

    return (
        <div className="p-4">
            {/* Header */}
            <div className="text-center mb-6">
                <h1 className="text-xl font-bold text-violet-700">HALLMARK ISSUE REGISTER</h1>
            </div>

            {/* Error Message */}
            {error && (
                <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                    {error}
                </div>
            )}

            {/* Filters */}
            <Card className="mb-6">
                <CardContent className="p-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Karigar Filter */}
                        <div>
                            <Label className="text-sm font-semibold mb-2 block">Karigar</Label>
                            <div className="border rounded-md p-3 bg-gray-400 text-white max-h-40 overflow-y-auto">
                                <div className="space-y-2">
                                    <div className="flex items-center space-x-2">
                                        <Checkbox
                                            id="karigar-all"
                                            checked={filters.karigar.all}
                                            onCheckedChange={(checked) => handleKarigarChange('all', checked)}
                                        />
                                        <label htmlFor="karigar-all" className="text-sm">All</label>
                                    </div>
                                    {filteredLedgerData.slice(0, 10).map((ledger) => (
                                        <div key={ledger.id} className="flex items-center space-x-2">
                                            <Checkbox
                                                id={`karigar-${ledger.id}`}
                                                checked={filters.karigar.selected.includes(ledger.id)}
                                                onCheckedChange={(checked) => handleKarigarChange(ledger.id, checked)}
                                            />
                                            <label htmlFor={`karigar-${ledger.id}`} className="text-sm truncate">
                                                {ledger.ac_name}
                                            </label>
                                        </div>
                                    ))}
                                    {filteredLedgerData.length > 10 && (
                                        <div className="text-xs text-gray-300">
                                            ... and {filteredLedgerData.length - 10} more
                                        </div>
                                    )}
                                </div>
                            </div>
                            <Input
                                placeholder="Select By Name"
                                className="mt-2"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>

                        {/* Purity Filter */}
                        <div>
                            <Label className="text-sm font-semibold mb-2 block">Purity</Label>
                            <div className="border rounded-md p-3 bg-gray-400 text-white max-h-40 overflow-y-auto">
                                <div className="space-y-2">
                                    <div className="flex items-center space-x-2">
                                        <Checkbox
                                            id="purity-all"
                                            checked={filters.purity.all}
                                            onCheckedChange={(checked) => handlePurityChange('all', checked)}
                                        />
                                        <label htmlFor="purity-all" className="text-sm">All</label>
                                    </div>
                                    {purityData.map((purity) => (
                                        <div key={purity.id} className="flex items-center space-x-2">
                                            <Checkbox
                                                id={`purity-${purity.purity}`}
                                                checked={filters.purity.selected.includes(purity.purity)}
                                                onCheckedChange={(checked) => handlePurityChange(purity.purity, checked)}
                                            />
                                            <label htmlFor={`purity-${purity.purity}`} className="text-sm">
                                                {purity.purity}
                                            </label>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Date Filters */}
                        <div className="space-y-4">
                            <div className="flex items-center space-x-4">
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="radio"
                                        id="from-date"
                                        name="dateFilter"
                                        checked={filters.dateFilter === 'FROM'}
                                        onChange={() => setFilters(prev => ({ ...prev, dateFilter: 'FROM' }))}
                                    />
                                    <Label htmlFor="from-date" className="text-sm">FROM</Label>
                                </div>
                                <Input
                                    type="date"
                                    value={filters.fromDate}
                                    onChange={(e) => setFilters(prev => ({ ...prev, fromDate: e.target.value }))}
                                    className="w-32"
                                />
                                <Label className="text-sm">TO</Label>
                                <Input
                                    type="date"
                                    value={filters.toDate}
                                    onChange={(e) => setFilters(prev => ({ ...prev, toDate: e.target.value }))}
                                    className="w-32"
                                />
                            </div>

                            <Button
                                onClick={handleSearch}
                                disabled={loading}
                                className="bg-violet-500 hover:bg-violet-600 text-white px-8 py-2 rounded-md disabled:opacity-50"
                            >
                                {loading ? "Loading..." : "GO"}
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Table - Updated for new data structure */}
            <div className="overflow-x-auto">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[120px]">VouDate</TableHead>
                            <TableHead className="w-[150px]">Vounum</TableHead>
                            <TableHead className="w-[150px]">St/Or No</TableHead>
                            <TableHead className="w-[300px]">Item Code & Name</TableHead>
                            <TableHead>Purity</TableHead>
                            <TableHead>Pcs</TableHead>
                            <TableHead>Gross Wt</TableHead>
                            <TableHead>Nett Wt</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8">
                                    Loading...
                                </TableCell>
                            </TableRow>
                        ) : filteredData.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8">
                                    No data found matching the selected filters
                                </TableCell>
                            </TableRow>
                        ) : (
                            // Updated mapping for new data structure (HallmarkIssue objects directly)
                            filteredData.map((issue, i) => (
                                <React.Fragment key={i}>
                                    {issue.hallmarkissueitem_set?.length > 0 ? (
                                        issue.hallmarkissueitem_set.map((item, j) => {
                                            const itemDetails = getItemById(item.item);
                                            const purityValue = getPurityById(item.purity);
                                            const ledgerName = getLedgerById(issue.hallmark_center);
                                            
                                            return (
                                                <TableRow key={j}>
                                                    <TableCell>
                                                        {j === 0 ? formatDate(issue.date1) : ""}
                                                    </TableCell>
                                                    <TableCell>
                                                        {j === 0 ? issue.issue_slip_no : ""}
                                                    </TableCell>
                                                    <TableCell>
                                                        {item.receive_sl
                                                            ? `BA24/${item.receive_sl.toString().padStart(5, "0")}`
                                                            : "N/A"}
                                                    </TableCell>
                                                    <TableCell>
                                                        <div>
                                                            {j === 0 && (
                                                                <div className="font-normal">
                                                                    Name : {ledgerName.toUpperCase()}
                                                                </div>
                                                            )}
                                                            {/* <div>
                                                                <span className="font-bold">
                                                                    {itemDetails.short_code || 'NO_CODE'}
                                                                </span> - {itemDetails.item_name || 'NO_NAME'}
                                                            </div> */}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>{purityValue}</TableCell>
                                                    <TableCell>{item.pcs || 0}</TableCell>
                                                    <TableCell>{Number(item.gw || 0).toFixed(3)}</TableCell>
                                                    <TableCell>{Number(item.nw || 0).toFixed(3)}</TableCell>
                                                </TableRow>
                                            );
                                        })
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={8} className="text-center py-4">
                                                No items found for this issue
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </React.Fragment>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
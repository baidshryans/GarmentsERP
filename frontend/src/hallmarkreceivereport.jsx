import React, { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// API functions for Hallmark Receive Report
async function fetchHallMarkReceiveReport(filterParams = {}) {
    try {
        // Convert filter parameters to query string for GET request
        const queryParams = new URLSearchParams();

        if (filterParams.start_date) {
            queryParams.append('start_date', filterParams.start_date);
        }

        if (filterParams.end_date) {
            queryParams.append('end_date', filterParams.end_date);
        }

        if (filterParams.ledger_ids && filterParams.ledger_ids.length > 0) {
            filterParams.ledger_ids.forEach(id => {
                queryParams.append('ledger_ids', id);
            });
        }

        if (filterParams.purity_id) {
            queryParams.append('purity_id', filterParams.purity_id);
        }

        if (filterParams.item_status !== undefined) {
            queryParams.append('item_status', filterParams.item_status);
        }

        const url = `http://127.0.0.1:8000/manufacturing/api/hallmark-receive-report${queryParams.toString() ? '?' + queryParams.toString() : ''}`;

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
        console.error("Error fetching hallmark receive report:", error);
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

async function fetchPacketData() {
    try {
        const response = await fetch("http://127.0.0.1:8000/mastersconfig/api/packet/");

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching packet data:", error);
        return [];
    }
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-GB");
}

export default function HallmarkReceiveReport() {
    const [data, setData] = useState([]);
    const [filteredData, setFilteredData] = useState([]);
    const [ledgerData, setLedgerData] = useState([]);
    const [filteredLedgerData, setFilteredLedgerData] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [packetData, setPacketData] = useState([]);
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
        fromDate: "2024-02-01",
        toDate: "2025-07-30",
        dateFilter: "FROM",
        month: "",
        year: "SELECT"
    });

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
                        selected: purities.map(p => p.id)
                    }
                }));
            } catch (error) {
                console.error("Error loading purity data:", error);
                setError("Failed to load purity data");
            }
        };
        loadPurityData();
    }, []);

    // Load packet data on component mount
    useEffect(() => {
        const loadPacketData = async () => {
            try {
                const packets = await fetchPacketData();
                setPacketData(packets);
            } catch (error) {
                console.error("Error loading packet data:", error);
                setError("Failed to load packet data");
            }
        };
        loadPacketData();
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

    const handlePurityChange = (purityId, checked) => {
        if (purityId === 'all') {
            setFilters(prev => ({
                ...prev,
                purity: {
                    all: checked,
                    selected: checked ? purityData.map(p => p.id) : []
                }
            }));
        } else {
            setFilters(prev => {
                const newSelected = checked
                    ? [...prev.purity.selected, purityId]
                    : prev.purity.selected.filter(id => id !== purityId);

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

    // Helper function to get purity name by ID
    const getPurityName = (purityId) => {
        const purity = purityData.find(p => p.id === purityId);
        return purity ? purity.purity : purityId;
    };

    const handleSearch = async () => {
        setLoading(true);
        setError(null);
        try {
            // Prepare filter parameters for API call
            const filterParams = {
                start_date: filters.fromDate,
                end_date: filters.toDate,
                ledger_ids: filters.karigar.all ? [] : filters.karigar.selected,
            };

            // Add purity filter if not all selected
            if (!filters.purity.all && filters.purity.selected.length > 0) {
                filterParams.purity_id = filters.purity.selected[0]; // API seems to accept single purity_id
            }

            // Handle month/year filtering by adjusting dates
            if (filters.dateFilter === 'MONTH' && filters.month && filters.year !== 'SELECT') {
                const year = parseInt(filters.year);
                const month = parseInt(filters.month);
                const startDate = new Date(year, month - 1, 1);
                const endDate = new Date(year, month, 0);
                
                filterParams.start_date = startDate.toISOString().split('T')[0];
                filterParams.end_date = endDate.toISOString().split('T')[0];
            }

            console.log("Filter params being sent:", filterParams);

            const report = await fetchHallMarkReceiveReport(filterParams);
            if (report.success) {
                console.log("API Response:", report.data);
                setData(report.data);
                setFilteredData(report.data);
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

    // Initial data load
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            setError(null);
            try {
                const report = await fetchHallMarkReceiveReport({
                    start_date: filters.fromDate,
                    end_date: filters.toDate
                });
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
                <h1 className="text-xl font-bold text-violet-700">HALLMARK RECEIVE REGISTER</h1>
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
                                                id={`purity-${purity.id}`}
                                                checked={filters.purity.selected.includes(purity.id)}
                                                onCheckedChange={(checked) => handlePurityChange(purity.id, checked)}
                                            />
                                            <label htmlFor={`purity-${purity.id}`} className="text-sm">
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

                            <div className="flex items-center space-x-4">
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="radio"
                                        id="month-filter"
                                        name="dateFilter"
                                        checked={filters.dateFilter === 'MONTH'}
                                        onChange={() => setFilters(prev => ({ ...prev, dateFilter: 'MONTH' }))}
                                    />
                                    <Label htmlFor="month-filter" className="text-sm">MONTH</Label>
                                </div>
                                <Select value={filters.month} onValueChange={(value) => setFilters(prev => ({ ...prev, month: value }))}>
                                    <SelectTrigger className="w-32">
                                        <SelectValue placeholder="SELECT" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="01">January</SelectItem>
                                        <SelectItem value="02">February</SelectItem>
                                        <SelectItem value="03">March</SelectItem>
                                        <SelectItem value="04">April</SelectItem>
                                        <SelectItem value="05">May</SelectItem>
                                        <SelectItem value="06">June</SelectItem>
                                        <SelectItem value="07">July</SelectItem>
                                        <SelectItem value="08">August</SelectItem>
                                        <SelectItem value="09">September</SelectItem>
                                        <SelectItem value="10">October</SelectItem>
                                        <SelectItem value="11">November</SelectItem>
                                        <SelectItem value="12">December</SelectItem>
                                    </SelectContent>
                                </Select>
                                <Label className="text-sm">YEAR</Label>
                                <Select value={filters.year} onValueChange={(value) => setFilters(prev => ({ ...prev, year: value }))}>
                                    <SelectTrigger className="w-24">
                                        <SelectValue placeholder="SELECT" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="2023">2023</SelectItem>
                                        <SelectItem value="2024">2024</SelectItem>
                                        <SelectItem value="2025">2025</SelectItem>
                                    </SelectContent>
                                </Select>
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

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full border-collapse border border-gray-300">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="border border-gray-300 px-4 py-2 text-left w-[120px]">Date</th>
                            <th className="border border-gray-300 px-4 py-2 text-left w-[150px]">Karigar Name</th>
                            <th className="border border-gray-300 px-4 py-2 text-left w-[150px]">Receive Slip No</th>
                            <th className="border border-gray-300 px-4 py-2 text-left w-[100px]">HUID</th>
                            <th className="border border-gray-300 px-4 py-2 text-left w-[300px]">Item Code & Name</th>
                            <th className="border border-gray-300 px-4 py-2 text-left">Purity</th>
                            <th className="border border-gray-300 px-4 py-2 text-left">Pcs</th>
                            <th className="border border-gray-300 px-4 py-2 text-left">Gross Wt</th>
                            <th className="border border-gray-300 px-4 py-2 text-left">Nett Wt</th>
                            <th className="border border-gray-300 px-4 py-2 text-left">Loss Wt</th>
                            <th className="border border-gray-300 px-4 py-2 text-left">Rejection Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={11} className="border border-gray-300 px-4 py-8 text-center text-gray-500">
                                    <div className="flex items-center justify-center space-x-2">
                                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500"></div>
                                        <span>Loading data...</span>
                                    </div>
                                </td>
                            </tr>
                        ) : filteredData && filteredData.length > 0 ? (
                            // Flatten the nested data structure and render rows
                            filteredData.flatMap((ledger) => 
                                ledger.hallmarkreceive_set.flatMap((hallmarkReceive) =>
                                    hallmarkReceive.hallmarkreceiveitem_set.map((item, itemIndex) => {
                                        const rowIndex = `${ledger.id}_${hallmarkReceive.id}_${item.id}`;
                                        return (
                                            <tr key={rowIndex} className={itemIndex % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    {item.date1 ? formatDate(item.date1) : '-'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    {ledger.ac_name || '-'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    {hallmarkReceive.receive_slip_no || '-'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    {item.huid || '-'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    <div>
                                                        <div className="font-medium">Item ID: {item.item || '-'}</div>
                                                        <div className="text-sm text-gray-600">SL No: {item.sl_no || '-'}</div>
                                                    </div>
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    {getPurityName(item.purity) || '-'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2 text-right">
                                                    {item.pcs || 0}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2 text-right">
                                                    {item.gw ? parseFloat(item.gw).toFixed(3) : '0.000'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2 text-right">
                                                    {item.nw ? parseFloat(item.nw).toFixed(3) : '0.000'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2 text-right">
                                                    {item.loss_wt ? parseFloat(item.loss_wt).toFixed(3) : '0.000'}
                                                </td>
                                                <td className="border border-gray-300 px-4 py-2">
                                                    {item.rejection_status ? 'Rejected' : 'Accepted'}
                                                </td>
                                            </tr>
                                        );
                                    })
                                )
                            )
                        ) : (
                            <tr>
                                <td colSpan={11} className="border border-gray-300 px-4 py-8 text-center text-gray-500">
                                    {error ? 'Error loading data. Please try again.' : 'No data found for the selected criteria.'}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
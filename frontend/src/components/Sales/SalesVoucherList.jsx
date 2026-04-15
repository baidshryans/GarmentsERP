import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { fetchSalesVoucher, updateEwayTransport } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Plus, Printer, Trash2, FileJson, Truck } from "lucide-react";
import { openAndPrint } from '@/services/print/utils';
import SalesInvoice from '@/services/print/SalesInvoice';
import { useToast } from "@/hooks/use-toast";
import { deleteSalesVoucher } from '../../services/apiService';
import { useSearchParams } from 'react-router-dom';
import { useF2Navigate } from "@/hooks/useF2Navigate";
import apiClient from '@/services/apiClient';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter,
} from "@/components/ui/sheet";

function SalesVoucherList() {
  useF2Navigate("/sales/add/");
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [vouchers, setVouchers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";

  // E-way bill sheet state
  const [ewaySheet, setEwaySheet] = useState(false);
  const [ewayVoucher, setEwayVoucher] = useState(null);
  const [ewayForm, setEwayForm] = useState({
    vehicle_no: '', transporter_name: '', transporter_id: '',
    trans_distance: '', trans_doc_no: '', trans_doc_date: '', mode_of_transport: 'Road',
  });
  const [ewayLoading, setEwayLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const result = await fetchSalesVoucher({ search, page, ordering: sortby });
      if (result.success) {
        setVouchers(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
    };
    fetchData();
  }, [search, page, sortby]);

  const openEwaySheet = (row) => {
    setEwayVoucher(row);
    setEwayForm({
      vehicle_no:        row.vehicle_no        || '',
      transporter_name:  row.transporter_name  || '',
      transporter_id:    row.transporter_id    || '',
      trans_distance:    row.trans_distance    || '',
      trans_doc_no:      row.trans_doc_no      || '',
      trans_doc_date:    row.trans_doc_date    || '',
      mode_of_transport: row.mode_of_transport || 'Road',
    });
    setEwaySheet(true);
  };

  const handleEwaySave = async () => {
    if (!ewayVoucher) return;
    setEwayLoading(true);
    const res = await updateEwayTransport(ewayVoucher.id, ewayForm);
    setEwayLoading(false);
    if (!res.success) {
      toast({ title: 'Save failed', description: JSON.stringify(res.error), variant: 'destructive' });
      return;
    }
    toast({ title: 'Transport details saved' });
  };

  const handleEwayDownload = async () => {
    if (!ewayVoucher) return;
    // Save first, then download
    setEwayLoading(true);
    await updateEwayTransport(ewayVoucher.id, ewayForm);
    try {
      const res = await apiClient.get('/sales/api/generate-eway-bill', {
        params: { bill: ewayVoucher.billno },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `EWAY_${ewayVoucher.billno}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({ title: 'E-Way Bill JSON downloaded', description: ewayVoucher.billno });
    } catch (e) {
      const errText = e.response?.data ? await e.response.data.text() : e.message;
      let detail = errText;
      try { detail = JSON.parse(errText)?.error || errText; } catch {}
      toast({ title: 'E-Way Bill generation failed', description: detail, variant: 'destructive' });
    }
    setEwayLoading(false);
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Link to={`/sales/${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="w-4 h-4" />
          </Link>
          <button
            onClick={() => deleteSalesVoucher(row.original.id, toast)}
            className="p-1.5 rounded text-destructive hover:bg-red-50 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={async () => {
              try {
                const res = await apiClient.get(`/sales/api/sale-voucher/${row.original.id}/print-data/`);
                openAndPrint(<SalesInvoice data={res.data} />);
              } catch (e) {
                toast({ title: 'Print failed', description: 'Could not load invoice data.', variant: 'destructive' });
              }
            }}
            className="text-muted-foreground hover:text-foreground"
            title="Print Invoice"
          >
            <Printer className="w-4 h-4" />
          </button>
          <button
            title="Download e-Invoice JSON"
            onClick={async () => {
              try {
                const res = await apiClient.get('/sales/api/generate-json', {
                  params: { bill: row.original.billno },
                  responseType: 'blob',
                });
                const url = URL.createObjectURL(res.data);
                const a = document.createElement('a');
                a.href = url;
                a.download = `JSON_${row.original.billno}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                toast({ title: 'e-Invoice JSON downloaded', description: row.original.billno });
              } catch (e) {
                const errText = e.response?.data ? await e.response.data.text() : e.message;
                let detail = errText;
                try { detail = JSON.parse(errText)?.error || errText; } catch {}
                toast({ title: 'JSON generation failed', description: detail, variant: 'destructive' });
              }
            }}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors"
          >
            <FileJson className="w-4 h-4" />
          </button>
          <button
            title="Generate E-Way Bill"
            onClick={() => openEwaySheet(row.original)}
            className="text-orange-500 hover:text-orange-700"
          >
            <Truck className="w-4 h-4" />
          </button>
          {(() => {
            const phone = row.original.mobile1 || row.original.mobile2 || row.original.mobile3;
            const hasPhone = !!phone;
            return (
              <button
                onClick={() => {
                  if (hasPhone) {
                    const cleaned = phone.replace(/\D/g, '');
                    window.open(`https://wa.me/${cleaned}`, '_blank');
                  }
                }}
                className={hasPhone ? "text-green-500 hover:text-green-600" : "text-red-500 cursor-not-allowed"}
                title={hasPhone ? `WhatsApp: ${phone}` : "No mobile number available"}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
              </button>
            );
          })()}
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => new Date(getValue()).toLocaleDateString('en-GB').replaceAll('/', '-'),
    },
    { header: "Bill No", accessorKey: "billno" },
    { header: "Party Name", accessorKey: "ldgr_name" },
    {
      header: "Discount",
      accessorKey: "discount",
      cell: ({ getValue }) => {
        const v = parseFloat(getValue() || 0);
        return v > 0 ? v.toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—";
      },
    },
    {
      header: "Total Amount",
      accessorKey: "total_bill_value",
      cell: ({ getValue }) => {
        const v = parseFloat(getValue() || 0);
        return v > 0 ? v.toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—";
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <Input
            type="text"
            value={search}
            onChange={(e) => setParams({ search: e.target.value, sortby })}
            placeholder="Search vouchers..."
            className="max-w-xs"
          />
          <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
            <SelectTrigger className="w-40">
              <span>{sortby ? sortby.replace('-', '↓ ') : "Sort by"}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date1">Date (Old first)</SelectItem>
              <SelectItem value="-date1">Date (New first)</SelectItem>
              <SelectItem value="billno">Bill No (Asc)</SelectItem>
              <SelectItem value="-billno">Bill No (Desc)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Link to="/sales/add/">
          <Button size="sm" className="gap-1.5">
            <Plus className="w-4 h-4" />
            Add Voucher
          </Button>
        </Link>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="w-full h-10" />
          ))}
        </div>
      ) : error ? (
        <div className="text-destructive text-sm">Error: {error}</div>
      ) : (
        <>
          <DataTable columns={columns} data={vouchers} />

          {/* Pagination */}
          <div className="flex items-center justify-between pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        </>
      )}

      {/* E-Way Bill Sheet */}
      <Sheet open={ewaySheet} onOpenChange={setEwaySheet}>
        <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto" aria-describedby={undefined}>
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Truck className="w-5 h-5 text-orange-500" />
              E-Way Bill — {ewayVoucher?.billno}
            </SheetTitle>
          </SheetHeader>

          <div className="flex flex-col gap-4 py-4">
            <p className="text-sm text-muted-foreground">
              Enter transport details below, then download the JSON to upload on the NIC e-Way Bill portal.
            </p>

            {/* Mode of Transport */}
            <div className="flex flex-col gap-1">
              <Label>Mode of Transport</Label>
              <Select
                value={ewayForm.mode_of_transport}
                onValueChange={(v) => setEwayForm(f => ({ ...f, mode_of_transport: v }))}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Road">Road</SelectItem>
                  <SelectItem value="Rail">Rail</SelectItem>
                  <SelectItem value="Air">Air</SelectItem>
                  <SelectItem value="Ship">Ship</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Vehicle No */}
            <div className="flex flex-col gap-1">
              <Label>Vehicle No</Label>
              <Input
                placeholder="e.g. WB01AB1234"
                value={ewayForm.vehicle_no}
                onChange={(e) => setEwayForm(f => ({ ...f, vehicle_no: e.target.value }))}
              />
            </div>

            {/* Transporter Name */}
            <div className="flex flex-col gap-1">
              <Label>Transporter Name</Label>
              <Input
                placeholder="Transporter name"
                value={ewayForm.transporter_name}
                onChange={(e) => setEwayForm(f => ({ ...f, transporter_name: e.target.value }))}
              />
            </div>

            {/* Transporter GSTIN/ID */}
            <div className="flex flex-col gap-1">
              <Label>Transporter GSTIN / ID</Label>
              <Input
                placeholder="Transporter GSTIN"
                value={ewayForm.transporter_id}
                onChange={(e) => setEwayForm(f => ({ ...f, transporter_id: e.target.value }))}
              />
            </div>

            {/* Distance */}
            <div className="flex flex-col gap-1">
              <Label>Approx. Distance (km)</Label>
              <Input
                type="number"
                placeholder="0"
                value={ewayForm.trans_distance}
                onChange={(e) => setEwayForm(f => ({ ...f, trans_distance: e.target.value }))}
              />
            </div>

            {/* Transport Doc No */}
            <div className="flex flex-col gap-1">
              <Label>Transport Document No</Label>
              <Input
                placeholder="LR / RR / Airway Bill No"
                value={ewayForm.trans_doc_no}
                onChange={(e) => setEwayForm(f => ({ ...f, trans_doc_no: e.target.value }))}
              />
            </div>

            {/* Transport Doc Date */}
            <div className="flex flex-col gap-1">
              <Label>Transport Document Date</Label>
              <Input
                type="date"
                value={ewayForm.trans_doc_date}
                onChange={(e) => setEwayForm(f => ({ ...f, trans_doc_date: e.target.value }))}
              />
            </div>
          </div>

          <SheetFooter className="flex gap-2 flex-col sm:flex-row">
            <Button
              variant="outline"
              onClick={handleEwaySave}
              disabled={ewayLoading}
              className="flex-1"
            >
              Save Details
            </Button>
            <Button
              onClick={handleEwayDownload}
              disabled={ewayLoading}
              className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
            >
              <Truck className="w-4 h-4 mr-1" />
              Download JSON
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default SalesVoucherList

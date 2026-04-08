
import React, { useCallback, useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { Plus, Pencil, Trash2, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
    Sheet, SheetContent,
} from '@/components/ui/sheet';
import { useToast } from '@/hooks/use-toast';
import {
    getOpeningBalances,
    createOpeningBalance,
    updateOpeningBalance,
    deleteOpeningBalance,
    getLedgerList,
} from '@/services/apiService';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function currentAndPastYears(count = 5) {
    const years = [];
    const now = new Date();
    const startYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
    for (let i = 0; i < count; i++) {
        const y = startYear - i;
        years.push(`${y}-${String(y + 1).slice(-2)}`);
    }
    return years;
}

const YEARS = currentAndPastYears();

const Field = ({ label, required, error, hint, children }) => (
    <div className="flex flex-col gap-2">
        <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
            {label}{required && <span className="text-red-400 ml-1">*</span>}
        </label>
        {children}
        {hint && !error && <p className="text-xs text-gray-400">{hint}</p>}
        {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
);

// ─── Entry form (used inside Sheet) ──────────────────────────────────────────

const EntryForm = ({ ledgers, initial, onSave, onClose }) => {
    const { register, handleSubmit, control, watch, setValue, formState: { errors, isSubmitting } } = useForm({
        defaultValues: {
            ldgr: initial?.ldgr ? String(initial.ldgr) : '',
            type: initial ? (Number(initial.debit) > 0 ? 'debit' : 'credit') : 'debit',
            amount: initial ? String(Number(initial.debit) > 0 ? initial.debit : initial.credit) : '',
            acc_year: initial?.acc_year || YEARS[0],
        },
    });

    const balanceType = watch('type');

    const inputCls = 'h-10 text-sm border-gray-200 focus:border-violet-400 focus:ring-violet-100';
    const triggerCls = 'h-10 text-sm border-gray-200 focus:border-violet-400';

    const onSubmit = (data) => {
        const amount = parseFloat(data.amount) || 0;
        onSave({
            ldgr: parseInt(data.ldgr),
            debit: data.type === 'debit' ? amount : 0,
            credit: data.type === 'credit' ? amount : 0,
            acc_year: data.acc_year,
        });
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col h-full">
            <div className="flex items-center gap-3 px-6 py-4 bg-violet-50 border-b border-violet-100 shrink-0">
                <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">
                    {initial ? '✎' : '+'}
                </span>
                <div>
                    <p className="text-sm font-bold text-primary tracking-widest uppercase">
                        {initial ? 'Edit Opening Balance' : 'Add Opening Balance'}
                    </p>
                    <p className="text-xs text-primary mt-0.5">Enter debit or credit opening amount</p>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
                <Field label="Ledger Account" required error={errors.ldgr?.message}>
                    <Controller name="ldgr" control={control} rules={{ required: 'Select a ledger' }} render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value}>
                            <SelectTrigger className={triggerCls}>
                                <SelectValue placeholder="Select ledger…" />
                            </SelectTrigger>
                            <SelectContent className="max-h-64 overflow-y-auto">
                                {ledgers.map(l => (
                                    <SelectItem key={l.id} value={String(l.id)}>
                                        {l.display_name || l.ac_name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )} />
                </Field>

                <Field label="Balance Type" required>
                    <Controller name="type" control={control} render={({ field }) => (
                        <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                            <button
                                type="button"
                                className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors ${field.value === 'debit' ? 'bg-primary text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
                                onClick={() => field.onChange('debit')}
                            >
                                <TrendingUp className="w-4 h-4" />
                                Debit (Dr)
                            </button>
                            <button
                                type="button"
                                className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors ${field.value === 'credit' ? 'bg-primary text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
                                onClick={() => field.onChange('credit')}
                            >
                                <TrendingDown className="w-4 h-4" />
                                Credit (Cr)
                            </button>
                        </div>
                    )} />
                </Field>

                <Field label="Amount" required error={errors.amount?.message}>
                    <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">₹</span>
                        <Input
                            className={`${inputCls} pl-7`}
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="0.00"
                            {...register('amount', {
                                required: 'Amount is required',
                                min: { value: 0.01, message: 'Must be greater than 0' },
                            })}
                        />
                    </div>
                </Field>

                <Field label="Accounting Year" required error={errors.acc_year?.message}>
                    <Controller name="acc_year" control={control} rules={{ required: 'Select year' }} render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value}>
                            <SelectTrigger className={triggerCls}>
                                <SelectValue placeholder="Select year…" />
                            </SelectTrigger>
                            <SelectContent>
                                {YEARS.map(y => (
                                    <SelectItem key={y} value={y}>{y}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )} />
                </Field>
            </div>

            <div className="flex gap-3 px-6 py-4 border-t border-gray-100 shrink-0">
                <Button
                    type="submit"
                    disabled={isSubmitting}
                    className="flex-1 bg-primary hover:bg-primary text-white font-semibold"
                >
                    {isSubmitting ? 'Saving…' : initial ? 'Update' : 'Save'}
                </Button>
                <Button type="button" variant="outline" onClick={onClose} className="flex-1">
                    Cancel
                </Button>
            </div>
        </form>
    );
};

// ─── Main page ────────────────────────────────────────────────────────────────

const OpeningBalance = () => {
    const { toast } = useToast();
    const [balances, setBalances] = useState([]);
    const [ledgers, setLedgers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [sheetOpen, setSheetOpen] = useState(false);
    const [editing, setEditing] = useState(null); // null = add mode, object = edit mode

    const load = useCallback(async () => {
        setLoading(true);
        const [balRes, ldgrRes] = await Promise.all([
            getOpeningBalances(),
            getLedgerList(),
        ]);
        if (balRes.success) setBalances(balRes.data);
        if (ldgrRes.success) setLedgers(ldgrRes.data);
        setLoading(false);
    }, []);

    useEffect(() => { load(); }, [load]);

    const openAdd = () => { setEditing(null); setSheetOpen(true); };
    const openEdit = (row) => { setEditing(row); setSheetOpen(true); };
    const closeSheet = () => setSheetOpen(false);

    const handleSave = async (payload) => {
        const res = editing
            ? await updateOpeningBalance(editing.id, payload)
            : await createOpeningBalance(payload);

        if (res.success) {
            toast({ title: editing ? 'Updated' : 'Saved', description: `Opening balance ${editing ? 'updated' : 'added'}.` });
            setSheetOpen(false);
            load();
        } else {
            const msg = typeof res.error === 'object'
                ? Object.values(res.error).flat().join(' ')
                : res.error;
            toast({ title: 'Error', description: msg });
        }
    };

    const handleDelete = async (row) => {
        if (!window.confirm(`Delete opening balance for "${row.ledger_name}"?`)) return;
        const res = await deleteOpeningBalance(row.id);
        if (res.success) {
            toast({ title: 'Deleted', description: `Balance for "${row.ledger_name}" removed.` });
            load();
        } else {
            toast({ title: 'Error', description: res.error });
        }
    };

    // Group by accounting year for display
    const byYear = balances.reduce((acc, b) => {
        (acc[b.acc_year] = acc[b.acc_year] || []).push(b);
        return acc;
    }, {});
    const sortedYears = Object.keys(byYear).sort().reverse();

    return (
        <div className="max-w-4xl mx-auto pb-12">

            {/* ── Header ──────────────────────────────────────────────── */}
            <div className="flex items-start justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Opening Balances</h1>
                    <p className="text-sm text-gray-400 mt-1">
                        {loading ? 'Loading…' : `${balances.length} record${balances.length !== 1 ? 's' : ''}`}
                    </p>
                </div>
                <div className="flex gap-3 mt-1">
                    <Button variant="outline" className="h-10 px-4 gap-2 text-sm" onClick={load} disabled={loading}>
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button
                        className="h-10 px-5 gap-2 bg-primary hover:bg-primary text-white font-semibold shadow-sm"
                        onClick={openAdd}
                    >
                        <Plus className="w-4 h-4" />
                        Add Balance
                    </Button>
                </div>
            </div>

            {/* ── Content ─────────────────────────────────────────────── */}
            {loading && (
                <div className="space-y-3">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="h-12 bg-gray-100 rounded-xl animate-pulse" />
                    ))}
                </div>
            )}

            {!loading && balances.length === 0 && (
                <div className="rounded-xl border border-violet-100 bg-white shadow-sm">
                    <div className="flex flex-col items-center gap-4 py-16 text-center">
                        <div className="w-12 h-12 rounded-full bg-violet-50 flex items-center justify-center">
                            <TrendingUp className="w-6 h-6 text-violet-300" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-gray-600">No opening balances yet</p>
                            <p className="text-xs text-gray-400 mt-1">Add opening balances for each ledger account</p>
                        </div>
                        <Button
                            className="gap-2 bg-primary hover:bg-primary text-white"
                            onClick={openAdd}
                        >
                            <Plus className="w-4 h-4" />
                            Add First Balance
                        </Button>
                    </div>
                </div>
            )}

            {!loading && sortedYears.map(year => {
                const rows = byYear[year];
                const totalDr = rows.reduce((s, r) => s + (Number(r.debit) || 0), 0);
                const totalCr = rows.reduce((s, r) => s + (Number(r.credit) || 0), 0);

                return (
                    <div key={year} className="rounded-xl border border-violet-100 bg-white shadow-sm overflow-hidden mb-4">
                        {/* Year header */}
                        <div className="flex items-center justify-between px-6 py-3 bg-violet-50 border-b border-violet-100">
                            <div className="flex items-center gap-3">
                                <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">
                                    {year.slice(0, 2)}
                                </span>
                                <span className="text-sm font-bold text-primary tracking-widest uppercase">
                                    FY {year}
                                </span>
                                <span className="text-xs text-gray-400">{rows.length} accounts</span>
                            </div>
                            <div className="flex gap-6 text-xs">
                                <span className="text-green-700 font-medium">
                                    Dr: ₹{totalDr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                </span>
                                <span className="text-red-600 font-medium">
                                    Cr: ₹{totalCr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                </span>
                            </div>
                        </div>

                        {/* Table */}
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-100">
                                    <th className="text-left text-[10px] font-semibold text-gray-400 uppercase tracking-widest px-6 py-2.5">Ledger</th>
                                    <th className="text-right text-[10px] font-semibold text-gray-400 uppercase tracking-widest px-4 py-2.5 w-36">Debit (Dr)</th>
                                    <th className="text-right text-[10px] font-semibold text-gray-400 uppercase tracking-widest px-4 py-2.5 w-36">Credit (Cr)</th>
                                    <th className="w-20 px-4 py-2.5"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((row, idx) => (
                                    <tr key={row.id} className={`group border-b border-gray-50 last:border-0 hover:bg-violet-50/40 transition-colors ${idx % 2 === 1 ? 'bg-gray-50/40' : ''}`}>
                                        <td className="px-6 py-3 font-medium text-gray-800">{row.ledger_name}</td>
                                        <td className="px-4 py-3 text-right tabular-nums">
                                            {Number(row.debit) > 0 ? (
                                                <span className="text-green-700 font-medium">
                                                    ₹{Number(row.debit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                </span>
                                            ) : <span className="text-gray-300">—</span>}
                                        </td>
                                        <td className="px-4 py-3 text-right tabular-nums">
                                            {Number(row.credit) > 0 ? (
                                                <span className="text-red-600 font-medium">
                                                    ₹{Number(row.credit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                </span>
                                            ) : <span className="text-gray-300">—</span>}
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <button
                                                    onClick={() => openEdit(row)}
                                                    className="p-1.5 rounded hover:bg-violet-100 text-primary transition-colors"
                                                    title="Edit"
                                                >
                                                    <Pencil className="w-3.5 h-3.5" />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(row)}
                                                    className="p-1.5 rounded hover:bg-red-50 text-red-400 transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                );
            })}

            {/* ── Add / Edit Sheet ─────────────────────────────────────── */}
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                <SheetContent side="right" className="w-[400px] sm:max-w-[400px] flex flex-col p-0">
                    {sheetOpen && (
                        <EntryForm
                            key={editing?.id ?? 'new'}
                            ledgers={ledgers}
                            initial={editing}
                            onSave={handleSave}
                            onClose={closeSheet}
                        />
                    )}
                </SheetContent>
            </Sheet>
        </div>
    );
};

export default OpeningBalance;

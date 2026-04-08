
import React, { useEffect, useState, useCallback } from 'react';
import { useForm, Controller } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useParams, useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Sheet,
    SheetContent,
} from "@/components/ui/sheet";
import { ChevronRight, ChevronDown, Folder, FolderOpen, Paperclip, Copy, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import LedgerDocuments from "@/components/shared/LedgerDocuments";
import { Checkbox } from "@/components/ui/checkbox";
import { renderErrorTree } from "@/Utils";
import { createLedger, getAccountGroup, getStates, getLedger, updateLedger, getTypes, addLedgerRole, removeLedgerRole, setPrimaryLedgerRole, fetchTDSSections, checkLedgerName } from '@/services/apiService';
import PhoneInput, { makePhoneValidator } from "@/components/ui/PhoneInput";

// ─── Account tree helpers ─────────────────────────────────────────────────────

function buildAccountTree(flatList) {
    const map = {};
    const roots = [];
    flatList.forEach(item => { map[item.id] = { ...item, children: [] }; });
    flatList.forEach(item => {
        if (item.parent && map[item.parent]) {
            map[item.parent].children.push(map[item.id]);
        } else if (!item.parent) {
            roots.push(map[item.id]);
        }
    });
    return roots;
}

const GroupPickerNode = ({ node, level, onSelect }) => {
    const hasChildren = node.children?.length > 0;
    const [open, setOpen] = useState(level === 0);
    const indent = level * 20;

    return (
        <div>
            <div
                className="group flex items-center gap-2 py-2 pr-3 rounded-lg hover:bg-violet-50 cursor-pointer transition-colors"
                style={{ paddingLeft: `${indent + 8}px` }}
                onClick={() => onSelect(node)}
            >
                {hasChildren ? (
                    <button
                        type="button"
                        className="shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-violet-100 text-primary"
                        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
                    >
                        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                ) : (
                    <span className="w-5 h-5 shrink-0 flex items-center justify-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                    </span>
                )}
                {hasChildren
                    ? open
                        ? <FolderOpen className={`w-4 h-4 shrink-0 ${level === 0 ? 'text-primary' : 'text-violet-400'}`} />
                        : <Folder className={`w-4 h-4 shrink-0 ${level === 0 ? 'text-primary' : 'text-violet-400'}`} />
                    : null
                }
                {node.code && (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 tracking-wider ${level === 0 ? 'bg-violet-200 text-primary' : 'bg-gray-100 text-gray-500'}`}>
                        {node.code}
                    </span>
                )}
                <span className={`text-sm truncate ${level === 0 ? 'font-semibold text-primary' : 'text-gray-700'} group-hover:text-primary`}>
                    {node.name}
                </span>
                {hasChildren && (
                    <span className="ml-auto text-[10px] text-gray-400 shrink-0">{node.children.length}</span>
                )}
            </div>
            {open && hasChildren && (
                <div className={level === 0 ? 'ml-3 border-l border-violet-100 pl-1 mb-1' : 'ml-3 border-l border-gray-100 pl-1'}>
                    {node.children.map(child => (
                        <GroupPickerNode key={child.id} node={child} level={level + 1} onSelect={onSelect} />
                    ))}
                </div>
            )}
        </div>
    );
};

// ─── Primitives ───────────────────────────────────────────────────────────────

const SectionCard = ({ number, title, children }) => (
    <div className="rounded-xl border border-violet-100 bg-white shadow-sm overflow-hidden">
        {/* Card header */}
        <div className="flex items-center gap-3 px-7 py-4 bg-violet-50 border-b border-violet-100">
            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">
                {number}
            </span>
            <span className="text-sm font-bold text-primary tracking-widest uppercase">
                {title}
            </span>
        </div>
        {/* Card body */}
        <div className="px-7 py-6 space-y-6">
            {children}
        </div>
    </div>
);

const Field = ({ label, required, error, children }) => (
    <div className="flex flex-col gap-2">
        <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
            {label}{required && <span className="text-red-400 ml-1">*</span>}
        </label>
        {children}
        {error && <p className="text-xs text-red-500 -mt-1">{error}</p>}
    </div>
);

// ─── Component ────────────────────────────────────────────────────────────────

const LedgerForm = () => {
    const { id } = useParams();
    const { toast } = useToast();
    const navigate = useNavigate();
    const acGroupBtnRef = React.useRef(null);

    const { register, handleSubmit, control, reset, watch, setValue, getValues, formState: { errors } } = useForm({
        defaultValues: {
            salutation: 'none',
            ac_name: '',
            display_name: '',
            b2b: 'false',
            ac_group: '',
            dob: '',
            anniversary: '',
            add1: '',
            add2: '',
            city: '',
            pincode: '',
            state: 'none',
            ship_add1: '',
            ship_add2: '',
            ship_city: '',
            ship_pincode: '',
            ship_state: 'none',
            phone1: '',
            phone2: '',
            phone3: '',
            mobile1: '',
            mobile2: '',
            mobile3: '',
            fax: '',
            email: '',
            pan: '',
            gst: '',
            aadhar: '',
            passport: '',
            dl_no: '',
            remarks: '',
            tds_applicable: false,
            tds_section: '',
            tds_deductor_type: '',
        },
    });

    const [states, setStates] = useState([]);
    const [shippingSameAsBilling, setShippingSameAsBilling] = useState(true);
    const [accounts, setAccounts] = useState([]);
    const [accountTree, setAccountTree] = useState([]);
    const [types, setTypes] = useState([]);
    const [pickerOpen, setPickerOpen] = useState(false);
    // ledgerRoles: array of { role, is_primary }
    const [ledgerRoles, setLedgerRoles] = useState([]);
    const [roleLoading, setRoleLoading] = useState(null);  // role code being toggled
    const [tdsSections, setTdsSections] = useState([]);
    const [nameCheck, setNameCheck] = useState({ checking: false, exists: null }); // null = not checked yet
    const nameCheckTimer = React.useRef(null);

    // Derived helpers
    const activeRoleCodes = ledgerRoles.map(r => r.role ?? r);   // support both old string[] and new {role,is_primary}[]
    const primaryRole = (ledgerRoles.find(r => r.is_primary)?.role)
        ?? (ledgerRoles[0]?.role ?? ledgerRoles[0]);              // fallback to first

    const NON_CUSTOMER_ROLES = ['DL','KR','VD','CA','BA','SC','SD','REF','EXP','INC','HM','OTH'];
    const hasNonCustomerRole = activeRoleCodes.some(r => NON_CUSTOMER_ROLES.includes(r));

    const acName = watch('ac_name');

    // Real-time ledger name uniqueness check (only for non-customer ledgers)
    useEffect(() => {
        if (nameCheckTimer.current) clearTimeout(nameCheckTimer.current);
        if (!hasNonCustomerRole || !acName || acName.trim().length < 2) {
            setNameCheck({ checking: false, exists: null });
            return;
        }
        setNameCheck({ checking: true, exists: null });
        nameCheckTimer.current = setTimeout(async () => {
            const res = await checkLedgerName(acName.trim(), id || null);
            setNameCheck({ checking: false, exists: res.exists });
        }, 500);
        return () => clearTimeout(nameCheckTimer.current);
    }, [acName, hasNonCustomerRole, id]);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [statesRes, typesRes, accountsRes] = await Promise.all([
                    getStates(),
                    getTypes(),
                    getAccountGroup(),
                ]);
                setStates(statesRes.data);
                setTypes(typesRes.data);
                setAccounts(accountsRes.data);
                setAccountTree(buildAccountTree(accountsRes.data));

                const tdsRes = await fetchTDSSections();
                if (tdsRes.success) {
                    const d = tdsRes.data;
                    setTdsSections(Array.isArray(d) ? d : d?.results ?? []);
                }

                if (id) {
                    const { data } = await getLedger(id);
                    // Determine if shipping address differs from billing
                    const shipDiffers = (
                        (data.ship_add1 && data.ship_add1 !== data.add1) ||
                        (data.ship_add2 && data.ship_add2 !== data.add2) ||
                        (data.ship_city && data.ship_city !== data.city) ||
                        (data.ship_pincode && data.ship_pincode !== data.pincode) ||
                        (data.ship_state && data.ship_state !== data.state)
                    );
                    setShippingSameAsBilling(!shipDiffers);
                    reset({
                        ...data,
                        b2b: data.b2b?.toString() ?? 'false',
                        dob: data.dob || '',
                        anniversary: data.anniversary || '',
                        ac_group: data.ac_group?.toString() || '',
                        tds_applicable: data.tds_applicable ?? false,
                        tds_section: data.tds_section ? String(data.tds_section) : '',
                        tds_deductor_type: data.tds_deductor_type ?? '',
                        // If no shipping data yet, mirror billing
                        ship_add1:    data.ship_add1    || data.add1    || '',
                        ship_add2:    data.ship_add2    || data.add2    || '',
                        ship_city:    data.ship_city    || data.city    || '',
                        ship_pincode: data.ship_pincode || data.pincode || '',
                        ship_state:   data.ship_state   || data.state   || 'none',
                    });
                    // Load existing roles (API now returns [{role, is_primary}])
                    setLedgerRoles(data.roles || []);
                }
            } catch (error) {
                console.error("Error loading ledger form:", error);
                toast({ title: "Error", description: "Failed to load form data." });
            }
        };
        fetchAll();
    }, [id, reset]);



    const validatePhone    = makePhoneValidator();
    const validatePAN      = (v) => !v || /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(v)       || 'Invalid PAN — expected format: ABCDE1234F';
    const validateGST      = (v) => !v || /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9]{1}Z[0-9A-Z]{1}$/.test(v) || 'Invalid GST — expected format: 22AAAAA0000A1Z5';
    const validateAadhar   = (v) => !v || /^[0-9]{12}$/.test(v)                        || 'Aadhar must be exactly 12 digits';
    const validatePassport = (v) => !v || /^[A-Z][0-9]{7}$/.test(v)                    || 'Invalid passport — expected format: A1234567';

    const onSubmit = async (data) => {
        if (activeRoleCodes.length === 0) {
            toast({ title: "Select at least one role", description: "Every ledger must have at least one role.", variant: "destructive" });
            return;
        }
        if (nameCheck.exists === true) {
            toast({ title: "Duplicate ledger name", description: "A ledger with this name already exists. Please use a different name.", variant: "destructive" });
            return;
        }
        try {
            const payload = {
            ...data,
            b2b: data.b2b === 'true',
            dob: data.dob || null,
            anniversary: data.anniversary || null,
        };
            const response = id ? await updateLedger(id, payload) : await createLedger(payload);
            if (response.success) {
                const newId = response.data?.id ?? id;
                // For new ledgers, sync locally-chosen roles to the API
                if (!id && newId) {
                    for (const r of ledgerRoles) {
                        const roleCode = r.role ?? r;
                        await addLedgerRole(newId, roleCode);
                    }
                    // Set primary role
                    const primary = ledgerRoles.find(r => r.is_primary)?.role ?? ledgerRoles[0]?.role ?? ledgerRoles[0];
                    if (primary) await setPrimaryLedgerRole(newId, primary);
                }
                toast({ title: "Success", description: `Ledger ${id ? 'updated' : 'created'} successfully.` });
                setTimeout(() => navigate("/crm/ledger"), 1200);
            } else {
                toast({ title: "Submission failed", description: renderErrorTree(response.error) });
            }
        } catch (error) {
            console.error('Error submitting ledger:', error);
            toast({ title: "Error", description: "Failed to save ledger. Please try again." });
        }
    };

    const handleRoleToggle = async (roleCode, checked) => {
        setRoleLoading(roleCode);
        if (id) {
            // Edit mode — call API immediately
            const res = checked
                ? await addLedgerRole(id, roleCode)
                : await removeLedgerRole(id, roleCode);
            if (res.success) {
                setLedgerRoles(res.data.roles);
            } else {
                const msg = res.error?.error || res.error || 'Failed to update role';
                toast({ title: "Role update failed", description: String(msg), variant: "destructive" });
            }
        } else {
            // Create mode — manage locally; will be sent on first save
            setLedgerRoles(prev => {
                if (checked) {
                    const alreadyExists = prev.some(r => (r.role ?? r) === roleCode);
                    if (alreadyExists) return prev;
                    const isFirst = prev.length === 0;
                    return [...prev, { role: roleCode, is_primary: isFirst }];
                }
                const filtered = prev.filter(r => (r.role ?? r) !== roleCode);
                // If we removed the primary, promote the first remaining
                const wasPrimary = prev.find(r => (r.role ?? r) === roleCode)?.is_primary;
                if (wasPrimary && filtered.length > 0) {
                    filtered[0] = { ...filtered[0], is_primary: true };
                }
                return filtered;
            });
        }
        setRoleLoading(null);
    };

    const handleSetPrimary = async (roleCode) => {
        setRoleLoading(roleCode);
        if (id) {
            const res = await setPrimaryLedgerRole(id, roleCode);
            if (res.success) {
                setLedgerRoles(res.data.roles);
            } else {
                toast({ title: "Failed to set primary role", description: String(res.error?.error || res.error), variant: "destructive" });
            }
        } else {
            setLedgerRoles(prev =>
                prev.map(r => ({ ...r, is_primary: (r.role ?? r) === roleCode }))
            );
        }
        setRoleLoading(null);
    };

    const inputCls = "h-10 text-sm border-gray-200 focus:border-violet-400 focus:ring-violet-100";
    const triggerCls = "h-10 text-sm border-gray-200 focus:border-violet-400";

    return (
        <div className="max-w-4xl mx-auto pb-12">

            {/* ── Page header ─────────────────────────────────────────────── */}
            <div className="flex items-start justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                        {id ? 'Edit Ledger' : 'New Ledger'}
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">
                        {id
                            ? `Editing record #${id}`
                            : 'Create a new ledger account for a customer, supplier, or other party'}
                    </p>
                </div>
                <div className="flex gap-3 mt-1">
                    <Button type="button" variant="outline" onClick={() => navigate('/crm/ledger')} className="h-10 px-5">
                        Cancel
                    </Button>
                    <Button
                        type="submit"
                        form="ledgerForm"
                        className="h-10 px-6 bg-primary hover:bg-primary text-white font-semibold shadow-sm"
                    >
                        {id ? 'Update Ledger' : 'Save Ledger'}
                    </Button>
                </div>
            </div>

            <form id="ledgerForm" onSubmit={handleSubmit(onSubmit)} className="space-y-6">

                {/* ── Section 1: Identity ──────────────────────────────────── */}
                <SectionCard number="1" title="Identity">

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                        <Field label="Salutation">
                            <Controller name="salutation" control={control} render={({ field }) => (
                                <Select onValueChange={field.onChange} value={field.value}>
                                    <SelectTrigger className={triggerCls}><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">— None —</SelectItem>
                                        <SelectItem value="shri">Shri</SelectItem>
                                        <SelectItem value="smt">Smt.</SelectItem>
                                        <SelectItem value="ms">Ms.</SelectItem>
                                        <SelectItem value="m/s">M/S.</SelectItem>
                                    </SelectContent>
                                </Select>
                            )} />
                        </Field>

                        <Field label="Party Name" required>
                            <div className="relative">
                                <Input
                                    className={`${inputCls} pr-8 ${nameCheck.exists ? 'border-red-400 focus:border-red-400' : nameCheck.exists === false && hasNonCustomerRole ? 'border-green-400 focus:border-green-400' : ''}`}
                                    {...register("ac_name")}
                                    required
                                    placeholder="Full legal name"
                                />
                                {hasNonCustomerRole && (
                                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
                                        {nameCheck.checking && <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />}
                                        {!nameCheck.checking && nameCheck.exists === false && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                                        {!nameCheck.checking && nameCheck.exists === true && <XCircle className="w-4 h-4 text-red-500" />}
                                    </span>
                                )}
                            </div>
                            {nameCheck.exists === true && (
                                <p className="text-xs text-red-500 -mt-1">A ledger with this name already exists.</p>
                            )}
                        </Field>

                        <Field label="Display Name" required>
                            <Input className={inputCls} {...register("display_name")} required placeholder="Name on bills" />
                        </Field>

                        <Field label="Business Type">
                            <Controller name="b2b" control={control} render={({ field }) => (
                                <Select onValueChange={field.onChange} value={field.value}>
                                    <SelectTrigger className={triggerCls}><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="false">Retail (B2C)</SelectItem>
                                        <SelectItem value="true">Wholesale (B2B)</SelectItem>
                                    </SelectContent>
                                </Select>
                            )} />
                        </Field>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                        <Field label="Account Group">
                            <Controller name="ac_group" control={control} render={({ field }) => {
                                const selected = accounts.find(a => a.id.toString() === field.value);
                                return (
                                    <>
                                        <button
                                            ref={acGroupBtnRef}
                                            type="button"
                                            onClick={() => setPickerOpen(true)}
                                            className="w-full h-10 flex items-center gap-2 px-3 rounded-md border border-gray-200 bg-white text-sm text-left hover:border-violet-400 transition-colors focus:outline-none focus:border-violet-400"
                                        >
                                            {selected ? (
                                                <>
                                                    {selected.code && (
                                                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-100 text-primary tracking-wider shrink-0">
                                                            {selected.code}
                                                        </span>
                                                    )}
                                                    <span className="text-gray-700 truncate">{selected.name}</span>
                                                </>
                                            ) : (
                                                <span className="text-gray-400">Select group…</span>
                                            )}
                                            <ChevronRight className="w-3.5 h-3.5 text-gray-300 ml-auto shrink-0" />
                                        </button>

                                        <Sheet open={pickerOpen} onOpenChange={setPickerOpen}>
                                            <SheetContent
                                                side="right"
                                                className="w-[400px] sm:max-w-[400px] flex flex-col p-0"
                                                onCloseAutoFocus={(e) => {
                                                    e.preventDefault();
                                                    acGroupBtnRef.current?.focus();
                                                }}
                                            >
                                                <div className="flex items-center gap-3 px-6 py-4 bg-violet-50 border-b border-violet-100 shrink-0">
                                                    <span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">≡</span>
                                                    <div>
                                                        <p className="text-sm font-bold text-primary tracking-widest uppercase">Select Account Group</p>
                                                        <p className="text-xs text-primary mt-0.5">Click a group to assign it</p>
                                                    </div>
                                                </div>
                                                <div className="flex-1 overflow-y-auto px-3 py-3">
                                                    {accountTree.map(node => (
                                                        <GroupPickerNode
                                                            key={node.id}
                                                            node={node}
                                                            level={0}
                                                            onSelect={(n) => {
                                                                field.onChange(n.id.toString());
                                                                setPickerOpen(false);
                                                            }}
                                                        />
                                                    ))}
                                                </div>
                                            </SheetContent>
                                        </Sheet>
                                    </>
                                );
                            }} />
                        </Field>

                        <Field label="Birthday">
                            <Input className={inputCls} type="date" {...register("dob")} />
                        </Field>

                        <Field label="Anniversary">
                            <Input className={inputCls} type="date" {...register("anniversary")} />
                        </Field>
                    </div>

                    {/* ── Roles — unified panel, always visible ── */}
                    {types.length > 0 && (
                        <div className="border-t border-gray-100 pt-4">
                            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">
                                Ledger Roles
                            </p>
                            <p className="text-xs text-gray-400 mb-3">
                                Select one or more roles. The ★ marks the primary role — click it to change.
                                A ledger with multiple roles appears in all relevant lists (e.g. a vendor who is also a customer appears in both sales and purchases).
                            </p>
                            <div className="flex flex-wrap gap-x-6 gap-y-3">
                                {types.map((t) => {
                                    const isChecked = activeRoleCodes.includes(t.code);
                                    const isPrimary = primaryRole === t.code;
                                    const isLoading = roleLoading === t.code;
                                    return (
                                        <div key={t.code} className="flex items-center gap-2">
                                            <Checkbox
                                                id={`role-${t.code}`}
                                                checked={isChecked}
                                                disabled={isLoading || (!!id && isChecked && isPrimary && activeRoleCodes.length === 1)}
                                                onCheckedChange={(checked) => handleRoleToggle(t.code, !!checked)}
                                            />
                                            <label
                                                htmlFor={`role-${t.code}`}
                                                className={`text-xs cursor-pointer select-none ${isChecked ? 'text-gray-800 font-medium' : 'text-gray-400'}`}
                                            >
                                                {t.name}
                                            </label>
                                            {/* Primary star — only shown when role is active */}
                                            {isChecked && (
                                                <button
                                                    type="button"
                                                    title={isPrimary ? 'Primary role' : 'Set as primary'}
                                                    disabled={isLoading || isPrimary}
                                                    onClick={() => handleSetPrimary(t.code)}
                                                    className={`text-sm leading-none transition-colors ${isPrimary ? 'text-primary cursor-default' : 'text-gray-300 hover:text-violet-400'}`}
                                                >
                                                    ★
                                                </button>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                </SectionCard>

                {/* ── Section 2: Contact & Address ─────────────────────────── */}
                <SectionCard number="2" title="Contact & Address">

                    {/* ── Billing Address ── */}
                    <div className="mb-1">
                        <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-3">
                            Billing Address
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                            <Field label="Address Line 1">
                                <Input className={inputCls}
                                    {...register("add1", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_add1", e.target.value);
                                        }
                                    })}
                                    placeholder="Street / Building" />
                            </Field>
                            <Field label="Address Line 2">
                                <Input className={inputCls}
                                    {...register("add2", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_add2", e.target.value);
                                        }
                                    })}
                                    placeholder="Area / Locality" />
                            </Field>
                            <Field label="City">
                                <Input className={inputCls}
                                    {...register("city", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_city", e.target.value);
                                        }
                                    })}
                                    placeholder="City" />
                            </Field>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-5 mt-5">
                            <Field label="Pincode">
                                <Input className={inputCls}
                                    {...register("pincode", {
                                        onChange: (e) => {
                                            if (shippingSameAsBilling) setValue("ship_pincode", e.target.value);
                                        }
                                    })}
                                    placeholder="6-digit pincode" maxLength={6} />
                            </Field>
                            <Field label="State">
                                <Controller name="state" control={control} render={({ field }) => (
                                    <Select
                                        onValueChange={(v) => {
                                            field.onChange(v);
                                            if (shippingSameAsBilling) setValue("ship_state", v);
                                        }}
                                        value={field.value}
                                    >
                                        <SelectTrigger className={triggerCls}><SelectValue placeholder="Select state" /></SelectTrigger>
                                        <SelectContent className="max-h-60 overflow-y-auto">
                                            <SelectItem value="none">— Select —</SelectItem>
                                            {states.map((s) => (
                                                <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )} />
                            </Field>
                        </div>
                    </div>

                    {/* ── Shipping Address ── */}
                    <div className="border-t border-gray-100 pt-5 mt-2">
                        <div className="flex items-center justify-between mb-3">
                            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
                                Shipping Address
                            </p>
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                                <Checkbox
                                    checked={shippingSameAsBilling}
                                    onCheckedChange={(checked) => {
                                        setShippingSameAsBilling(checked);
                                        if (checked) {
                                            // Mirror billing → shipping immediately
                                            setValue("ship_add1",    getValues("add1")    || '');
                                            setValue("ship_add2",    getValues("add2")    || '');
                                            setValue("ship_city",    getValues("city")    || '');
                                            setValue("ship_pincode", getValues("pincode") || '');
                                            setValue("ship_state",   getValues("state")   || 'none');
                                        }
                                    }}
                                />
                                <span className="text-xs text-gray-500">Same as billing address</span>
                            </label>
                        </div>

                        {shippingSameAsBilling ? (
                            <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-3 flex items-center gap-2 text-xs text-gray-400">
                                <Copy className="w-3.5 h-3.5 shrink-0" />
                                Shipping address is the same as billing. Uncheck above to enter a different address.
                            </div>
                        ) : (
                            <>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                                    <Field label="Address Line 1">
                                        <Input className={inputCls} {...register("ship_add1")} placeholder="Street / Building" />
                                    </Field>
                                    <Field label="Address Line 2">
                                        <Input className={inputCls} {...register("ship_add2")} placeholder="Area / Locality" />
                                    </Field>
                                    <Field label="City">
                                        <Input className={inputCls} {...register("ship_city")} placeholder="City" />
                                    </Field>
                                </div>
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-5 mt-5">
                                    <Field label="Pincode">
                                        <Input className={inputCls} {...register("ship_pincode")} placeholder="6-digit pincode" maxLength={6} />
                                    </Field>
                                    <Field label="State">
                                        <Controller name="ship_state" control={control} render={({ field }) => (
                                            <Select onValueChange={field.onChange} value={field.value || 'none'}>
                                                <SelectTrigger className={triggerCls}><SelectValue placeholder="Select state" /></SelectTrigger>
                                                <SelectContent className="max-h-60 overflow-y-auto">
                                                    <SelectItem value="none">— Select —</SelectItem>
                                                    {states.map((s) => (
                                                        <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        )} />
                                    </Field>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Divider between address and contact numbers */}
                    <div className="border-t border-gray-100 pt-2">
                        <p className="text-[11px] font-semibold text-gray-300 uppercase tracking-widest mb-4">
                            Phone &amp; Mobile
                        </p>
                        <div className="grid grid-cols-3 gap-5 mb-5">
                            <Field label="Phone 1">
                                <Input className={inputCls} type="tel" {...register("phone1")} placeholder="—" />
                            </Field>
                            <Field label="Phone 2">
                                <Input className={inputCls} type="tel" {...register("phone2")} placeholder="—" disabled={!watch("phone1")} />
                            </Field>
                            <Field label="Phone 3">
                                <Input className={inputCls} type="tel" {...register("phone3")} placeholder="—" disabled={!watch("phone2")} />
                            </Field>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                            <Field label="Mobile 1">
                                <Controller name="mobile1" control={control}
                                    rules={{ validate: validatePhone }}
                                    render={({ field, fieldState }) => (
                                        <PhoneInput value={field.value} onChange={field.onChange}
                                            error={fieldState.error?.message} placeholder="Mobile number" />
                                    )} />
                            </Field>
                            <Field label="Mobile 2">
                                <Controller name="mobile2" control={control}
                                    rules={{ validate: validatePhone }}
                                    render={({ field, fieldState }) => (
                                        <PhoneInput value={field.value} onChange={field.onChange}
                                            error={fieldState.error?.message} placeholder="Mobile number"
                                            disabled={!watch("mobile1")} />
                                    )} />
                            </Field>
                            <Field label="Mobile 3">
                                <Controller name="mobile3" control={control}
                                    rules={{ validate: validatePhone }}
                                    render={({ field, fieldState }) => (
                                        <PhoneInput value={field.value} onChange={field.onChange}
                                            error={fieldState.error?.message} placeholder="Mobile number"
                                            disabled={!watch("mobile2")} />
                                    )} />
                            </Field>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-5">
                        <Field label="Email">
                            <Input className={inputCls} type="email" {...register("email")} placeholder="email@example.com" />
                        </Field>
                        <Field label="Fax">
                            <Input className={inputCls} {...register("fax")} placeholder="Fax number" />
                        </Field>
                    </div>

                </SectionCard>

                {/* ── Section 3: Compliance & KYC ──────────────────────────── */}
                <SectionCard number="3" title="Compliance & KYC">

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                        <Field label="PAN" error={errors.pan?.message}>
                            <Input
                                className={`${inputCls} uppercase ${errors.pan ? 'border-red-400 focus:border-red-500' : ''}`}
                                {...register("pan", { validate: validatePAN })}
                                placeholder="ABCDE1234F"
                                maxLength={10}
                            />
                        </Field>
                        <Field label="GST Number" error={errors.gst?.message}>
                            <Input
                                className={`${inputCls} uppercase ${errors.gst ? 'border-red-400 focus:border-red-500' : ''}`}
                                {...register("gst", { validate: validateGST })}
                                placeholder="22AAAAA0000A1Z5"
                                maxLength={15}
                            />
                        </Field>
                        <Field label="Aadhar Number" error={errors.aadhar?.message}>
                            <Input className={`${inputCls} ${errors.aadhar ? 'border-red-400 focus:border-red-500' : ''}`} {...register("aadhar", { validate: validateAadhar })} placeholder="12-digit Aadhar" maxLength={12} />
                        </Field>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                        <Field label="Passport" error={errors.passport?.message}>
                            <Input className={`${inputCls} uppercase ${errors.passport ? 'border-red-400 focus:border-red-500' : ''}`} {...register("passport", { validate: validatePassport })} placeholder="Passport number" />
                        </Field>
                        <Field label="Driving License">
                            <Input className={`${inputCls} uppercase`} {...register("dl_no")} placeholder="DL number" />
                        </Field>
                        <Field label="Remarks">
                            <Input className={inputCls} {...register("remarks")} placeholder="Any additional notes…" />
                        </Field>
                    </div>

                    {id && (
                        <div className="border-t border-gray-100 pt-4 mt-2">
                            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-3">
                                KYC Documents
                            </p>
                            <LedgerDocuments
                                ledgerId={id}
                                ledgerName={watch("ac_name") || ""}
                            />
                        </div>
                    )}

                </SectionCard>

                {/* ── Section 4: TDS Configuration ─────────────────────────── */}
                {primaryRole && !['CA','BA','CO','INC'].includes(primaryRole) && (
                    <SectionCard number="4" title="TDS Configuration">
                        <div className="flex items-center gap-3 mb-2">
                            <Controller name="tds_applicable" control={control} render={({ field }) => (
                                <Checkbox
                                    id="tds_applicable"
                                    checked={!!field.value}
                                    onCheckedChange={field.onChange}
                                />
                            )} />
                            <label htmlFor="tds_applicable" className="text-sm text-gray-700 cursor-pointer select-none">
                                TDS Applicable for this party
                            </label>
                        </div>

                        {watch('tds_applicable') && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-4">
                                <Field label="TDS Section">
                                    <Controller name="tds_section" control={control} render={({ field }) => (
                                        <Select onValueChange={field.onChange} value={field.value}>
                                            <SelectTrigger className={triggerCls}><SelectValue placeholder="Select section…" /></SelectTrigger>
                                            <SelectContent>
                                                {tdsSections.map(s => (
                                                    <SelectItem key={s.id} value={String(s.id)}>
                                                        {s.section_code} — {s.description}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    )} />
                                </Field>

                                <Field label="Deductor Type">
                                    <Controller name="tds_deductor_type" control={control} render={({ field }) => (
                                        <Select onValueChange={field.onChange} value={field.value}>
                                            <SelectTrigger className={triggerCls}><SelectValue placeholder="Select…" /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="IND">Individual / HUF</SelectItem>
                                                <SelectItem value="CO">Company / Firm</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    )} />
                                </Field>
                            </div>
                        )}

                        {watch('tds_applicable') && !watch('pan') && (
                            <p className="text-xs text-amber-600 mt-2">
                                ⚠ No PAN on file — higher TDS rate (20%) will apply. Add PAN in Compliance & KYC section.
                            </p>
                        )}
                    </SectionCard>
                )}

                {/* ── Footer ───────────────────────────────────────────────── */}
                <div className="flex justify-end items-center gap-3 pt-2">
                    <Button type="button" variant="outline" onClick={() => navigate('/crm/ledger')} className="h-10 px-5">
                        Cancel
                    </Button>
                    <Button type="submit" className="h-10 px-6 bg-primary hover:bg-primary text-white font-semibold shadow-sm">
                        {id ? 'Update Ledger' : 'Save Ledger'}
                    </Button>
                </div>

            </form>
        </div>
    );
};

export default LedgerForm;

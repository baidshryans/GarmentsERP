
import React, { useEffect, useState } from 'react';
import { useForm, Controller, useWatch } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useNavigate, useParams } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ChevronRight, ChevronDown, Folder, FolderOpen } from 'lucide-react';
import { createAccount, updateAccount, getAccount, fetchParentAccount } from '@/services/apiService';

// ─── Build tree from flat list ────────────────────────────────────────────────

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

// ─── Tree picker node (same pattern as addLedger) ─────────────────────────────

const GroupPickerNode = ({ node, level, onSelect, disabledId }) => {
    const hasChildren = node.children?.length > 0;
    const [open, setOpen] = useState(level === 0);
    const indent = level * 20;
    const isDisabled = String(node.id) === String(disabledId);

    return (
        <div>
            <div
                className={`group flex items-center gap-2 py-2 pr-3 rounded-lg transition-colors ${isDisabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-accent-50 cursor-pointer'}`}
                style={{ paddingLeft: `${indent + 8}px` }}
                onClick={() => { if (!isDisabled) onSelect(node); }}
            >
                {hasChildren ? (
                    <button
                        type="button"
                        className="shrink-0 size-5 flex items-center justify-center rounded hover:bg-accent-100 text-primary"
                        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
                    >
                        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                ) : (
                    <span className="size-5 shrink-0 flex items-center justify-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                    </span>
                )}
                {hasChildren
                    ? open
                        ? <FolderOpen className={`w-4 h-4 shrink-0 ${level === 0 ? 'text-primary' : 'text-accent-400'}`} />
                        : <Folder className={`w-4 h-4 shrink-0 ${level === 0 ? 'text-primary' : 'text-accent-400'}`} />
                    : null
                }
                {node.code && (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 tracking-wider ${level === 0 ? 'bg-accent-200 text-primary' : 'bg-gray-100 text-gray-500'}`}>
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
                <div className={level === 0 ? 'ml-3 border-l border-accent-100 pl-1 mb-1' : 'ml-3 border-l border-gray-100 pl-1'}>
                    {node.children.map(child => (
                        <GroupPickerNode key={child.id} node={child} level={level + 1} onSelect={onSelect} disabledId={disabledId} />
                    ))}
                </div>
            )}
        </div>
    );
};

// ─── Field wrapper ────────────────────────────────────────────────────────────

const Field = ({ label, required, hint, error, children }) => (
    <div className="flex flex-col gap-2">
        <label className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">
            {label}{required && <span className="text-red-400 ml-1">*</span>}
        </label>
        {children}
        {hint && !error && <p className="text-xs text-gray-400">{hint}</p>}
        {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
);

// ─── Main Component ───────────────────────────────────────────────────────────

const AccountCreate = () => {
    const { toast } = useToast();
    const navigate = useNavigate();
    const { id } = useParams();
    const isEdit = Boolean(id);

    const {
        register,
        handleSubmit,
        control,
        reset,
        setValue,
        getValues,
        formState: { errors, isSubmitting, isDirty },
    } = useForm({
        defaultValues: { name: '', code: '', parent: '' },
    });

    const [flatAccounts, setFlatAccounts] = useState([]);
    const [accountTree, setAccountTree] = useState([]);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [isSystemGroup, setIsSystemGroup] = useState(false);

    const watchedParent = useWatch({ control, name: 'parent' });

    // Auto-prefix code hint when parent changes
    useEffect(() => {
        if (!watchedParent) return;
        const parent = flatAccounts.find(a => String(a.id) === String(watchedParent));
        if (!parent?.code) return;
        const currentCode = getValues('code');
        if (!currentCode) {
            setValue('code', parent.code.charAt(0), { shouldValidate: false });
        }
    }, [watchedParent, flatAccounts, getValues, setValue]);

    useEffect(() => {
        const init = async () => {
            const [accountsRes, editRes] = await Promise.all([
                fetchParentAccount(),
                isEdit ? getAccount(id) : Promise.resolve(null),
            ]);

            if (accountsRes.success) {
                const list = isEdit
                    ? accountsRes.data.filter(a => String(a.id) !== String(id))
                    : accountsRes.data;
                setFlatAccounts(list);
                setAccountTree(buildAccountTree(list));
            }

            if (isEdit && editRes?.success) {
                const d = editRes.data;
                reset({
                    name: d.name,
                    code: d.code,
                    parent: d.parent ? String(d.parent) : '',
                });
                setIsSystemGroup(!d.can_be_deleted);
            }
        };
        init();
    }, [id, isEdit, reset]);

    const onSubmit = async (data) => {
        const payload = {
            name: data.name.trim(),
            code: data.code.trim().toUpperCase(),
            parent: data.parent || null,
        };

        const response = isEdit
            ? await updateAccount(id, payload)
            : await createAccount(payload);

        if (response.success) {
            toast({
                title: isEdit ? "Account group updated." : "Account group created.",
                description: `${payload.code} — ${payload.name}`,
            });
            setTimeout(() => navigate('/accounting/account-tree'), 800);
        } else {
            const msg = typeof response.error === 'object'
                ? Object.values(response.error).flat().join(' ')
                : response.error;
            toast({ title: isEdit ? "Update failed" : "Failed to create account", description: msg });
        }
    };

    const inputCls = "h-10 text-sm border-gray-200 focus:border-accent-400 focus:ring-accent-100";

    return (
        <div className="max-w-2xl mx-auto pb-12">

            {/* ── Page header ─────────────────────────────────────────────── */}
            <div className="flex items-start justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                        {isEdit ? 'Edit Account Group' : 'New Account Group'}
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">
                        {isEdit
                            ? `Editing record #${id}`
                            : 'Add a group to the chart of accounts hierarchy'}
                    </p>
                </div>
                <div className="flex gap-3 mt-1">
                    <Button type="button" variant="outline" className="h-10 px-5" onClick={() => navigate('/accounting/account-tree')}>
                        {isSystemGroup ? 'Back' : 'Cancel'}
                    </Button>
                    {!isSystemGroup && (
                        <Button type="submit" form="accountForm" disabled={isSubmitting || (isEdit && !isDirty)}
                            className="h-10 px-6 bg-primary hover:bg-primary text-white font-semibold shadow-sm">
                            {isSubmitting ? (isEdit ? 'Updating…' : 'Saving…') : isEdit ? 'Update Group' : 'Save Group'}
                        </Button>
                    )}
                </div>
            </div>

            {/* ── System group banner ─────────────────────────────────────── */}
            {isSystemGroup && (
                <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 mb-6 text-sm text-amber-800">
                    <strong>System group — read only.</strong> This account group was created during initial setup and cannot be modified.
                </div>
            )}

            {/* ── Form card ───────────────────────────────────────────────── */}
            <div className="rounded-xl border border-accent-100 bg-white shadow-sm overflow-hidden">
                <div className="flex items-center gap-3 px-7 py-4 bg-accent-50 border-b border-accent-100">
                    <span className="flex items-center justify-center size-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">1</span>
                    <span className="text-sm font-bold text-primary tracking-widest uppercase">Group Details</span>
                </div>

                <form id="accountForm" onSubmit={handleSubmit(onSubmit)} className="px-7 py-8 space-y-6">

                    <div className="grid grid-cols-2 gap-6">
                        <Field label="Group Name" required error={errors.name?.message}>
                            <Input
                                className={inputCls}
                                placeholder="e.g. Current Assets"
                                disabled={isSystemGroup}
                                {...register("name", {
                                    required: "Group name is required",
                                    minLength: { value: 3, message: "At least 3 characters" },
                                    maxLength: { value: 100, message: "Max 100 characters" },
                                })}
                            />
                        </Field>

                        <Field
                            label="Group Code"
                            required
                            hint={(() => {
                                const parent = flatAccounts.find(a => String(a.id) === String(watchedParent));
                                return parent?.code
                                    ? `Should start with "${parent.code.charAt(0)}" to match parent hierarchy`
                                    : "Uppercase letters, numbers, hyphens";
                            })()}
                            error={errors.code?.message}
                        >
                            <Input
                                className={`${inputCls} uppercase`}
                                placeholder="e.g. CA-INV"
                                maxLength={20}
                                disabled={isSystemGroup}
                                {...register("code", {
                                    required: "Group code is required",
                                    minLength: { value: 2, message: "At least 2 characters" },
                                    maxLength: { value: 20, message: "Max 20 characters" },
                                    pattern: {
                                        value: /^[A-Za-z0-9-]+$/,
                                        message: "Only letters, numbers, and hyphens",
                                    },
                                })}
                            />
                        </Field>
                    </div>

                    {/* ── Parent Group — sheet tree picker ─────────────────── */}
                    <Field label="Parent Group" hint="Leave empty to create a top-level group">
                        <Controller
                            name="parent"
                            control={control}
                            render={({ field }) => {
                                const selected = flatAccounts.find(a => String(a.id) === String(field.value));
                                return (
                                    <>
                                        <button
                                            type="button"
                                            onClick={() => setPickerOpen(true)}
                                            className="w-full h-10 flex items-center gap-2 px-3 rounded-md border border-gray-200 bg-white text-sm text-left hover:border-accent-400 transition-colors focus:outline-none focus:border-accent-400"
                                        >
                                            {selected ? (
                                                <>
                                                    {selected.code && (
                                                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent-100 text-primary tracking-wider shrink-0">
                                                            {selected.code}
                                                        </span>
                                                    )}
                                                    <span className="text-gray-700 truncate">{selected.name}</span>
                                                </>
                                            ) : (
                                                <span className="text-gray-400">— Top-level group —</span>
                                            )}
                                            <ChevronRight className="w-3.5 h-3.5 text-gray-300 ml-auto shrink-0" />
                                        </button>

                                        {selected && (
                                            <button
                                                type="button"
                                                onClick={() => field.onChange('')}
                                                className="text-xs text-red-400 hover:text-red-600 self-start mt-0.5"
                                            >
                                                Clear (make top-level)
                                            </button>
                                        )}

                                        <Sheet open={pickerOpen} onOpenChange={setPickerOpen}>
                                            <SheetContent side="right" className="w-[400px] sm:max-w-[400px] flex flex-col p-0">
                                                <div className="flex items-center gap-3 px-6 py-4 bg-accent-50 border-b border-accent-100 shrink-0">
                                                    <span className="flex items-center justify-center size-7 rounded-full bg-primary text-white text-xs font-bold shrink-0">≡</span>
                                                    <div>
                                                        <p className="text-sm font-bold text-primary tracking-widest uppercase">Select Parent Group</p>
                                                        <p className="text-xs text-primary mt-0.5">Click a group to set it as the parent</p>
                                                    </div>
                                                </div>
                                                <div className="flex-1 overflow-y-auto px-3 py-3">
                                                    {accountTree.map(node => (
                                                        <GroupPickerNode
                                                            key={node.id}
                                                            node={node}
                                                            level={0}
                                                            disabledId={id} // prevent selecting self as parent
                                                            onSelect={(n) => {
                                                                field.onChange(String(n.id));
                                                                setPickerOpen(false);
                                                            }}
                                                        />
                                                    ))}
                                                </div>
                                            </SheetContent>
                                        </Sheet>
                                    </>
                                );
                            }}
                        />
                    </Field>

                </form>
            </div>

            {/* ── Footer ───────────────────────────────────────────────────── */}
            {!isSystemGroup && (
                <div className="flex justify-end gap-3 pt-4">
                    <Button type="button" variant="outline" className="h-10 px-5" onClick={() => navigate('/accounting/account-tree')}>
                        Cancel
                    </Button>
                    <Button type="submit" form="accountForm" disabled={isSubmitting}
                        className="h-10 px-6 bg-primary hover:bg-primary text-white font-semibold shadow-sm">
                        {isSubmitting ? 'Saving…' : isEdit ? 'Update Group' : 'Save Group'}
                    </Button>
                </div>
            )}

        </div>
    );
};

export default AccountCreate;

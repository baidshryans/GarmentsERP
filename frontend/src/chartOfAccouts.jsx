
import React, { useState, useEffect, useCallback } from 'react';
import { ChevronRight, ChevronDown, Plus, FolderOpen, Folder, RefreshCw, Pencil, Trash2, Users } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { getChartOfAccounts, deleteAccount } from "@/services/apiService";

// ─── Collect all expandable node IDs ─────────────────────────────────────────
function collectExpandable(nodes, acc = new Set()) {
    nodes.forEach((node) => {
        if (node.children?.length) {
            acc.add(node.id);
            collectExpandable(node.children, acc);
        }
    });
    return acc;
}

// ─── Parse "CODE - Name" format ───────────────────────────────────────────────
function parseName(raw) {
    const idx = raw.indexOf(' - ');
    if (idx === -1) return { code: '', name: raw };
    return { code: raw.slice(0, idx), name: raw.slice(idx + 3) };
}

// ─── Single tree node ─────────────────────────────────────────────────────────
const TreeNode = ({ node, level, expanded, onToggle, onDelete }) => {
    const hasChildren = node.children?.length > 0;
    const isOpen = expanded.has(node.id);
    const { code, name } = parseName(node.name);
    const indent = level * 22;
    const isRoot = level === 0;

    return (
        <div>
            <div
                className={`
                    group flex items-center gap-2 py-2 pr-2 rounded-lg transition-colors
                    ${isRoot
                        ? 'bg-violet-50 border border-violet-100 mb-1 font-semibold'
                        : 'hover:bg-muted/50'
                    }
                `}
                style={{ paddingLeft: `${indent + 10}px` }}
            >
                {/* Expand / collapse toggle */}
                <button
                    onClick={() => hasChildren && onToggle(node.id)}
                    className={`shrink-0 w-5 h-5 flex items-center justify-center rounded transition-colors
                        ${hasChildren ? 'hover:bg-violet-100 text-primary cursor-pointer' : 'cursor-default opacity-0'}`}
                    tabIndex={hasChildren ? 0 : -1}
                >
                    {isOpen
                        ? <ChevronDown className="w-3.5 h-3.5" />
                        : <ChevronRight className="w-3.5 h-3.5" />
                    }
                </button>

                {/* Folder icon */}
                {hasChildren
                    ? isOpen
                        ? <FolderOpen className={`w-4 h-4 shrink-0 ${isRoot ? 'text-primary' : 'text-violet-400'}`} />
                        : <Folder className={`w-4 h-4 shrink-0 ${isRoot ? 'text-primary' : 'text-violet-400'}`} />
                    : <span className="size-4 shrink-0 flex items-center justify-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
                    </span>
                }

                {/* Code badge */}
                {code && (
                    <span className={`
                        text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 tracking-wider font-mono
                        ${isRoot ? 'bg-violet-200 text-primary' : 'bg-muted text-muted-foreground'}
                    `}>
                        {code}
                    </span>
                )}

                {/* Name */}
                <span className={`text-sm truncate flex-1 ${isRoot ? 'text-primary' : 'text-foreground'}`}>
                    {name}
                </span>

                {/* Ledger count badge */}
                {node.ledger_count > 0 && (
                    <span className="flex items-center gap-1 text-[10px] text-muted-foreground bg-muted rounded px-1.5 py-0.5 shrink-0">
                        <Users className="w-2.5 h-2.5" />
                        {node.ledger_count}
                    </span>
                )}

                {/* Child group count */}
                {hasChildren && (
                    <span className="text-[10px] text-muted-foreground font-medium shrink-0 mr-1">
                        {node.children.length}
                    </span>
                )}

                {/* Edit / Delete actions — visible on row hover */}
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    {node.can_be_deleted ? (
                        <Link
                            to={`/accounting/account-edit/${node.id}`}
                            className="p-1 rounded hover:bg-violet-100 text-primary transition-colors"
                            title="Edit group"
                        >
                            <Pencil className="size-4" />
                        </Link>
                    ) : (
                        <span
                            className="p-1 rounded text-muted-foreground/30 cursor-not-allowed"
                            title="System group — cannot be modified"
                        >
                            <Pencil className="size-4" />
                        </span>
                    )}
                    {node.can_delete ? (
                        <button
                            onClick={() => onDelete(node.id, node.name)}
                            className="p-1 rounded hover:bg-red-50 text-red-400 transition-colors"
                            title="Delete group"
                        >
                            <Trash2 className="size-4" />
                        </button>
                    ) : (
                        <span
                            className="p-1 rounded text-muted-foreground/30 cursor-not-allowed"
                            title={
                                node.ledger_count > 0
                                    ? `${node.ledger_count} ledger(s) assigned — reassign first`
                                    : hasChildren
                                    ? 'Has sub-groups — delete them first'
                                    : 'System group — cannot delete'
                            }
                        >
                            <Trash2 className="size-4" />
                        </span>
                    )}
                </div>
            </div>

            {/* Children */}
            {isOpen && hasChildren && (
                <div className={isRoot ? 'ml-3 border-l border-violet-100 pl-1 mb-2' : 'ml-3 border-l border-border pl-1'}>
                    {node.children.map((child) => (
                        <TreeNode
                            key={child.id}
                            node={child}
                            level={level + 1}
                            expanded={expanded}
                            onToggle={onToggle}
                            onDelete={onDelete}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

// ─── Main component ───────────────────────────────────────────────────────────
const AccountTree = () => {
    const { toast } = useToast();
    const navigate = useNavigate();
    const [treeData, setTreeData] = useState([]);
    const [expanded, setExpanded] = useState(new Set());
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await getChartOfAccounts();
            if (!res.success) throw new Error('Failed to load account tree');
            setTreeData(res.data);
            setExpanded(new Set(res.data.map((n) => n.id)));
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const toggleNode = useCallback((id) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    }, []);

    const allExpandable = collectExpandable(treeData);
    const allExpanded = allExpandable.size > 0 && allExpandable.size === expanded.size;
    const handleToggleAll = () => setExpanded(allExpanded ? new Set() : new Set(allExpandable));

    const countNodes = (nodes) => nodes.reduce((s, n) => s + 1 + countNodes(n.children || []), 0);
    const totalLedgers = (nodes) => nodes.reduce((s, n) => s + (n.ledger_count || 0) + totalLedgers(n.children || []), 0);
    const total = countNodes(treeData);
    const ledgerTotal = totalLedgers(treeData);

    const handleDelete = useCallback(async (id, nodeName) => {
        if (!window.confirm(`Delete "${nodeName}"? This cannot be undone.`)) return;
        const res = await deleteAccount(id);
        if (res.success) {
            toast({ title: "Deleted", description: `"${nodeName}" removed.` });
            load();
        } else {
            const msg = typeof res.error === 'object'
                ? (res.error.detail || Object.values(res.error).flat().join(' '))
                : res.error;
            toast({ title: "Cannot delete", description: msg, variant: "destructive" });
        }
    }, [load, toast]);

    return (
        <div className="max-w-4xl mx-auto pb-12">

            {/* Page header */}
            <div className="flex items-start justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Chart of Accounts</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {loading
                            ? 'Loading…'
                            : `${treeData.length} root groups · ${total} total · ${ledgerTotal} ledgers assigned`
                        }
                    </p>
                </div>
                <div className="flex gap-2 mt-1">
                    <Button variant="outline" size="sm" onClick={load} disabled={loading}>
                        <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleToggleAll} disabled={loading || allExpandable.size === 0}>
                        {allExpanded ? 'Collapse All' : 'Expand All'}
                    </Button>
                    <Link to="/accounting/account-create">
                        <Button size="sm" className="gap-1.5 bg-primary hover:bg-primary text-white">
                            <Plus className="size-4" />
                            Add Group
                        </Button>
                    </Link>
                </div>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 mb-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                    <Users className="size-3" />
                    Number = ledgers assigned to group
                </span>
                <span className="flex items-center gap-1.5">
                    <Pencil className="size-3 text-muted-foreground/40" />
                    Greyed edit = system group — cannot be modified
                </span>
                <span className="flex items-center gap-1.5">
                    <Trash2 className="size-3 text-muted-foreground/40" />
                    Greyed delete = cannot delete (has ledgers, sub-groups, or is system group)
                </span>
            </div>

            {/* Tree card */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex items-center gap-3 px-5 py-3 bg-muted/50 border-b border-border">
                    <span className="flex items-center justify-center size-6 rounded-full bg-primary text-white text-xs font-bold shrink-0">≡</span>
                    <span className="text-sm font-semibold tracking-wider uppercase text-foreground">Account Groups</span>
                </div>

                <div className="px-4 py-4">
                    {loading && (
                        <div className="space-y-2 py-4">
                            {[...Array(8)].map((_, i) => (
                                <div
                                    key={i}
                                    className="h-8 bg-muted rounded-lg animate-pulse"
                                    style={{ marginLeft: `${(i % 4) * 22}px` }}
                                />
                            ))}
                        </div>
                    )}

                    {!loading && error && (
                        <div className="flex flex-col items-center gap-3 py-12 text-center">
                            <p className="text-sm text-destructive">{error}</p>
                            <Button variant="outline" size="sm" onClick={load}>Try again</Button>
                        </div>
                    )}

                    {!loading && !error && treeData.length === 0 && (
                        <div className="flex flex-col items-center gap-4 py-16 text-center">
                            <FolderOpen className="size-10 text-muted-foreground/30" />
                            <div>
                                <p className="text-sm font-medium">No account groups yet</p>
                                <p className="text-xs text-muted-foreground mt-1">
                                    Run the ERP Setup Wizard to seed the standard chart of accounts.
                                </p>
                            </div>
                            <Link to="/settings/setup">
                                <Button size="sm" className="gap-2 bg-primary hover:bg-primary text-white">
                                    Open Setup Wizard
                                </Button>
                            </Link>
                        </div>
                    )}

                    {!loading && !error && treeData.length > 0 && (
                        <div className="space-y-1">
                            {treeData.map((node) => (
                                <TreeNode
                                    key={node.id}
                                    node={node}
                                    level={0}
                                    expanded={expanded}
                                    onToggle={toggleNode}
                                    onDelete={handleDelete}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AccountTree;

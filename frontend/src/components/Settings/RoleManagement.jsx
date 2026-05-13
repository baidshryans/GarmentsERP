import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchRoles, createRole, updateRole, deleteRole,
  fetchRolePermissions, saveRolePermissions, fetchModules,
} from "@/services/apiService";
import { Plus, Trash2, Save, Pencil, Check, X, Users } from "lucide-react";

const PERM_COLS = [
  { key: "can_list",   label: "List"   },
  { key: "can_get",    label: "View"   },
  { key: "can_post",   label: "Create" },
  { key: "can_put",    label: "Edit"   },
  { key: "can_delete", label: "Delete" },
];

// When "Edit" is toggled, also sync can_patch
const EDIT_SYNC = { can_put: "can_patch" };

export default function RoleManagement() {
  const { toast } = useToast();

  const [roles,   setRoles]   = useState([]);
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  // Selected role
  const [selectedRole, setSelectedRole] = useState(null);

  // Permission map: { [module_id]: { can_list, can_get, can_post, can_put, can_patch, can_delete } }
  const [permMap, setPermMap]   = useState({});
  const [permLoading, setPermLoading] = useState(false);
  const [saving, setSaving]   = useState(false);

  // New role input
  const [newRoleName, setNewRoleName] = useState("");
  const [creating, setCreating] = useState(false);

  // Rename state
  const [renaming, setRenaming] = useState(false);
  const [renameVal, setRenameVal] = useState("");

  // ── Load roles + modules ────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([fetchRoles(), fetchModules()]).then(([rr, mr]) => {
      if (rr.success) setRoles(rr.data);
      if (mr.success) setModules(mr.data);
      setLoading(false);
    });
  }, []);

  // ── Load permissions when role selected ────────────────────────────────────
  useEffect(() => {
    if (!selectedRole) { setPermMap({}); return; }
    setPermLoading(true);
    fetchRolePermissions(selectedRole.id).then((res) => {
      if (res.success) {
        const map = {};
        for (const p of res.data) {
          map[p.module_id] = {
            can_list: p.can_list, can_get: p.can_get, can_post: p.can_post,
            can_put: p.can_put, can_patch: p.can_patch, can_delete: p.can_delete,
          };
        }
        setPermMap(map);
      }
      setPermLoading(false);
    });
  }, [selectedRole]);

  // ── Group modules by app ────────────────────────────────────────────────────
  const groupedModules = useMemo(() => {
    const groups = {};
    for (const m of modules) {
      if (!groups[m.app_label]) groups[m.app_label] = { display: m.app_display, models: [] };
      groups[m.app_label].models.push(m);
    }
    return groups;
  }, [modules]);

  // ── Toggle a single permission cell ────────────────────────────────────────
  const togglePerm = (moduleId, key) => {
    setPermMap((prev) => {
      const cur = prev[moduleId] || {};
      const newVal = !cur[key];
      const updated = { ...cur, [key]: newVal };
      // Sync can_patch when can_put is toggled
      if (EDIT_SYNC[key]) updated[EDIT_SYNC[key]] = newVal;
      return { ...prev, [moduleId]: updated };
    });
  };

  // ── Toggle an entire row ────────────────────────────────────────────────────
  const toggleRow = (moduleId) => {
    const cur = permMap[moduleId] || {};
    const allOn = PERM_COLS.every((c) => cur[c.key]);
    const newState = allOn
      ? { can_list: false, can_get: false, can_post: false, can_put: false, can_patch: false, can_delete: false }
      : { can_list: true,  can_get: true,  can_post: true,  can_put: true,  can_patch: true,  can_delete: true  };
    setPermMap((prev) => ({ ...prev, [moduleId]: newState }));
  };

  // ── Toggle an entire column ─────────────────────────────────────────────────
  const toggleCol = (key) => {
    const allOn = modules.every((m) => permMap[m.id]?.[key]);
    setPermMap((prev) => {
      const next = { ...prev };
      for (const m of modules) {
        next[m.id] = { ...(next[m.id] || {}), [key]: !allOn };
        if (EDIT_SYNC[key]) next[m.id][EDIT_SYNC[key]] = !allOn;
      }
      return next;
    });
  };

  // ── Toggle entire app group ─────────────────────────────────────────────────
  const toggleGroup = (appLabel) => {
    const groupMods = groupedModules[appLabel]?.models ?? [];
    const allOn = groupMods.every((m) =>
      PERM_COLS.every((c) => permMap[m.id]?.[c.key])
    );
    setPermMap((prev) => {
      const next = { ...prev };
      for (const m of groupMods) {
        next[m.id] = allOn
          ? { can_list: false, can_get: false, can_post: false, can_put: false, can_patch: false, can_delete: false }
          : { can_list: true,  can_get: true,  can_post: true,  can_put: true,  can_patch: true,  can_delete: true  };
      }
      return next;
    });
  };

  // ── Save permissions ────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!selectedRole) return;
    setSaving(true);
    const payload = Object.entries(permMap)
      .filter(([, p]) => Object.values(p).some(Boolean))
      .map(([module_id, p]) => ({ module_id: Number(module_id), ...p }));
    const res = await saveRolePermissions(selectedRole.id, payload);
    if (res.success) {
      toast({ title: `Permissions saved for "${selectedRole.name}".` });
    } else {
      toast({ title: "Failed to save permissions.", variant: "destructive" });
    }
    setSaving(false);
  };

  useF4Submit(handleSave);

  // ── Create role ─────────────────────────────────────────────────────────────
  const handleCreateRole = async () => {
    if (!newRoleName.trim()) return;
    setCreating(true);
    const res = await createRole({ name: newRoleName.trim() });
    if (res.success) {
      setRoles((prev) => [...prev, res.data]);
      setSelectedRole(res.data);
      setNewRoleName("");
      toast({ title: `Role "${res.data.name}" created.` });
    } else {
      toast({ title: res.error?.detail || "Failed to create role.", variant: "destructive" });
    }
    setCreating(false);
  };

  // ── Delete role ─────────────────────────────────────────────────────────────
  const handleDeleteRole = async () => {
    if (!selectedRole) return;
    if (!window.confirm(`Delete role "${selectedRole.name}"? This cannot be undone.`)) return;
    const res = await deleteRole(selectedRole.id);
    if (res.success) {
      setRoles((prev) => prev.filter((r) => r.id !== selectedRole.id));
      setSelectedRole(null);
      toast({ title: "Role deleted." });
    } else {
      toast({ title: res.error?.detail || "Failed to delete role.", variant: "destructive" });
    }
  };

  // ── Rename role ─────────────────────────────────────────────────────────────
  const handleRename = async () => {
    if (!renameVal.trim()) { setRenaming(false); return; }
    const res = await updateRole(selectedRole.id, { name: renameVal.trim() });
    if (res.success) {
      setRoles((prev) => prev.map((r) => r.id === selectedRole.id ? { ...r, name: res.data.name } : r));
      setSelectedRole((prev) => ({ ...prev, name: res.data.name }));
      toast({ title: "Role renamed." });
    } else {
      toast({ title: "Failed to rename.", variant: "destructive" });
    }
    setRenaming(false);
  };

  if (loading) {
    return (
      <div className="p-4 flex flex-col gap-3">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[calc(100vh-8rem)] divide-x divide-border">

      {/* ── Left: Role list ─────────────────────────────────────────────── */}
      <div className="w-56 shrink-0 flex flex-col gap-1 p-3 overflow-y-auto">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Roles</p>

        {roles.map((r) => (
          <button
            key={r.id}
            onClick={() => setSelectedRole(r)}
            className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-between group ${
              selectedRole?.id === r.id
                ? "bg-primary text-primary-foreground"
                : "hover:bg-muted text-foreground"
            }`}
          >
            <span className="truncate font-medium">{r.name}</span>
            <span className={`text-[10px] flex items-center gap-0.5 ${selectedRole?.id === r.id ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
              <Users className="size-3" />{r.user_count}
            </span>
          </button>
        ))}

        {/* New role input */}
        <div className="mt-3 flex flex-col gap-1">
          <Input
            className="h-7 text-xs"
            placeholder="New role name�"
            value={newRoleName}
            onChange={(e) => setNewRoleName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateRole()}
          />
          <Button size="sm" className="h-7 text-xs w-full" onClick={handleCreateRole} disabled={creating || !newRoleName.trim()}>
            <Plus className="size-3 mr-1" /> {creating ? "Creating�" : "Add Role"}
          </Button>
        </div>
      </div>

      {/* ── Right: Permission matrix ─────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedRole ? (
          <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
            Select a role on the left to configure its permissions.
          </div>
        ) : (
          <>
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
              <div className="flex items-center gap-2">
                {renaming ? (
                  <>
                    <Input
                      className="h-7 text-sm w-44"
                      value={renameVal}
                      onChange={(e) => setRenameVal(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleRename(); if (e.key === "Escape") setRenaming(false); }}
                      autoFocus
                    />
                    <button onClick={handleRename} className="text-green-600 hover:text-green-700"><Check className="size-4" /></button>
                    <button onClick={() => setRenaming(false)} className="text-muted-foreground hover:text-foreground"><X className="size-4" /></button>
                  </>
                ) : (
                  <>
                    <h2 className="font-semibold text-sm">{selectedRole.name}</h2>
                    <button
                      onClick={() => { setRenameVal(selectedRole.name); setRenaming(true); }}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <Pencil className="size-3.5" />
                    </button>
                  </>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm" variant="destructive" className="h-7 text-xs gap-1"
                  onClick={handleDeleteRole}
                >
                  <Trash2 className="size-3" /> Delete Role
                </Button>
                <Button
                  size="sm" className="h-7 text-xs gap-1"
                  onClick={handleSave} disabled={saving}
                >
                  <Save className="size-3" /> {saving ? "Saving�" : "Save Permissions"}
                </Button>
              </div>
            </div>

            {/* Customer data visibility toggle */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/10">
              <Checkbox
                id="customer-data-toggle"
                checked={selectedRole.can_view_customer_data ?? true}
                onCheckedChange={async (val) => {
                  const res = await updateRole(selectedRole.id, { can_view_customer_data: val });
                  if (res.success) {
                    setSelectedRole((prev) => ({ ...prev, can_view_customer_data: val }));
                    setRoles((prev) => prev.map((r) => r.id === selectedRole.id ? { ...r, can_view_customer_data: val } : r));
                    toast({ title: val ? "Customer data visible for this role." : "Customer data hidden for this role." });
                  } else {
                    toast({ title: "Failed to update.", variant: "destructive" });
                  }
                }}
                className="size-4"
              />
              <Label htmlFor="customer-data-toggle" className="text-sm cursor-pointer">
                Can view customer data <span className="text-muted-foreground">(names, phones, addresses, PAN, GST)</span>
              </Label>
            </div>

            {/* Matrix */}
            {permLoading ? (
              <div className="p-4 flex flex-col gap-2">
                {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
              </div>
            ) : (
              <div className="flex-1 overflow-auto">
                <table className="w-full text-sm border-collapse">
                  <thead className="sticky top-0 bg-muted/80 backdrop-blur z-10">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium text-muted-foreground text-xs w-8">
                        {/* row-all toggle */}
                      </th>
                      <th className="text-left px-4 py-2 font-medium text-xs text-muted-foreground">
                        Model
                      </th>
                      {PERM_COLS.map((col) => {
                        const allOn = modules.length > 0 && modules.every((m) => permMap[m.id]?.[col.key]);
                        return (
                          <th key={col.key} className="px-3 py-2 text-center w-20">
                            <div className="flex flex-col items-center gap-1">
                              <span className="text-[11px] font-medium text-muted-foreground">{col.label}</span>
                              <Checkbox
                                checked={allOn}
                                onCheckedChange={() => toggleCol(col.key)}
                                className="size-3.5"
                                title={`Toggle all ${col.label}`}
                              />
                            </div>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(groupedModules).map(([appLabel, { display, models }]) => {
                      const groupAllOn = models.every((m) => PERM_COLS.every((c) => permMap[m.id]?.[c.key]));
                      return [
                        /* App group header row */
                        <tr key={`hdr-${appLabel}`} className="bg-muted/50">
                          <td className="px-2 py-1.5" colSpan={2}>
                            <div className="flex items-center gap-2">
                              <Checkbox
                                checked={groupAllOn}
                                onCheckedChange={() => toggleGroup(appLabel)}
                                className="size-3.5"
                                title={`Toggle all ${display}`}
                              />
                              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                                {display}
                              </span>
                            </div>
                          </td>
                          {PERM_COLS.map((c) => <td key={c.key} />)}
                        </tr>,
                        /* Model rows */
                        ...models.map((mod) => {
                          const p = permMap[mod.id] || {};
                          const rowAllOn = PERM_COLS.every((c) => p[c.key]);
                          return (
                            <tr key={mod.id} className="border-b border-border/50 hover:bg-muted/20 transition-colors">
                              <td className="px-4 py-2 text-center">
                                <Checkbox
                                  checked={rowAllOn}
                                  onCheckedChange={() => toggleRow(mod.id)}
                                  className="size-3.5"
                                  title="Toggle all permissions for this model"
                                />
                              </td>
                              <td className="px-4 py-2 font-medium text-sm">{mod.model_display}</td>
                              {PERM_COLS.map((col) => (
                                <td key={col.key} className="px-3 py-2 text-center">
                                  <Checkbox
                                    checked={!!p[col.key]}
                                    onCheckedChange={() => togglePerm(mod.id, col.key)}
                                    className="size-4"
                                  />
                                </td>
                              ))}
                            </tr>
                          );
                        }),
                      ];
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { DataTable } from "@/table";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter,
} from "@/components/ui/sheet";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Edit, Plus, Building2, UserCheck, UserX, ShieldCheck } from "lucide-react";
import {
  fetchUsers, createUser, updateUser, assignUserRetail, fetchRetails,
  fetchRoles, assignUserRole,
} from "@/services/apiService";

export default function UserManagement() {
  const { toast } = useToast();

  const [users, setUsers]       = useState([]);
  const [retails, setRetails]   = useState([]);
  const [roles, setRoles]       = useState([]);
  const [loading, setLoading]   = useState(true);

  // Sheet state
  const [sheet, setSheet]       = useState(null);  // "create" | "edit" | "retail" | "role"
  const [selected, setSelected] = useState(null);  // user being edited

  // Form state
  const [form, setForm]         = useState({});
  const [saving, setSaving]     = useState(false);

  useEffect(() => {
    load();
    fetchRetails().then((res) => {
      if (res.success) {
        const d = res.data?.results ?? (Array.isArray(res.data) ? res.data : []);
        setRetails(d);
      }
    });
    fetchRoles().then((res) => { if (res.success) setRoles(Array.isArray(res.data) ? res.data : []); });
  }, []);

  const load = async () => {
    setLoading(true);
    const res = await fetchUsers();
    if (res.success) setUsers(Array.isArray(res.data) ? res.data : []);
    setLoading(false);
  };

  const openCreate = () => {
    setForm({ username: "", password: "", email: "", first_name: "", last_name: "", is_staff: false });
    setSelected(null);
    setSheet("create");
  };

  const openEdit = (user) => {
    setForm({
      email: user.email || "",
      first_name: user.first_name || "",
      last_name: user.last_name || "",
      is_staff: user.is_staff || false,
      is_active: user.is_active !== false,
      password: "",
    });
    setSelected(user);
    setSheet("edit");
  };

  const openRetail = (user) => {
    const currentIds = (user.locations || []).map((l) => l.id);
    const defaultId = user.default_location?.id || "";
    setForm({ retail_ids: currentIds, default_retail_id: defaultId });
    setSelected(user);
    setSheet("retail");
  };

  const openRole = (user) => {
    setForm({ role_id: user.role?.id ?? null });
    setSelected(user);
    setSheet("role");
  };

  const handleCreate = async () => {
    if (!form.username || !form.password) {
      toast({ title: "Username and password are required", variant: "destructive" });
      return;
    }
    setSaving(true);
    const res = await createUser(form);
    if (res.success) {
      toast({ title: `User '${res.data.username}' created` });
      setSheet(null);
      load();
    } else {
      toast({ title: "Failed to create user", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setSaving(false);
  };

  const handleUpdate = async () => {
    setSaving(true);
    const payload = { ...form };
    if (!payload.password) delete payload.password;
    const res = await updateUser(selected.id, payload);
    if (res.success) {
      toast({ title: "User updated" });
      setSheet(null);
      load();
    } else {
      toast({ title: "Failed to update user", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setSaving(false);
  };

  const handleAssignRetail = async () => {
    setSaving(true);
    const res = await assignUserRetail(
      selected.id,
      form.retail_ids || [],
      form.default_retail_id || null,
    );
    if (res.success) {
      toast({ title: "Retail assignments updated" });
      setSheet(null);
      load();
    } else {
      toast({ title: "Failed to assign retail", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setSaving(false);
  };

  const handleAssignRole = async () => {
    setSaving(true);
    const res = await assignUserRole(selected.id, form.role_id ?? null);
    if (res.success) {
      toast({ title: "Role updated." });
      setSheet(null);
      load();
    } else {
      toast({ title: "Failed to update role.", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setSaving(false);
  };

  const toggleRetailId = (id) => {
    setForm((f) => {
      const ids = f.retail_ids || [];
      return {
        ...f,
        retail_ids: ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id],
      };
    });
  };

  const columns = [
    {
      header: "Actions",
      cell: ({ row }) => {
        const u = row.original;
        return (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => openEdit(u)}>
              <Edit className="size-3 mr-1" /> Edit
            </Button>
            <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => openRetail(u)}>
              <Building2 className="size-3 mr-1" /> Retails
            </Button>
            <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => openRole(u)}>
              <ShieldCheck className="size-3 mr-1" /> Role
            </Button>
          </div>
        );
      },
    },
    {
      header: "Username",
      accessorKey: "username",
      cell: ({ row }) => (
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-sm">{row.original.username}</span>
          {row.original.is_staff && (
            <span className="px-1 py-0.5 rounded text-[9px] bg-violet-100 text-violet-700 font-semibold">admin</span>
          )}
        </div>
      ),
    },
    { header: "Name", cell: ({ row }) => `${row.original.first_name} ${row.original.last_name}`.trim() || "—" },
    { header: "Email", accessorKey: "email" },
    {
      header: "Status",
      cell: ({ row }) => row.original.is_active
        ? <span className="inline-flex items-center gap-1 text-[11px] text-green-700"><UserCheck className="size-3" /> Active</span>
        : <span className="inline-flex items-center gap-1 text-[11px] text-red-600"><UserX className="size-3" /> Inactive</span>,
    },
    {
      header: "Assigned Retails",
      cell: ({ row }) => {
        const locs = row.original.locations || [];
        if (!locs.length) return <span className="text-xs text-muted-foreground">None</span>;
        return (
          <div className="flex flex-wrap gap-1">
            {locs.map((l) => (
              <span key={l.id} className="px-1.5 py-0.5 rounded-full text-[10px] bg-muted border border-border">
                {l.retail_name}
                {row.original.default_location?.id === l.id && " ★"}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      header: "Role",
      cell: ({ row }) => {
        const r = row.original.role;
        if (!r) return <span className="text-xs text-muted-foreground">No role</span>;
        return <span className="px-1.5 py-0.5 rounded text-[11px] bg-violet-100 text-violet-700 font-medium">{r.name}</span>;
      },
    },
    { header: "Joined", accessorKey: "date_joined" },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold">User Management</h1>
        <Button size="sm" className="bg-violet-700 hover:bg-violet-800 text-white" onClick={openCreate}>
          <Plus className="size-4 mr-1" /> New User
        </Button>
      </div>

      {loading
        ? <div className="flex flex-col gap-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        : <DataTable columns={columns} data={users} />
      }

      {/* ── Create User Sheet ── */}
      <Sheet open={sheet === "create"} onOpenChange={(open) => !open && setSheet(null)}>
        <SheetContent aria-describedby={undefined} className="w-[400px] sm:w-[480px] overflow-y-auto">
          <SheetHeader><SheetTitle>Create New User</SheetTitle></SheetHeader>
          <div className="grid grid-cols-2 gap-3 py-4">
            <div className="col-span-2">
              <Label className="text-xs">Username *</Label>
              <Input className="h-8 text-sm mt-1" value={form.username || ""} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">Password *</Label>
              <Input type="password" className="h-8 text-sm mt-1" value={form.password || ""} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
            </div>
            <div>
              <Label className="text-xs">First Name</Label>
              <Input className="h-8 text-sm mt-1" value={form.first_name || ""} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} />
            </div>
            <div>
              <Label className="text-xs">Last Name</Label>
              <Input className="h-8 text-sm mt-1" value={form.last_name || ""} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">Email</Label>
              <Input type="email" className="h-8 text-sm mt-1" value={form.email || ""} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <Checkbox id="is_staff_c" checked={!!form.is_staff} onCheckedChange={(v) => setForm((f) => ({ ...f, is_staff: v }))} />
              <Label htmlFor="is_staff_c" className="text-sm cursor-pointer">Admin / Staff access</Label>
            </div>
          </div>
          <SheetFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setSheet(null)}>Cancel</Button>
            <Button size="sm" className="bg-violet-700 hover:bg-violet-800 text-white" onClick={handleCreate} disabled={saving}>
              {saving ? "Creating..." : "Create User"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* ── Edit User Sheet ── */}
      <Sheet open={sheet === "edit"} onOpenChange={(open) => !open && setSheet(null)}>
        <SheetContent aria-describedby={undefined} className="w-[400px] sm:w-[480px] overflow-y-auto">
          <SheetHeader><SheetTitle>Edit User — {selected?.username}</SheetTitle></SheetHeader>
          <div className="grid grid-cols-2 gap-3 py-4">
            <div>
              <Label className="text-xs">First Name</Label>
              <Input className="h-8 text-sm mt-1" value={form.first_name || ""} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} />
            </div>
            <div>
              <Label className="text-xs">Last Name</Label>
              <Input className="h-8 text-sm mt-1" value={form.last_name || ""} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">Email</Label>
              <Input type="email" className="h-8 text-sm mt-1" value={form.email || ""} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">New Password (leave blank to keep current)</Label>
              <Input type="password" className="h-8 text-sm mt-1" value={form.password || ""} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
            </div>
            <div className="col-span-2 flex gap-4">
              <div className="flex items-center gap-2">
                <Checkbox id="is_staff_e" checked={!!form.is_staff} onCheckedChange={(v) => setForm((f) => ({ ...f, is_staff: v }))} />
                <Label htmlFor="is_staff_e" className="text-sm cursor-pointer">Admin / Staff</Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox id="is_active_e" checked={form.is_active !== false} onCheckedChange={(v) => setForm((f) => ({ ...f, is_active: v }))} />
                <Label htmlFor="is_active_e" className="text-sm cursor-pointer">Active</Label>
              </div>
            </div>
          </div>
          <SheetFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setSheet(null)}>Cancel</Button>
            <Button size="sm" className="bg-violet-700 hover:bg-violet-800 text-white" onClick={handleUpdate} disabled={saving}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* ── Assign Role Sheet ── */}
      <Sheet open={sheet === "role"} onOpenChange={(open) => !open && setSheet(null)}>
        <SheetContent aria-describedby={undefined} className="w-[400px] sm:w-[480px] overflow-y-auto">
          <SheetHeader><SheetTitle>Assign Role — {selected?.username}</SheetTitle></SheetHeader>
          <div className="py-4 flex flex-col gap-3">
            <Label className="text-xs text-muted-foreground block">
              Choose the role that defines what this user can view, create, edit, and delete.
            </Label>
            <Select
              value={form.role_id ? String(form.role_id) : "__none__"}
              onValueChange={(v) => setForm((f) => ({ ...f, role_id: v === "__none__" ? null : Number(v) }))}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue placeholder="— No role —" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">— No role (access denied) —</SelectItem>
                {roles.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>{r.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Manage roles and their permissions in{" "}
              <a href="/settings/roles" className="text-primary underline">Roles & Permissions</a>.
            </p>
          </div>
          <SheetFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setSheet(null)}>Cancel</Button>
            <Button size="sm" className="bg-violet-700 hover:bg-violet-800 text-white" onClick={handleAssignRole} disabled={saving}>
              {saving ? "Saving..." : "Save Role"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* ── Assign Retail Sheet ── */}
      <Sheet open={sheet === "retail"} onOpenChange={(open) => !open && setSheet(null)}>
        <SheetContent aria-describedby={undefined} className="w-[400px] sm:w-[480px] overflow-y-auto">
          <SheetHeader><SheetTitle>Assign Retails — {selected?.username}</SheetTitle></SheetHeader>
          <div className="py-4 flex flex-col gap-4">
            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Select retails this user can access:</Label>
              <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
                {retails.map((r) => (
                  <div key={r.id} className="flex items-center gap-2">
                    <Checkbox
                      id={`r_${r.id}`}
                      checked={(form.retail_ids || []).includes(r.id)}
                      onCheckedChange={() => toggleRetailId(r.id)}
                    />
                    <Label htmlFor={`r_${r.id}`} className="text-sm cursor-pointer">{r.retail_name}</Label>
                  </div>
                ))}
              </div>
            </div>
            {(form.retail_ids || []).length > 0 && (
              <div>
                <Label className="text-xs mb-1 block">Default Retail (pre-selected on login)</Label>
                <Select
                  value={form.default_retail_id ? String(form.default_retail_id) : "__none__"}
                  onValueChange={(v) => setForm((f) => ({ ...f, default_retail_id: v === "__none__" ? null : Number(v) }))}
                >
                  <SelectTrigger className="h-8 text-sm">
                    <SelectValue placeholder="— None —" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— None —</SelectItem>
                    {retails
                      .filter((r) => (form.retail_ids || []).includes(r.id))
                      .map((r) => (
                        <SelectItem key={r.id} value={String(r.id)}>{r.retail_name}</SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <SheetFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setSheet(null)}>Cancel</Button>
            <Button size="sm" className="bg-violet-700 hover:bg-violet-800 text-white" onClick={handleAssignRetail} disabled={saving}>
              {saving ? "Saving..." : "Save Assignments"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}

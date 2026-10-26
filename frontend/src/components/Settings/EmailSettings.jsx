import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { usePermissions } from "@/contexts/PermissionContext";
import { fetchEmailSettings, updateEmailSettings } from "@/services/apiService";
import { Mail, Save } from "lucide-react";

const PROVIDERS = [
  { value: "gmail",       label: "Gmail (SMTP + app password)" },
  { value: "outlook",     label: "Outlook / Office365 (SMTP + app password)" },
  { value: "custom_smtp", label: "Custom SMTP" },
];

export default function EmailSettings() {
  const { toast } = useToast();
  const { is_superuser } = usePermissions();

  const [form, setForm] = useState({
    provider: "gmail", host: "", port: 587, use_tls: true,
    username: "", password: "", from_email: "", from_name: "", is_enabled: false,
  });
  const [autoSend, setAutoSend] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [togglingAuto, setTogglingAuto] = useState(false);

  const load = useCallback(async () => {
    const res = await fetchEmailSettings();
    setLoading(false);
    if (!res.success) {
      toast({ title: "Could not load email settings", variant: "destructive" });
      return;
    }
    const d = res.data;
    setForm({
      provider: d.provider ?? "gmail", host: d.host ?? "", port: d.port ?? 587,
      use_tls: d.use_tls ?? true, username: d.username ?? "",
      password: "", // write-only; never returned
      from_email: d.from_email ?? "", from_name: d.from_name ?? "",
      is_enabled: d.is_enabled ?? false,
    });
    setAutoSend(Boolean(d.auto_send_bills));
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));
  const isCustom = form.provider === "custom_smtp";

  const handleSave = async () => {
    setSaving(true);
    const payload = { ...form };
    if (!payload.password) delete payload.password; // keep the stored one
    if (!isCustom) { delete payload.host; delete payload.port; delete payload.use_tls; }
    const res = await updateEmailSettings(payload);
    setSaving(false);
    if (res.success) {
      toast({ title: "Email settings saved" });
      load();
    } else {
      toast({ title: "Save failed", description: "Could not save email settings.", variant: "destructive" });
    }
  };

  // Saved on its own so the switch takes effect immediately.
  const handleAutoSend = async (checked) => {
    setTogglingAuto(true);
    const res = await updateEmailSettings({ auto_send_bills: checked });
    setTogglingAuto(false);
    if (res.success) {
      setAutoSend(checked);
      toast({ title: checked ? "Auto-send bills turned on" : "Auto-send bills turned off" });
    } else {
      toast({
        title: "Could not change auto-send",
        description: res.data?.error ?? "Only a superadmin can change this setting.",
        variant: "destructive",
      });
    }
  };

  if (loading) return <p className="p-4 text-sm text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-6 p-1 max-w-3xl">
      <div className="flex items-center gap-2">
        <Mail className="size-5" />
        <h1 className="text-xl font-semibold">Email Settings</h1>
      </div>

      <section className="rounded-lg border p-4 space-y-4">
        <h2 className="font-medium">Outgoing mail server</h2>

        <div className="flex items-center gap-2">
          <Checkbox id="email-enabled" checked={form.is_enabled}
            onCheckedChange={v => set("is_enabled", Boolean(v))} />
          <Label htmlFor="email-enabled">Enable outgoing email for this branch</Label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>Provider</Label>
            <Select value={form.provider} onValueChange={v => set("provider", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PROVIDERS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>From name</Label>
            <Input value={form.from_name} onChange={e => set("from_name", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>From email</Label>
            <Input type="email" value={form.from_email} onChange={e => set("from_email", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Username</Label>
            <Input value={form.username} onChange={e => set("username", e.target.value)} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Password / app password</Label>
            <Input type="password" value={form.password} placeholder="Leave blank to keep the saved one"
              autoComplete="new-password" onChange={e => set("password", e.target.value)} />
          </div>
          {isCustom && (
            <>
              <div className="space-y-1">
                <Label>SMTP host</Label>
                <Input value={form.host} onChange={e => set("host", e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Port</Label>
                <Input type="number" value={form.port} onChange={e => set("port", Number(e.target.value))} />
              </div>
              <div className="flex items-center gap-2">
                <Checkbox id="email-tls" checked={form.use_tls}
                  onCheckedChange={v => set("use_tls", Boolean(v))} />
                <Label htmlFor="email-tls">Use TLS</Label>
              </div>
            </>
          )}
        </div>

        <Button onClick={handleSave} disabled={saving}>
          <Save className="size-4 mr-1" /> {saving ? "Saving…" : "Save"}
        </Button>
      </section>

      <section className="rounded-lg border p-4 space-y-2">
        <h2 className="font-medium">Auto-send bills</h2>
        <div className="flex items-center gap-2">
          <Checkbox id="auto-send" checked={autoSend}
            disabled={!is_superuser || togglingAuto}
            onCheckedChange={v => handleAutoSend(Boolean(v))} />
          <Label htmlFor="auto-send">Email each sales bill to the customer when it is saved</Label>
        </div>
        <p className="text-xs text-muted-foreground">
          Needs outgoing email enabled above and an email address on the customer's ledger.
          Customers without an email are skipped. Takes effect immediately.
          {!is_superuser && " Only a superadmin can change this."}
        </p>
      </section>
    </div>
  );
}

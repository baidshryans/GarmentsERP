import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import {
  fetchCRMSettings, updateCRMSettings, fetchCRMSendLog, triggerCRMTestSend,
} from "@/services/apiService";
import {
  MessageCircle, Save, RefreshCw, PlayCircle, CheckCircle2, XCircle, SkipForward,
  Clock, Settings2, BookOpen,
} from "lucide-react";

const PROVIDERS = [
  { value: "meta",    label: "Meta Cloud API (official)" },
  { value: "wati",    label: "WATI" },
  { value: "aisensy", label: "AiSensy" },
  { value: "webhook", label: "Custom HTTP Webhook" },
];

const PROVIDER_HELP = {
  meta: (
    <p className="text-xs text-muted-foreground mt-1">
      Requires a <strong>Meta Business Account</strong> with WhatsApp Cloud API enabled.
      Set your <em>Phone Number ID</em> and <em>Permanent Access Token</em>.
      Messages are sent via pre-approved templates.{" "}
      <a href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started" target="_blank" rel="noreferrer" className="underline text-blue-600">Setup guide ↗</a>
    </p>
  ),
  wati: (
    <p className="text-xs text-muted-foreground mt-1">
      Enter your <strong>WATI server URL</strong> (e.g. <code>https://live-server-XXXXX.wati.io</code>)
      in the Webhook URL field and your <strong>API key</strong> as the access token.{" "}
      <a href="https://docs.wati.io/" target="_blank" rel="noreferrer" className="underline text-blue-600">Docs ↗</a>
    </p>
  ),
  aisensy: (
    <p className="text-xs text-muted-foreground mt-1">
      Enter your <strong>AiSensy API key</strong>. Template names must match those
      approved in your AiSensy account.{" "}
      <a href="https://help.aisensy.com/" target="_blank" rel="noreferrer" className="underline text-blue-600">Docs ↗</a>
    </p>
  ),
  webhook: (
    <p className="text-xs text-muted-foreground mt-1">
      The ERP will POST JSON to your webhook URL:
      <code className="block bg-muted rounded p-1 mt-1 text-xs">{"{ to, mobile, message, customer_name, occasion }"}</code>
      Add any required headers as JSON in the <em>Webhook Headers</em> field.
    </p>
  ),
};

function StatusChip({ status }) {
  if (status === "success")
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
        <CheckCircle2 className="w-3 h-3" /> Sent
      </span>
    );
  if (status === "failed")
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
        <XCircle className="w-3 h-3" /> Failed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
      <SkipForward className="w-3 h-3" /> Skipped
    </span>
  );
}

export default function CRMAutomation() {
  const { toast } = useToast();

  const [form, setForm] = useState({
    is_enabled: false,
    send_time: "09:00",
    provider: "webhook",
    api_key: "",
    phone_number_id: "",
    birthday_template_name: "birthday_wishes",
    anniversary_template_name: "anniversary_wishes",
    webhook_url: "",
    webhook_headers: "",
  });
  const [lastSendDate, setLastSendDate]     = useState(null);
  const [lastRunStatus, setLastRunStatus]   = useState("");
  const [saving,     setSaving]   = useState(false);
  const [testing,    setTesting]  = useState(false);
  const [logs,       setLogs]     = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [tab, setTab] = useState("config"); // config | logs

  const loadSettings = useCallback(async () => {
    const res = await fetchCRMSettings();
    if (res.success) {
      const d = res.data;
      setForm({
        is_enabled:                d.is_enabled ?? false,
        send_time:                 d.send_time ?? "09:00",
        provider:                  d.provider ?? "webhook",
        api_key:                   d.api_key ?? "",
        phone_number_id:           d.phone_number_id ?? "",
        birthday_template_name:    d.birthday_template_name ?? "birthday_wishes",
        anniversary_template_name: d.anniversary_template_name ?? "anniversary_wishes",
        webhook_url:               d.webhook_url ?? "",
        webhook_headers:           typeof d.webhook_headers === "object"
          ? JSON.stringify(d.webhook_headers, null, 2)
          : (d.webhook_headers ?? ""),
      });
      setLastSendDate(d.last_send_date);
      setLastRunStatus(d.last_run_status);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    const res = await fetchCRMSendLog();
    setLogsLoading(false);
    if (res.success) setLogs(res.data);
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (tab === "logs") loadLogs();
  }, [tab, loadLogs]);

  const handleChange = (key, value) =>
    setForm(prev => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    let headers_val = form.webhook_headers;
    if (typeof headers_val === "string" && headers_val.trim()) {
      try { headers_val = JSON.parse(headers_val); } catch { headers_val = {}; }
    } else if (!headers_val) {
      headers_val = {};
    }
    const payload = { ...form, webhook_headers: headers_val };
    const res = await updateCRMSettings(payload);
    setSaving(false);
    if (res.success) {
      toast({ title: "Settings saved", description: "CRM automation settings updated." });
      setLastSendDate(res.data.last_send_date);
      setLastRunStatus(res.data.last_run_status);
    } else {
      toast({ title: "Save failed", description: "Could not save settings.", variant: "destructive" });
    }
  };

  const handleTestSend = async () => {
    setTesting(true);
    const res = await triggerCRMTestSend();
    setTesting(false);
    if (res.success) {
      toast({ title: "Test send complete", description: res.data?.message ?? "Messages sent for today's occasions." });
      loadSettings();
      if (tab === "logs") loadLogs();
    } else {
      toast({
        title: "Test send failed",
        description: res.data?.error ?? "An error occurred.",
        variant: "destructive",
      });
    }
  };

  const showPhoneNumberId    = form.provider === "meta";
  const showWebhookUrl       = ["wati", "webhook"].includes(form.provider);
  const showWebhookHeaders   = form.provider === "webhook";
  const showTemplateNames    = ["meta", "wati", "aisensy"].includes(form.provider);

  return (
    <div className="space-y-6 p-1 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <MessageCircle className="w-6 h-6 text-green-600" />
            CRM Automation
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Automatically send WhatsApp birthday &amp; anniversary greetings to customers.
          </p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {[
          { id: "config", label: "Configuration", icon: Settings2 },
          { id: "logs",   label: "Send Log",       icon: BookOpen  },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* ── Configuration Tab ── */}
      {tab === "config" && (
        <div className="space-y-6">
          {/* Enable + Send Time card */}
          <div className="rounded-xl border bg-card p-5 space-y-5">
            <h2 className="font-semibold text-base flex items-center gap-2">
              <Clock className="w-4 h-4 text-muted-foreground" />
              Schedule
            </h2>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">Enable Automatic Sending</p>
                <p className="text-xs text-muted-foreground">
                  When enabled, messages are sent every day at the configured time.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={form.is_enabled}
                onClick={() => handleChange("is_enabled", !form.is_enabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${
                  form.is_enabled ? "bg-green-600" : "bg-muted-foreground/30"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                    form.is_enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Send Time (IST)</Label>
                <Input
                  type="time"
                  value={form.send_time}
                  onChange={e => handleChange("send_time", e.target.value)}
                  className="w-40"
                />
                <p className="text-xs text-muted-foreground">
                  Messages go out once per day at this time.
                </p>
              </div>

              {lastSendDate && (
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Last Run</Label>
                  <p className="text-sm font-mono">{lastSendDate}</p>
                  {lastRunStatus && (
                    <p className="text-xs text-muted-foreground">{lastRunStatus}</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Provider card */}
          <div className="rounded-xl border bg-card p-5 space-y-5">
            <h2 className="font-semibold text-base flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-muted-foreground" />
              WhatsApp Provider
            </h2>

            <div className="flex flex-col gap-1">
              <Label className="text-xs">Provider</Label>
              <Select value={form.provider} onValueChange={v => handleChange("provider", v)}>
                <SelectTrigger className="w-72">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map(p => (
                    <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {PROVIDER_HELP[form.provider]}
            </div>

            <div className="flex flex-col gap-1">
              <Label className="text-xs">
                {form.provider === "meta" ? "Permanent Access Token" : "API Key / Access Token"}
              </Label>
              <Input
                type="password"
                placeholder="Paste your API key or access token"
                value={form.api_key}
                onChange={e => handleChange("api_key", e.target.value)}
                autoComplete="off"
              />
            </div>

            {showPhoneNumberId && (
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Phone Number ID (Meta)</Label>
                <Input
                  placeholder="e.g. 123456789012345"
                  value={form.phone_number_id}
                  onChange={e => handleChange("phone_number_id", e.target.value)}
                />
              </div>
            )}

            {showWebhookUrl && (
              <div className="flex flex-col gap-1">
                <Label className="text-xs">
                  {form.provider === "wati" ? "WATI Server URL" : "Webhook URL"}
                </Label>
                <Input
                  placeholder={
                    form.provider === "wati"
                      ? "https://live-server-XXXXX.wati.io"
                      : "https://your-server.com/api/whatsapp"
                  }
                  value={form.webhook_url}
                  onChange={e => handleChange("webhook_url", e.target.value)}
                />
              </div>
            )}

            {showWebhookHeaders && (
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Webhook Headers (JSON)</Label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring font-mono"
                  placeholder={'{"Authorization": "Bearer token", "X-Custom": "value"}'}
                  value={form.webhook_headers}
                  onChange={e => handleChange("webhook_headers", e.target.value)}
                  rows={3}
                />
              </div>
            )}

            {showTemplateNames && (
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Birthday Template Name</Label>
                  <Input
                    value={form.birthday_template_name}
                    onChange={e => handleChange("birthday_template_name", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Anniversary Template Name</Label>
                  <Input
                    value={form.anniversary_template_name}
                    onChange={e => handleChange("anniversary_template_name", e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={handleSave} disabled={saving} className="gap-2">
              {saving
                ? <RefreshCw className="w-4 h-4 animate-spin" />
                : <Save className="w-4 h-4" />}
              {saving ? "Saving…" : "Save Settings"}
            </Button>

            <Button
              variant="outline"
              onClick={handleTestSend}
              disabled={testing || !form.is_enabled}
              className="gap-2"
              title={!form.is_enabled ? "Enable CRM automation first" : "Immediately send today's occasion messages"}
            >
              {testing
                ? <RefreshCw className="w-4 h-4 animate-spin" />
                : <PlayCircle className="w-4 h-4 text-green-600" />}
              {testing ? "Sending…" : "Send Now (Test)"}
            </Button>

            <p className="text-xs text-muted-foreground">
              "Send Now" immediately sends today's occasion messages, ignoring the scheduled time. Use for testing.
            </p>
          </div>
        </div>
      )}

      {/* ── Send Log Tab ── */}
      {tab === "logs" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">Last 100 send attempts.</p>
            <Button variant="outline" size="sm" onClick={loadLogs} disabled={logsLoading} className="gap-1.5">
              <RefreshCw className={`w-3.5 h-3.5 ${logsLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          {logsLoading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Loading…</p>
          ) : logs.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <p className="font-medium">No send history yet</p>
              <p className="text-sm mt-1">Use "Send Now" to test, or wait for the scheduled time.</p>
            </div>
          ) : (
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="px-3">Customer</TableHead>
                    <TableHead className="px-3">Mobile</TableHead>
                    <TableHead className="px-3">Occasion</TableHead>
                    <TableHead className="px-3">Sent At</TableHead>
                    <TableHead className="px-3">Status</TableHead>
                    <TableHead className="px-3">Note</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map(log => (
                    <TableRow key={log.id} className="hover:bg-muted/20">
                      <TableCell className="px-3 py-2 font-medium text-sm">{log.customer_name}</TableCell>
                      <TableCell className="px-3 py-2 text-sm font-mono">{log.mobile || "—"}</TableCell>
                      <TableCell className="px-3 py-2 text-sm capitalize">{log.occasion}</TableCell>
                      <TableCell className="px-3 py-2 text-sm text-muted-foreground">
                        {new Date(log.sent_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                      </TableCell>
                      <TableCell className="px-3 py-2">
                        <StatusChip status={log.status} />
                      </TableCell>
                      <TableCell className="px-3 py-2 text-xs text-muted-foreground max-w-xs truncate">
                        {log.error_message || "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

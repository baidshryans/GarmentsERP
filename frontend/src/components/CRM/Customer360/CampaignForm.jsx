// Compose a campaign, preview exactly who will receive it, then launch.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Rocket, Save } from "lucide-react";

import {
  createCampaign,
  fetchCampaign,
  fetchCampaignRecipients,
  fetchMessageTemplates,
  fetchSegments,
  launchCampaign,
  previewCampaign,
  updateCampaign,
} from "@/services/api/customerIntel";
import { EmptyNote } from "./badges";

const RECIPIENT_STATUS_STYLES = {
  pending:   "bg-slate-100 text-slate-600",
  queued:    "bg-blue-100 text-blue-700",
  sent:      "bg-emerald-100 text-emerald-700",
  delivered: "bg-emerald-100 text-emerald-800",
  read:      "bg-teal-100 text-teal-800",
  replied:   "bg-indigo-100 text-indigo-800",
  failed:    "bg-red-100 text-red-700",
  skipped:   "bg-amber-100 text-amber-700",
  opted_out: "bg-amber-100 text-amber-800",
};

export default function CampaignForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [segments, setSegments] = useState([]);
  const [templates, setTemplates] = useState([]);

  const [name, setName] = useState("");
  const [segmentId, setSegmentId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [body, setBody] = useState("");
  const [throttle, setThrottle] = useState(20);
  const [scheduledAt, setScheduledAt] = useState("");

  const [campaign, setCampaign] = useState(null);
  const [preview, setPreview] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const editable = !campaign || ["draft", "scheduled"].includes(campaign.status);

  useEffect(() => {
    fetchSegments().then((r) => {
      if (r.success) setSegments(r.data.results || r.data || []);
    });
    fetchMessageTemplates().then((r) => {
      if (r.success) setTemplates(r.data.results || r.data || []);
    });
  }, []);

  const load = useCallback(async () => {
    if (!isEdit) return;
    const result = await fetchCampaign(id);
    if (!result.success) return;
    const c = result.data;
    setCampaign(c);
    setName(c.name);
    setSegmentId(String(c.segment || ""));
    setTemplateId(c.template ? String(c.template) : "");
    setBody(c.message_body || "");
    setThrottle(c.throttle_per_minute);
    setScheduledAt(c.scheduled_at ? c.scheduled_at.slice(0, 16) : "");

    const [p, r] = await Promise.all([
      previewCampaign(id),
      fetchCampaignRecipients(id, { page_size: 50 }),
    ]);
    if (p.success) setPreview(p.data);
    if (r.success) setRecipients(r.data.results || []);
  }, [id, isEdit]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!name.trim() || !segmentId) {
      setError("A campaign needs a name and a segment.");
      return null;
    }
    setSaving(true);
    setError("");
    const payload = {
      name: name.trim(),
      segment: Number(segmentId),
      template: templateId ? Number(templateId) : null,
      message_body: body,
      throttle_per_minute: Number(throttle) || 20,
      scheduled_at: scheduledAt || null,
    };
    const result = isEdit
      ? await updateCampaign(id, payload)
      : await createCampaign(payload);
    setSaving(false);

    if (!result.success) {
      const err = result.error;
      setError(typeof err === "string" ? err : Object.values(err || {}).flat().join(" "));
      return null;
    }
    return result.data;
  };

  const saveAndClose = async () => {
    const saved = await save();
    if (saved) navigate("/crm/campaigns");
  };

  const launch = async () => {
    const saved = await save();
    if (!saved) return;

    const count = preview?.sendable;
    const confirmText = count != null
      ? `Send this message to ${count} customer${count === 1 ? "" : "s"}?`
      : "Launch this campaign?";
    if (!window.confirm(confirmText)) return;

    const result = await launchCampaign(saved.id);
    if (result.success) navigate("/crm/campaigns");
    else setError(result.error?.error || "Could not launch the campaign.");
  };

  return (
    <div className="space-y-4 p-4">
      <button
        type="button"
        onClick={() => navigate("/crm/campaigns")}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" /> All campaigns
      </button>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
            <label className="block text-xs text-slate-600">
              Campaign name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!editable}
                placeholder="e.g. Diwali collection preview"
                className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
              />
            </label>

            <label className="block text-xs text-slate-600">
              Send to segment
              <select
                value={segmentId}
                onChange={(e) => setSegmentId(e.target.value)}
                disabled={!editable}
                className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
              >
                <option value="">Choose a segment…</option>
                {segments.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}{s.last_member_count ? ` (${s.last_member_count})` : ""}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-xs text-slate-600">
              Approved template
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                disabled={!editable}
                className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
              >
                <option value="">None — free text (webhook providers only)</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}{t.provider_template_name ? ` · ${t.provider_template_name}` : ""}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-start gap-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                WhatsApp will not deliver free-form text outside a 24-hour reply
                window. For Meta, WATI and AiSensy, pick a template that is
                already approved on the provider side or the send will fail.
              </span>
            </div>

            <label className="block text-xs text-slate-600">
              Message
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                disabled={!editable}
                rows={4}
                placeholder="Hello {{customer_name}}, our new collection has just arrived…"
                className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
              />
              <span className="mt-1 block text-slate-400">
                Placeholders: {"{{customer_name}}"}, {"{{first_name}}"},
                {" "}{"{{retail_name}}"}, {"{{city}}"}
              </span>
            </label>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-xs text-slate-600">
                Messages per minute
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={throttle}
                  onChange={(e) => setThrottle(e.target.value)}
                  disabled={!editable}
                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
                />
              </label>
              <label className="block text-xs text-slate-600">
                Schedule for (optional)
                <input
                  type="datetime-local"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  disabled={!editable}
                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm disabled:bg-slate-50"
                />
              </label>
            </div>
          </div>

          {editable && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={saveAndClose}
                disabled={saving}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <Save className="h-4 w-4" /> Save draft
              </button>
              <button
                type="button"
                onClick={launch}
                disabled={saving}
                className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                <Rocket className="h-4 w-4" />
                {scheduledAt ? "Save & schedule" : "Save & send now"}
              </button>
              {error && <span className="text-sm text-red-600">{error}</span>}
            </div>
          )}

          {recipients.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Customer</th>
                    <th className="px-3 py-2">Mobile</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recipients.map((r) => (
                    <tr key={r.id}>
                      <td className="px-3 py-2 text-slate-800">{r.customer_name}</td>
                      <td className="px-3 py-2 text-slate-600">{r.mobile || "—"}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded px-2 py-0.5 text-xs ${RECIPIENT_STATUS_STYLES[r.status] || ""}`}>
                          {r.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {r.error_message || (r.sent_at ? new Date(r.sent_at).toLocaleString("en-IN") : "")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── who will receive this ─────────────────────────────────────── */}
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-800">Who will receive this</h3>
          {preview ? (
            <>
              <div className="text-3xl font-semibold text-emerald-600">
                {preview.sendable}
              </div>
              <p className="text-xs text-slate-500">
                {preview.total} in the segment
                {preview.opted_out > 0 && (
                  <> · <strong>{preview.opted_out} opted out</strong> and will be skipped</>
                )}
              </p>
              {preview.sample_message && (
                <div className="mt-2 rounded border border-slate-200 bg-slate-50 p-2">
                  <div className="text-xs uppercase tracking-wide text-slate-400">
                    Sample
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                    {preview.sample_message}
                  </p>
                </div>
              )}
            </>
          ) : (
            <EmptyNote>
              Save the campaign to see exactly how many customers it will reach.
            </EmptyNote>
          )}
        </div>
      </div>
    </div>
  );
}

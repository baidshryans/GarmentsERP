// WhatsApp campaigns — list, progress, and the pause/resume controls.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Megaphone, Pause, Play, Plus, XCircle } from "lucide-react";

import {
  cancelCampaign,
  fetchCampaigns,
  pauseCampaign,
  resumeCampaign,
} from "@/services/api/customerIntel";
import { EmptyNote } from "./badges";

const STATUS_STYLES = {
  draft:     "bg-slate-100 text-slate-700",
  scheduled: "bg-blue-100 text-blue-700",
  running:   "bg-emerald-100 text-emerald-700",
  paused:    "bg-amber-100 text-amber-700",
  completed: "bg-indigo-100 text-indigo-700",
  cancelled: "bg-slate-200 text-slate-600",
  failed:    "bg-red-100 text-red-700",
};

function ProgressBar({ campaign }) {
  const total = campaign.total_recipients || 0;
  if (!total) return null;
  const done = (campaign.sent_count || 0) + (campaign.failed_count || 0)
    + (campaign.skipped_count || 0);
  const pct = Math.min(100, Math.round((done / total) * 100));
  return (
    <div className="mt-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
        <span>{campaign.sent_count} sent</span>
        {campaign.failed_count > 0 && (
          <span className="text-red-600">{campaign.failed_count} failed</span>
        )}
        {campaign.skipped_count > 0 && (
          <span className="text-amber-600">{campaign.skipped_count} skipped</span>
        )}
        <span className="ml-auto">{done} of {total}</span>
      </div>
    </div>
  );
}

export default function CampaignList() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const result = await fetchCampaigns();
    if (result.success) {
      setCampaigns(result.data.results || result.data || []);
      setError("");
    } else {
      setError("Could not load campaigns.");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Running campaigns drain a slice a minute, so refresh while any is in flight.
  useEffect(() => {
    const anyRunning = campaigns.some((c) => c.status === "running");
    if (!anyRunning) return undefined;
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [campaigns, load]);

  const act = async (fn, campaign) => {
    const result = await fn(campaign.id);
    if (result.success) load();
    else setError(result.error?.error || "That action was not allowed.");
  };

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Campaigns</h1>
          <p className="text-sm text-slate-500">
            Messages are sent in slices each minute, so a large campaign drains
            gradually and can be paused at any point.
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/crm/campaigns/new")}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" /> New campaign
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Loading…</p>}

      {!loading && campaigns.length === 0 && (
        <EmptyNote>
          No campaigns yet. Create a segment first, then send it a message.
        </EmptyNote>
      )}

      <div className="space-y-3">
        {campaigns.map((campaign) => (
          <div key={campaign.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <button
                type="button"
                onClick={() => navigate(`/crm/campaigns/${campaign.id}`)}
                className="text-left"
              >
                <div className="flex items-center gap-2">
                  <Megaphone className="h-4 w-4 text-slate-300" />
                  <span className="font-medium text-slate-800 hover:text-indigo-700">
                    {campaign.name}
                  </span>
                  <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLES[campaign.status] || ""}`}>
                    {campaign.status}
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-slate-500">
                  {campaign.campaign_no ? `${campaign.campaign_no} · ` : ""}
                  to “{campaign.segment_name}”
                  {campaign.scheduled_at ? ` · scheduled ${new Date(campaign.scheduled_at).toLocaleString("en-IN")}` : ""}
                </div>
              </button>

              <div className="flex items-center gap-2">
                {campaign.status === "running" && (
                  <button
                    type="button"
                    onClick={() => act(pauseCampaign, campaign)}
                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50"
                  >
                    <Pause className="h-3.5 w-3.5" /> Pause
                  </button>
                )}
                {campaign.status === "paused" && (
                  <button
                    type="button"
                    onClick={() => act(resumeCampaign, campaign)}
                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50"
                  >
                    <Play className="h-3.5 w-3.5" /> Resume
                  </button>
                )}
                {["running", "paused", "scheduled"].includes(campaign.status) && (
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm("Cancel this campaign? Unsent messages will be dropped.")) {
                        act(cancelCampaign, campaign);
                      }
                    }}
                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                  >
                    <XCircle className="h-3.5 w-3.5" /> Cancel
                  </button>
                )}
              </div>
            </div>

            <ProgressBar campaign={campaign} />

            {campaign.last_error && (
              <p className="mt-2 text-xs text-red-600">{campaign.last_error}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

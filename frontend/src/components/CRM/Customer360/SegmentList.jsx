// Saved segments — the lists campaigns and audience exports are aimed at.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Filter, Plus, Share2, Trash2 } from "lucide-react";

import apiClient from "@/services/apiClient";
import {
  deleteSegment,
  fetchSegments,
  metaAudienceUrl,
  segmentExportUrl,
} from "@/services/api/customerIntel";
import { EmptyNote } from "./badges";

export default function SegmentList() {
  const navigate = useNavigate();
  const [segments, setSegments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchSegments();
    if (result.success) {
      setSegments(result.data.results || result.data || []);
      setError("");
    } else {
      setError("Could not load segments.");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (segment) => {
    if (!window.confirm(`Delete the segment “${segment.name}”?`)) return;
    const result = await deleteSegment(segment.id);
    if (result.success) load();
    else setError("Could not delete that segment.");
  };

  // Exports go through apiClient so the auth and retail headers are attached,
  // then are handed to the browser as a blob download.
  const exportCsv = async (segment) => {
    try {
      const response = await apiClient.get(segmentExportUrl(segment.id), {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `segment-${segment.name}.csv`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(
        e.response?.status === 403
          ? "You do not have permission to export customer data."
          : "Export failed.",
      );
    }
  };

  // Exporting hashed identifiers to Meta is a cross-border transfer of personal
  // data, so the dialog names exactly which fields leave before it happens.
  const exportMetaAudience = async (segment) => {
    const confirmed = window.confirm(
      [
        `Send “${segment.name}” to Meta as a Custom Audience?`,
        "",
        "The file contains SHA-256 hashes of: phone, email, first name, " +
        "last name, city and country. Nothing leaves in plain text, and no " +
        "data comes back from Meta.",
        "",
        "Customers who have opted out of marketing are excluded automatically.",
      ].join("\n")
    );
    if (!confirmed) return;

    try {
      const response = await apiClient.get(metaAudienceUrl(segment.id), {
        responseType: "blob",
      });
      const exported = response.headers["x-audience-exported"];
      const optedOut = response.headers["x-audience-opted-out"];

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = `meta-audience-${segment.name}.csv`;
      link.click();
      window.URL.revokeObjectURL(url);

      setNotice(
        `${exported} customer${exported === "1" ? "" : "s"} exported` +
        (Number(optedOut) > 0 ? ` · ${optedOut} skipped (opted out)` : "")
      );
    } catch (e) {
      setError(
        e.response?.status === 403
          ? "You do not have permission to export customer data."
          : "Meta audience export failed.",
      );
    }
  };

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Segments</h1>
          <p className="text-sm text-slate-500">
            Saved customer lists. Membership is recalculated every time they're used.
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/crm/segments/new")}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" /> New segment
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {notice && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {notice}
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Loading…</p>}

      {!loading && segments.length === 0 && (
        <EmptyNote>
          No segments yet. Create one to target a campaign — for example
          “bought diamonds, silent 9 months”.
        </EmptyNote>
      )}

      {segments.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {segments.map((segment) => (
            <div key={segment.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <button
                  type="button"
                  onClick={() => navigate(`/crm/segments/${segment.id}`)}
                  className="text-left"
                >
                  <div className="font-medium text-slate-800 hover:text-indigo-700">
                    {segment.name}
                  </div>
                  {segment.description && (
                    <div className="mt-0.5 text-xs text-slate-500">{segment.description}</div>
                  )}
                </button>
                <Filter className="h-4 w-4 shrink-0 text-slate-300" />
              </div>

              <div className="mt-3 text-sm text-slate-600">
                {segment.last_member_count > 0 || segment.last_evaluated_at ? (
                  <>
                    <strong>{segment.last_member_count.toLocaleString("en-IN")}</strong> members
                    <span className="block text-xs text-slate-400">
                      as of last evaluation
                    </span>
                  </>
                ) : (
                  <span className="text-xs text-slate-400">not evaluated yet</span>
                )}
              </div>

              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => navigate(`/crm/segments/${segment.id}`)}
                  className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => exportCsv(segment)}
                  className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                  title="Download as CSV — requires the export permission"
                >
                  <Download className="h-3.5 w-3.5" /> CSV
                </button>
                <button
                  type="button"
                  onClick={() => exportMetaAudience(segment)}
                  className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                  title="Export as a hashed Meta Custom Audience for Facebook/Instagram ads"
                >
                  <Share2 className="h-3.5 w-3.5" /> Meta
                </button>
                <button
                  type="button"
                  onClick={() => remove(segment)}
                  className="ml-auto rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                  title="Delete segment"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

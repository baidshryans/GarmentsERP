// Build a saved customer segment, with a live member count as you type.
//
// The field catalogue comes from the backend (GET /api/segments/fields/) so the
// builder and the compiler can never disagree about what is filterable.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Plus, Save, Trash2 } from "lucide-react";

import {
  createSegment,
  fetchSegment,
  fetchSegmentFields,
  previewSegment,
  updateSegment,
} from "@/services/api/customerIntel";
import { EmptyNote, Money, SegmentChip } from "./badges";

const OP_LABELS = {
  eq: "is", ne: "is not", in: "is any of",
  gt: "more than", gte: "at least", lt: "less than", lte: "at most",
  icontains: "contains", iexact: "is exactly", isnull: "is empty",
};

function RuleRow({ rule, fieldsByKey, groups, onChange, onRemove }) {
  const field = fieldsByKey[rule.field];

  const setField = (key) => {
    const next = fieldsByKey[key];
    onChange({ field: key, op: next.ops[0], value: next.kind === "bool" ? true : "" });
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-white p-2">
      <select
        value={rule.field}
        onChange={(e) => setField(e.target.value)}
        className="min-w-[190px] rounded border border-slate-200 px-2 py-1.5 text-sm"
      >
        {groups.map((g) => (
          <optgroup key={g.group} label={g.group}>
            {g.fields.map((f) => (
              <option key={f.key} value={f.key}>{f.label}</option>
            ))}
          </optgroup>
        ))}
      </select>

      <select
        value={rule.op}
        onChange={(e) => onChange({ ...rule, op: e.target.value })}
        className="rounded border border-slate-200 px-2 py-1.5 text-sm"
      >
        {(field?.ops || []).map((op) => (
          <option key={op} value={op}>{OP_LABELS[op] || op}</option>
        ))}
      </select>

      {field?.kind === "bool" ? (
        <select
          value={String(rule.value)}
          onChange={(e) => onChange({ ...rule, value: e.target.value === "true" })}
          className="rounded border border-slate-200 px-2 py-1.5 text-sm"
        >
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      ) : field?.kind === "choice" && rule.op !== "in" ? (
        <select
          value={rule.value ?? ""}
          onChange={(e) => onChange({ ...rule, value: e.target.value })}
          className="rounded border border-slate-200 px-2 py-1.5 text-sm"
        >
          <option value="">Choose…</option>
          {field.choices.map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
          ))}
        </select>
      ) : rule.op === "in" ? (
        <select
          multiple
          value={Array.isArray(rule.value) ? rule.value.map(String) : []}
          onChange={(e) =>
            onChange({
              ...rule,
              value: Array.from(e.target.selectedOptions, (o) => o.value),
            })
          }
          className="min-w-[200px] rounded border border-slate-200 px-2 py-1.5 text-sm"
          size={4}
        >
          {(field?.choices || []).map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
          ))}
        </select>
      ) : (
        <input
          type={field?.kind === "text" ? "text" : "number"}
          value={rule.value ?? ""}
          onChange={(e) => onChange({ ...rule, value: e.target.value })}
          placeholder={field?.kind === "text" ? "value" : "0"}
          className="w-36 rounded border border-slate-200 px-2 py-1.5 text-sm"
        />
      )}

      <button
        type="button"
        onClick={onRemove}
        className="ml-auto rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
        title="Remove rule"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function SegmentBuilder() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [groups, setGroups] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [match, setMatch] = useState("all");
  const [rules, setRules] = useState([]);

  const [preview, setPreview] = useState({ count: null, sample: [] });
  const [previewError, setPreviewError] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const fieldsByKey = useMemo(() => {
    const map = {};
    groups.forEach((g) => g.fields.forEach((f) => { map[f.key] = f; }));
    return map;
  }, [groups]);

  useEffect(() => {
    fetchSegmentFields().then((r) => {
      if (r.success) setGroups(r.data || []);
    });
  }, []);

  useEffect(() => {
    if (!isEdit) return;
    fetchSegment(id).then((r) => {
      if (!r.success) return;
      setName(r.data.name);
      setDescription(r.data.description || "");
      setMatch(r.data.definition?.match || "all");
      setRules(r.data.definition?.rules || []);
    });
  }, [id, isEdit]);

  const definition = useMemo(() => ({ match, rules }), [match, rules]);

  // Debounced so a half-typed threshold does not hammer the API.
  const runPreview = useCallback(async () => {
    setPreviewing(true);
    const result = await previewSegment(definition);
    setPreviewing(false);
    if (result.success) {
      setPreview(result.data);
      setPreviewError("");
    } else {
      const err = result.error;
      setPreviewError(
        Array.isArray(err?.error) ? err.error.join(" ") : err?.error || "Invalid rule.",
      );
    }
  }, [definition]);

  useEffect(() => {
    const timer = setTimeout(runPreview, 400);
    return () => clearTimeout(timer);
  }, [runPreview]);

  const addRule = () => {
    const first = groups[0]?.fields?.[0];
    if (!first) return;
    setRules((r) => [...r, { field: first.key, op: first.ops[0], value: "" }]);
  };

  const save = async () => {
    if (!name.trim()) { setSaveError("Give the segment a name."); return; }
    setSaving(true);
    setSaveError("");
    const payload = { name: name.trim(), description, definition };
    const result = isEdit
      ? await updateSegment(id, payload)
      : await createSegment(payload);
    setSaving(false);
    if (result.success) navigate("/crm/segments");
    else {
      const err = result.error;
      setSaveError(
        typeof err === "string" ? err : Object.values(err || {}).flat().join(" "),
      );
    }
  };

  return (
    <div className="space-y-4 p-4">
      <button
        type="button"
        onClick={() => navigate("/crm/segments")}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" /> All segments
      </button>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs text-slate-600">
                Segment name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Lapsed diamond buyers"
                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-xs text-slate-600">
                Description
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What is this list for?"
                  className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
                />
              </label>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-600">Include customers matching</span>
              <select
                value={match}
                onChange={(e) => setMatch(e.target.value)}
                className="rounded border border-slate-200 px-2 py-1 text-sm"
              >
                <option value="all">all of these rules</option>
                <option value="any">any of these rules</option>
              </select>
            </div>

            <div className="mt-3 space-y-2">
              {rules.map((rule, index) => (
                <RuleRow
                  key={index}
                  rule={rule}
                  fieldsByKey={fieldsByKey}
                  groups={groups}
                  onChange={(next) =>
                    setRules((r) => r.map((x, i) => (i === index ? next : x)))
                  }
                  onRemove={() => setRules((r) => r.filter((_, i) => i !== index))}
                />
              ))}
              {rules.length === 0 && (
                <EmptyNote>
                  No rules yet — this segment would include every customer.
                </EmptyNote>
              )}
            </div>

            <button
              type="button"
              onClick={addRule}
              disabled={!groups.length}
              className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" /> Add rule
            </button>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save segment"}
            </button>
            {saveError && <span className="text-sm text-red-600">{saveError}</span>}
          </div>
        </div>

        {/* ── live preview ─────────────────────────────────────────────── */}
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-800">Matching customers</h3>
          {previewError ? (
            <p className="mt-2 rounded border border-red-200 bg-red-50 px-2 py-1.5 text-sm text-red-700">
              {previewError}
            </p>
          ) : (
            <>
              <div className="mt-1 text-3xl font-semibold text-indigo-600">
                {previewing ? "…" : (preview.count ?? 0).toLocaleString("en-IN")}
              </div>
              <p className="text-xs text-slate-500">
                updates as you edit the rules
              </p>

              <ul className="mt-3 max-h-96 space-y-2 overflow-y-auto">
                {(preview.sample || []).map((c) => (
                  <li key={c.id} className="border-b border-slate-100 pb-2 last:border-0">
                    <div className="text-sm font-medium text-slate-700">{c.ac_name}</div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <SegmentChip segment={c.rfm_segment} />
                      <Money value={c.lifetime_value} />
                    </div>
                  </li>
                ))}
              </ul>
              {preview.count > (preview.sample?.length || 0) && (
                <p className="mt-2 text-xs text-slate-400">
                  showing the first {preview.sample.length}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

import React from "react";
import Select from "react-select";
import useUnbarcodedList from "../../../hooks/useUnbarcodedList";

/**
 * Single-select picker backed by UnBarcodedMain filtered by karigar ownership.
 * Accepts value=<id> and calls onChange(pieceObj) with the full option object
 * (so the caller can populate item/purity/gw side columns).
 *
 * Props:
 *   karigarId    � ledger id; pieces with another karigar are hidden
 *   value        � currently selected UnBarcodedMain id (or null)
 *   onChange(opt)� called with the selected option (or null)
 *   isDisabled
 */
export default function UnbarcodedPicker({ karigarId, value, onChange, isDisabled }) {
  const { options, loading } = useUnbarcodedList({ karigarId });

  const mapped = options.map((o) => ({
    ...o,
    value: o.id,
    // Show a trailing "(with <karigar>)" tag only if the piece is with the
    // current karigar � available elsewhere pieces are hidden server-side.
    label: o.with_karigar ? `${o.label}  �  with ${o.with_karigar}` : o.label,
  }));

  const selected = mapped.find((o) => o.value === value) || null;

  return (
    <Select
      isClearable
      isDisabled={isDisabled}
      isLoading={loading}
      value={selected}
      options={mapped}
      onChange={(opt) => onChange(opt || null)}
      placeholder="Select piece�"
      menuPortalTarget={typeof document !== "undefined" ? document.body : null}
      styles={{ menuPortal: (b) => ({ ...b, zIndex: 9999 }) }}
    />
  );
}

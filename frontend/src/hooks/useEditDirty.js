import { useState, useCallback } from "react";

/**
 * Tracks whether an edit form has unsaved changes.
 * Combines react-hook-form's `isDirty` with a manual `tableDirty` flag for
 * non-RHF state like row arrays (rs/items). In create mode (no id), Save is
 * always enabled. In edit mode, Save is disabled until something changes.
 */
export function useEditDirty({ id, isDirty }) {
  const [tableDirty, setTableDirty] = useState(false);
  const isEdit = !!id;
  const dirty = !!isDirty || tableDirty;
  const canSave = !isEdit || dirty;
  const markTableDirty = useCallback(() => setTableDirty(true), []);
  const resetTableDirty = useCallback(() => setTableDirty(false), []);
  const saveLabel = (saving) =>
    saving ? (isEdit ? "Updating…" : "Saving…") : isEdit ? "Update" : "Save";
  return { isEdit, dirty, canSave, saveLabel, markTableDirty, resetTableDirty };
}

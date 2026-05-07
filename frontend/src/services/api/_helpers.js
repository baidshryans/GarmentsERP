// frontend/src/services/api/_helpers.js
// Shared internal helpers for all domain API modules.
import apiClient from "../apiClient";

/**
 * Thin wrapper around apiClient that normalises responses to
 * { success: true, data } | { success: false, error }.
 * Use for simple GET/POST/PATCH/DELETE calls.
 */
export const _api = async (method, url, data) => {
  try {
    const r = await apiClient[method](url, data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

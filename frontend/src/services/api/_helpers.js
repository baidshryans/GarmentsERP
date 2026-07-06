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

export async function deleteResource(url, id) {
  try {
    const response = await apiClient.delete(`${url}/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`Failed to delete resource at ${url}:`, error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Note: page-reload belongs in the component layer, not the API layer.
// TODO: move the reload side-effect into each call-site component.
export function handleDelete(result, toast, message, onSuccess) {
  if (result.success) {
    toast({ title: "Success", description: message });
    // Callers that can refresh their own list in place (e.g. a paginated
    // table) should pass onSuccess so a delete doesn't reload the whole app
    // and reset unrelated state like the current page number.
    if (onSuccess) {
      onSuccess();
    } else {
      setTimeout(() => window.location.reload(), 600);
    }
  } else {
    toast({ title: "Error", description: result.error });
  }
}

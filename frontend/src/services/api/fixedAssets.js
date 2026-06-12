// frontend/src/services/api/fixedAssets.js
import apiClient from "../apiClient";

export async function fetchFixedAssets(params = {}) {
  try {
    const response = await apiClient.get("/accounting/api/fa/assets/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createFixedAsset(data) {
  try {
    const response = await apiClient.post("/accounting/api/fa/assets/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateFixedAsset(id, data) {
  try {
    const response = await apiClient.patch(`/accounting/api/fa/assets/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function generateDepreciationSuggestion(data) {
  try {
    const response = await apiClient.post("/accounting/api/fa/generate-suggestion/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function postDepreciation(payload) {
  try {
    const response = await apiClient.post("/accounting/api/fa/post-depreciation/", payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchFASettings() {
  try {
    const response = await apiClient.get("/accounting/api/fa/settings/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function saveFASettings(data) {
  try {
    const response = await apiClient.put("/accounting/api/fa/settings/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

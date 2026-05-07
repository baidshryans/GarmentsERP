// frontend/src/services/api/carryforward.js
import apiClient from "../apiClient";

export async function carryForwardPreview({ cutoff_date, retail_id }) {
  try {
    const r = await apiClient.post("/carryforward/api/carry-forward/preview/", { cutoff_date, retail_id });
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function carryForwardExecute({ cutoff_date, retail_id }) {
  try {
    const r = await apiClient.post("/carryforward/api/carry-forward/execute/", { cutoff_date, retail_id });
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getCarryForwardLog() {
  try {
    const r = await apiClient.get("/carryforward/api/carry-forward/log/");
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

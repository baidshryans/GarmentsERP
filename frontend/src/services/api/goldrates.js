// frontend/src/services/api/goldrates.js
import apiClient from "../apiClient";

export async function getGoldRate(date) {

  try {
    const response = await apiClient.get(`/goldrates/api/current-gold-rate/?date=${date}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

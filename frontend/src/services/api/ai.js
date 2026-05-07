// frontend/src/services/api/ai.js
import apiClient from "../apiClient";

export async function askAIQuery(query) {
  try {
    const response = await apiClient.post("/ai/nl-query/", { query });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function parseInvoice(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/ai/invoice-parse/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function suggestAccounts(narration, voucherType = "JRNL", amount = 0) {
  try {
    const response = await apiClient.post("/ai/suggest-accounts/", {
      narration,
      voucher_type: voucherType,
      amount,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

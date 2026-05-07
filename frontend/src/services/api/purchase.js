// frontend/src/services/api/purchase.js
import apiClient from "../apiClient";

// ── Private helpers (mirrors apiService.js internals) ─────────────────────────
async function deleteResource(url, id) {
  try {
    const response = await apiClient.delete(`${url}/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error(`Failed to delete resource at ${url}:`, error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

function handleDelete(result, toast, message) {
  if (result.success) {
    toast({ title: "Success", description: message });
    setTimeout(() => window.location.reload(), 600);
  } else {
    toast({ title: "Error", description: result.error });
  }
}

// ── Next-number helpers ────────────────────────────────────────────────────────

export async function fetchPVNoNext(voucher_type = 'Vendor') {
  try {
    const response = await apiClient.get(`/purchase/get-next-pv-no/`, { params: { voucher_type } });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPRNoNext() {
  try {
    const response = await apiClient.get(`/purchase/get-next-pr-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPoNoNext() {
  try {
    const response = await apiClient.get(`/purchase/get-next-po-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── List fetchers ──────────────────────────────────────────────────────────────

export async function fetchPurchaseVoucher({ search = "", page = 1, ordering = "", voucher_type = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (voucher_type) params.append("voucher_type", voucher_type);
    params.append("page", page);

    const response = await apiClient.get(`/purchase/api/purchase-voucher/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseOrder({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/purchase/api/purchase-order/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseRetun({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/purchase/api/purchase-return/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseApproval() {
  return { results: [] }
  try {
    const response = await apiClient.get(``);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPos(slip_type) {
  try {
    const response = await apiClient.get(`manufacturing/get-pojo-list/?slip_type=${slip_type}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Purchase Order CRUD ────────────────────────────────────────────────────────

export async function updatePurchaseOrderForEdit(data, id) {

  try {
    const response = await apiClient.put(`/purchase/api/purchase-order/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update PurchaseOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createPurchaseOrder(data) {

  try {
    const response = await apiClient.post("/purchase/api/purchase-order/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create PurchaseOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseOrderForEdit(id) {

  try {
    const response = await apiClient.get(`/purchase/api/purchase-order/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPendingPOItemsByVendor(vendorId) {
  try {
    const response = await apiClient.get(`/purchase/api/pending-po-items/`, { params: { vendor: vendorId } });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch pending PO items:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Purchase Return CRUD ───────────────────────────────────────────────────────

export async function fetchDetailsForPurchaseReturn(po_no) {
  try {
    const response = await apiClient.get(`/purchase/api/fetch-pv-for-return/${po_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch purity :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createPurchaseReturn(data) {

  try {
    const response = await apiClient.post("/purchase/api/purchase-return/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create PurchaseReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updatePurchaseReturnForEdit(data, id) {

  try {
    const response = await apiClient.put(`/purchase/api/purchase-return/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update PurchaseReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseReturnForEdit(id) {

  try {
    const response = await apiClient.get(`/purchase/api/purchase-return/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseReturnInitialData() {
  try {
    const response = await apiClient.get(`/purchase/api/purchase-return-initial-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch purchase return initial data:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Purchase Attachments ───────────────────────────────────────────────────────

export async function getPurchaseAttachments(purchaseId) {
  try {
    const response = await apiClient.get(`/purchase/api/purchase-attachments/?purchase=${purchaseId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function uploadPurchaseAttachment(purchaseId, file) {
  try {
    const formData = new FormData();
    formData.append("purchase", purchaseId);
    formData.append("file", file);
    const response = await apiClient.post("/purchase/api/purchase-attachments/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deletePurchaseAttachment(id) {
  try {
    await apiClient.delete(`/purchase/api/purchase-attachments/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Purchase Voucher CRUD ──────────────────────────────────────────────────────

export async function updatePurchaseVoucherForEdit(data, id) {

  try {
    const response = await apiClient.put(`/purchase/api/purchase-voucher/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, status: error.response?.status, error: error.response?.data || error.message };
  }
}

export async function createPurchaseVoucher(data) {

  try {
    const response = await apiClient.post("/purchase/api/purchase-voucher/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, status: error.response?.status, error: error.response?.data || error.message };
  }
}

// ── Delete actions ─────────────────────────────────────────────────────────────

export const deletePurchaseVoucher = async (id) => {
  const result = await deleteResource("purchase/api/purchase-voucher", id);
  if (!result.success) throw new Error(result.error?.detail || "Failed to delete purchase voucher");
  return result;
};

export const deletePurchaseReturn = async (id, toast) => {
  const result = await deleteResource("purchase/api/purchase-return", id);
  handleDelete(result, toast, "Purchase return deleted successfully.");
};

export const deletePurchaseOrder = async (id, toast) => {
  const result = await deleteResource("purchase/api/purchase-order", id);
  handleDelete(result, toast, "Purchase order deleted successfully.");
};

// ── Sample / matching ──────────────────────────────────────────────────────────

export async function fetchPurchaseVoucherForSample(billNo) {
  try {
    const response = await apiClient.get(`/manufacturing/api/purchase-voucher-for-sample/?bill_no=${encodeURIComponent(billNo)}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseVouchersForSample(query = "") {
  try {
    const response = await apiClient.get(`/manufacturing/api/purchase-vouchers-for-sample/?q=${encodeURIComponent(query)}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStockMatchingReport({ from, to, tolerance = 0.05, mismatchesOnly = false } = {}) {
  try {
    const params = {};
    if (from) params.from = from;
    if (to) params.to = to;
    if (tolerance != null) params.tolerance = tolerance;
    if (mismatchesOnly) params.mismatches_only = 1;
    const response = await apiClient.get(`/purchase/api/stock-matching/`, { params });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch stock matching report:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

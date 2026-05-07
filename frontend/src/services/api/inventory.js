// frontend/src/services/api/inventory.js
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

// ── Closing Stock ─────────────────────────────────────────────────────────────

export async function getClosingStockValuation({ to_date, retail_ids, hide_zero } = {}) {
  try {
    const params = new URLSearchParams();
    if (to_date) params.append("to_date", to_date);
    if (Array.isArray(retail_ids) && retail_ids.length > 0) {
      retail_ids.forEach((rid) => params.append("retail_ids", String(rid)));
    }
    if (hide_zero === false) params.append("hide_zero", "false");
    const response = await apiClient.get(`/inventory/api/closing-stock?${params.toString()}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch closing stock:", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Inter-Retail Transfer Vouchers ────────────────────────────────────────
export async function fetchInterRetailTransfers(params = {}) {
  try {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qp.append(k, v);
    });
    const qs = qp.toString();
    const response = await apiClient.get(`/inventory/inter-retail-transfers/${qs ? `?${qs}` : ""}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch inter-retail transfers:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchInterRetailTransfer(id) {
  try {
    const response = await apiClient.get(`/inventory/inter-retail-transfers/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createInterRetailTransfer(payload) {
  try {
    const response = await apiClient.post(`/inventory/inter-retail-transfers/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateInterRetailTransfer(id, payload) {
  try {
    const response = await apiClient.patch(`/inventory/inter-retail-transfers/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteInterRetailTransfer(id) {
  try {
    const response = await apiClient.delete(`/inventory/inter-retail-transfers/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function sendInterRetailTransfer(id) {
  try {
    const response = await apiClient.post(`/inventory/inter-retail-transfers/${id}/send/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function receiveInterRetailTransfer(id) {
  try {
    const response = await apiClient.post(`/inventory/inter-retail-transfers/${id}/receive/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function cancelInterRetailTransfer(id) {
  try {
    const response = await apiClient.post(`/inventory/inter-retail-transfers/${id}/cancel/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getNextInterRetailTransferNo() {
  try {
    const response = await apiClient.get(`/inventory/api/next_inter_retail_transfer_no`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getClosingStockTxns({ item_id, txn_type, to_date } = {}) {
  try {
    const params = new URLSearchParams({ item_id, txn_type, to_date });
    const response = await apiClient.get(`/inventory/api/closing-stock-txns/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Stock Journal ─────────────────────────────────────────────────────────────

export async function fetchNextStockJournalNo() {
  try {
    const response = await apiClient.get(`/inventory/api/next_stock_journal_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createStockJournal(data) {

  try {
    const response = await apiClient.post("/inventory/stock-journal/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStockJournal({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/inventory/stock-journal/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStockJournalForEdit(id) {

  try {
    const response = await apiClient.get(`/inventory/stock-journal/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateStockJournalForEdit(data, id) {

  try {
    const response = await apiClient.put(`/inventory/stock-journal/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export const deleteStockJournal = async (id, toast) => {
  const result = await deleteResource("inventory/stock-journal", id);
  handleDelete(result, toast, "Stock journal deleted successfully.");
};

// ── Barcode Management ────────────────────────────────────────────────────────

export async function fetchBarcodeDetail(barcode, hsn, ldgr) {
  try {
    if ((barcode === "")) return { success: false, error: "Barcode should not be blank" }

    const qs = (ldgr !== undefined && ldgr !== null && ldgr !== "") ? `?ldgr=${encodeURIComponent(ldgr)}` : "";
    const response = await apiClient.get(`/inventory/api/get-barcode-detail/${barcode}/${hsn}/${qs}`);
    console.log(barcode)
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Serial numbers :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeForEdit(id) {

  try {
    const response = await apiClient.get(`/inventory/barcode/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch barcode:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeDetailOnly(barcode, ldgr) {
  try {
    if ((barcode === "")) return { success: false, error: "Barcode should not be blank" }

    const qs = (ldgr !== undefined && ldgr !== null && ldgr !== "") ? `?ldgr=${encodeURIComponent(ldgr)}` : "";
    const response = await apiClient.get(`/inventory/api/get-barcode-detail/${barcode}/${qs}`);
    console.log(barcode)
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Serial numbers :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateBarcodeForEdit(data, id) {

  try {
    const response = await apiClient.put(`/inventory/barcode/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update barcode:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function splitBarcode(data, oldBarcode) {

  try {
    const response = await apiClient.post(`/inventory/api/barcode-split/${oldBarcode}`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export const deleteBarcodeManagement = async (id, toast) => {
  const result = await deleteResource("inventory/barcode", id);
  handleDelete(result, toast, "Barcode management entry deleted successfully.");
};

export async function fetchUnbarcodedForPicker({ karigar } = {}) {
  try {
    const params = new URLSearchParams();
    if (karigar) params.append("karigar", karigar);
    const response = await apiClient.get(`/manufacturing/api/unbarcoded-picker/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchInTransitBarcodes() {
  try {
    const response = await apiClient.get('/inventory/stock-transfer/in-transit-barcodes/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Stock Transfer ────────────────────────────────────────────────────────────

export async function markStockTransferSent(id) {
  try {
    const response = await apiClient.post(`/inventory/stock-transfer/${id}/mark-sent/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function markStockTransferReceived(id) {
  try {
    const response = await apiClient.post(`/inventory/stock-transfer/${id}/mark-received/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export const deleteStockTransfer = async (id, toast) => {
  const result = await deleteResource("inventory/stock-transfer", id);
  handleDelete(result, toast, "Stock Transfer deleted successfully.");
};

export async function fetchNextStockTransferNo() {
  try {
    const response = await apiClient.get(`/inventory/api/next_stock_transfer_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Reports ───────────────────────────────────────────────────────────────────

export async function fetchStockValuationReport() {
  try {
    const response = await apiClient.get(`/inventory/api/stock-valuation-report/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchIDGenerationReport(fromDate, toDate, itemType, purity, minWeight, maxWeight) {
  try {
    const response = await apiClient.get('/inventory/api/idgeneration', {
      params: {
        start_date: fromDate,
        end_date: toDate,
        item_type: itemType,
        purity: purity,
        min_weight: minWeight,
        max_weight: maxWeight
      }
    });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ID Generation Report:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchIDGenerationReportAPI(filterParams = {}) {
  try {
    const queryParams = new URLSearchParams();

    if (filterParams.from_date) {
      queryParams.append('from_date', filterParams.from_date);
    }

    if (filterParams.to_date) {
      queryParams.append('to_date', filterParams.to_date);
    }

    if (filterParams.artisan_ids && filterParams.artisan_ids.length > 0) {
      queryParams.append('artisan_ids', filterParams.artisan_ids.join(','));
    }

    if (filterParams.item_ids && filterParams.item_ids.length > 0) {
      queryParams.append('item_ids', filterParams.item_ids.join(','));
    }

    if (filterParams.purity_ids && filterParams.purity_ids.length > 0) {
      queryParams.append('purity_ids', filterParams.purity_ids.join(','));
    }

    if (filterParams.user_ids && filterParams.user_ids.length > 0) {
      queryParams.append('user_ids', filterParams.user_ids.join(','));
    }

    const url = `/inventory/api/barcode-creation-report${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await apiClient.get(url);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Error fetching ID generation report:", error.response?.data || error.message);
    return { success: false, data: [], error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeStockReport(asOnDate) {
  try {
    const response = await apiClient.get(`/inventory/api/stock-report?as_on_date=${asOnDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function fetchBarcodeStockReportBarcodes({ itemId, column, asOnDate }) {
  try {
    const params = new URLSearchParams({ item_id: itemId, column, as_on_date: asOnDate });
    const response = await apiClient.get(`/inventory/api/stock-report/barcodes?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function fetchItemWiseBarcode(fromDate,toDate) {
  try {
    const response = await apiClient.get(`/inventory/api/item-barcode-report/?from_date=${fromDate}&to_date=${toDate}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch itemwise barcode report:", error.response?.data || error.message);
    throw error;
  }
}

// ── Opening Inventory ──────────────────────────────────────────────────────
export async function getOpeningInventory(type = null) {
  try {
    const params = type ? { type } : {};
    const response = await apiClient.get('/inventory/opening-inventory/', { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createOpeningInventory(data) {
  try {
    const response = await apiClient.post('/inventory/opening-inventory/', data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateOpeningInventory(id, data) {
  try {
    const response = await apiClient.patch(`/inventory/opening-inventory/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteOpeningInventory(id) {
  try {
    await apiClient.delete(`/inventory/opening-inventory/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getOpeningInventoryById(id) {
  try {
    const response = await apiClient.get(`/inventory/opening-inventory/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── RFID ──────────────────────────────────────────────────────────────────────

export async function fetchRfidTagList({ search = "", assigned = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (assigned) params.append("assigned", assigned);
    const r = await apiClient.get(`inventory/api/rfid/tags/?${params.toString()}`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function assignRfidTag(barcode, rfidTag) {
  try {
    const r = await apiClient.post("inventory/api/rfid/assign/", { barcode, rfid_tag: rfidTag });
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function submitRfidCount({ tags, save_session = false, note = "" } = {}) {
  try {
    const r = await apiClient.post("inventory/api/rfid/count/", { tags, save_session, note });
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRfidSessions() {
  try {
    const r = await apiClient.get("inventory/rfid-sessions/");
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRfidSessionResults(sessionId) {
  try {
    const r = await apiClient.get(`inventory/rfid-sessions/${sessionId}/results/`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

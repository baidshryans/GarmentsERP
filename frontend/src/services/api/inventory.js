// frontend/src/services/api/inventory.js
import apiClient from "../apiClient";
import { deleteResource, handleDelete } from "./_helpers";

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
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Serial numbers :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeForReturn(barcode) {
  try {
    if (!barcode) return { success: false, error: "Barcode cannot be blank" };
    const response = await apiClient.get(`/inventory/api/get-barcode-for-return/${barcode}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchBarcodeForReturn:", error.response?.data || error.message);
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

export async function downloadOpeningStockTemplate() {
  try {
    const response = await apiClient.get('/inventory/api/templates/opening-stock/', {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'opening_stock_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadOpeningStockCSV(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/inventory/api/opening-stock/import/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
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

// ── Barcode List/Bulk ─────────────────────────────────────────────────────────

export async function fetchBarcodes({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`inventory/barcode/?stk_status=true&${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeList({ search = "", page = 1, ordering = "", ids = "", page_size = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (ids) params.append("ids", ids);
    if (page_size) params.append("page_size", page_size);
    params.append("page", page);
    const response = await apiClient.get(`inventory/barcode/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeBulk({ item, packet, purity, stk_status, search } = {}) {
  try {
    const params = new URLSearchParams();
    if (item) params.append("item", item);
    if (packet) params.append("packet", packet);
    if (purity) params.append("purity", purity);
    if (stk_status !== undefined && stk_status !== "") params.append("stk_status", stk_status);
    if (search) params.append("search", search);
    const response = await apiClient.get(`inventory/api/barcode-bulk/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeByText(barcodeText) {
  try {
    const response = await apiClient.get(
      `inventory/barcode/?barcode=${encodeURIComponent(barcodeText)}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch barcode by text:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeHistoryList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`inventory/brcode-history?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Barcode Merges / Splits ───────────────────────────────────────────────────

export async function fetchBarcodeMerges({ from_date = "", to_date = "" } = {}) {
  try {
    const params = new URLSearchParams({ transaction_type: "Merge" });
    if (from_date) params.append("date1__gte", from_date);
    if (to_date) params.append("date1__lte", to_date);
    const response = await apiClient.get(`inventory/api/brcode-split-merge?${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch barcode merges:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeSplits({ from_date = "", to_date = "" } = {}) {
  try {
    const params = new URLSearchParams({ transaction_type: "Split" });
    if (from_date) params.append("date1__gte", from_date);
    if (to_date) params.append("date1__lte", to_date);
    const response = await apiClient.get(`inventory/api/brcode-split-merge?${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch barcode splits:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Barcode CRUD ──────────────────────────────────────────────────────────────

export async function createBarcode(data) {
  try {
    const response = await apiClient.post("/inventory/barcode/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function convertBarcode(barcode) {
  const data = { barcode: barcode };
  try {
    const response = await apiClient.post("inventory/api/bar-unbar/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function mergeBarcode(data) {
  try {
    const response = await apiClient.post("/inventory/api/barcode-merge/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextBarcode() {
  try {
    const response = await apiClient.get(`/inventory/api/generate-barcode/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Barcode Images ────────────────────────────────────────────────────────────

export async function deleteBarcodeImage(id) {
  try {
    await apiClient.delete(`/inventory/api/barcode-images/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function uploadBarcodeImages(barcodeId, files) {
  try {
    const formData = new FormData();
    formData.append("barcode", barcodeId);
    for (const file of files) {
      formData.append("image", file);
    }
    const response = await apiClient.post("/inventory/api/barcode-images/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getBarcodeImages(barcodeId) {
  try {
    const response = await apiClient.get(`/inventory/api/barcode-images/?barcode=${barcodeId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function setBarcodeImagePrimary(id) {
  try {
    const response = await apiClient.patch(`/inventory/api/barcode-images/${id}/`, { is_primary: true });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function reorderBarcodeImages(barcodeId, orderedIds) {
  try {
    const response = await apiClient.post(`/inventory/api/barcode-images/reorder/`, {
      barcode: barcodeId,
      order: orderedIds,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Catalog (priced, design-driven) ───────────────────────────────────────────
export async function fetchCatalog(params = "") {
  try {
    const response = await apiClient.get(`/inventory/api/catalog/${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCatalogDetail(id, params = "") {
  try {
    const response = await apiClient.get(`/inventory/api/catalog/${id}/${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function downloadCatalogPdf(params = "") {
  try {
    const response = await apiClient.get(`/inventory/api/catalog/pdf/${params}`, { responseType: "blob" });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Catalog share links ───────────────────────────────────────────────────────
export async function fetchCatalogShares() {
  try {
    const r = await apiClient.get("/inventory/api/catalog-shares/");
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function createCatalogShare(data) {
  try {
    const r = await apiClient.post("/inventory/api/catalog-shares/", data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function deleteCatalogShare(id) {
  try {
    await apiClient.delete(`/inventory/api/catalog-shares/${id}/`);
    return { success: true };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function fetchPublicCatalog(token, params = "") {
  try {
    const r = await apiClient.get(`/inventory/api/catalog-share/${token}/${params}`);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message, status: e.response?.status }; }
}

// ── Design CRUD (catalog designs) ─────────────────────────────────────────────
export async function fetchDesigns(params = "") {
  try {
    const response = await apiClient.get(`/inventory/api/design-main/${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDesignForEdit(id) {
  try {
    const response = await apiClient.get(`/inventory/api/design-main/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createDesign(data) {
  try {
    const response = await apiClient.post("/inventory/api/design-main/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateDesign(data, id) {
  try {
    const response = await apiClient.put(`/inventory/api/design-main/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteDesign(id) {
  try {
    await apiClient.delete(`/inventory/api/design-main/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Design images (catalog photos) — mirror of barcode image helpers ──────────
export async function uploadDesignImages(designId, files) {
  try {
    const formData = new FormData();
    formData.append("design", designId);
    for (const file of files) {
      formData.append("image", file);
    }
    const response = await apiClient.post("/inventory/api/design-images/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getDesignImages(designId) {
  try {
    const response = await apiClient.get(`/inventory/api/design-images/?design=${designId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteDesignImage(id) {
  try {
    await apiClient.delete(`/inventory/api/design-images/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function reorderDesignImages(designId, orderedIds) {
  try {
    const response = await apiClient.post(`/inventory/api/design-images/reorder/`, {
      design: designId,
      order: orderedIds,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Barcode Order Ops ─────────────────────────────────────────────────────────

export async function releaseBarcodeFromOrder(id, { mode, remarks = "" }) {
  try {
    const response = await apiClient.post(
      `inventory/barcode/${id}/release-from-order/`,
      { mode, remarks }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function transferBarcodeToOrder(id, { order_id }) {
  try {
    const response = await apiClient.post(
      `inventory/barcode/${id}/transfer-to-order/`,
      { order_id }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Stock Transfer ────────────────────────────────────────────────────────────

export async function fetchStockTransferForEdit(id) {
  try {
    const response = await apiClient.get(`/inventory/stock-transfer/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStockTransferForList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`/inventory/stock-transfer/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createStockTransfer(data) {
  try {
    const response = await apiClient.post("/inventory/stock-transfer/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateStockTransferForEdit(data, id) {
  try {
    const response = await apiClient.put(`/inventory/stock-transfer/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Raw Material ──────────────────────────────────────────────────────────────

export async function getRawMaterialBalance(params = {}) {
  try {
    const query = new URLSearchParams(params).toString();
    const response = await apiClient.get(`/inventory/api/raw-material-balance/?${query}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getRawMaterialLedger(params = {}) {
  try {
    const query = new URLSearchParams(params).toString();
    const response = await apiClient.get(`/inventory/api/raw-material-ledger/?${query}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getRawMaterialTransactions(params = {}) {
  try {
    const query = new URLSearchParams(params).toString();
    const response = await apiClient.get(`inventory/raw-material-txn/?${query}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getSemiFinishedStock() {
  try {
    const response = await apiClient.get("/inventory/api/semi-finished-stock/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getUnbarcodedStockReport(params = {}) {
  try {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
    );
    const query = new URLSearchParams(cleaned).toString();
    const response = await apiClient.get(`inventory/api/unbarcoded-stock-report/?${query}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchUnBarcodedList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`inventory/unbarcoded/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPacketBalance(pcktNo) {
  try {
    const response = await apiClient.get(`manufacturing/packet-balance/?pckt_no=${encodeURIComponent(pcktNo)}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch packet balance:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

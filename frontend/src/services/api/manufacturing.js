// frontend/src/services/api/manufacturing.js
import apiClient from "../apiClient";
import { deleteResource, handleDelete } from "./_helpers";

// ── Karigar Issue ─────────────────────────────────────────────────────────────

export async function createKarigarIssue(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/karigar-issue/create/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createKarigarStoneIssue(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/karigar-stone-issue/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStoneIssueForEdit(id) {

  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-stone-issue/${id}/`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}


export async function updateKarigarStoneIssue(data, id) {

  try {
    const response = await apiClient.put(`/manufacturing/api/karigar-stone-issue/${id}/`, data);;

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createKarigarGoldIssue(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/karigar-gold-issue/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function FetchKarigarGoldIssueBill() {

  try {
    const response = await apiClient.get("/manufacturing/api/karigar-gold-issue/bill-no");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Sample Issue ───────────────────────────────────────────────────────────────

export async function createSampleIssue(data) {
  try {
    const response = await apiClient.post(`/manufacturing/api/sample-issue/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSampleIssue(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/sample-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSampleIssues({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (page) params.append("page", page);
    if (ordering) params.append("ordering", ordering);
    const response = await apiClient.get(`/manufacturing/api/sample-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSampleIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/sample-issue/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteSampleIssue(id) {
  try {
    await apiClient.delete(`/manufacturing/api/sample-issue/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSampleIssueNextBillno({ retail, fiscal_year } = {}) {
  try {
    const params = new URLSearchParams();
    if (retail) params.append("retail", retail);
    if (fiscal_year) params.append("fiscal_year", fiscal_year);
    const response = await apiClient.get(`/manufacturing/api/sample-issue/next-billno/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarReceiveSlipForSample(slipNo) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-slip-for-sample/?slip_no=${encodeURIComponent(slipNo)}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarReceiveSlipsForSample(query = "") {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-slips-for-sample/?q=${encodeURIComponent(query)}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeForSample(barcodeNo) {
  try {
    const response = await apiClient.get(`/manufacturing/api/barcode-for-sample/?barcode=${encodeURIComponent(barcodeNo)}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarReceiveForSamplePicker({ search } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-picker/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSampleIssueInitialData() {
  try {
    const response = await apiClient.get(`/manufacturing/api/sample-issue-initial-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Reports ───────────────────────────────────────────────────────────────────

export async function fetchKarigarStoneIssueReport(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-stoneissue-item-report?from_date=${fromDate}&to_date=${toDate}&packet_group=${packet_group}&krid=${krid}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarStoneRecReport(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-stonerec-item-report?from_date=${fromDate}&to_date=${toDate}&packet_group=${packet_group}&krid=${krid}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarReceiveReport(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-item-report?finish_status=true&karigar_ldgr=${ldgrs.join(",")}&purity=${purity}&date_from=${fromDate}&date_to=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchHallMarkIssueReport(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/manufacturing/api/hallmark-issue-report?start_date=${fromDate ?? ''}&end_date=${toDate ?? ''}&purity_id=${purity ?? ''}&ledger_ids=${ldgrs?.join(',') ?? ""}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurchaseFinished(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/purchase/api/purchase-vou-item?is_finished=true&ldgr=${ldgrs.join(",")}&purity=${purity}&date_from=${fromDate}&date_to=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchReceivedFinished(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-item-report?finish_status=true&karigar_ldgr=${ldgrs.join(",")}&purity=${purity}&date_from=${fromDate}&date_to=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchJobStatusReport(params = {}) {
  try {
    const response = await apiClient.get('/manufacturing/api/job-status-report', { params });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Job Status Report:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStockTransfer(fromDate, toDate, purity, ldgr) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-stonerec-item-report?from_date=${fromDate}&to_date=${toDate}&packet_group=${packet_group}&krid=${krid}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSubcontractorLedger({ karigar, start, end }) {
  try {
    const params = new URLSearchParams();
    if (karigar) params.append("karigar", karigar);
    if (start) params.append("start", start);
    if (end) params.append("end", end);
    const response = await apiClient.get(`/manufacturing/api/karigar-subcontractor-ledger/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSlipNoNext() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next-slip-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchReceiveItemsForBarcode(sl_no, rec_slip_no) {
  try {
    const response = await apiClient.get(`/inventory/api/create-barcode-from-receive/?rec_slip_no=${rec_slip_no}&sl_no=${sl_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPurhcaseItemsForBarcode(sl_no, bill_no) {
  try {
    const response = await apiClient.get(`/inventory/api/create-barcode-from-pur/?bill_no=${bill_no}&sl_no=${sl_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchOrderItem(id, slNo) {
  try {
    const response = await apiClient.get(`/manufacturing/fetch-order-details/?order_no_id=${id}&sl_no=${slNo}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Delete � Issues ───────────────────────────────────────────────────────────

export const deleteJobWorkIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/karigar-issue-vs", id);
  handleDelete(result, toast, "Job work issue deleted successfully.");
};

export const deleteGoldIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/karigar-gold-issue", id);
  handleDelete(result, toast, "Gold issue deleted successfully.");
};

export const deleteStoneIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/karigar-stone-issue", id);
  handleDelete(result, toast, "Stone issue deleted successfully.");
};

export const deleteHallmarkIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/hallmark-issue", id);
  handleDelete(result, toast, "Hallmark issue deleted successfully.");
};

export const deleteRefineryIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/refinery-issue", id);
  handleDelete(result, toast, "Refinery issue deleted successfully.");
};

export const deleteMeltingIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/melting-issue", id);
  handleDelete(result, toast, "Melting issue deleted successfully.");
};

export const deleteAssayIssue = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/assay-issue", id);
  handleDelete(result, toast, "Assay issue deleted successfully.");
};

// ── Delete � Receives ─────────────────────────────────────────────────────────

export const deleteJobWorkReceive = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/karigar-receive", id);
  handleDelete(result, toast, "Job work receive deleted successfully.");
};

export const deleteStoneReceive = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/karigar-stone-receive", id);
  handleDelete(result, toast, "Stone receive deleted successfully.");
};

export const deleteHallmarkReceive = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/hallmark-receive", id);
  handleDelete(result, toast, "Hallmark receive deleted successfully.");
};

export const deleteRefineryReceive = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/refinery-receive", id);
  handleDelete(result, toast, "Refinery receive deleted successfully.");
};

export const deleteMeltingReceive = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/melting-receive", id);
  handleDelete(result, toast, "Melting receive deleted successfully.");
};

export const deleteAssayReceive = async (id, toast) => {
  const result = await deleteResource("manufacturing/api/assay-receive", id);
  handleDelete(result, toast, "Assay receive deleted successfully.");
};

// ── Barcode Reports ───────────────────────────────────────────────────────────
// Note: these functions call /inventory/api/ endpoints but are kept here
// as they relate to the karigar barcode workflow in manufacturing.

export async function fetchSplitBarcodeReport(fromDate, toDate) {
  try {
    const response = await apiClient.get(`/inventory/api/brcode-split-merge?transaction_type=Split&date1__range=${fromDate},${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchMergeBarcodeReport(fromDate, toDate) {
  try {
    const response = await apiClient.get(`/inventory/api/brcode-split-merge?transaction_type=Merge&date1__range=${fromDate},${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Stone Work Order / API Reports ───────────────────────────────────────────

export async function fetchArtisanDataAPI(searchTerm = "") {
  try {
    const queryParams = new URLSearchParams();
    queryParams.append('role', 'KR');
    queryParams.append('page_size', '500');
    if (searchTerm) queryParams.append('search', searchTerm);
    const url = `/contacts/api/ledger/?${queryParams.toString()}`;

    const response = await apiClient.get(url);
    return { success: true, data: response.data.results || response.data };
  } catch (error) {
    console.error("Error fetching artisan data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchItemDataAPI() {
  try {
    const response = await apiClient.get("/mastersconfig/api/item/?item_type=M&page_size=500");

    // Handle different possible response structures
    let data = [];
    if (response.data) {
      if (response.data.results) {
        data = response.data.results;
      } else if (Array.isArray(response.data)) {
        data = response.data;
      } else if (response.data.data) {
        data = response.data.data;
      }
    }

    return { success: true, data };
  } catch (error) {
    console.error("Error fetching item data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchUserDataAPI() {
  try {
    const response = await apiClient.get("/userauth/api/users/");
    return { success: true, data: response.data.results || response.data };
  } catch (error) {
    console.error("Error fetching user data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchStoneWorkOrderReportAPI(filterParams = {}) {
  try {
    const queryParams = new URLSearchParams();

    if (filterParams.from_date) {
      queryParams.append('from_date', filterParams.from_date);
    }

    if (filterParams.to_date) {
      queryParams.append('to_date', filterParams.to_date);
    }

    if (filterParams.karigar_ids && filterParams.karigar_ids.length > 0) {
      queryParams.append('karigar_ids', filterParams.karigar_ids.join(','));
    }

    if (filterParams.group_ids && filterParams.group_ids.length > 0) {
      queryParams.append('group_ids', filterParams.group_ids.join(','));
    }

    if (filterParams.shape_ids && filterParams.shape_ids.length > 0) {
      queryParams.append('shape_ids', filterParams.shape_ids.join(','));
    }

    const url = `/manufacturing/api/stoneworkorder-report${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await apiClient.get(url);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Error fetching stone work order report:", error.response?.data || error.message);
    return { success: false, data: [], error: error.response?.data || error.message };
  }
}

export async function fetchGroupDataAPI() {
  try {
    const response = await apiClient.get("/mastersconfig/api/item_group/");

    // Handle different possible response structures
    let data = [];
    if (response.data) {
      if (response.data.results) {
        data = response.data.results;
      } else if (Array.isArray(response.data)) {
        data = response.data;
      } else if (response.data.data) {
        data = response.data.data;
      }
    }

    return { success: true, data };
  } catch (error) {
    console.error("Error fetching item group data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchShapeDataAPI() {
  try {
    const response = await apiClient.get("/mastersconfig/api/shape/");

    // Handle different possible response structures
    let data = [];
    if (response.data) {
      if (response.data.results) {
        data = response.data.results;
      } else if (Array.isArray(response.data)) {
        data = response.data;
      } else if (response.data.data) {
        data = response.data.data;
      }
    }

    return { success: true, data };
  } catch (error) {
    console.error("Error fetching shape data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchPacketWiseStoneReportAPI(filterParams = {}) {
  try {
    const queryParams = new URLSearchParams();

    if (filterParams.from_date) {
      queryParams.append('from_date', filterParams.from_date);
    }

    if (filterParams.to_date) {
      queryParams.append('to_date', filterParams.to_date);
    }

    if (filterParams.packet_ids && filterParams.packet_ids.length > 0) {
      queryParams.append('packet_ids', filterParams.packet_ids.join(','));
    }

    if (filterParams.item_ids && filterParams.item_ids.length > 0) {
      queryParams.append('item_ids', filterParams.item_ids.join(','));
    }

    const url = `/manufacturing/api/packetwise-stone-api${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await apiClient.get(url);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Error fetching packet-wise stone report:", error.response?.data || error.message);
    return { success: false, data: [], error: error.response?.data || error.message };
  }
}

export async function fetchPacketDataAPI() {
  try {
    const response = await apiClient.get("/mastersconfig/api/packet/");

    let data = [];
    if (response.data) {
      if (response.data.results) {
        data = response.data.results;
      } else if (Array.isArray(response.data)) {
        data = response.data;
      } else if (response.data.data) {
        data = response.data.data;
      }
    }

    return { success: true, data };
  } catch (error) {
    console.error("Error fetching packet data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

// ── Karigar Issue ─────────────────────────────────────────────────────────────

export async function fetchKarigarIssues({ search = "", page = 1, ordering = "", page_size = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    if (page_size) params.append("page_size", page_size);
    const response = await apiClient.get(`/manufacturing/api/karigar-issue-vs/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ledgers:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-issue-vs/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateKarigarIssue(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/karigar-issue-vs/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Karigar Jobs ──────────────────────────────────────────────────────────────

export async function fetchKarigarJobs() {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-jobs/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Karigar Receive ───────────────────────────────────────────────────────────

export async function fetchKarigarReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/karigar-receive/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarReceivewithID(id) {
  try {
    const response = await apiClient.get(`manufacturing/api/karigar-receive/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createKarigarReceive(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/karigar-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create Karigar Receive:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateKarigarReceive(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/karigar-receive/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Karigar Stone Receive ─────────────────────────────────────────────────────

export async function createKarigarStoneReceive(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/karigar-stone-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchKarigarStoneReceiveforEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-stone-receive/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateKarigarStoneReceiveforEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/karigar-stone-receive/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Receive Slip No ───────────────────────────────────────────────────────────

export async function fetchReceiveSlipNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-slip-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Gold Issues ───────────────────────────────────────────────────────────────

export async function fetchGoldIssues({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/karigar-gold-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGoldIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-gold-issue/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGoldIssuewithID(id) {
  try {
    const response = await apiClient.get('/sales/api/karigar-gold-issue/' + `${id}/`);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateGoldIssue(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/karigar-gold-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Hallmark Issue ────────────────────────────────────────────────────────────

export async function fetchHallmarkIssue({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`/manufacturing/api/hallmark-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchHallmarkIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/hallmark-issue/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchHallmarkIssuewithslno(slip_no) {
  try {
    const response = await apiClient.get(`manufacturing/api/hallmark-issue/?issue_slip_no=${slip_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createHallmarkIssue(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/hallmark-issue/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateHallmarkIssue(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/hallmark-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Hallmark Receive ──────────────────────────────────────────────────────────

export async function fetchHallmarkReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`/manufacturing/api/hallmark-receive/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchHallMarkRecForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/hallmark-receive/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch HallMarkRec:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createHallMarkRec(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/hallmark-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create HallMarkRec:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateHallMarkRecForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/hallmark-receive/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update HallMarkRec:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Hallmark Next Numbers ─────────────────────────────────────────────────────

export async function fetchNextHallMarkIssueNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_hmis_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextHallMarkReceiveNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_hmrec_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Melting Issue ─────────────────────────────────────────────────────────────

export async function fetchMeltingIssue({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/melting-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch melting issues:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchMeltingIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/melting-issue/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch melting issue for edit:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchMeltingIssueWithBillno(billno) {
  try {
    const response = await apiClient.get(`manufacturing/api/melting-issue/?billno=${billno}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch melting issue by billno:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createMeltingIssue(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/melting-issue/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create melting issue:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateMeltingIssueForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/melting-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update melting issue:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Melting Receive ───────────────────────────────────────────────────────────

export async function fetchMeltingReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/melting-receive/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch melting receives:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchMeltingReceiveForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/melting-receive/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch melting receive for edit:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createMeltingReceive(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/melting-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create melting receive:", error.response?.data || error.message);
    return { success: false, status: error.response?.status, error: error.response?.data || error.message };
  }
}

export async function updateMeltingReceiveForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/melting-receive/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update melting receive:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Melting Next Numbers ──────────────────────────────────────────────────────

export async function fetchNextMeltingIssueNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_melt_iss_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch next melting issue no:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextMeltingReceiveNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_melt_rec_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch next melting receive no:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchAvailableMeltingReceives(excludeAssayIssueId = null) {
  try {
    const params = excludeAssayIssueId ? `?exclude_assay_issue=${excludeAssayIssueId}` : "";
    const response = await apiClient.get(`manufacturing/api/available-melting-receives/${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch available melting receives:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Refinery Issue ────────────────────────────────────────────────────────────

export async function fetchRefinaryIssue({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/refinery-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRefinaryIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/refinery-issue/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRefinaryIssuewithslno(slip_no) {
  try {
    const response = await apiClient.get(`manufacturing/api/refinery-issue/?billno=${slip_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createRefinaryIssue(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/refinery-issue/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateRefinaryIssueForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/refinery-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Refinery Receive ──────────────────────────────────────────────────────────

export async function fetchRefinaryReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/refinery-receive/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRefinaryReceiveForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/refinery-receive/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createRefinaryReceive(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/refinery-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, status: error.response.status, error: error.response?.data || error.message };
  }
}

export async function updateRefinaryReceiveForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/refinery-receive/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Refinery Next Numbers ─────────────────────────────────────────────────────

export async function fetchNextRefinaryIssueNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_ref_iss_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextRefinaryReceiveNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_ref_rec_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRefineryReport({ from_date, to_date, refiner } = {}) {
  try {
    const params = new URLSearchParams();
    if (from_date) params.append("from_date", from_date);
    if (to_date)   params.append("to_date",   to_date);
    if (refiner)   params.append("refiner",   refiner);
    const response = await apiClient.get(`manufacturing/api/refinery-report/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch refinery report:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Assay Issue ───────────────────────────────────────────────────────────────

export async function fetchAssayIssue({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/assay-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch assay issues:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchAssayIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/assay-issue/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch assay issue for edit:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchAssayIssueWithBillno(billno) {
  try {
    const response = await apiClient.get(`manufacturing/api/assay-issue/?billno=${billno}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch assay issue by billno:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createAssayIssue(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/assay-issue/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create assay issue:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateAssayIssueForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/assay-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update assay issue:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Assay Receive ─────────────────────────────────────────────────────────────

export async function fetchAssayReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/assay-receive/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch assay receives:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchAssayReceiveForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/assay-receive/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch assay receive for edit:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createAssayReceive(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/assay-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create assay receive:", error.response?.data || error.message);
    return { success: false, status: error.response?.status, error: error.response?.data || error.message };
  }
}

export async function updateAssayReceiveForEdit(data, id) {
  try {
    const response = await apiClient.put(`/manufacturing/api/assay-receive/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update assay receive:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Assay Next Numbers ────────────────────────────────────────────────────────

export async function fetchNextAssayIssueNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_assay_iss_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch next assay issue no:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextAssayReceiveNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_assay_rec_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch next assay receive no:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Stone Issues ──────────────────────────────────────────────────────────────

export async function fetchStoneIssued(refJobNo, jobSlipNo, OrderType) {
  try {
    const response = await apiClient.get(`manufacturing/fetch-receive-packets/?ref_job_no=${refJobNo}&ref_job_sl_no=${jobSlipNo}&slip_type=${OrderType}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStoneIssues({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`manufacturing/api/karigar-stone-issue/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStoneIssuesFilterJobs(jobId, slipType) {
  try {
    const response = await apiClient.get(`manufacturing/filter-job-items/?job_id=${jobId}&slip_type=${slipType}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextStoneBillNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next-stone-bill-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Stone Return ──────────────────────────────────────────────────────────────

export async function fetchStoneReturn({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    const response = await apiClient.get(`/manufacturing/api/karigar-stone-receive/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStoneReceiveBillNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/stone-receive-billno/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Repair Job Cards ──────────────────────────────────────────────────────────

export async function fetchRepairJobCards({ search = "", page = 1, status = "" } = {}) {
  try {
    const params = new URLSearchParams({ page });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    const response = await apiClient.get(`/manufacturing/api/repair-job-card/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRepairJobCardById(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/repair-job-card/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRepairJobCardNextNo() {
  try {
    const response = await apiClient.get('/manufacturing/api/repair-job-card-no/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createRepairJobCard(data) {
  try {
    const response = await apiClient.post('/manufacturing/api/repair-job-card/', data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateRepairJobCard(id, data) {
  try {
    const response = await apiClient.patch(`/manufacturing/api/repair-job-card/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateRepairJobCardStatus(id, status) {
  try {
    const response = await apiClient.patch(`/manufacturing/api/repair-job-card/${id}/status/`, { status });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteRepairJobCard(id) {
  try {
    await apiClient.delete(`/manufacturing/api/repair-job-card/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createHallmarkReceive(data) {
  try {
    const response = await apiClient.post("/manufacturing/api/hallmark-receive/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// frontend/src/services/api/manufacturing.js
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

// ── Delete — Issues ───────────────────────────────────────────────────────────

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

// ── Delete — Receives ─────────────────────────────────────────────────────────

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
    console.log("Raw API Response for items:", response); // Debug line

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

    console.log("Processed item data:", data); // Debug line
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
    console.log("Raw API Response for item groups:", response); // Debug line

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

    console.log("Processed item group data:", data); // Debug line
    return { success: true, data };
  } catch (error) {
    console.error("Error fetching item group data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchShapeDataAPI() {
  try {
    const response = await apiClient.get("/mastersconfig/api/shape/");
    console.log("Raw API Response for shapes:", response); // Debug line

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

    console.log("Processed shape data:", data); // Debug line
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
    console.log("Raw API Response for packets:", response);

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

    console.log("Processed packet data:", data);
    return { success: true, data };
  } catch (error) {
    console.error("Error fetching packet data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

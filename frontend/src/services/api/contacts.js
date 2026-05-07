// frontend/src/services/api/contacts.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";

// ── Internal helpers (mirrored from apiService.js) ────────────────────────────
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

// ── Ledgers ───────────────────────────────────────────────────────────────────
export async function getLedgers({ search = "", page = 1, ordering = "", type = "KR", page_size, ac_group_code = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    if (page_size) params.append("page_size", page_size);

    // Use role-based filtering so a ledger with multiple roles (e.g. a
    // Dealer who is also a Customer) appears in both filtered lists.
    // Empty string means "all ledgers" — skip the filter entirely.
    if (type) {
      params.append("role", type);          // supports comma-separated: "DL,SD,KR"
    }

    // Account-group code filter — e.g. "INC-DIR-SAL" or "EXP-DIR-PUR"
    if (ac_group_code) {
      params.append("ac_group_code", ac_group_code);
    }

    const response = await apiClient.get(`/contacts/api/ledger/?${params.toString()}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ledgers:", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createLedger(data) {
  try {
    const response = await apiClient.post("/contacts/api/ledger/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createGC(data) {
  try {
    const response = await apiClient.post("/accounting/api/gc/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getgcbillno() {
  try {
    const response = await apiClient.get("accounting/api/gc-no/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getcgbillno() {
  try {
    const response = await apiClient.get("accounting/api/cg-no/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateLedger(id, data) {
  try {
    const response = await apiClient.put(`/contacts/api/ledger/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update ledger:", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function addLedgerRole(id, role) {
  try {
    const response = await apiClient.post(`/contacts/api/ledger/${id}/roles/`, { role });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function removeLedgerRole(id, role) {
  try {
    const response = await apiClient.delete(`/contacts/api/ledger/${id}/roles/`, { data: { role } });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function setPrimaryLedgerRole(id, role) {
  try {
    const response = await apiClient.patch(`/contacts/api/ledger/${id}/roles/primary/`, { role });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getLedger(id) {
  try {
    const response = await apiClient.get(`/contacts/api/ledger/${id}/`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ledger :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

// Fetch all ledgers (no type filter, no pagination) — for pickers
export async function getLedgerList(params = {}) {
  try {
    const response = await apiClient.get('/contacts/api/ledger/', { params: { page_size: 10000, ...params } });
    const data = response.data;
    return { success: true, data: Array.isArray(data) ? data : (data.results || []) };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// Alias — same endpoint as getAccountGroup
export async function fetchParentAccount() {
  try {
    const response = await apiClient.get("/accounting/api/accounts/");
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function checkLedgerName(ac_name, excludeId = null) {
  try {
    const params = new URLSearchParams({ ac_name });
    if (excludeId) params.set('exclude_id', excludeId);
    const response = await apiClient.get(`/contacts/api/ledger/check-name/?${params}`);
    return { success: true, exists: response.data.exists };
  } catch (error) {
    return { success: false, exists: false };
  }
}

export const deleteLedger = async (id, toast) => {
  const result = await deleteResource("contacts/api/ledger", id);
  handleDelete(result, toast, "Ledger deleted successfully");
};

// ── Salesperson ───────────────────────────────────────────────────────────────
export async function fetchSalesperson() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/salesperson/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch salesperson :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Create Salesperson
export async function createSalesperson(data) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/salesperson/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create salesperson:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Update Salesperson
export async function updateSalesperson(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/salesperson/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update salesperson:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Delete Salesperson
export async function deleteSalesperson(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/salesperson/${id}/`);
    return { success: true };
  } catch (error) {
    console.error("Failed to delete salesperson:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── CRM ───────────────────────────────────────────────────────────────────────
export const fetchCRMOccasions     = (days = 30) =>
  _api('get', `/contacts/api/crm/occasions/?days=${days}`);

export const fetchCRMSettings      = ()     => _api('get',   '/mastersconfig/api/crm-settings/');
export const updateCRMSettings     = (data) => _api('patch', '/mastersconfig/api/crm-settings/', data);
export const fetchCRMSendLog       = ()     => _api('get',   '/mastersconfig/api/crm-send-log/');
export const triggerCRMTestSend    = ()     => _api('post',  '/mastersconfig/api/crm-test-send/');

// ── Ledger TDS / Customer history ────────────────────────────────────────────
export async function fetchLedgerTDSInfo(ledgerId) {
  try {
    const response = await apiClient.get(`/contacts/api/ledger/${ledgerId}/tds-info/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerPurchasesByLedger(ldgr_id) {
  try {
    const params = new URLSearchParams({ ldgr: ldgr_id });
    const response = await apiClient.get(`/purchase/api/customer-purchases-for-adjustment/?${params.toString()}`);
    return { success: true, data: response.data ?? [] };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerOrdersByLedger(ldgr_id, { onlyWithAdvance = true } = {}) {
  try {
    const params = new URLSearchParams({ ldgr: ldgr_id });
    const response = await apiClient.get(`/sales/api/customer-orders-vs/?${params.toString()}`);
    let results = response.data?.results ?? response.data ?? [];
    if (onlyWithAdvance) {
      results = results.filter(o => parseFloat(o.advance_amt || 0) > 0 && parseFloat(o.advance_available ?? o.advance_amt ?? 0) > 0);
    }
    return { success: true, data: results };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

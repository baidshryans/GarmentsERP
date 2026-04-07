import apiClient from "./apiClient";

export async function loginAndSaveToken(username, password) {
  try {
    const response = await apiClient.post("/userauth/api-token-auth/", { username, password });


    const { token, user } = response.data;

    localStorage.setItem("Token", token);
    localStorage.setItem("user", JSON.stringify(user));
    const data = await getRetails();
    if (data.success && data.data.results?.length > 0) {
      const ul = data.data.results[0];
      // Prefer default_location; fall back to first assigned retail
      const loc = ul.default_location || (ul.location?.length > 0 ? ul.location[0] : null);
      if (loc) {
        localStorage.setItem('retail_code', loc.retail_code);
        localStorage.setItem('state_code', loc.state?.code ?? '');
      }
    }


    return { success: true, data: response.data };
  } catch (error) {
    // Log error details for debugging
    console.error("Login failed:", error.response?.data || error.message);

    // Return false indicating failure and include the error response
    return { success: false, error: error.response?.data || error.message };
  }
}

{/*export async function authorizedToken() {
    try {
      const response = await apiClient.get("/userauth/token-auth/");
      
      const token  = req.cookies.token; 
  
      localStorage.setItem("Token", token);
  
  
      return { success: true, data: response.data };
    } catch (error) {
      // Log error details for debugging
      console.error("Login failed:", error.response?.data || error.message);
  
      // Return false indicating failure and include the error response
      return { success: false, error: error.response?.data || error.message };
    }
  }*/}

// export async function getLedgers() {
//   try {
//     const response = await apiClient.get("/contacts/api/ledger/");

//     return { success: true, data: response.data };
//   } catch (error) {
//     console.error("Failed to fetch ledgers:", error.response?.data || error.message);

//     return { success: false, error: error.response?.data || error.message };
//   }
// } getLedgers()

export async function getLedgers({ search = "", page = 1, ordering = "", type = "KR", page_size } = {}) {
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

    const response = await apiClient.get(`/contacts/api/ledger/?${params.toString()}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ledgers:", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getNextGCno() {
  try {
    const response = await apiClient.get("/accounting/api/gc-no/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getClosingStockValuation({ to_date } = {}) {
  try {
    const params = new URLSearchParams();
    if (to_date) params.append("to_date", to_date);
    const response = await apiClient.get(`/inventory/api/closing-stock?${params.toString()}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch closing stock:", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}
export async function getStates() {
  try {
    const response = await apiClient.get("/contacts/api/states/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getTypes() {
  try {
    const response = await apiClient.get("/contacts/api/custom-tags/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getRetails() {
  try {
    const response = await apiClient.get("/contacts/api/allowed_retail_list");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

// ── User Management ───────────────────────────────────────────────────────────
export async function fetchUsers() {
  try {
    const r = await apiClient.get('/userauth/api/users/');
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function createUser(data) {
  try {
    const r = await apiClient.post('/userauth/api/users/create/', data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function updateUser(id, data) {
  try {
    const r = await apiClient.patch(`/userauth/api/users/${id}/`, data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function assignUserRetail(id, retail_ids, default_retail_id) {
  try {
    const r = await apiClient.post(`/userauth/api/users/${id}/assign-retail/`, { retail_ids, default_retail_id });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

// ── Roles & Permissions ───────────────────────────────────────────────────────
export async function fetchRoles() {
  try { const r = await apiClient.get('/userauth/api/roles/'); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function createRole(data) {
  try { const r = await apiClient.post('/userauth/api/roles/', data); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function updateRole(id, data) {
  try { const r = await apiClient.patch(`/userauth/api/roles/${id}/`, data); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function deleteRole(id) {
  try { await apiClient.delete(`/userauth/api/roles/${id}/`); return { success: true }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function fetchRolePermissions(roleId) {
  try { const r = await apiClient.get(`/userauth/api/roles/${roleId}/permissions/`); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function saveRolePermissions(roleId, data) {
  try { const r = await apiClient.post(`/userauth/api/roles/${roleId}/permissions/`, data); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function fetchModules() {
  try { const r = await apiClient.get('/userauth/api/modules/'); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}
export async function assignUserRole(userId, roleId) {
  try { const r = await apiClient.post(`/userauth/api/users/${userId}/assign-role/`, { role_id: roleId }); return { success: true, data: r.data }; }
  catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

// ── System Settings ───────────────────────────────────────────────────────────
export async function fetchSystemSettings() {
  try {
    const r = await apiClient.get('/mastersconfig/api/system-settings/');
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function updateSystemSettings(payload) {
  try {
    const r = await apiClient.patch('/mastersconfig/api/system-settings/', payload);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

// ── Database Backup ────────────────────────────────────────────────────────────
export async function backupDatabaseToPath(path) {
  try {
    const r = await apiClient.post('/userauth/api/backup-database/', { path });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function backupDatabaseDownload() {
  try {
    const r = await apiClient.post('/userauth/api/backup-database/', {}, { responseType: 'blob' });
    const cd = r.headers['content-disposition'] || '';
    const match = cd.match(/filename="?([^";\n]+)"?/);
    const filename = match ? match[1] : `jewel_erp_backup_${Date.now()}.sqlite3`;
    const url = URL.createObjectURL(r.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true };
  } catch (e) { return { success: false, error: e.message }; }
}

// ── Internal helper ───────────────────────────────────────────────────────────
const _api = async (method, url, data) => {
  try {
    const r = await apiClient[method](url, data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// ── CRM ───────────────────────────────────────────────────────────────────────
export const fetchCRMOccasions     = (days = 30) =>
  _api('get', `/contacts/api/crm/occasions/?days=${days}`);

export const fetchCRMSettings      = ()     => _api('get',   '/mastersconfig/api/crm-settings/');
export const updateCRMSettings     = (data) => _api('patch', '/mastersconfig/api/crm-settings/', data);
export const fetchCRMSendLog       = ()     => _api('get',   '/mastersconfig/api/crm-send-log/');
export const triggerCRMTestSend    = ()     => _api('post',  '/mastersconfig/api/crm-test-send/');

// ── Audit Log ─────────────────────────────────────────────────────────────────
export const fetchAuditLog = async (params = {}) => {
  try {
    const r = await apiClient.get('/userauth/api/audit-log/', { params });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// ── Dashboard Summary ─────────────────────────────────────────────────────────
export const fetchDashboardSummary = () => _api('get', '/userauth/api/dashboard-summary/');

export async function getAccountGroup() {
  try {
    const response = await apiClient.get("/accounting/api/accounts/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

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

export async function getChartOfAccounts() {
  try {
    const response = await apiClient.get(`/accounting/account-tree/`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch chart of accounts :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

// Alias — same endpoint as getAccountGroup
export async function fetchParentAccount() {
  return getAccountGroup();
}

export async function getAccount(id) {
  try {
    const response = await apiClient.get(`/accounting/api/accounts/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createAccount(data) {
  try {
    const response = await apiClient.post(`/accounting/api/accounts/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateAccount(id, data) {
  try {
    const response = await apiClient.put(`/accounting/api/accounts/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteAccount(id) {
  try {
    await apiClient.delete(`/accounting/api/accounts/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// Fetch all ledgers (no type filter, no pagination) — for pickers
export async function getLedgerList() {
  try {
    const response = await apiClient.get('/contacts/api/ledger/?page_size=10000');
    const data = response.data;
    // Handle both paginated and plain list responses
    return { success: true, data: Array.isArray(data) ? data : (data.results || []) };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ─── Opening Balances ────────────────────────────────────────────────────────

export async function getOpeningBalances() {
  try {
    const response = await apiClient.get('/accounting/api/open-balance/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createOpeningBalance(data) {
  try {
    const response = await apiClient.post('/accounting/api/open-balance/', data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateOpeningBalance(id, data) {
  try {
    const response = await apiClient.put(`/accounting/api/open-balance/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteOpeningBalance(id) {
  try {
    await apiClient.delete(`/accounting/api/open-balance/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// Fetch Salesperson
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

// Fetch Order Number
export async function fetchOrderNoNext() {
  try {
    const response = await apiClient.get(`/sales/api/order-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Fetch Order Number
export async function fetchVoucherNoNext(vouType) {
  try {
    const response = await apiClient.get(`/accounting/api/vou-no/${vouType}/`);
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

export async function fetchPVNoNext() {
  try {
    const response = await apiClient.get(`/purchase/get-next-pv-no/`);
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


// Fetch Main Item
export async function fetchMainItem({type=""}={}) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item/?item_type=${type}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch main item :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchShape() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/shape/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGroup() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item_group/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

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

// export async function fetchPurchaseFinished(po_no) {
//   try {
//     const response = await apiClient.get(`/purchase/api/purchase-vou-item/${po_no}`);
//     return { success: true, data: response.data };
//   } catch (error) {
//     console.error("Failed to fetch purity :", error.response?.data || error.message);
//     return { success: false, error: error.response?.data || error.message };
//   }
// }



export async function fetchKarigarReceiveReport(fromDate, toDate, purity, ldgrs) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-item-report?finish_status=true&karigar_ldgr=${ldgrs.join(",")}&purity=${purity}&date_from=${fromDate}&date_to=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

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

export async function fetchGSTinputReport(fromDate, toDate) {
  try {
    const response = await apiClient.get(`/sales/api/gst-input?start_date=${startDate}&end_date=${endDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGSToutputReport(fromDate, toDate) {
  try {
    const response = await apiClient.get(`/sales/api/api/gst-output?start_date=${fromDate}&end_date=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
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


// Fetch Main Item
export async function fetchMainItemsForHSN(hsnId) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item/?hsn_no=${hsnId}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch main item :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Fetch Purity
export async function fetchPurity() {
  try {
    const response = await apiClient.get(`/goldrates/api/purity/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch purity :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createPurity(data) {
  try {
    const response = await apiClient.post(`/goldrates/api/purity/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updatePurity(id, data) {
  try {
    const response = await apiClient.put(`/goldrates/api/purity/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deletePurity(id) {
  try {
    await apiClient.delete(`/goldrates/api/purity/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}



// Fetch Purity
export async function fetchDetailsForPurchaseReturn(po_no) {
  try {
    const response = await apiClient.get(`/purchase/api/fetch-pv-for-return/${po_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch purity :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// Fetch Purity
export async function fetchHSNs() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/hsn/?page_size=10000`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch HSN :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateCustomerOrderForEdit(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/customer-orders-vs/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update CustomerOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createCustomerOrder(data) {
  try {
    const response = await apiClient.post("/sales/api/customer-orders-vs/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create CustomerOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerOrderForEdit(id) {
  try {
    const response = await apiClient.get(`/sales/api/customer-orders-vs/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch CustomerOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createKarigarIssue(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/karigar-issue/create/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

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
export async function updatePurchaseOrderForEdit(data, id) {

  try {
    const response = await apiClient.put(`/purchase/api/purchase-order/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update PurchaseOrder:", error.response?.data || error.message);
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



export async function fetchSlipNoNext() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next-slip-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStockValuationReport() {
  try {
    const response = await apiClient.get(`/inventory/api/stock-valuation-report/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// export async function fetchCashBook() {
//   try {
//     const response = await apiClient.get(`/accounting/api/cash-book/`);
//     return { success: true, data: response.data };
//   } catch (error) {
//     console.error("Failed to fetch order number :", error.response?.data || error.message);
//     return { success: false, error: error.response?.data || error.message };
//   }
// }

// export async function fetchBankBookReport(fromDate,toDate,selectedLedgerId) {
//   try {
//     const response = await apiClient.get(`/accounting/api/bank-book?from_date=${fromDate}&to_date=${toDate}&bank_ldgr=${selectedLedgerId}`);
//     return { success: true, data: response.data };
//   } catch (error) {
//     console.error("Failed to fetch order number :", error.response?.data || error.message);
//     return { success: false, error: error.response?.data || error.message };
//   }
// }

export async function fetchtrial() {
  try {
    const response = await apiClient.get(`/accounting/api/trial/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSaleRetNext() {
  try {
    const response = await apiClient.get(`/sales/api/next_sr_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}



export async function fetchCustomerOrders({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/sales/api/customer-orders-vs/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

/**
 * Fetch all customer orders for the Kanban board (no pagination).
 */
export async function fetchCustomerOrdersKanban({ search = "" } = {}) {
  try {
    const params = new URLSearchParams({ page_size: 500, ordering: "-date1" });
    if (search) params.append("search", search);
    const response = await apiClient.get(`/sales/api/customer-orders-vs/?${params.toString()}`);
    return { success: true, data: response.data?.results ?? response.data ?? [] };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

/**
 * Fetch open customer orders for a given customer ledger.
 * Used in SalesVoucherAdd to populate the "Link Order / Advance" dropdown.
 * Returns orders that have an advance_amt > 0 (all statuses unless filtered).
 */
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

export async function fetchCustomerPurchasesByLedger(ldgr_id) {
  try {
    const params = new URLSearchParams({ ldgr: ldgr_id });
    const response = await apiClient.get(`/purchase/api/customer-purchases-for-adjustment/?${params.toString()}`);
    return { success: true, data: response.data ?? [] };
  } catch (error) {
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

export async function fetchSlNosOrders(id) {
  try {
    const response = await apiClient.get(`/manufacturing/fetch-sl-no/?order_no_id=${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Serial numbers :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}


export async function fetchBarcodeDetail(barcode, hsn) {
  try {
    if ((barcode === "")) return { success: false, error: "Barcode should not be blank" }

    const response = await apiClient.get(`/inventory/api/get-barcode-detail/${barcode}/${hsn}/`);
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

export async function fetchBarcodeDetailOnly(barcode) {
  try {
    if ((barcode === "")) return { success: false, error: "Barcode should not be blank" }

    const response = await apiClient.get(`/inventory/api/get-barcode-detail/${barcode}/`);
    console.log(barcode)
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Serial numbers :", error.response?.data || error.message);
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

export async function fetchNextStoneBillNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next-stone-bill-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}



export async function fetchNextSaleNo() {
  try {
    const response = await apiClient.get(`/sales/api/next_sv_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSaleVoucherInitialData() {
  try {
    const response = await apiClient.get(`/sales/api/sale-voucher-initial-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch sale voucher initial data:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSaleReturnInitialData() {
  try {
    const response = await apiClient.get(`/sales/api/sale-return-initial-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch sale return initial data:", error.response?.data || error.message);
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

export async function fetchNextHallMarkIssueNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_hmis_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextStockTransferNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/next_stock_transfer_no`);
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
export async function fetchNextStockJournalNo() {
  try {
    const response = await apiClient.get(`/inventory/api/next_stock_journal_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextSaleAppNo() {
  try {
    const response = await apiClient.get(`/sales/api/next_sa_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchKarigarIssues({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/manufacturing/api/karigar-issue-vs/?${params.toString()}`);


    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ledgers:", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }

}

export async function fetchKarigarJobs() {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-jobs/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
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

export async function fetchGoldIssueForEdit(id) {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-gold-issue/${id}`);
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

export async function updateHallmarkIssue(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/hallmark-issue/${id}/`, data);
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

export async function updateGoldIssue(id, data) {
  try {
    const response = await apiClient.put(`/manufacturing/api/karigar-gold-issue/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchReceiveSlipNo() {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-receive-slip-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
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


export async function fetchNextBarcode() {
  try {
    const response = await apiClient.get(`/inventory/api/generate-barcode/`);
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




export async function fetchPackets() {
  try {
    const response = await apiClient.get(`mastersconfig/api/packet/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodes({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchDetailsforSaleReturn(billno) {
  try {
    const response = await apiClient.get(`sales/api/get-sale-vou-for-return/?bill_no=${billno}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeMerges() {
  try {
    const response = await apiClient.get(`inventory/api/barcode-merge/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchBarcodeSplits() {
  try {
    const response = await apiClient.get(`inventory/api/barcode-split/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}




export async function fetchStoneIssues({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchGoldIssues({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchRefinaryIssue({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchRefinaryReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchSalesVoucher({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/sales/api/sale-voucher/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}



export async function fetchSalesReturn({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/sales/api/sale-return/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApproval({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);

    const response = await apiClient.get(`/sales/api/sale-approval/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBarcodeList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
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

export async function fetchBarcodeHistoryList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchUnBarcodedList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchHallmarkIssue({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchHallmarkReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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

export async function fetchStoneReturn({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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



export async function fetchKarigarReceive({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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


export async function fetchStoneIssuesFilterJobs(jobId, slipType) {
  try {
    const response = await apiClient.get(`manufacturing/filter-job-items/?job_id=${jobId}&slip_type=${slipType}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchMainItemDetails(ref_job_no, job_sl_no) {
  try {
    const response = await apiClient.get(`manufacturing/fetch-main-details/?job_sl_no=${job_sl_no}&ref_job_no=${ref_job_no}`);
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

export async function fetchHallmarkIssuewithslno(slip_no) {
  try {
    const response = await apiClient.get(`manufacturing/api/hallmark-issue/?issue_slip_no=${slip_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
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


export async function fetchRCVs() {
  try {
    const response = await apiClient.get(`manufacturing/api/fetch-rcv-slip-nos`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStoneIssued(refJobNo, jobSlipNo, OrderType) {
  try {
    const response = await apiClient.get(`manufacturing/fetch-receive-packets/?ref_job_no=${refJobNo}&ref_job_sl_no=${jobSlipNo}&slip_type=${OrderType}`);
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


export async function createHallmarkIssue(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/hallmark-issue/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
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
export async function createStockJournal(data) {

  try {
    const response = await apiClient.post("/inventory/stock-journal/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// export async function fetchStockTransferForList(data) {

//   try {
//     const response = await apiClient.get("/inventory/stock-transfer/", data);

//     return { success: true, data: response.data };
//   } catch (error) {
//     console.error("Failed to fetch states :", error.response?.data || error.message);
//     return { success: false, error: error.response?.data || error.message };
//   }
// }

export async function fetchStockTransferForList({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
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


// export async function fetchStockJournalForList(data) {

//   try {
//     const response = await apiClient.get("/inventory/stock-journal/", data);

//     return { success: true, data: response.data };
//   } catch (error) {
//     console.error("Failed to fetch states :", error.response?.data || error.message);
//     return { success: false, error: error.response?.data || error.message };
//   }
// }
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

export async function fetchStockTransferForEdit(id) {

  try {
    const response = await apiClient.get(`/inventory/stock-transfer/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
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
export async function updateStockTransferForEdit(data, id) {

  try {
    const response = await apiClient.put(`/inventory/stock-transfer/${id}/`, data);

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
export async function createRefinaryIssue(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/refinery-issue/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
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

export async function updateRefinaryIssueForEdit(data, id) {

  try {
    const response = await apiClient.put(`/manufacturing/api/refinery-issue/${id}/`, data);

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
export async function fetchRefinaryReceiveForEdit(id) {

  try {
    const response = await apiClient.get(`/manufacturing/api/refinery-receive/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
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

export async function createHallMarkRec(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/hallmark-receive/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create HallMarkRec:", error.response?.data || error.message);
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

export async function updateRefinaryReceiveForEdit(data, id) {

  try {
    const response = await apiClient.put(`/manufacturing/api/refinery-receive/${id}/`, data);

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

export async function createHallmarkReceive(data) {

  try {
    const response = await apiClient.post("/manufacturing/api/hallmark-receive/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
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

  const data = { barcode: barcode }

  try {
    const response = await apiClient.post("inventory/api/bar-unbar/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);
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


export async function updatePurchaseReturnForEdit(data, id) {

  try {
    const response = await apiClient.put(`/purchase/api/purchase-return/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update PurchaseReturn:", error.response?.data || error.message);
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

export async function fetchPurchaseReturnForEdit(id) {

  try {
    const response = await apiClient.get(`/purchase/api/purchase-return/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}




export async function createSalesApproval(data) {
  try {
    const response = await apiClient.post('/sales/api/sale-approval/', data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Approval:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesApproval(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-approval/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Approval:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApprovalById(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-approval/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Approval:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createSalesReturn(data) {
  try {
    const response = await apiClient.post('/sales/api/sale-return/', data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesReturn(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-return/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesReturnById(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-return/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateJournalEntryForEdit(data, id) {
  try {
    const response = await apiClient.put(`/accounting/api/journal/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update JournalEntry:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createJournalEntry(data) {
  try {
    const response = await apiClient.post("/accounting/api/journal/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create JournalEntry:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchJournalEntryForEdit(id) {
  try {
    const response = await apiClient.get(`/accounting/api/journal/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch JournalEntry:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export const deleteJournalentry = async (id, toast) => {
  const result = await deleteResource("/accounting/api/journal", id);
  handleDelete(result, toast, "Accounting Voucher deleted successfully.");
};

// Voucher Attachments
export async function getVoucherAttachments(voucherId) {
  try {
    const response = await apiClient.get(`/accounting/api/voucher-attachments/?voucher=${voucherId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function uploadVoucherAttachment(voucherId, file) {
  try {
    const formData = new FormData();
    formData.append("voucher", voucherId);
    formData.append("file", file);
    const response = await apiClient.post("/accounting/api/voucher-attachments/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteVoucherAttachment(id) {
  try {
    await apiClient.delete(`/accounting/api/voucher-attachments/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// Purchase Attachments
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

// Ledger Documents
export async function getLedgerDocuments(ldgrId) {
  try {
    const response = await apiClient.get(`/contacts/api/ledger-documents/?ldgr=${ldgrId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function uploadLedgerDocument(ldgrId, file, documentType) {
  try {
    const formData = new FormData();
    formData.append("ldgr", ldgrId);
    formData.append("document", file);
    formData.append("document_type", documentType);
    const response = await apiClient.post("/contacts/api/ledger-documents/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteLedgerDocument(id) {
  try {
    await apiClient.delete(`/contacts/api/ledger-documents/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}


export async function fetchAccountingVoucher({ search = "", page = 1, ordering = "", voucher_type = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (voucher_type) params.append("voucher_type", voucher_type);
    params.append("page", page);

    const response = await apiClient.get(`/accounting/api/journal/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch voucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createSalesVoucher(data) {
  try {
    const response = await apiClient.post('/sales/api/sale-voucher/', data);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}


export async function CashTotalLedger(ledger_id) {
  try {
    const response = await apiClient.get(`accounting/api/get-ldgr-cash-total/${ledger_id}`);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to get total ledger:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesVoucher(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-voucher/${id}/`, data);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesVoucherwithID(id) {
  try {
    const response = await apiClient.get('/sales/api/sale-voucher/' + `${id}/`);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
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

export async function fetchPurchaseVoucherForEdit(id) {

  try {
    const response = await apiClient.get(`/purchase/api/purchase-voucher/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRetails() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/retail/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch retails:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createRetail(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/retail/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateRetail(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/retail/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStates() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/state/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Karigar Making Master ────────────────────────────────────────────────────

export async function fetchKarigarMaking() {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-making/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createKarigarMaking(payload) {
  try {
    const response = await apiClient.post(`/manufacturing/api/karigar-making/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateKarigarMaking(id, payload) {
  try {
    const response = await apiClient.patch(`/manufacturing/api/karigar-making/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteKarigarMaking(id) {
  try {
    await apiClient.delete(`/manufacturing/api/karigar-making/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Company Master ───────────────────────────────────────────────────────────

export async function fetchCompanies() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/company/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createCompany(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/company/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateCompany(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/company/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteCompany(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/company/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Branch Master ────────────────────────────────────────────────────────────

export async function fetchBranches() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/branch/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createBranch(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/branch/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateBranch(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/branch/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteBranch(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/branch/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBranchAnalytics(id) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/branch/${id}/analytics/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchTDSSections() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/tds-section/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createTDSSection(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/tds-section/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateTDSSection(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/tds-section/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteTDSSection(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/tds-section/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchLedgerTDSInfo(ledgerId) {
  try {
    const response = await apiClient.get(`/contacts/api/ledger/${ledgerId}/tds-info/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchTDSRegister({ from_date, to_date, section } = {}) {
  try {
    const params = new URLSearchParams();
    if (from_date) params.append('from_date', from_date);
    if (to_date) params.append('to_date', to_date);
    if (section) params.append('section', section);
    const response = await apiClient.get(`/purchase/api/tds-register/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchTCSRegister({ from_date, to_date, section } = {}) {
  try {
    const params = new URLSearchParams();
    if (from_date) params.append('from_date', from_date);
    if (to_date) params.append('to_date', to_date);
    if (section) params.append('section', section);
    const response = await apiClient.get(`/sales/api/tcs-register/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchTCSSections() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/tcs-section/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createTCSSection(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/tcs-section/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateTCSSection(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/tcs-section/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteTCSSection(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/tcs-section/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDuePayments(id) {

  try {
    const response = await apiClient.get(`/accounting/api/due-payments/?ldgr_id=${id}&type=PMNT`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDuePaymentsSale(id) {

  try {
    const response = await apiClient.get(`/accounting/api/due-payments/sale/?ldgr_id=${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getGoldRate(date) {

  try {
    const response = await apiClient.get(`/goldrates/api/current-gold-rate/?date=${date}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getCustomerItemAsPurchaseStyle(order_no, sl_no) {
  try {
    const response = await apiClient.get(`sales/api/customer-item/${order_no}/${sl_no}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch CustomerOrderItem:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}




export async function deleteResource(url, id) {
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

// Manufacturing - Issues
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

// Manufacturing - Receives
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
export const deleteStockTransfer = async (id, toast) => {
  const result = await deleteResource("inventory/stock-transfer", id);
  handleDelete(result, toast, "Stock Transfer deleted successfully.");
};

export async function fetchInTransitBarcodes() {
  try {
    const response = await apiClient.get('/inventory/stock-transfer/in-transit-barcodes/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

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
export const deleteStockJournal = async (id, toast) => {
  const result = await deleteResource("inventory/stock-journal", id);
  handleDelete(result, toast, "Stock journal deleted successfully.");
};
// Purchase
export const deletePurchaseVoucher = async (id) => {
  const result = await deleteResource("purchase/api/purchase-voucher", id);
  // handleDelete(result, toast, "Purchase voucher deleted successfully.");
};

export const deletePurchaseReturn = async (id, toast) => {
  const result = await deleteResource("purchase/api/purchase-return", id);
  handleDelete(result, toast, "Purchase return deleted successfully.");
};


export const deletePurchaseOrder = async (id, toast) => {
  const result = await deleteResource("purchase/api/purchase-order", id);
  handleDelete(result, toast, "Purchase order deleted successfully.");
};

// Sales
export const deleteCustomerOrder = async (id, toast) => {
  const result = await deleteResource("sales/api/customer-orders-vs", id);
  handleDelete(result, toast, "Customer order deleted successfully.");
};

export async function fetchDeliveryOverview() {
  try {
    const res = await apiClient.get('/sales/api/customer-orders/delivery-overview/');
    return { success: true, data: res.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateOrderDeliveryStatus(id, delivery_status, actual_delivery_date) {
  try {
    const body = { delivery_status };
    if (actual_delivery_date) body.actual_delivery_date = actual_delivery_date;
    const res = await apiClient.patch(`/sales/api/customer-orders/${id}/update-delivery/`, body);
    return { success: true, data: res.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export const deleteSalesReturn = async (id, toast) => {
  const result = await deleteResource("sales/api/sale-return", id);
  handleDelete(result, toast, "Sales return deleted successfully.");
};

export const deleteSalesApproval = async (id, toast) => {
  const result = await deleteResource("sales/api/sale-approval", id);
  handleDelete(result, toast, "Sales approval deleted successfully.");
};

export const deleteSalesVoucher = async (id, toast) => {
  const result = await deleteResource("sales/api/sale-voucher", id);
  handleDelete(result, toast, "Sales voucher deleted successfully.");
};

// Account ledger 

export const deleteLedger = async (id, toast) => {
  const result = await deleteResource("contacts/api/ledger", id);
  handleDelete(result, toast, "Ledger deleted successfully");
};

// Inventory
export const deleteBarcodeManagement = async (id, toast) => {
  const result = await deleteResource("inventory/barcode", id);
  handleDelete(result, toast, "Barcode management entry deleted successfully.");
};

export async function fetchGSTInputReport(startDate, endDate) {
  try {
    const response = await apiClient.get(`/sales/api/gst-input?start_date=${startDate}&end_date=${endDate}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch gstinputreport:", error.response?.data || error.message);
    throw error;
  }
}

export async function fetchGSTOutputReport(startDate, endDate) {
  try {
    const response = await apiClient.get(`/sales/api/gst-output?start_date=${startDate}&end_date=${endDate}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch gstoutputreport:", error.response?.data || error.message);
    throw error;
  }
}

export async function fetchGSTR1Report({ from_date, to_date } = {}) {
  try {
    const response = await apiClient.get(`/sales/api/gstr1/?from_date=${from_date}&to_date=${to_date}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGSTR3BReport({ from_date, to_date } = {}) {
  try {
    const response = await apiClient.get(`/sales/api/gstr3b/?from_date=${from_date}&to_date=${to_date}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
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

export async function fetchProfitDemo() {

  try {
    const response = await apiClient.get(`/accounting/api/pnl`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch ProfitDemo:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
} 

export async function fetchBankBookReport(fromDate, toDate, selectedLedgerId) {
  try {
    const response = await apiClient.get(`/accounting/api/bank-book?from_date=${fromDate}&to_date=${toDate}&bank_ldgr=${selectedLedgerId}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch bankbookreport:", error.response?.data || error.message);
    // return { success: false, error: error.response?.data || error.message };
    throw error;
  }
}



// ── Bank Reconciliation ────────────────────────────────────────────────────────
export async function fetchBankStatements({ bank_ledger, from_date, to_date } = {}) {
  try {
    const p = new URLSearchParams();
    if (bank_ledger) p.append('bank_ledger', bank_ledger);
    if (from_date)   p.append('from_date', from_date);
    if (to_date)     p.append('to_date', to_date);
    const r = await apiClient.get(`/accounting/api/bank-statement/?${p}`);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function createBankStatement(data) {
  try {
    const r = await apiClient.post('/accounting/api/bank-statement/', data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function deleteBankStatement(id) {
  try {
    await apiClient.delete(`/accounting/api/bank-statement/${id}/`);
    return { success: true };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function matchBankStatement(id, voucher_detail_id) {
  try {
    const r = await apiClient.post(`/accounting/api/bank-statement/${id}/match/`, { voucher_detail_id });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function fetchBankReconBookEntries({ bank_ledger, from_date, to_date } = {}) {
  try {
    const p = new URLSearchParams();
    if (bank_ledger) p.append('bank_ledger', bank_ledger);
    if (from_date)   p.append('from_date', from_date);
    if (to_date)     p.append('to_date', to_date);
    const r = await apiClient.get(`/accounting/api/bank-reconciliation/book-entries/?${p}`);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function fetchCashBookReport(selectedLedgerId, fromDate, toDate) {
  try {
    const response = await apiClient.get(`/accounting/api/cash-book?ledger_id=${selectedLedgerId}&from_date=${(fromDate)}&to_date=${(toDate)}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch cashbookreport:", error.response?.data || error.message);
    // return { success: false, error: error.response?.data || error.message };
    throw error;
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

export async function fetchArtisanDataAPI(searchTerm = "") {
  try {
    let url = "/contacts/api/ledger/";

    if (searchTerm) {
      const queryParams = new URLSearchParams();
      queryParams.append('search', searchTerm);
      url += `?${queryParams.toString()}`;
    }

    const response = await apiClient.get(url);
    return { success: true, data: response.data.results || response.data };
  } catch (error) {
    console.error("Error fetching artisan data:", error.response?.data || error.message);
    return { success: false, data: [] };
  }
}

export async function fetchItemDataAPI() {
  try {
    const response = await apiClient.get("/mastersconfig/api/item/");
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
    const response = await apiClient.get("/auth/api/users/");
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

// export async function fetchGroupDataAPI() {
//   try {
//     const response = await apiClient.get("/mastersconfig/api/item_group/");
//     return { success: true, data: response.data.results || response.data };
//   } catch (error) {
//     console.error("Error fetching group data:", error.response?.data || error.message);
//     return { success: false, data: [] };
//   }
// }

// export async function fetchShapeDataAPI() {
//   try {
//     const response = await apiClient.get("/mastersconfig/api/shape/");
//     return { success: true, data: response.data.results || response.data };
//   } catch (error) {
//     console.error("Error fetching shape data:", error.response?.data || error.message);
//     return { success: false, data: [] };
//   }
// }
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
export async function fetchLedgerStatement({ ledger_id, from_date, to_date }) {
  try {
    const response = await apiClient.get(
      `/accounting/api/ledger-statement/?ledger_id=${ledger_id}&from_date=${from_date}&to_date=${to_date}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function fetchDayBook({ from_date, to_date }) {
  try {
    const response = await apiClient.get(
      `/accounting/api/day-book/?from_date=${from_date}&to_date=${to_date}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function fetchOutstandingReport({ type = "debtor", as_of_date }) {
  try {
    const response = await apiClient.get(
      `/accounting/api/outstanding/?type=${type}&as_of_date=${as_of_date}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

// ---------------------------------------------------------------------------
// Masters Config — Item Group
// ---------------------------------------------------------------------------

export async function fetchItemGroups() {
  try {
    const response = await apiClient.get("/mastersconfig/api/item_group/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createItemGroup(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/item_group/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateItemGroup(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/item_group/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deleteItemGroup(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/item_group/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ---------------------------------------------------------------------------
// Masters Config — Packet Group
// ---------------------------------------------------------------------------

export async function fetchPacketGroups() {
  try {
    const response = await apiClient.get("/mastersconfig/api/packet_group/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createPacketGroup(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/packet_group/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updatePacketGroup(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/packet_group/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deletePacketGroup(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/packet_group/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ---------------------------------------------------------------------------
// Masters Config — HSN  (fetchHSNs already exists)
// ---------------------------------------------------------------------------

export async function createHsn(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/hsn/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateHsn(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/hsn/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deleteHsn(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/hsn/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ---------------------------------------------------------------------------
// Masters Config — Item  (fetchItemDataAPI exists; adding clean versions)
// ---------------------------------------------------------------------------

export async function fetchItems() {
  try {
    const response = await apiClient.get("/mastersconfig/api/item/");
    const raw = response.data;
    const data = Array.isArray(raw) ? raw : raw?.results ?? [];
    return { success: true, data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createItem(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/item/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateItem(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/item/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deleteItem(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/item/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ---------------------------------------------------------------------------
// Masters Config — Packet  (fetchPackets already exists)
// ---------------------------------------------------------------------------

export async function createPacket(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/packet/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updatePacket(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/packet/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deletePacket(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/packet/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ---------------------------------------------------------------------------
// Masters Config — Shapes & Colors (for Packet master dropdowns)
// ---------------------------------------------------------------------------

export async function fetchShapes() {
  try {
    const response = await apiClient.get("/mastersconfig/api/shape/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createShape(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/shape/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateShape(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/shape/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deleteShape(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/shape/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchColors() {
  try {
    const response = await apiClient.get("/mastersconfig/api/color/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createColor(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/color/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateColor(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/color/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deleteColor(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/color/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ---------------------------------------------------------------------------
// AI Layer
// ---------------------------------------------------------------------------

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

// ── Master Data CSV Upload ──────────────────────────────────────────────────

// ── Ledger Master Template & CSV Upload ──────────────────────────────────────

export async function downloadLedgerTemplate(type) {
  try {
    const response = await apiClient.get(`/contacts/api/ledger/template/?type=${type}`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ledger_template_${type.toLowerCase()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadLedgerCSV(file, type) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post(
      `/contacts/api/ledger/csv-upload/?type=${type}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadHSNCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/hsn/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadItemGroupCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/item_group/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadItemCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/item/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadPacketGroupCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/packet_group/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadPacketCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/packet/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadKarigarMakingCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/manufacturing/api/karigar-making/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function runMySQLSync(tables = null) {
  try {
    const body = tables ? { tables } : {};
    const response = await apiClient.post("/mastersconfig/api/mysql-sync/", body);
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


// ─── Fiscal Year Management ──────────────────────────────────────────────────

export async function getFiscalYears() {
  try {
    const response = await apiClient.get("/mastersconfig/api/fiscal-years/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createFiscalYear(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/fiscal-years/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function setActiveFiscalYear(id) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/fiscal-years/${id}/set-active/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function closeFiscalYear(id) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/fiscal-years/${id}/close/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function reopenFiscalYear(id) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/fiscal-years/${id}/reopen/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Setup Wizard ──────────────────────────────────────────────────────────────

export async function getSetupStatus() {
  try {
    const response = await apiClient.get('/userauth/api/setup/status/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function seedAccountGroups() {
  try {
    const response = await apiClient.post('/userauth/api/setup/seed-accounts/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function seedTdsTcs() {
  try {
    const response = await apiClient.post('/userauth/api/setup/seed-tds-tcs/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function resetErp(password) {
  try {
    const response = await apiClient.post('/userauth/api/setup/reset-erp/', { password });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function setupRollback() {
  try {
    const response = await apiClient.post('/userauth/api/setup/rollback/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── GSTIN Master ──────────────────────────────────────────────────────────────

export async function fetchGstins() {
  try {
    const response = await apiClient.get('/mastersconfig/api/gstin/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createGstin(payload) {
  try {
    const response = await apiClient.post('/mastersconfig/api/gstin/', payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Exhibition Profiles ───────────────────────────────────────────────────────

export async function fetchExhibitions() {
  try {
    const response = await apiClient.get('/mastersconfig/api/exhibition/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createExhibition(payload) {
  try {
    const response = await apiClient.post('/mastersconfig/api/exhibition/', payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateExhibition(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/exhibition/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteExhibition(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/exhibition/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function activateExhibition(id) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/exhibition/${id}/activate/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deactivateExhibition(id) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/exhibition/${id}/deactivate/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerCashReceived(customerId) {
  try {
    const response = await apiClient.get(`/sales/api/customer-cash-received/?customer_id=${customerId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateEwayTransport(id, data) {
  try {
    const response = await apiClient.patch(`/sales/api/sale-voucher/${id}/eway-transport/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Salesperson Commission ────────────────────────────────────────────────────
export async function fetchCommissionReport(params) {
  try {
    const response = await apiClient.get('/mastersconfig/api/commission/report/', { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createCommissionJV(entries) {
  try {
    const response = await apiClient.post('/mastersconfig/api/commission/create-jv/', { entries });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCommissionLedgerConfig() {
  try {
    const response = await apiClient.get('/mastersconfig/api/commission/ledger-config/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function setCommissionLedger(commission_ldgr_id) {
  try {
    const response = await apiClient.patch('/mastersconfig/api/commission/ledger-set/', { commission_ldgr_id });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Repair Job Card ──────────────────────────────────────────────────────────

export async function fetchRepairJobCardNextNo() {
  try {
    const response = await apiClient.get('/manufacturing/api/repair-job-card-no/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

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

export async function deleteRepairJobCard(id) {
  try {
    await apiClient.delete(`/manufacturing/api/repair-job-card/${id}/`);
    return { success: true };
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

// ── Raw Material & Semi-Finished Stock ────────────────────────────────────────

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

export async function getSemiFinishedStock() {
  try {
    const response = await apiClient.get("/inventory/api/semi-finished-stock/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Barcode Images ────────────────────────────────────────────────────────────

export async function getBarcodeImages(barcodeId) {
  try {
    const response = await apiClient.get(`/inventory/api/barcode-images/?barcode=${barcodeId}`);
    return { success: true, data: response.data };
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

export async function deleteBarcodeImage(id) {
  try {
    await apiClient.delete(`/inventory/api/barcode-images/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Licensing ─────────────────────────────────────────────────────────────────

export async function fetchAllApps() {
  try {
    const response = await apiClient.get("/licensing/api/all-apps/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

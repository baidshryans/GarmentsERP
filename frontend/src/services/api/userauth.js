// frontend/src/services/api/userauth.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";

export async function loginAndSaveToken(username, password) {
  try {
    const response = await apiClient.post("/userauth/api-token-auth/", { username, password });


    const { token, user } = response.data;

    sessionStorage.setItem("Token", token);
    sessionStorage.setItem("user", JSON.stringify(user));
    // Notify same-tab listeners (storage event only fires cross-tab natively)
    window.dispatchEvent(new Event("storage"));
    const data = await getRetails();
    if (data.success && data.data.results?.length > 0) {
      const ul = data.data.results[0];
      // Prefer default_location; fall back to first assigned retail
      const loc = ul.default_location || (ul.location?.length > 0 ? ul.location[0] : null);
      if (loc) {
        sessionStorage.setItem('retail_code', loc.retail_code);
        sessionStorage.setItem('state_code', loc.state?.code ?? '');
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

export async function changePassword(old_password, new_password) {
  try {
    const r = await apiClient.post('/userauth/api/users/change-password/', { old_password, new_password });
    if (r.data?.token) sessionStorage.setItem('Token', r.data.token);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data?.detail || e.response?.data || e.message }; }
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

// ── Logout ────────────────────────────────────────────────────────────────────
export const callLogout = async () => {
  try {
    await apiClient.post('/userauth/api/logout/');
    return { success: true };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// ── Login Log ─────────────────────────────────────────────────────────────────
export const fetchLoginLog = async (params = {}) => {
  try {
    const r = await apiClient.get('/userauth/api/login-log/', { params });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// ── Audit Log ─────────────────────────────────────────────────────────────────
export const fetchAuditLog = async (params = {}) => {
  try {
    const r = await apiClient.get('/userauth/api/audit-log/', { params });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// Fetch every event sharing one correlation_id (parent + child rows that
// were written inside a single transaction.atomic / HTTP request).
export const fetchAuditCorrelation = async (correlation_id) => {
  try {
    const r = await apiClient.get('/audit/api/log/correlation/', { params: { id: correlation_id } });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// Fetch old→new field diff for a single history record
export const fetchAuditDetail = async (id) => {
  try {
    const r = await apiClient.get('/userauth/api/audit-log/detail/', { params: { id } });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// Reverse a single past operation (parent + nested children that share one history_transaction_id)
export const reverseTransaction = async (history_transaction_id, dry_run = false) => {
  try {
    const r = await apiClient.post('/userauth/api/audit-log/reverse-transaction/', {
      history_transaction_id, dry_run,
    });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// Restore the system to its state at a specific timestamp
export const restoreToPoint = async (timestamp, dry_run = false, retail_id = null) => {
  try {
    const r = await apiClient.post('/userauth/api/audit-log/restore-to-point/', {
      timestamp, dry_run, retail_id,
    });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
};

// ── Dashboard Summary ─────────────────────────────────────────────────────────
export const fetchDashboardSummary = () => _api('get', '/userauth/api/dashboard-summary/');

// ── Retails & States (admin-level) ────────────────────────────────────────────
export async function fetchRetails() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/retail/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch retails:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchStates() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/state/?page_size=100`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
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

export async function seedStates() {
  try {
    const response = await apiClient.post('/userauth/api/setup/seed-states/');
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

export async function syncUserRetails() {
  try {
    const response = await apiClient.post('/userauth/api/setup/sync-retails/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function seedSystemLedgers() {
  try {
    const r = await apiClient.post('/userauth/api/setup/seed-system-ledgers/', {}, { timeout: 60000 });
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getMySQLConfig() {
  try {
    const r = await apiClient.get("/mastersconfig/api/mysql-sync/");
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function runMySQLSync(connection = {}, tables = null) {
  try {
    const body = { ...connection, ...(tables ? { tables } : {}) };
    const response = await apiClient.post("/mastersconfig/api/mysql-sync/", body, { timeout: 300000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

// ── GSTIN Master ──────────────────────────────────────────────────────────────

export async function fetchGstins() {
  try {
    const response = await apiClient.get('/mastersconfig/api/gstin/?page_size=100');
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

// ── Retail Management ─────────────────────────────────────────────────────────

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

// ── Licensing ─────────────────────────────────────────────────────────────────

export async function fetchAllApps() {
  try {
    const response = await apiClient.get("/licensing/api/all-apps/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// frontend/src/services/api/hr.js
import apiClient from "../apiClient";

export async function fetchEmployees(params = {}) {
  try {
    const response = await apiClient.get("/hr/api/employees/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createEmployeeWithUser(data) {
  try {
    const response = await apiClient.post("/hr/api/employees/create-with-user/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateEmployee(id, data) {
  try {
    const response = await apiClient.patch(`/hr/api/employees/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSalaryStructures(params = {}) {
  try {
    const response = await apiClient.get("/hr/api/salary-structure/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createSalaryStructure(data) {
  try {
    const response = await apiClient.post("/hr/api/salary-structure/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchDeductionConfig(params = {}) {
  try {
    const response = await apiClient.get("/hr/api/deduction-config/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function saveDeductionConfig(data) {
  try {
    const url = data.id ? `/hr/api/deduction-config/${data.id}/` : "/hr/api/deduction-config/";
    const method = data.id ? "patch" : "post";
    const response = await apiClient[method](url, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSalarySlips(params = {}) {
  try {
    const response = await apiClient.get("/hr/api/salary-slips/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function generatePayslip(data) {
  try {
    const response = await apiClient.post("/hr/api/generate-payslip/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function bulkGeneratePayslip(data) {
  try {
    const response = await apiClient.post("/hr/api/bulk-generate-payslip/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function approvePayslip(id) {
  try {
    const response = await apiClient.post(`/hr/api/approve-payslip/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchHRSettings() {
  try {
    const response = await apiClient.get("/hr/api/hr-settings/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function saveHRSettings(data) {
  try {
    const response = await apiClient.put("/hr/api/hr-settings/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchLeaveBalances(params = {}) {
  try {
    const response = await apiClient.get("/hr/api/leave-balance/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchITBlockRates() {
  try {
    const response = await apiClient.get("/accounting/api/fa/it-block-rates/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function seedHRLedgers() {
  try {
    const r = await apiClient.post('/userauth/api/setup/seed-hr-ledgers/');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function getHRSettings() {
  try {
    const r = await apiClient.get('/hr/api/hr-settings/');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function getPendingCheques() {
  try {
    const r = await apiClient.get('/sales/api/pending-cheques/');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function depositCheque(id, data) {
  try {
    const r = await apiClient.post(`/sales/api/deposit-cheque/${id}/`, data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

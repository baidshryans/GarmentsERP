// frontend/src/services/api/goldscheme.js
import apiClient from "../apiClient";

export async function fetchSchemes() {
  try {
    const response = await apiClient.get("/goldscheme/api/schemes/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createScheme(data) {
  try {
    const response = await apiClient.post("/goldscheme/api/schemes/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function updateScheme(id, data) {
  try {
    const response = await apiClient.put(`/goldscheme/api/schemes/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function deleteScheme(id) {
  try {
    await apiClient.delete(`/goldscheme/api/schemes/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSchemeEnrollments(params = {}) {
  try {
    const response = await apiClient.get("/goldscheme/api/enrollments/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSchemeEnrollment(id) {
  try {
    const response = await apiClient.get(`/goldscheme/api/enrollments/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function createSchemeEnrollment(payload) {
  try {
    const hasFile = payload && payload.enrollment_form_file instanceof File;
    let response;
    if (hasFile) {
      const fd = new FormData();
      Object.entries(payload).forEach(([k, v]) => {
        if (v === undefined || v === null) return;
        if (k === "nominee" && typeof v === "object") {
          Object.entries(v).forEach(([nk, nv]) => {
            if (nv !== undefined && nv !== null) fd.append(`nominee.${nk}`, nv);
          });
        } else {
          fd.append(k, v);
        }
      });
      response = await apiClient.post("/goldscheme/api/enrollments/", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    } else {
      response = await apiClient.post("/goldscheme/api/enrollments/", payload);
    }
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function schemeEnrollmentPay(id, data) {
  try {
    const response = await apiClient.post(`/goldscheme/api/enrollments/${id}/pay/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSchemeStatement(id) {
  try {
    const response = await apiClient.get(`/goldscheme/api/enrollments/${id}/statement/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSchemeBenefit(id) {
  try {
    const response = await apiClient.get(`/goldscheme/api/enrollments/${id}/benefit/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function redeemSchemeEnrollment(id, data) {
  try {
    const response = await apiClient.post(`/goldscheme/api/enrollments/${id}/redeem/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function cancelSchemeEnrollment(id, data) {
  try {
    const response = await apiClient.post(`/goldscheme/api/enrollments/${id}/cancel/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSchemeSummary() {
  try {
    const response = await apiClient.get("/goldscheme/api/reports/scheme-summary/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchMaturityCalendar(params = {}) {
  try {
    const response = await apiClient.get("/goldscheme/api/reports/maturity-calendar/", { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchOverduePayments() {
  try {
    const response = await apiClient.get("/goldscheme/api/reports/overdue-payments/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
export async function fetchSchemeDashboardExt() {
  try {
    const response = await apiClient.get("/goldscheme/api/reports/scheme-dashboard-ext/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

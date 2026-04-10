import apiClient from "./hrPortalApiClient";

// Login via existing ERP token endpoint
export async function hrPortalLogin(username, password) {
  try {
    const r = await apiClient.post("/userauth/api-token-auth/", { username, password });
    return { success: true, data: r.data };
  } catch (err) {
    return { success: false, error: err.response?.data || err.message };
  }
}

export async function hrPortalFetchProfile() {
  try {
    const r = await apiClient.get("/hr/api/portal/my-profile/");
    return { success: true, data: r.data };
  } catch (err) {
    return { success: false, error: err.response?.data || err.message };
  }
}

export async function hrPortalFetchSlips(year) {
  try {
    const r = await apiClient.get("/hr/api/portal/my-slips/", { params: year ? { year } : {} });
    return { success: true, data: r.data };
  } catch (err) {
    return { success: false, error: err.response?.data || err.message };
  }
}

export async function hrPortalFetchSlip(month, year) {
  try {
    const r = await apiClient.get(`/hr/api/portal/my-slip/${month}/${year}/`);
    return { success: true, data: r.data };
  } catch (err) {
    return { success: false, error: err.response?.data || err.message };
  }
}

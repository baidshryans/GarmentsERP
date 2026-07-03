import portalApiClient from "./portalApiClient";

async function wrap(promise) {
  try {
    const res = await promise;
    return { success: true, data: res.data };
  } catch (err) {
    const data = err.response?.data;
    return { success: false, error: data?.error || data || err.message };
  }
}

export function portalRequestOtp({ userid, purpose }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/request-otp/", { userid, purpose }));
}

export function portalVerifyOtp({ userid, otp }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/verify-otp/", { userid, otp }));
}

export function portalPasswordLogin({ userid, password }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/login/", { userid, password }));
}

export function portalSetPassword({ userid, otp, new_password }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/set-password/", { userid, otp, new_password }));
}

export function portalFetchDashboard() {
  return wrap(portalApiClient.get("/goldscheme/api/portal/dashboard/"));
}

export function portalFetchEnrollment(enrollment_no) {
  return wrap(portalApiClient.get(`/goldscheme/api/portal/enrollment/${enrollment_no}/`));
}

export function portalPayInstallment({ enrollment_no, amount, upi_reference }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/pay/", { enrollment_no, amount, upi_reference }));
}

export function portalFetchOrders() {
  return wrap(portalApiClient.get("/sales/api/portal/customer-orders/"));
}

export function portalLogout() {
  return wrap(portalApiClient.post("/goldscheme/api/portal/logout/"));
}

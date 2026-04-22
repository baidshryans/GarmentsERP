import axios from "axios";

const BASE_URL = localStorage.getItem("baseUrl") || import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const hrPortalApiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

hrPortalApiClient.interceptors.request.use(config => {
  const token = sessionStorage.getItem("hrPortalToken");
  if (token) config.headers["Authorization"] = `Token ${token}`;
  return config;
});

hrPortalApiClient.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      sessionStorage.removeItem("hrPortalToken");
      sessionStorage.removeItem("hrPortalEmployee");
      window.location.href = "/hr-portal/login";
    }
    return Promise.reject(err);
  }
);

export default hrPortalApiClient;

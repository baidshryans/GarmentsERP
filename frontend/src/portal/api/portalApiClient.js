import axios from "axios";

const portalApiClient = axios.create({
  timeout: 15000,
});

// Set base URL dynamically
portalApiClient.interceptors.request.use((config) => {
  const base = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
  config.baseURL = base;

  // Attach portal token if available
  const token = sessionStorage.getItem("portalToken");
  if (token) {
    config.headers.Authorization = `PortalToken ${token}`;
  }

  return config;
});

// Handle 401 — redirect to portal login
portalApiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem("portalToken");
      sessionStorage.removeItem("portalCustomerName");
      sessionStorage.removeItem("portalMobile");
      window.location.href = "/portal/login";
    }
    return Promise.reject(error);
  }
);

export default portalApiClient;

import axios from 'axios';
const getBaseUrl = () => {
  const url = sessionStorage.getItem('baseUrl');
  if (!url) {
    // baseUrl is set during initial setup at /config. If it's gone (cleared
    // session, new tab), redirect the user back to config to re-enter it.
    if (!window.location.pathname.startsWith('/config') && window.location.pathname !== '/login') {
      window.location.href = '/config';
    }
    return 'http://127.0.0.1:8000/'; // harmless fallback during redirect
  }
  return url;
};

// Create an Axios instance
const apiClient = axios.create({
  baseURL: getBaseUrl(),
  timeout: 15000,
});

// Add a request interceptor to attach the token to every request
apiClient.interceptors.request.use(
  (config) => {
    config.baseURL = getBaseUrl();

    // Get the token from local storage or wherever you store it
    const token = sessionStorage.getItem('Token');
    const retail_code = sessionStorage.getItem('retail_code');

    if (token) {
      config.headers['Authorization'] = `Token ${token}`;
      config.headers["ngrok-skip-browser-warning"] = "true";
    }

    // Always set X-RETAIL-ID if available (required by backend middleware)
    // Skip during setup wizard � retail may not exist yet (fresh install / rollback)
    const isSetupPage = window.location.pathname.startsWith('/settings/setup');
    if (retail_code && !isSetupPage) {
      config.headers['X-RETAIL-ID'] = retail_code;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor to handle errors (optional)
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Don't redirect during setup wizard or login � those pages handle errors themselves
    const path = window.location.pathname;
    const isSetupOrLogin = path.startsWith("/settings/setup") || path === "/login" || path === "/config";

    if (error.response && error.response.status === 401 && !isSetupOrLogin) {
      console.log("Unauthorized. Redirecting to login...");
      sessionStorage.removeItem("Token");
      sessionStorage.removeItem("user");
      window.location.href = "/login";
    }

    if (error.response && error.response.status === 403 && !isSetupOrLogin) {
      console.log("Forbidden. Redirecting to forbidden...");
      window.location.href = "/forbidden";
    }
    return Promise.reject(error);
  }
);

export default apiClient;

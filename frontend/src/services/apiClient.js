import axios from 'axios';
const getBaseUrl = () => {
  return sessionStorage.getItem('baseUrl') || 'http://127.0.0.1:8000/';
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
    const token = localStorage.getItem('Token');
    const retail_code = localStorage.getItem('retail_code');

    if (token) {
      config.headers['Authorization'] = `Token ${token}`;
      config.headers["ngrok-skip-browser-warning"] = "true";
    }

    // Always set X-RETAIL-ID if available (required by backend middleware)
    if (retail_code) {
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
    // Don't redirect during setup wizard or login — those pages handle errors themselves
    const path = window.location.pathname;
    const isSetupOrLogin = path.startsWith("/settings/setup") || path === "/login" || path === "/config";

    if (error.response && error.response.status === 401 && !isSetupOrLogin) {
      console.log("Unauthorized. Redirecting to login...");
      localStorage.removeItem("Token");
      localStorage.removeItem("user");
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

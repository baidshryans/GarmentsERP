import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from "react-router-dom";
import './sessionPersist';        // rehydrate sessionStorage from localStorage (must run first)
import './index.css'
import App from './App.jsx'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LicenseProvider } from './contexts/LicenseContext';
import { ThemeProvider } from './contexts/ThemeContext';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});


createRoot(document.getElementById('root')).render(
  <BrowserRouter>
     <QueryClientProvider client={queryClient}>
      <LicenseProvider>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </LicenseProvider>
    </QueryClientProvider>
  </BrowserRouter>
)

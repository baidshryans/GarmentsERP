import { Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "@/contexts/ThemeContext";
import HRPortalLayout from "./HRPortalLayout";
import HRPortalAuthGuard from "./components/HRPortalAuthGuard";
import HRPortalLogin from "./pages/HRPortalLogin";
import HRPortalDashboard from "./pages/HRPortalDashboard";
import HRPortalSlipList from "./pages/HRPortalSlipList";
import HRPortalSlipDetail from "./pages/HRPortalSlipDetail";

export default function HRPortalApp() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="login" element={<HRPortalLogin />} />
        <Route
          path="/"
          element={
            <HRPortalAuthGuard>
              <HRPortalLayout />
            </HRPortalAuthGuard>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<HRPortalDashboard />} />
          <Route path="slips" element={<HRPortalSlipList />} />
          <Route path="slip/:month/:year" element={<HRPortalSlipDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="login" replace />} />
      </Routes>
    </ThemeProvider>
  );
}

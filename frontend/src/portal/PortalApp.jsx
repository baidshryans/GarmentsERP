import { Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "@/contexts/ThemeContext";
import PortalAuthGuard from "./components/PortalAuthGuard";
import PortalLayout from "./PortalLayout";
import PortalLogin from "./pages/PortalLogin";
import PortalDashboard from "./pages/PortalDashboard";
import PortalEnrollment from "./pages/PortalEnrollment";
import PortalPayment from "./pages/PortalPayment";

export default function PortalApp() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="login" element={<PortalLogin />} />
        <Route element={<PortalAuthGuard />}>
          <Route element={<PortalLayout />}>
            <Route index element={<PortalDashboard />} />
            <Route path="enrollment/:enrollmentNo" element={<PortalEnrollment />} />
            <Route path="pay/:enrollmentNo" element={<PortalPayment />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/portal/login" replace />} />
      </Routes>
    </ThemeProvider>
  );
}

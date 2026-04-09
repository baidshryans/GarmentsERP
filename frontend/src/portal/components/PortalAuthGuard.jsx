import { Navigate, Outlet } from "react-router-dom";

export default function PortalAuthGuard() {
  const token = localStorage.getItem("portalToken");
  if (!token) return <Navigate to="/portal/login" replace />;
  return <Outlet />;
}

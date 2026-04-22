import { Navigate } from "react-router-dom";

export default function HRPortalAuthGuard({ children }) {
  const token = sessionStorage.getItem("hrPortalToken");
  if (!token) return <Navigate to="/hr-portal/login" replace />;
  return children;
}

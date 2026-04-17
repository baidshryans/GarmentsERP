import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { LogOut, Gem } from "lucide-react";
import { portalLogout } from "../api/portalApiService";

export default function PortalHeader() {
  const navigate = useNavigate();
  const customerName = localStorage.getItem("portalCustomerName") || "Customer";

  const handleLogout = async () => {
    await portalLogout();
    localStorage.removeItem("portalToken");
    localStorage.removeItem("portalCustomerName");
    localStorage.removeItem("portalMobile");
    navigate("/portal/login");
  };

  return (
    <header className="border-b bg-card">
      <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Gem className="size-5 text-primary" />
          <span className="font-semibold text-sm">Gold Scheme Portal</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground hidden sm:inline">{customerName}</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}

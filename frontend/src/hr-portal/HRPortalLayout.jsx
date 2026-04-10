import { Outlet, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { LogOut, BriefcaseBusiness } from "lucide-react";

export default function HRPortalLayout() {
  const navigate = useNavigate();
  const emp = JSON.parse(localStorage.getItem("hrPortalEmployee") || "{}");

  function handleLogout() {
    localStorage.removeItem("hrPortalToken");
    localStorage.removeItem("hrPortalEmployee");
    navigate("/hr-portal/login");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate("/hr-portal/dashboard")}>
            <BriefcaseBusiness className="h-5 w-5 text-primary" />
            <span className="font-semibold text-sm">Employee Portal</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground hidden sm:inline">{emp.full_name}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

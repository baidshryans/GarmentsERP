import { Outlet } from "react-router-dom";
import PortalHeader from "./components/PortalHeader";
import { Toaster } from "@/components/ui/toaster";

export default function PortalLayout() {
  return (
    <div className="min-h-screen bg-background">
      <PortalHeader />
      <main className="max-w-2xl mx-auto px-4 py-6">
        <Outlet />
      </main>
      <Toaster />
    </div>
  );
}

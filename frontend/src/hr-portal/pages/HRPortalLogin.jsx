import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { hrPortalLogin, hrPortalFetchProfile } from "../hrPortalApiService";
import { BriefcaseBusiness } from "lucide-react";

export default function HRPortalLogin() {
  const navigate = useNavigate();
  const [form, setForm]   = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const r = await hrPortalLogin(form.username, form.password);
    if (!r.success) {
      setLoading(false);
      setError(r.error?.non_field_errors?.[0] || r.error?.detail || "Invalid credentials.");
      return;
    }

    sessionStorage.setItem("hrPortalToken", r.data.token);

    // Verify this user has an employee profile
    const pr = await hrPortalFetchProfile();
    setLoading(false);
    if (!pr.success) {
      sessionStorage.removeItem("hrPortalToken");
      setError("Your account is not linked to an employee profile. Please contact HR.");
      return;
    }

    sessionStorage.setItem("hrPortalEmployee", JSON.stringify(pr.data));
    navigate("/hr-portal/dashboard");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <div className="inline-flex items-center justify-center size-12 rounded-full bg-primary/10 mb-3">
            <BriefcaseBusiness className="size-6 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">Employee Portal</h1>
          <p className="text-sm text-muted-foreground mt-1">Sign in with your ERP credentials</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <Label>Username</Label>
            <Input
              value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              autoFocus
            />
          </div>
          <div className="space-y-1">
            <Label>Password</Label>
            <Input
              type="password"
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </Button>
        </form>
      </div>
    </div>
  );
}

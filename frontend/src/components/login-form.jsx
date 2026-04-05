import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { loginAndSaveToken } from "@/services/apiService";
import { Gem } from "lucide-react"

export function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const baseUrl = sessionStorage.getItem("baseUrl");
    if (!baseUrl) {
      navigate("/config");
    }
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const { success, data, error } = await loginAndSaveToken(username, password);
    if (success) {
      navigate("/", { replace: true });
      window.location.reload();
    } else {
      setError("Invalid username or password.");
    }
  };

  return (
    <div className="w-full max-w-sm">
      {/* Mobile-only logo */}
      <div className="flex md:hidden items-center gap-3 mb-8">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-500">
          <Gem className="w-5 h-5 text-gray-900" />
        </div>
        <div>
          <p className="font-bold text-foreground">Jewel India ERP</p>
        </div>
      </div>

      <div className="mb-8">
        <h2 className="text-2xl font-bold text-foreground">Welcome back</h2>
        <p className="text-muted-foreground text-sm mt-1">Sign in to your account to continue</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="username" className="text-sm font-medium">Username</Label>
          <Input
            id="username"
            type="text"
            placeholder="Enter your username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="h-10"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password" className="text-sm font-medium">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="Enter your password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-10"
          />
        </div>

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        <Button type="submit" className="w-full h-10 mt-1">
          Sign in
        </Button>
      </form>
    </div>
  );
}

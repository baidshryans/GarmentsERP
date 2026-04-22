import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function BaseUrlConfig() {
  const [baseUrl, setBaseUrl] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    // Check if base URL is already configured
    const storedBaseUrl = sessionStorage.getItem("baseUrl");
    if (storedBaseUrl) {
      navigate("/");
    }
  }, [navigate]);

  const validateUrl = (url) => {
    try {
      const parsedUrl = new URL(url);
      return parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:";
    } catch {
      return false;
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    if (!baseUrl.trim()) {
      setError("Base URL is required");
      return;
    }

    // Ensure URL ends with /
    let formattedUrl = baseUrl.trim();
    if (!formattedUrl.endsWith("/")) {
      formattedUrl += "/";
    }

    if (!validateUrl(formattedUrl)) {
      setError("Please enter a valid URL (http:// or https://)");
      return;
    }

    // Store in session storage
    sessionStorage.setItem("baseUrl", formattedUrl);

    // Redirect to login or dashboard
    const token = sessionStorage.getItem("Token");
    if (token) {
      navigate("/");
    } else {
      navigate("/login");
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">
            Configure Base URL
          </CardTitle>
          <CardDescription className="text-center">
            Enter your API base URL to get started
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="baseUrl">Base URL</Label>
              <Input
                id="baseUrl"
                type="text"
                placeholder="http://127.0.0.1:8000/"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className={error ? "border-red-500" : ""}
              />
              {error && (
                <p className="text-sm text-red-500">{error}</p>
              )}
              <p className="text-xs text-gray-500">
                Example: http://127.0.0.1:8000/ or https://api.example.com/
              </p>
            </div>
            <Button type="submit" className="w-full">
              Continue
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Gem, ArrowRight, ArrowLeft } from "lucide-react";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { Toaster } from "@/components/ui/toaster";
import { useToast } from "@/hooks/use-toast";
import OtpInput from "../components/OtpInput";
import { portalRequestOtp, portalVerifyOtp, portalPasswordLogin } from "../api/portalApiService";

export default function PortalLogin() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [mode, setMode] = useState("password"); // "password" | "otp"
  const [step, setStep] = useState(1); // OTP mode: 1 = userid, 2 = otp
  const [loading, setLoading] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [resendTimer, setResendTimer] = useState(0);

  const [userid, setUserid] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");

  // Already logged in?
  useEffect(() => {
    if (sessionStorage.getItem("portalToken")) navigate("/portal/", { replace: true });
  }, [navigate]);

  // Resend countdown
  useEffect(() => {
    if (resendTimer <= 0) return;
    const t = setTimeout(() => setResendTimer((v) => v - 1), 1000);
    return () => clearTimeout(t);
  }, [resendTimer]);

  const saveAndRedirect = (data) => {
    sessionStorage.setItem("portalToken", data.token);
    sessionStorage.setItem("portalCustomerName", data.customer_name || "");
    navigate("/portal/", { replace: true });
  };

  const switchMode = (next) => {
    setMode(next);
    setStep(1);
    setPassword("");
    setOtp("");
    setCustomerName("");
    setResendTimer(0);
  };

  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    if (!userid.trim() || !password) return;
    setLoading(true);
    const res = await portalPasswordLogin({ userid: userid.trim(), password });
    if (res.success && res.data.token) {
      saveAndRedirect(res.data);
    } else {
      toast({ title: "Error", description: String(res.error || "Login failed"), variant: "destructive" });
    }
    setLoading(false);
  };

  const handleRequestOTP = async (e) => {
    e.preventDefault();
    if (!userid.trim()) return;
    setLoading(true);
    const res = await portalRequestOtp({ userid: userid.trim() });
    if (res.success) {
      setStep(2);
      setResendTimer(60);
      toast({ title: "OTP sent" });
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setLoading(false);
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    if (otp.length < 4) return;
    setLoading(true);
    const res = await portalVerifyOtp({ userid: userid.trim(), otp });
    if (res.success && res.data.token) {
      saveAndRedirect(res.data);
    } else {
      toast({ title: "Error", description: String(res.error || "Verification failed"), variant: "destructive" });
    }
    setLoading(false);
  };

  const handleResendOTP = async () => {
    if (resendTimer > 0) return;
    setLoading(true);
    const res = await portalRequestOtp({ userid: userid.trim() });
    if (res.success) {
      setResendTimer(60);
      toast({ title: "OTP resent" });
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setLoading(false);
  };

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-sm">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-2">
              <Gem className="size-8 text-primary" />
            </div>
            <CardTitle className="text-lg">Gold Scheme Portal</CardTitle>
            {customerName && (
              <p className="text-sm text-muted-foreground mt-1">Welcome, {customerName}</p>
            )}
          </CardHeader>
          <CardContent>
            {/* Mode toggle */}
            <div className="flex gap-2 mb-4">
              <Button
                type="button"
                variant={mode === "password" ? "default" : "outline"}
                size="sm"
                className="flex-1"
                onClick={() => switchMode("password")}
              >
                Password
              </Button>
              <Button
                type="button"
                variant={mode === "otp" ? "default" : "outline"}
                size="sm"
                className="flex-1"
                onClick={() => switchMode("otp")}
              >
                Email OTP
              </Button>
            </div>

            {mode === "password" ? (
              <form onSubmit={handlePasswordLogin} className="space-y-4">
                <div>
                  <Label>Email or phone</Label>
                  <Input
                    type="text"
                    placeholder="Enter your email or phone"
                    value={userid}
                    onChange={(e) => setUserid(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <div>
                  <Label>Password</Label>
                  <Input
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? "Logging in..." : "Login"}
                </Button>
              </form>
            ) : step === 1 ? (
              <form onSubmit={handleRequestOTP} className="space-y-4">
                <div>
                  <Label>Email or phone</Label>
                  <Input
                    type="text"
                    placeholder="Enter your email or phone"
                    value={userid}
                    onChange={(e) => setUserid(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? "Sending OTP..." : "Continue"}
                  {!loading && <ArrowRight className="size-4 ml-1" />}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleVerify} className="space-y-4">
                <div>
                  <Label className="mb-2 block">Enter OTP</Label>
                  <OtpInput value={otp} onChange={setOtp} />
                  <div className="flex justify-between items-center mt-2">
                    <button
                      type="button"
                      className="text-xs text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
                      onClick={handleResendOTP}
                      disabled={resendTimer > 0 || loading}
                    >
                      {resendTimer > 0 ? `Resend in ${resendTimer}s` : "Resend OTP"}
                    </button>
                  </div>
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? "Verifying..." : "Login"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => { setStep(1); setOtp(""); }}
                >
                  <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Change email or phone
                </Button>
              </form>
            )}

            <div className="mt-4 text-center">
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => navigate("/portal/set-password")}
              >
                First time here / forgot password?
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
      <Toaster />
    </ThemeProvider>
  );
}

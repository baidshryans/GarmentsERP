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
import { portalRequestOTP, portalVerifyOTP } from "../api/portalApiService";

export default function PortalLogin() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [step, setStep] = useState(1); // 1 = mobile, 2 = password+OTP
  const [loading, setLoading] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [resendTimer, setResendTimer] = useState(0);

  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");

  // Already logged in?
  useEffect(() => {
    if (localStorage.getItem("portalToken")) navigate("/portal/", { replace: true });
  }, [navigate]);

  // Resend countdown
  useEffect(() => {
    if (resendTimer <= 0) return;
    const t = setTimeout(() => setResendTimer((v) => v - 1), 1000);
    return () => clearTimeout(t);
  }, [resendTimer]);

  const handleRequestOTP = async (e) => {
    e.preventDefault();
    if (!mobile.trim()) return;
    setLoading(true);

    const res = await portalRequestOTP({ mobile: mobile.trim() });
    if (res.success) {
      setCustomerName(res.data.customer_name || "");
      setStep(2);
      setResendTimer(60);
      toast({ title: "OTP sent to your mobile" });
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setLoading(false);
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!password || otp.length < 4) return;
    setLoading(true);

    const res = await portalVerifyOTP({
      mobile: mobile.trim(),
      password,
      otp,
    });

    if (res.success) {
      localStorage.setItem("portalToken", res.data.token);
      localStorage.setItem("portalCustomerName", res.data.customer_name);
      localStorage.setItem("portalMobile", res.data.mobile);
      navigate("/portal/", { replace: true });
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setLoading(false);
  };

  const handleResendOTP = async () => {
    if (resendTimer > 0) return;
    setLoading(true);
    const res = await portalRequestOTP({ mobile: mobile.trim() });
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
              <Gem className="h-8 w-8 text-primary" />
            </div>
            <CardTitle className="text-lg">Gold Scheme Portal</CardTitle>
            {customerName && step === 2 && (
              <p className="text-sm text-muted-foreground mt-1">Welcome, {customerName}</p>
            )}
          </CardHeader>
          <CardContent>
            {step === 1 ? (
              <form onSubmit={handleRequestOTP} className="space-y-4">
                <div>
                  <Label>Mobile Number</Label>
                  <Input
                    type="tel"
                    placeholder="Enter your mobile number"
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? "Sending OTP..." : "Continue"}
                  {!loading && <ArrowRight className="h-4 w-4 ml-1" />}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleVerify} className="space-y-4">
                <div>
                  <Label>Password</Label>
                  <Input
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoFocus
                  />
                </div>

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
                  onClick={() => { setStep(1); setPassword(""); setOtp(""); }}
                >
                  <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Change mobile number
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
      <Toaster />
    </ThemeProvider>
  );
}

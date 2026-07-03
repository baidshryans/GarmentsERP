import { useState } from "react";
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
import { portalRequestOtp, portalSetPassword } from "../api/portalApiService";

export default function PortalSetPassword() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [step, setStep] = useState(1); // 1 = userid, 2 = otp + new password
  const [loading, setLoading] = useState(false);
  const [resendTimer, setResendTimer] = useState(0);

  const [userid, setUserid] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const handleRequestOTP = async (e) => {
    e.preventDefault();
    if (!userid.trim()) return;
    setLoading(true);
    const res = await portalRequestOtp({ userid: userid.trim(), purpose: "reset" });
    if (res.success) {
      setStep(2);
      toast({ title: "OTP sent" });
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setLoading(false);
  };

  const handleSetPassword = async (e) => {
    e.preventDefault();
    if (otp.length < 4) {
      toast({ title: "Error", description: "Enter the OTP", variant: "destructive" });
      return;
    }
    if (newPassword.length < 6) {
      toast({ title: "Error", description: "Password must be at least 6 characters", variant: "destructive" });
      return;
    }
    setLoading(true);
    const res = await portalSetPassword({ userid: userid.trim(), otp, new_password: newPassword });
    if (res.success) {
      toast({ title: "Password set successfully", description: "Please log in with your new password" });
      navigate("/portal/login");
    } else {
      toast({ title: "Error", description: String(res.error || "Could not set password"), variant: "destructive" });
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
            <CardTitle className="text-lg">Set Password</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">First time here or forgot your password?</p>
          </CardHeader>
          <CardContent>
            {step === 1 ? (
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
              <form onSubmit={handleSetPassword} className="space-y-4">
                <div>
                  <Label className="mb-2 block">Enter OTP</Label>
                  <OtpInput value={otp} onChange={setOtp} />
                </div>
                <div>
                  <Label>New password</Label>
                  <Input
                    type="password"
                    placeholder="At least 6 characters"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? "Saving..." : "Set Password"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => { setStep(1); setOtp(""); setNewPassword(""); }}
                >
                  <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Change email or phone
                </Button>
              </form>
            )}

            <div className="mt-4 text-center">
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => navigate("/portal/login")}
              >
                Back to login
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
      <Toaster />
    </ThemeProvider>
  );
}

"use client"

import { useState } from "react"
import {
  BadgeCheck,
  Bell,
  ChevronsUpDown,
  CreditCard,
  KeyRound,
  LogOut,
  Settings,
  Sparkles,
} from "lucide-react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { useToast } from "@/hooks/use-toast"
import { changePassword } from "@/services/apiService"

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function NavUser({
  user
}) {
  const { isMobile } = useSidebar()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [pwdOpen, setPwdOpen] = useState(false)
  const [oldPwd, setOldPwd] = useState("")
  const [newPwd, setNewPwd] = useState("")
  const [confirmPwd, setConfirmPwd] = useState("")
  const [saving, setSaving] = useState(false)

  function openPwdDialog() {
    setOldPwd(""); setNewPwd(""); setConfirmPwd("")
    setPwdOpen(true)
  }

  async function handleChangePassword() {
    if (newPwd !== confirmPwd) {
      toast({ title: "Passwords do not match", variant: "destructive" })
      return
    }
    if (newPwd.length < 8) {
      toast({ title: "New password must be at least 8 characters", variant: "destructive" })
      return
    }
    setSaving(true)
    const r = await changePassword(oldPwd, newPwd)
    setSaving(false)
    if (r.success) {
      toast({ title: "Password changed successfully." })
      setPwdOpen(false)
    } else {
      const msg = typeof r.error === "string" ? r.error
        : (r.error?.detail || Object.values(r.error || {}).flat().join(", ") || "Failed to change password.")
      toast({ title: "Error", description: msg, variant: "destructive" })
    }
  }

  return (
    (<>
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground">
              <Avatar className="size-8 rounded-lg">
                <AvatarImage src={user.avatar} alt={user.name} />
                <AvatarFallback className="rounded-lg bg-gray-50">{user.name.charAt(0).toUpperCase()}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{user.name}</span>
                <span className="truncate text-xs">{user.email}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}>
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="size-8 rounded-lg">
                  <AvatarImage src={user.avatar} alt={user.name} />
                  <AvatarFallback className="rounded-lg">{user.name.charAt(0).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{user.name}</span>
                  <span className="truncate text-xs">{user.email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />

            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem onClick={openPwdDialog}>
              <KeyRound />
              Change Password
            </DropdownMenuItem>
            <DropdownMenuSeparator />

            <DropdownMenuItem onClick={async (e)=>{
              try {
                if (sessionStorage.getItem("erpSetupComplete") !== "true") {
                  const { setupRollback } = await import("@/services/apiService");
                  await setupRollback();
                }
              } catch (err) { /* swallow */ }
              try {
                const { callLogout } = await import("@/services/apiService");
                await callLogout();
              } catch (err) { /* swallow — token cleanup still happens below */ }
              sessionStorage.clear();
              sessionStorage.removeItem("erpSetupComplete");
              window.location.reload();
            }} >
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>

    <Dialog open={pwdOpen} onOpenChange={setPwdOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Change Password</DialogTitle>
          <DialogDescription>
            Enter your current password and pick a new one (minimum 8 characters).
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs">Current Password</Label>
            <Input type="password" autoComplete="current-password" value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">New Password</Label>
            <Input type="password" autoComplete="new-password" value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Confirm New Password</Label>
            <Input type="password" autoComplete="new-password" value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setPwdOpen(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleChangePassword}
            disabled={saving || !oldPwd || !newPwd || !confirmPwd}>
            {saving ? "Saving…" : "Update Password"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>)
  );
}

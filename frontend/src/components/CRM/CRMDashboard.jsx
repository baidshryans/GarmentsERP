import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { fetchCRMOccasions } from "@/services/apiService";
import {
  Gift, Heart, Phone, RefreshCw, MessageCircle, Send, CalendarDays, User,
} from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────────

function OccasionBadge({ occasion }) {
  return occasion === "birthday" ? (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-pink-100 text-pink-700 border border-pink-200">
      🎂 Birthday
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-purple-100 text-primary border border-purple-200">
      💍 Anniversary
    </span>
  );
}

function InitialsAvatar({ name, occasion }) {
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  const bg = occasion === "birthday"
    ? "bg-pink-500"
    : "bg-primary";
  return (
    <div className={`w-9 h-9 rounded-full ${bg} text-white flex items-center justify-center text-sm font-bold flex-shrink-0`}>
      {initials || <User className="size-4" />}
    </div>
  );
}

function DaysChip({ daysUntil }) {
  if (daysUntil === 0) return null;
  if (daysUntil === 1) return <span className="text-xs text-amber-600 font-semibold">Tomorrow</span>;
  return <span className="text-xs text-muted-foreground">{daysUntil}d away</span>;
}

function MessagePreview({ message }) {
  const lines = message.split("\n");
  return (
    <p className="text-xs text-muted-foreground line-clamp-2 max-w-xs">
      {lines[0]}
    </p>
  );
}

// ── Occasion Row ─────────────────────────────────────────────────────────────

function OccasionRow({ row, isToday = false }) {
  const { toast } = useToast();

  const handleSend = () => {
    if (!row.wa_url) {
      toast({ title: "No mobile number", description: `${row.name} has no mobile number on file.`, variant: "destructive" });
      return;
    }
    window.open(row.wa_url, "_blank");
  };

  return (
    <TableRow className={isToday ? "bg-amber-50/50 hover:bg-amber-50" : "hover:bg-muted/30"}>
      <TableCell className="py-3 px-3">
        <div className="flex items-center gap-3">
          <InitialsAvatar name={row.name} occasion={row.occasion} />
          <div>
            <p className="font-semibold text-sm leading-tight">{row.name}</p>
            <OccasionBadge occasion={row.occasion} />
          </div>
        </div>
      </TableCell>
      <TableCell className="py-3 px-3 text-sm">
        <div className="flex items-center gap-1.5">
          <CalendarDays className="w-3.5 h-3.5 text-muted-foreground" />
          {row.date_str}
          <span className="ml-1"><DaysChip daysUntil={row.days_until} /></span>
        </div>
      </TableCell>
      <TableCell className="py-3 px-3">
        {row.mobile ? (
          <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
            <Phone className="size-3" /> {row.mobile}
          </div>
        ) : (
          <span className="text-xs text-red-500 italic">No mobile</span>
        )}
      </TableCell>
      <TableCell className="py-3 px-3 max-w-xs">
        <MessagePreview message={row.message} />
      </TableCell>
      <TableCell className="py-3 px-3 text-right">
        <Button
          size="sm"
          variant={row.wa_url ? "default" : "outline"}
          className={`gap-1.5 text-xs h-8 ${row.wa_url ? "bg-green-600 hover:bg-green-700" : "opacity-50 cursor-not-allowed"}`}
          onClick={handleSend}
          disabled={!row.wa_url}
          title={row.wa_url ? "Open WhatsApp chat with pre-filled message" : "No mobile number available"}
        >
          <MessageCircle className="w-3.5 h-3.5" />
          Send WhatsApp ↗
        </Button>
      </TableCell>
    </TableRow>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

function CRMDashboard() {
  const { toast } = useToast();

  const [days,       setDays]     = useState(30);
  const [search,     setSearch]   = useState("");
  const [data,       setData]     = useState(null);
  const [loading,    setLoading]  = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await fetchCRMOccasions(days);
    setLoading(false);
    if (res.success) {
      setData(res.data);
    } else {
      toast({ title: "Error loading occasions", description: "Could not fetch CRM data.", variant: "destructive" });
    }
  }, [days, toast]);

  useEffect(() => { load(); }, [load]);

  const todayRows    = (data?.today    ?? []).filter(r => !search || r.name.toLowerCase().includes(search.toLowerCase()));
  const upcomingRows = (data?.upcoming ?? []).filter(r => !search || r.name.toLowerCase().includes(search.toLowerCase()));

  // Send All Today — opens each wa_url with a small delay between tabs
  const handleSendAll = () => {
    const withUrls = todayRows.filter(r => r.wa_url);
    if (!withUrls.length) {
      toast({ title: "Nothing to send", description: "No customers with mobile numbers for today." });
      return;
    }
    withUrls.forEach((row, i) => {
      setTimeout(() => window.open(row.wa_url, "_blank"), i * 350);
    });
    toast({ title: `Opening ${withUrls.length} WhatsApp chat(s)…`, description: "Allow pop-ups if your browser blocks them." });
  };

  return (
    <div className="space-y-6 p-1">
      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Heart className="size-6 text-pink-500" /> Customer Occasions
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Birthday & anniversary greetings with 20% off on making charges
          </p>
        </div>
      </div>

      {/* ── Filters ── */}
      <div className="rounded-xl border bg-card p-4 flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Search customer</Label>
          <Input
            placeholder="Type a name…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-52"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Show upcoming (days)</Label>
          <div className="flex gap-1.5">
            {[7, 30, 90].map(d => (
              <Button
                key={d}
                size="sm"
                variant={days === d ? "default" : "outline"}
                className="h-9 px-3"
                onClick={() => setDays(d)}
              >
                {d}d
              </Button>
            ))}
          </div>
        </div>
        <Button onClick={load} disabled={loading} variant="outline" className="gap-2 h-9">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {/* ── Today Strip ── */}
      <div className={`rounded-xl border-2 overflow-hidden ${todayRows.length > 0 ? "border-amber-300 bg-amber-50/40" : "border-muted bg-card"}`}>
        <div className="px-4 py-3 flex items-center justify-between border-b border-amber-200">
          <div className="flex items-center gap-2">
            <Gift className={`w-5 h-5 ${todayRows.length > 0 ? "text-amber-600" : "text-muted-foreground"}`} />
            <h2 className="font-semibold text-base">
              Today's Occasions
            </h2>
            {todayRows.length > 0 && (
              <span className="text-xs bg-amber-500 text-white rounded-full px-2 py-0.5 font-bold">
                {todayRows.length}
              </span>
            )}
          </div>
          {todayRows.length > 0 && (
            <Button
              size="sm"
              className="gap-1.5 bg-green-600 hover:bg-green-700 h-8 text-xs"
              onClick={handleSendAll}
            >
              <Send className="w-3.5 h-3.5" />
              Send All Today ({todayRows.filter(r => r.wa_url).length})
            </Button>
          )}
        </div>

        {loading && !data ? (
          <div className="p-4 space-y-3">
            {[1, 2].map(i => <Skeleton key={i} className="h-14 rounded-lg" />)}
          </div>
        ) : todayRows.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <span className="text-3xl">🎉</span>
            <p className="mt-2 font-medium">No occasions today</p>
            <p className="text-sm">Check back tomorrow or look at upcoming occasions below.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-amber-100/60">
                <TableHead className="px-3">Customer</TableHead>
                <TableHead className="px-3">Date</TableHead>
                <TableHead className="px-3">Mobile</TableHead>
                <TableHead className="px-3">Message Preview</TableHead>
                <TableHead className="px-3 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {todayRows.map((row, i) => (
                <OccasionRow key={`${row.id}-${row.occasion}`} row={row} isToday />
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* ── Upcoming Tabs ── */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center gap-2">
          <CalendarDays className="size-5 text-muted-foreground" />
          <h2 className="font-semibold text-base">Upcoming Occasions</h2>
          {upcomingRows.length > 0 && (
            <span className="text-xs bg-muted text-foreground rounded-full px-2 py-0.5 font-semibold">
              {upcomingRows.length}
            </span>
          )}
        </div>

        {loading && !data ? (
          <div className="p-4 space-y-3">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-12 rounded-lg" />)}
          </div>
        ) : upcomingRows.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <p className="font-medium">No upcoming occasions in the next {days} days</p>
            <p className="text-sm mt-1">Try increasing the "Show upcoming" days filter.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/30">
                <TableHead className="px-3">Customer</TableHead>
                <TableHead className="px-3">Date</TableHead>
                <TableHead className="px-3">Mobile</TableHead>
                <TableHead className="px-3">Message Preview</TableHead>
                <TableHead className="px-3 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {upcomingRows.map((row) => (
                <OccasionRow key={`${row.id}-${row.occasion}`} row={row} />
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* ── Footer tip ── */}
      <p className="text-xs text-muted-foreground text-center pb-2">
        Clicking "Send WhatsApp ↗" opens a pre-filled WhatsApp chat in a new tab. Allow pop-ups in your browser if they are blocked.
        <br />
        Birthday and anniversary dates are taken from the customer ledger. To update, edit the customer in <strong>Accounts → Ledger</strong>.
      </p>
    </div>
  );
}

export default CRMDashboard;

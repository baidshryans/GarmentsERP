import React, { useEffect, useState } from 'react';
import { CalendarDays, ChevronsUpDown, Check, Lock } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { SidebarMenu, SidebarMenuItem, SidebarMenuButton, useSidebar } from '@/components/ui/sidebar';
import { getFiscalYears, setActiveFiscalYear } from '@/services/apiService';
import { useToast } from '@/hooks/use-toast';

export function FiscalYearSwitcher() {
  const { isMobile } = useSidebar();
  const { toast } = useToast();
  const [fiscalYears, setFiscalYears] = useState([]);
  const [activeFy, setActiveFy] = useState(null);

  const fetchFYs = async () => {
    const result = await getFiscalYears();
    if (result.success) {
      setFiscalYears(result.data);
      const active = result.data.find(fy => fy.is_active);
      setActiveFy(active || null);
    }
  };

  useEffect(() => { fetchFYs(); }, []);

  const handleSwitch = async (fy) => {
    if (fy.id === activeFy?.id) return;
    const result = await setActiveFiscalYear(fy.id);
    if (result.success) {
      setActiveFy(fy);
      toast({ title: 'Fiscal Year Changed', description: `Switched to FY ${fy.fy_code}` });
      // Refresh the page to update all bill number contexts
      setTimeout(() => window.location.reload(), 500);
    } else {
      toast({ title: 'Error', description: 'Failed to switch fiscal year', variant: 'destructive' });
    }
  };

  if (fiscalYears.length === 0) {
    return (
      <div className="px-3 py-2 border-b border-sidebar-border">
        <a
          href="/masters/fiscal-years"
          className="flex items-center gap-2 text-xs text-sidebar-foreground/50 hover:text-sidebar-foreground transition-colors"
        >
          <CalendarDays className="w-3.5 h-3.5" />
          <span>Set up fiscal year</span>
        </a>
      </div>
    );
  }

  return (
    <div className="border-b border-sidebar-border">
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton size="sm" className="h-9 px-3">
                <CalendarDays className="size-4 text-primary shrink-0" />
                <span className="flex-1 text-xs font-semibold text-sidebar-foreground truncate">
                  FY {activeFy?.fy_code || '—'}
                </span>
                {activeFy?.is_closed && <Lock className="size-3 text-red-400 shrink-0" />}
                <ChevronsUpDown className="w-3.5 h-3.5 text-sidebar-foreground/40 shrink-0" />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="w-56 rounded-lg"
              align="start"
              side={isMobile ? 'bottom' : 'right'}
              sideOffset={4}
            >
              <DropdownMenuLabel className="text-xs text-muted-foreground">
                Switch Fiscal Year
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {fiscalYears.map((fy) => (
                <DropdownMenuItem
                  key={fy.id}
                  onClick={() => handleSwitch(fy)}
                  className="gap-2 cursor-pointer"
                >
                  <CalendarDays className={`w-4 h-4 ${fy.is_active ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className={fy.is_active ? 'font-semibold' : ''}>FY {fy.fy_code}</span>
                  {fy.is_closed && (
                    <Lock className="size-3 text-red-400 ml-1" />
                  )}
                  {fy.is_active && (
                    <Check className="size-4 text-primary ml-auto" />
                  )}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <a href="/masters/fiscal-years" className="gap-2 cursor-pointer text-xs text-muted-foreground">
                  Manage fiscal years
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
    </div>
  );
}

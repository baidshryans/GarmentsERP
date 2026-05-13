import React, { useEffect, useState } from 'react';
import { Building2, ChevronsUpDown, Check } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
} from '@/components/ui/sidebar';
import { getRetails } from '@/services/apiService';
import { useToast } from '@/hooks/use-toast';

export function RetailSwitcher() {
  const { isMobile } = useSidebar();
  const { toast } = useToast();
  const [retails, setRetails] = useState([]);
  const [activeCode, setActiveCode] = useState(
    () => sessionStorage.getItem('retail_code') || ''
  );

  useEffect(() => {
    getRetails().then((res) => {
      if (res.success && res.data.results?.length > 0) {
        const ul = res.data.results[0];
        const locations = ul.location || [];
        setRetails(locations);

        // Store the default country code for the active retail so PhoneInput can use it
        const countryCode = ul.default_country_code || 'IN';
        sessionStorage.setItem('default_country_code', countryCode);

        // Auto-select default retail if none is saved in sessionStorage yet
        const savedCode = sessionStorage.getItem('retail_code');
        if (!savedCode && locations.length > 0) {
          // Prefer user's default_location, fall back to first in list
          const defaultRetail = ul.default_location || locations[0];
          if (defaultRetail) {
            sessionStorage.setItem('retail_code', defaultRetail.retail_code);
            sessionStorage.setItem('state_code', defaultRetail.state?.code ?? '');
            setActiveCode(defaultRetail.retail_code);
            // Reload so all API calls pick up the new X-RETAIL-ID header
            window.location.reload();
          }
        }
      }
    });
  }, []);

  const handleSwitch = (retail) => {
    if (retail.retail_code === activeCode) return;
    sessionStorage.setItem('retail_code', retail.retail_code);
    sessionStorage.setItem('state_code', retail.state?.code ?? '');
    sessionStorage.setItem('default_country_code', retail.default_country_code || 'IN');
    setActiveCode(retail.retail_code);
    toast({
      title: 'Retail Switched',
      description: `Now viewing: ${retail.retail_name}`,
    });
    setTimeout(() => window.location.reload(), 400);
  };

  // Don't render switcher if user only has 0 or 1 retail (nothing to switch)
  if (retails.length <= 1) {
    const single = retails[0];
    if (!single) return null;
    return (
      <div className="px-3 py-2 border-b border-sidebar-border flex items-center gap-2">
        <Building2 className="w-3.5 h-3.5 text-primary shrink-0" />
        <span className="text-xs font-semibold text-sidebar-foreground truncate">
          {single.retail_name}
        </span>
      </div>
    );
  }

  const active = retails.find((r) => r.retail_code === activeCode) || retails[0];

  return (
    <div className="border-b border-sidebar-border">
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton size="sm" className="h-9 px-3">
                <Building2 className="size-4 text-primary shrink-0" />
                <span className="flex-1 text-xs font-semibold text-sidebar-foreground truncate">
                  {active?.retail_name || '�'}
                </span>
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
                Switch Retail
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {retails.map((r) => (
                <DropdownMenuItem
                  key={r.id}
                  onClick={() => handleSwitch(r)}
                  className="gap-2 cursor-pointer"
                >
                  <Building2
                    className={`w-4 h-4 ${
                      r.retail_code === activeCode
                        ? 'text-primary'
                        : 'text-muted-foreground'
                    }`}
                  />
                  <span className={r.retail_code === activeCode ? 'font-semibold' : ''}>
                    {r.retail_name}
                  </span>
                  {r.retail_code === activeCode && (
                    <Check className="size-4 text-primary ml-auto" />
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
    </div>
  );
}

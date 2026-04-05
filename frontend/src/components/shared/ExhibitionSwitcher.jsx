import React, { useEffect, useState } from 'react';
import { MapPin, ChevronsUpDown, Check, Zap, ZapOff } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { SidebarMenu, SidebarMenuItem, SidebarMenuButton, useSidebar } from '@/components/ui/sidebar';
import { fetchExhibitions, activateExhibition, deactivateExhibition } from '@/services/apiService';
import { useToast } from '@/hooks/use-toast';

export function ExhibitionSwitcher() {
  const { isMobile } = useSidebar();
  const { toast } = useToast();
  const [exhibitions, setExhibitions] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const res = await fetchExhibitions();
    if (res.success) {
      setExhibitions(Array.isArray(res.data) ? res.data : res.data?.results ?? []);
    }
  };

  useEffect(() => { load(); }, []);

  // Don't render anything if there are no exhibition profiles
  if (exhibitions.length === 0) return null;

  const activeExhibition = exhibitions.find(e => e.is_active) || null;

  const handleActivate = async (exh) => {
    if (exh.is_active) return;
    setLoading(true);
    const res = await activateExhibition(exh.id);
    if (res.success) {
      toast({ title: 'Exhibition Activated', description: `Invoices will now use: ${exh.name}` });
      load();
    } else {
      toast({ title: 'Error', description: 'Failed to activate exhibition', variant: 'destructive' });
    }
    setLoading(false);
  };

  const handleDeactivate = async () => {
    if (!activeExhibition) return;
    setLoading(true);
    const res = await deactivateExhibition(activeExhibition.id);
    if (res.success) {
      toast({ title: 'Exhibition Deactivated', description: 'Invoices will use your regular retail address & GSTIN.' });
      load();
    } else {
      toast({ title: 'Error', description: 'Failed to deactivate exhibition', variant: 'destructive' });
    }
    setLoading(false);
  };

  return (
    <div className={`border-b border-sidebar-border ${activeExhibition ? 'bg-amber-50/60' : ''}`}>
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton
                size="sm"
                className={`h-9 px-3 ${activeExhibition ? 'text-amber-700' : ''}`}
                disabled={loading}
              >
                <MapPin className={`w-4 h-4 shrink-0 ${activeExhibition ? 'text-amber-500' : 'text-muted-foreground'}`} />
                <span className={`flex-1 text-xs font-semibold truncate ${activeExhibition ? 'text-amber-800' : 'text-sidebar-foreground/60'}`}>
                  {activeExhibition ? activeExhibition.name : 'No exhibition active'}
                </span>
                <ChevronsUpDown className="w-3.5 h-3.5 text-sidebar-foreground/40 shrink-0" />
              </SidebarMenuButton>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              className="w-64 rounded-lg"
              align="start"
              side={isMobile ? 'bottom' : 'right'}
              sideOffset={4}
            >
              <DropdownMenuLabel className="text-xs text-muted-foreground">
                Default Exhibition
              </DropdownMenuLabel>
              <DropdownMenuSeparator />

              {/* Deactivate option when one is active */}
              {activeExhibition && (
                <>
                  <DropdownMenuItem
                    onClick={handleDeactivate}
                    className="gap-2 cursor-pointer text-amber-700 hover:text-amber-900"
                  >
                    <ZapOff className="w-4 h-4" />
                    <span className="text-sm">Deactivate exhibition</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}

              {/* List all exhibitions */}
              {exhibitions.map((exh) => (
                <DropdownMenuItem
                  key={exh.id}
                  onClick={() => handleActivate(exh)}
                  className="gap-2 cursor-pointer"
                  disabled={exh.is_active}
                >
                  <MapPin className={`w-4 h-4 ${exh.is_active ? 'text-amber-500' : 'text-muted-foreground'}`} />
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm truncate ${exh.is_active ? 'font-semibold text-amber-800' : ''}`}>
                      {exh.name}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono truncate">{exh.gstin}</div>
                  </div>
                  {exh.is_active && <Check className="w-4 h-4 text-amber-600 ml-auto shrink-0" />}
                </DropdownMenuItem>
              ))}

              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <a href="/masters/exhibitions" className="gap-2 cursor-pointer text-xs text-muted-foreground">
                  <Zap className="w-3.5 h-3.5" />
                  Manage exhibitions
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>
    </div>
  );
}

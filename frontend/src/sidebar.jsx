import { Calendar, Home, Inbox, Search, Settings } from "lucide-react"
import {
    Sidebar,
    SidebarMenu,
    SidebarMenuSub,
    SidebarMenuSubItem,
    SidebarMenuItem,
    SidebarMenuButton,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarHeader,
    SidebarProvider,
    SidebarTrigger,
    SidebarGroupLabel,
    SidebarGroupContent
} from "@/components/ui/sidebar"
import { ChevronDown } from "lucide-react";
import { CollapsibleTrigger, Collapsible, CollapsibleContent } from "@radix-ui/react-collapsible";
import { Outlet } from "react-router-dom";

const items = [
    {
        title: "Setup",
        url: "/about",
        icon: Home,
        submenu: [
            {title : "Item",icon : Settings},
            {title : "Accounts",icon : Settings},
            {title : "Sales Persons",icon : Settings},
            {title : "Karigar Making",icon : Settings},
        ]
    },
    {
        title: "Manufacturing",
        url: "#",
        icon: Inbox,  submenu: [
            {title : "Issue",icon : Settings},
            {title : "Receive",icon : Settings},
            {title : "Purchases",icon : Settings},
        ]
        
    },
    {
        title: "Sales",
        url: "#",
        icon: Calendar,  submenu: [
            {title : "Estimate",icon : Settings},
            {title : "Customer Order",icon : Settings},
            {title : "Sales Voucher",icon : Settings},
            {title : "Sales Return",icon : Settings},
            {title : "Sales Approval",icon : Settings},
            {title : "Customer Purchase",icon : Settings},
        ]
    },
    {
        title: "Inventory",
        url: "#",
        icon: Search,  submenu: [
            
            {title : "Barcode Management",icon : Settings},
            {title : "Stock Transfer",icon : Settings},
            {title : "Barcode History", icon : Settings},
            {title : "Design", icon : Settings}
        ]
    },
    {
        title: "Financial Accounting",
        url: "#",
        icon: Settings,  submenu: [
            {title : "Vouchers",icon : Settings},
            {title : "Due Advances",icon : Settings},
            {title : "Cash Book",icon : Settings},
            {title : "Bank Book",icon : Settings},
            {title : "P/L",icon : Settings},
            {title : "Trial Balance",icon : Settings},
            {title : "Balance Sheet",icon : Settings},
            {title : "CashFlow Statement",icon : Settings},
        ]
    },
    {
        title: "Reports",
        url: "#",
        icon: Settings,  submenu: [
            {title : "Financial Ratios",icon : Settings},
            {title : "Closing Stock Valuation",icon : Settings},
            {title : "Pcs Report",icon : Settings},
            {title : "Refinery Report",icon : Settings},
            {title : "Karigar",icon : Settings},
            {title : "Gold Ledger Balances",icon : Settings},
            {title : "Stock",icon : Settings},
        ]
    },
    {
        title: "Stat reports",
        url: "#",
        icon: Settings,  submenu: [
            {title : "GSTR1",icon : Settings},
            {title : "GST3B",icon : Settings},
            {title : "GST Input ",icon : Settings},
            {title : "GST Output",icon : Settings},
            {title : "TDS",icon : Settings},
            {title : "TCS",icon : Settings},
        ]
    },
]


export function AppSidebar() {
    return (
        <SidebarProvider>
            <Sidebar>
                <SidebarHeader >
                    <SidebarMenuItem>

                    </SidebarMenuItem>
                </SidebarHeader>
                <SidebarContent>
                        <SidebarGroup>
                            <SidebarMenu>
                                {items.map((item) => (<>

                                    <Collapsible key={item.title}  className="group/collapsible">
                                        <SidebarGroup>
                                            <SidebarGroupLabel asChild>
                                                <CollapsibleTrigger >
                                                     <SidebarMenuButton>
                                                        {item.title}
                                                        <ChevronDown className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-180" />

                                                    </SidebarMenuButton>
                                                </CollapsibleTrigger>
                                            </SidebarGroupLabel>
                                            <CollapsibleContent>
                                                <SidebarMenuSub>

                                                    <SidebarGroupContent>
                                                        <SidebarMenuSubItem >
                                                            {item.submenu.map((submenuitem) => (
                                                                <SidebarMenuButton asChild >
                                                                <a href={submenuitem.url}>
                                                                    <submenuitem.icon />
                                                                    <span>{submenuitem.title}</span>
                                                                </a>
                                                            </SidebarMenuButton>
                                                            ))}
                                                            
                                                        </SidebarMenuSubItem>
                                                    </SidebarGroupContent>
                                                </SidebarMenuSub>
                                            </CollapsibleContent>
                                        </SidebarGroup>
                                    </Collapsible>


                                </>

                                ))}
                            </SidebarMenu>

                        </SidebarGroup>
                </SidebarContent>
                <SidebarFooter />
            </Sidebar>
            <main>
                <div>
                    <SidebarTrigger />

                </div>
                <Outlet />

            </main>
        </SidebarProvider>
    )
}

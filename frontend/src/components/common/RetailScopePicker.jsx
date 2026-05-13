import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Store, ChevronDown } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuCheckboxItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { fetchRetails } from "@/services/apiService";

/**
 * Multi-retail scope picker used by Closing Stock / Balance Sheet / P&L.
 *
 * Controlled via:
 *   - `scope` ("all" | "selected")
 *   - `selectedIds` (number[])
 * Emits:
 *   - `onChange({ scope, selectedIds })`
 *
 * Buildss the appropriate URLSearchParams entries via the helper
 * `buildRetailScopeParams(scope, selectedIds)` exported below.
 */
export function RetailScopePicker({
  scope, selectedIds, onChange,
  label = "Retails",
  retails: retailsProp,
  disabled = false,
  className = "",
}) {
  const [retails, setRetails] = useState(retailsProp || []);

  useEffect(() => {
    if (retailsProp) { setRetails(retailsProp); return; }
    fetchRetails().then((res) => {
      if (res.success) setRetails(res.data?.results || res.data || []);
    });
  }, [retailsProp]);

  const buttonText =
    scope === "all"
      ? "All retails (combined)"
      : selectedIds.length === 0
        ? "Select retails…"
        : selectedIds.length === 1
          ? (retails.find((r) => r.id === selectedIds[0])?.retail_name || `#${selectedIds[0]}`)
          : `${selectedIds.length} retails selected`;

  return (
    <div className={`flex flex-col gap-1.5 min-w-[16rem] ${className}`}>
      <Label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-9 w-full justify-between gap-2 font-normal px-3 cursor-pointer"
          >
            <span className="flex items-center gap-2 truncate">
              <Store className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
              <span className={`truncate ${scope === "selected" && selectedIds.length === 0 ? "text-muted-foreground" : ""}`}>
                {buttonText}
              </span>
            </span>
            <ChevronDown className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64 max-h-80 overflow-y-auto">
          <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Scope
          </DropdownMenuLabel>
          <DropdownMenuCheckboxItem
            checked={scope === "all"}
            onCheckedChange={() => onChange({ scope: "all", selectedIds: [] })}
            onSelect={(e) => e.preventDefault()}
          >
            All retails (combined)
          </DropdownMenuCheckboxItem>
          {retails.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Individual retails
              </DropdownMenuLabel>
              {retails.map((r) => (
                <DropdownMenuCheckboxItem
                  key={r.id}
                  checked={scope === "selected" && selectedIds.includes(r.id)}
                  onCheckedChange={(checked) => {
                    const next = checked
                      ? [...new Set([...selectedIds, r.id])]
                      : selectedIds.filter((x) => x !== r.id);
                    onChange({ scope: "selected", selectedIds: next });
                  }}
                  onSelect={(e) => e.preventDefault()}
                >
                  {r.retail_name || r.retail_code || `#${r.id}`}
                </DropdownMenuCheckboxItem>
              ))}
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

/**
 * Append retail scope params to an existing URLSearchParams object.
 *
 *   scope "all"      → ?combined=true
 *   scope "selected" → ?retail_ids=<id>&retail_ids=<id>…
 *
 * Returns the same URLSearchParams for chainability.
 */
export function applyRetailScopeParams(params, scope, selectedIds) {
  if (scope === "all") {
    params.set("combined", "true");
  } else if (scope === "selected" && selectedIds?.length) {
    selectedIds.forEach((id) => params.append("retail_ids", String(id)));
  }
  return params;
}

/**
 * Shorthand for service-layer callers that pass a plain object to the API
 * client. Returns the object form (useful for axios `params`).
 */
export function retailScopeObject(scope, selectedIds) {
  if (scope === "all") return { combined: true };
  if (scope === "selected" && selectedIds?.length) return { retail_ids: selectedIds };
  return {};
}

import React, { useEffect, useRef } from "react";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { UserSearch } from "lucide-react";

/**
 * Full-screen modal shown on POS load to pick a customer before scanning.
 * Customer selection is mandatory — cannot be dismissed without selecting.
 * Props:
 *   customers  — array of { id, ac_name, mobile1, phone1 }
 *   onSelect   — fn(opt) called when a customer is chosen
 */
export default function CustomerSelectModal({ customers, onSelect }) {
  const comboRef = useRef(null);

  // Auto-focus the search input when modal opens
  useEffect(() => {
    const timer = setTimeout(() => comboRef.current?.focus(), 80);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[2px]">
      <div className="bg-background rounded-xl shadow-2xl w-[50vw] max-h-[80vh] mx-4 overflow-hidden border border-border flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="size-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <UserSearch className="size-5 text-primary" />
            </div>
            <div>
              <div className="text-[18px] font-bold text-foreground">Select Customer</div>
              <div className="text-[12px] text-muted-foreground">Search by name or mobile number</div>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="px-6 pb-6 flex-1 flex flex-col gap-4">
          <SearchableComboBox
            ref={comboRef}
            options={customers}
            labelKey="ac_name"
            searchKeys={["mobile1", "phone1"]}
            placeholder="Type name or mobile number…"
            onSelect={opt => onSelect(opt)}
            className="w-full border border-input rounded-lg px-4 py-3 text-[15px] font-[Assistant] bg-background text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors"
            renderOption={opt => (
              <div className="py-0.5">
                <div className="text-[14px] font-medium text-foreground">{opt.ac_name}</div>
                {(opt.mobile1 || opt.phone1) && (
                  <div className="text-[12px] text-muted-foreground mt-0.5">
                    {[opt.mobile1, opt.phone1].filter(Boolean).join("  ·  ")}
                  </div>
                )}
              </div>
            )}
          />
        </div>

      </div>
    </div>
  );
}

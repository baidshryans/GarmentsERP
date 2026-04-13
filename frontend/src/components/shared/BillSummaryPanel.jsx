import React from 'react';
import { Calculator } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

/**
 * BillSummaryPanel — a clean, card-style bill summary aligned to the right.
 *
 * Props:
 *   rows          — Array of row descriptors:
 *     { label, field, editable?, isTotal?, isSeparator?, step?, isEditableTotal? }
 *     - editable:       shows a compact number input (user can type)
 *     - isTotal:        renders with highlighted total styling
 *     - isSeparator:    renders a divider line (no label/field needed)
 *     - step:           step attribute for editable inputs (default "0.01")
 *     - isEditableTotal: when true AND autoCalcTotal prop is true, renders an
 *                        editable input + Calculator button instead of read-only
 *   register      — react-hook-form register function
 *   watch         — react-hook-form watch function
 *   autoCalcTotal — boolean; enables the editable-total + Calculate button
 *   onAutoCalc    — callback fired when the Calculate button is clicked
 */
const BillSummaryPanel = ({ rows, register, watch, standalone = true, autoCalcTotal = false, onAutoCalc }) => {
  return (
    <div className={standalone ? "flex justify-end mt-8 mb-6 w-full" : ""}>
      <div className={`${standalone ? 'w-full sm:w-[480px]' : 'w-full'} rounded-lg overflow-hidden border border-border shadow-sm`}>

        {/* Header */}
        <div className="flex items-center gap-2 px-6 py-3 bg-muted/60 border-b border-border">
          <svg className="w-3.5 h-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="text-xs font-semibold tracking-widest uppercase text-muted-foreground">
            Bill Summary
          </span>
        </div>

        {/* Rows */}
        <div className="bg-background divide-y divide-border/60">
          {rows.map((row, i) => {
            if (row.isSeparator) {
              return <div key={i} className="h-px bg-border/80" />;
            }

            const value = watch ? watch(row.field) : 0;
            const isTotal = row.isTotal;
            const isEditable = row.editable;
            const showEditableTotal = row.isEditableTotal && autoCalcTotal;

            return (
              <div
                key={i}
                className={`flex items-center justify-between px-6 ${
                  isTotal
                    ? 'py-3.5 bg-violet-50 dark:bg-violet-950/20'
                    : isEditable
                    ? 'py-2'
                    : 'py-2.5'
                }`}
              >
                <span
                  className={`text-sm whitespace-nowrap pr-6 ${
                    isTotal
                      ? 'font-bold text-primary dark:text-violet-300'
                      : isEditable
                      ? 'text-foreground/70 font-medium'
                      : 'text-muted-foreground'
                  }`}
                >
                  {row.label}
                </span>

                {row.captionField ? (
                  <div className="flex items-center gap-1 flex-1 justify-end">
                    <Input
                      type="text"
                      placeholder={row.captionPlaceholder || "Charge name"}
                      className="w-32 h-7 text-sm py-0 px-2 bg-muted/30 border-border/60 focus-visible:ring-primary focus-visible:border-violet-400"
                      {...register(row.captionField)}
                    />
                    <Input
                      type="number"
                      step={row.step || '0.01'}
                      disabled={!watch?.(row.captionField)}
                      className="w-24 h-7 text-right text-sm py-0 px-2 bg-muted/30 border-border/60 focus-visible:ring-primary focus-visible:border-violet-400 disabled:opacity-40 disabled:cursor-not-allowed"
                      {...register(row.field, { valueAsNumber: true })}
                    />
                  </div>
                ) : showEditableTotal ? (
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      step="0.01"
                      className="w-36 h-7 text-right text-sm py-0 px-2 bg-muted/30 border-border/60 focus-visible:ring-primary focus-visible:border-violet-400 font-bold text-primary"
                      {...register(row.field, { valueAsNumber: true })}
                    />
                    <Button
                      type="button"
                      size="icon"
                      variant="outline"
                      className="h-7 w-7 shrink-0 border-violet-300 text-primary hover:bg-violet-50"
                      onClick={onAutoCalc}
                      title="Auto-calculate Discount & GST from this total"
                    >
                      <Calculator className="size-3.5" />
                    </Button>
                  </div>
                ) : isEditable ? (
                  <Input
                    type="number"
                    step={row.step || '0.01'}
                    className="w-36 h-7 text-right text-sm py-0 px-2 bg-muted/30 border-border/60 focus-visible:ring-primary focus-visible:border-violet-400"
                    {...register(row.field, { valueAsNumber: true })}
                  />
                ) : (
                  <>
                    <input type="hidden" {...register(row.field)} />
                    <span
                      className={`tabular-nums text-right ${
                        isTotal
                          ? 'text-base font-bold text-primary dark:text-violet-300'
                          : 'text-sm font-semibold text-foreground/80'
                      }`}
                    >
                      {Number(value || 0).toLocaleString('en-IN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </span>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default BillSummaryPanel;

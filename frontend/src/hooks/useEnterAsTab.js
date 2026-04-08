import { useEffect, useRef } from "react";

/**
 * Makes Enter behave like Tab inside a form container, which is the expected
 * data-entry behavior for ERP/accounting forms.
 *
 * - Enter on input/select/combobox/date → focus next tabbable element
 * - Shift+Enter → focus previous tabbable element
 * - Ignored inside <textarea> (multi-line input) and inside buttons (so
 *   Enter still submits buttons naturally)
 * - Ignored when an autocomplete dropdown is open (Enter selects the option)
 * - Elements with data-enter-submit="true" still trigger form submit (Save)
 *
 * Usage:
 *   const formRef = useRef(null);
 *   useEnterAsTab(formRef);
 *   return <form ref={formRef}>…</form>;
 *
 * Or attach to any container div that wraps the form fields.
 */
export function useEnterAsTab(containerRef) {
  const refLatest = useRef(containerRef);
  useEffect(() => {
    refLatest.current = containerRef;
  });

  useEffect(() => {
    const container = containerRef?.current;
    if (!container) return;

    const isTabbable = (el) => {
      if (!el || el.disabled || el.hidden) return false;
      if (el.getAttribute("aria-hidden") === "true") return false;
      if (el.tabIndex < 0) return false;
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return false;
      return true;
    };

    const getTabbables = () => {
      const selector = [
        "input:not([type=hidden])",
        "select",
        "textarea",
        "button",
        "[role=combobox]",
        "[role=button]",
        "[tabindex]:not([tabindex='-1'])",
      ].join(",");
      return Array.from(container.querySelectorAll(selector)).filter(isTabbable);
    };

    const handler = (e) => {
      if (e.key !== "Enter") return;
      const target = e.target;
      if (!target) return;

      // Allow Enter in textareas (new line)
      if (target.tagName === "TEXTAREA") return;

      // Allow Enter on buttons (native click) unless it's our "next" field flow
      if (target.tagName === "BUTTON" && target.type !== "button") return;

      // If an autocomplete/combobox popover is open, let it handle Enter
      if (document.querySelector("[role=listbox][data-state=open]")) return;
      if (document.querySelector("[cmdk-root] [cmdk-item][data-selected='true']")) return;

      // Elements explicitly marked as submit triggers
      if (target.getAttribute("data-enter-submit") === "true") return;

      e.preventDefault();

      const tabbables = getTabbables();
      const idx = tabbables.indexOf(target);
      if (idx === -1) return;

      const nextIdx = e.shiftKey ? idx - 1 : idx + 1;
      const next = tabbables[nextIdx];
      if (next) {
        next.focus();
        if (typeof next.select === "function") {
          try { next.select(); } catch {}
        }
      }
    };

    container.addEventListener("keydown", handler);
    return () => container.removeEventListener("keydown", handler);
  }, [containerRef]);
}

export default useEnterAsTab;

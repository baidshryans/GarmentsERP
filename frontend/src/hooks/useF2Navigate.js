import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Press F2 anywhere on the page to navigate to the "Add New" URL.
 * Pass an absolute path (e.g. "/sales/add/") or a relative one (e.g. "add/").
 *
 * Usage:
 *   useF2Navigate("/sales/add/");
 *   useF2Navigate(`/accounting/${journal_type}/add`);
 */
export function useF2Navigate(to) {
  const navigate = useNavigate();
  const toRef = useRef(to);

  useEffect(() => {
    toRef.current = to;
  });

  useEffect(() => {
    const handler = (e) => {
      // Ignore F2 if the user is typing in an input/textarea/select
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "F2") {
        e.preventDefault();
        navigate(toRef.current);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}

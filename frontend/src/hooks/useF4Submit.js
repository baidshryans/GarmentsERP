import { useEffect, useRef } from "react";

/**
 * Press F4 anywhere on the page to trigger the form's save/update action.
 * Uses a ref internally so the latest callback is always called without
 * re-registering the event listener on every render.
 *
 * Usage (React Hook Form):
 *   useF4Submit(handleSubmit(onSubmit));
 *
 * Usage (plain handler):
 *   useF4Submit(handleSave);
 */
export function useF4Submit(onSubmit) {
  const cbRef = useRef(onSubmit);

  // Keep the ref in sync with the latest callback each render
  useEffect(() => {
    cbRef.current = onSubmit;
  });

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "F4") {
        e.preventDefault();
        cbRef.current?.();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []); // register once, ref handles updates
}

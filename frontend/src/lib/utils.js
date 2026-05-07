import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Normalises API error responses to a human-readable string.
 * Handles both DRF field-level errors (objects) and plain string errors.
 *
 * @param {object|string|null} error - The error from { success, error } API response
 * @returns {string}
 *
 * @example
 * const msg = parseApiError(res.error)
 * toast({ title: "Error", description: msg, variant: "destructive" })
 */
export function parseApiError(error) {
  if (error === null || error === undefined) {
    return "An unexpected error occurred."
  }
  if (typeof error === "object") {
    return Object.values(error).flat().join(", ")
  }
  return String(error)
}

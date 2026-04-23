export function isValidDateRange(from, to) {
  if (!from || !to) return true;
  return new Date(from) <= new Date(to);
}

export function dateRangeError(from, to) {
  return isValidDateRange(from, to) ? null : "From date cannot be after To date";
}

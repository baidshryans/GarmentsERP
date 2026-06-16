export function slugify(heading) {
  return String(heading)
    .trim()
    .toLowerCase()
    .replace(/[^\w\s.-]/g, '') // keep word chars, whitespace, dot, dash
    .replace(/\./g, '-')       // 14.3 -> 14-3
    .replace(/\s+/g, '-')      // spaces -> dash
    .replace(/-+/g, '-')       // collapse repeats
    .replace(/^-+|-+$/g, '');  // trim leading/trailing dashes
}

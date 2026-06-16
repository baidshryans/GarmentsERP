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

export function stripMarkdown(md) {
  return String(md)
    .replace(/```[\s\S]*?```/g, ' ')  // drop fenced code (incl. mermaid)
    .replace(/`([^`]+)`/g, '$1')      // inline code
    .replace(/^#{1,6}\s+/gm, '')      // heading hashes
    .replace(/\*\*([^*]+)\*\*/g, '$1')// bold
    .replace(/\*([^*]+)\*/g, '$1')    // italic
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '') // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // links -> text
    .replace(/^\s*[-*+]\s+/gm, '')    // list bullets
    .replace(/\|/g, ' ')              // table pipes
    .replace(/[ \t]+/g, ' ')
    .trim();
}

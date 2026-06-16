import Fuse from 'fuse.js';

export function buildIndex(sections) {
  return new Fuse(sections, {
    keys: [
      { name: 'title', weight: 2 },
      { name: 'plainText', weight: 1 },
    ],
    includeScore: true,
    threshold: 0.4,
    ignoreLocation: true,
    minMatchCharLength: 2,
  });
}

export function makeSnippet(plainText, query, radius = 60) {
  const text = plainText || '';
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  let idx = -1;
  for (const t of terms) {
    idx = text.toLowerCase().indexOf(t);
    if (idx !== -1) break;
  }
  if (idx === -1) return text.slice(0, radius * 2).trim();
  const start = Math.max(0, idx - radius);
  const end = Math.min(text.length, idx + radius);
  return (start > 0 ? '… ' : '') + text.slice(start, end).trim() + (end < text.length ? ' …' : '');
}

export function search(fuse, query) {
  const q = (query || '').trim();
  if (q.length < 2) return [];
  return fuse.search(q).slice(0, 20).map((r) => ({
    section: r.item,
    score: r.score,
    snippet: makeSnippet(r.item.plainText, q),
  }));
}

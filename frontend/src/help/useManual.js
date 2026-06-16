import rawManual from './manual.generated.md?raw';
import { parseManual } from './manual';
import { buildIndex, search as runSearch } from './helpSearch';

let _cache = null;

export function getManual() {
  if (!_cache) {
    const { sections, toc } = parseManual(rawManual);
    _cache = {
      sections,
      toc,
      byId: Object.fromEntries(sections.map((s) => [s.id, s])),
      fuse: buildIndex(sections),
    };
  }
  return _cache;
}

export function useManual() {
  const m = getManual();
  return {
    toc: m.toc,
    sections: m.sections,
    getSection: (id) => m.byId[id] || null,
    search: (query) => runSearch(m.fuse, query),
  };
}

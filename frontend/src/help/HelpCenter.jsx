import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useManual } from './useManual';
import MarkdownView from './MarkdownView';

export default function HelpCenter() {
  const { toc, getSection, sections, search } = useManual();
  const location = useLocation();

  const initialHash = location.hash?.replace('#', '') || (toc[0] && toc[0].id);
  const initialQ = new URLSearchParams(location.search).get('q') || '';
  const [activeId, setActiveId] = useState(initialHash);
  const [query, setQuery] = useState(initialQ);

  useEffect(() => {
    const id = location.hash?.replace('#', '');
    if (id) setActiveId(id);
  }, [location.hash]);

  const results = query.trim().length >= 2 ? search(query) : [];
  const active = useMemo(() => getSection(activeId) || sections[0], [activeId, getSection, sections]);
  const terms = query.trim().split(/\s+/).filter(Boolean);

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      <aside className="w-72 shrink-0 border-r pr-3">
        <div className="relative mb-3">
          <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <ScrollArea className="h-full pr-2">
          {results.length > 0 ? (
            <ul className="space-y-1">
              {results.map((r) => (
                <li key={r.section.id}>
                  <button
                    className="w-full rounded p-2 text-left text-sm hover:bg-accent"
                    onClick={() => setActiveId(r.section.id)}
                  >
                    <div className="font-medium">{r.section.title}</div>
                    <div className="line-clamp-1 text-xs text-muted-foreground">{r.snippet}</div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <nav className="space-y-2">
              {toc.map((ch) => (
                <div key={ch.id}>
                  <button
                    className={`w-full rounded px-2 py-1 text-left text-sm font-semibold hover:bg-accent ${
                      active?.id === ch.id ? 'bg-accent' : ''
                    }`}
                    onClick={() => setActiveId(ch.id)}
                  >
                    {ch.title}
                  </button>
                  <ul className="ml-3 border-l pl-2">
                    {ch.children.map((s) => (
                      <li key={s.id}>
                        <button
                          className={`w-full rounded px-2 py-1 text-left text-xs hover:bg-accent ${
                            active?.id === s.id ? 'bg-accent font-medium' : 'text-muted-foreground'
                          }`}
                          onClick={() => setActiveId(s.id)}
                        >
                          {s.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </nav>
          )}
        </ScrollArea>
      </aside>

      <ScrollArea className="flex-1">
        {active && (
          <article className="pr-4">
            <MarkdownView markdown={active.markdown} highlightTerms={terms} idPrefix={`help-${active.id}`} />
          </article>
        )}
      </ScrollArea>
    </div>
  );
}

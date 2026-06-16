import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowLeft, ExternalLink } from 'lucide-react';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useManual } from './useManual';
import MarkdownView from './MarkdownView';

export default function HelpDrawer({ open, onOpenChange }) {
  const { search, getSection } = useManual();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [activeId, setActiveId] = useState(null);

  const results = query.trim().length >= 2 ? search(query) : [];
  const active = activeId ? getSection(activeId) : null;
  const terms = query.trim().split(/\s+/).filter(Boolean);

  const openFullPage = (id) => {
    onOpenChange(false);
    navigate(`/help?q=${encodeURIComponent(query)}#${id}`);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-3 sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{active ? active.title : 'Help & Manual'}</SheetTitle>
        </SheetHeader>

        {!active && (
          <div className="relative">
            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
            <Input
              autoFocus
              className="pl-8"
              placeholder="Search the manual…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        )}

        <ScrollArea className="flex-1 pr-3">
          {active ? (
            <div className="space-y-3">
              <Button variant="ghost" size="sm" onClick={() => setActiveId(null)}>
                <ArrowLeft className="mr-1 size-4" /> Back to results
              </Button>
              <MarkdownView markdown={active.markdown} highlightTerms={terms} idPrefix={`drawer-${active.id}`} />
              <Button variant="outline" size="sm" className="w-full" onClick={() => openFullPage(active.id)}>
                <ExternalLink className="mr-1 size-4" /> Open full page
              </Button>
            </div>
          ) : (
            <ul className="space-y-1">
              {results.map((r) => (
                <li key={r.section.id}>
                  <button
                    className="w-full rounded p-2 text-left hover:bg-accent"
                    onClick={() => setActiveId(r.section.id)}
                  >
                    <div className="text-sm font-medium">{r.section.title}</div>
                    <div className="line-clamp-2 text-xs text-muted-foreground">{r.snippet}</div>
                  </button>
                </li>
              ))}
              {query.trim().length >= 2 && results.length === 0 && (
                <li className="p-2 text-sm text-muted-foreground">No results for “{query}”.</li>
              )}
            </ul>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

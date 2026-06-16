import './help.css';
import { useMemo, useState, useRef } from 'react';
import { renderMarkdown } from './markdown';
import MermaidDiagram from './MermaidDiagram';

// Split rendered HTML around mermaid code blocks so we can mount React diagrams.
const MERMAID_RE = /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g;

function decode(html) {
  return html
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
}

function highlight(html, terms) {
  if (!terms || terms.length === 0) return html;
  const escaped = terms.filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (escaped.length === 0) return html;
  const re = new RegExp(`(${escaped.join('|')})`, 'gi');
  // Only highlight inside text nodes: split on tags, transform non-tag chunks.
  return html.replace(/(<[^>]+>)|([^<]+)/g, (m, tag, text) =>
    tag ? tag : text.replace(re, '<mark>$1</mark>')
  );
}

export default function MarkdownView({ markdown, highlightTerms, idPrefix = 'doc' }) {
  const parts = useMemo(() => {
    const html = renderMarkdown(markdown);
    const out = [];
    let last = 0;
    let i = 0;
    let match;
    MERMAID_RE.lastIndex = 0;
    while ((match = MERMAID_RE.exec(html)) !== null) {
      const before = html.slice(last, match.index);
      if (before) out.push({ type: 'html', html: highlight(before, highlightTerms) });
      out.push({ type: 'mermaid', code: decode(match[1]).trim(), key: `${idPrefix}-${i++}` });
      last = MERMAID_RE.lastIndex;
    }
    const tail = html.slice(last);
    if (tail) out.push({ type: 'html', html: highlight(tail, highlightTerms) });
    return out;
  }, [markdown, highlightTerms, idPrefix]);

  const matchCount = useMemo(() => {
    if (!highlightTerms || highlightTerms.length === 0) return 0;
    return parts
      .filter((p) => p.type === 'html')
      .reduce((n, p) => n + (p.html.match(/<mark>/g) || []).length, 0);
  }, [parts, highlightTerms]);

  const [matchIdx, setMatchIdx] = useState(0);
  const rootRef = useRef(null);

  const gotoMatch = (next) => {
    const marks = rootRef.current?.querySelectorAll('mark');
    if (!marks || marks.length === 0) return;
    const i = (next + marks.length) % marks.length;
    setMatchIdx(i);
    marks[i].scrollIntoView({ block: 'center', behavior: 'smooth' });
  };

  return (
    <div ref={rootRef} className="manual-prose prose prose-sm max-w-none dark:prose-invert">
      {matchCount > 0 && (
        <div className="sticky top-0 z-10 mb-2 flex items-center gap-2 bg-background/90 py-1 text-xs">
          <span>{matchCount} matches</span>
          <button className="rounded border px-1" onClick={() => gotoMatch(matchIdx - 1)} aria-label="Previous match">▲</button>
          <button className="rounded border px-1" onClick={() => gotoMatch(matchIdx + 1)} aria-label="Next match">▼</button>
        </div>
      )}
      {parts.map((p, idx) =>
        p.type === 'mermaid' ? (
          <MermaidDiagram key={p.key} id={p.key} code={p.code} />
        ) : (
          <div key={idx} dangerouslySetInnerHTML={{ __html: p.html }} />
        )
      )}
    </div>
  );
}

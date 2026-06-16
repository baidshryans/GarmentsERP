import { useMemo } from 'react';
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

  return (
    <div className="manual-prose prose prose-sm max-w-none dark:prose-invert">
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

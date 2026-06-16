import { describe, it, expect } from 'vitest';
import { renderMarkdown } from './markdown';

describe('renderMarkdown', () => {
  it('renders headings and tables to HTML', () => {
    const html = renderMarkdown('## Title\n\n| A | B |\n|---|---|\n| 1 | 2 |');
    expect(html).toContain('<h2');
    expect(html).toContain('<table');
  });
  it('strips script tags', () => {
    const html = renderMarkdown('ok <script>alert(1)</script>');
    expect(html).not.toContain('<script');
  });
  it('keeps mermaid code blocks as code elements', () => {
    const html = renderMarkdown('```mermaid\ngraph TD; A-->B\n```');
    expect(html).toContain('language-mermaid');
  });
});

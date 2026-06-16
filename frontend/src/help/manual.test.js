import { describe, it, expect } from 'vitest';
import { slugify, stripMarkdown, parseManual } from './manual';

describe('slugify', () => {
  it('turns a chapter heading into a numeric slug', () => {
    expect(slugify('14. Gold Scheme Management')).toBe('14-gold-scheme-management');
  });
  it('turns a sub-section heading into a dotted-number slug', () => {
    expect(slugify('14.3 Recording a Payment')).toBe('14-3-recording-a-payment');
  });
  it('drops punctuation and lowercases', () => {
    expect(slugify('GST & Tax Compliance')).toBe('gst-tax-compliance');
  });
  it('handles headings with no number', () => {
    expect(slugify('Best Practices')).toBe('best-practices');
  });
});

describe('stripMarkdown', () => {
  it('removes fenced code blocks entirely', () => {
    const md = 'Intro text\n```mermaid\ngraph TD; A-->B\n```\nOutro text';
    const out = stripMarkdown(md);
    expect(out).toContain('Intro text');
    expect(out).toContain('Outro text');
    expect(out).not.toContain('graph TD');
  });
  it('strips heading hashes and emphasis', () => {
    expect(stripMarkdown('## 7. Sales Module')).toBe('7. Sales Module');
    expect(stripMarkdown('Use **bold** and *italic*')).toBe('Use bold and italic');
  });
});

const SAMPLE = [
  '# Jewel India ERP - User Manual',
  '',
  '## 7. Sales Module',
  'Sales intro paragraph.',
  '',
  '### 7.1 Create an Invoice',
  'Steps to create an invoice.',
  '```bash',
  '## not a heading inside fence',
  '```',
  '',
  '## 14. Gold Scheme Management',
  'Scheme intro.',
  '',
  '### 14.3 Recording a Payment',
  'How to record a payment.',
].join('\n');

describe('parseManual', () => {
  it('splits into chapters and sections', () => {
    const { sections } = parseManual(SAMPLE);
    const ids = sections.map((s) => s.id);
    expect(ids).toEqual([
      '7-sales-module',
      '7-1-create-an-invoice',
      '14-gold-scheme-management',
      '14-3-recording-a-payment',
    ]);
  });
  it('ignores ## lines inside code fences', () => {
    const { sections } = parseManual(SAMPLE);
    expect(sections.find((s) => s.title.includes('not a heading'))).toBeUndefined();
  });
  it('links sections to their parent chapter', () => {
    const { sections } = parseManual(SAMPLE);
    const pay = sections.find((s) => s.id === '14-3-recording-a-payment');
    expect(pay.level).toBe('section');
    expect(pay.chapterId).toBe('14-gold-scheme-management');
  });
  it('captures markdown body and plainText for each section', () => {
    const { sections } = parseManual(SAMPLE);
    const sales = sections.find((s) => s.id === '7-sales-module');
    expect(sales.markdown).toContain('Sales intro paragraph.');
    expect(sales.plainText).toContain('Sales intro paragraph.');
  });
  it('builds a nested toc of chapters with section children', () => {
    const { toc } = parseManual(SAMPLE);
    expect(toc.map((c) => c.id)).toEqual(['7-sales-module', '14-gold-scheme-management']);
    expect(toc[1].children.map((s) => s.id)).toEqual(['14-3-recording-a-payment']);
  });
});

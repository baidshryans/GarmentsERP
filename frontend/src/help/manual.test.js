import { describe, it, expect } from 'vitest';
import { slugify } from './manual';

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

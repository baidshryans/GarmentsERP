import { describe, it, expect } from 'vitest';
import { buildIndex, search } from './helpSearch';

const SECTIONS = [
  { id: '14-3-recording-a-payment', title: 'Recording a Payment', chapterId: '14-gold-scheme-management',
    plainText: 'To record a gold scheme installment payment, open the enrollment and click Pay.' },
  { id: '10-2-barcode-split', title: 'Barcode Split', chapterId: '10-inventory',
    plainText: 'Split a barcoded lot into multiple pieces, each with its own weight.' },
  { id: '13-1-depreciation', title: 'Depreciation', chapterId: '13-fixed-assets',
    plainText: 'Fixed assets depreciate using the WDV or SLM method each fiscal year.' },
];

describe('help search', () => {
  it('finds a section by a natural phrase in the body', () => {
    const fuse = buildIndex(SECTIONS);
    const results = search(fuse, 'record scheme payment');
    expect(results[0].section.id).toBe('14-3-recording-a-payment');
  });
  it('matches on title', () => {
    const fuse = buildIndex(SECTIONS);
    const results = search(fuse, 'barcode split');
    expect(results[0].section.id).toBe('10-2-barcode-split');
  });
  it('returns a snippet containing a query term', () => {
    const fuse = buildIndex(SECTIONS);
    const results = search(fuse, 'depreciation');
    expect(results[0].snippet.toLowerCase()).toContain('depreciat');
  });
  it('returns nothing for blank/too-short queries', () => {
    const fuse = buildIndex(SECTIONS);
    expect(search(fuse, '')).toEqual([]);
    expect(search(fuse, 'a')).toEqual([]);
  });
});

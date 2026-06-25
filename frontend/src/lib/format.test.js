import { describe, it, expect, beforeEach } from 'vitest';
import { formatMoney, formatNumber, formatDate, formatWords, setFormatConfig, INR_CONFIG } from './format';

beforeEach(() => setFormatConfig(INR_CONFIG));

describe('formatNumber', () => {
  it('Indian grouping with 2 decimals', () => {
    expect(formatNumber(200000, { decimals: 2 })).toBe('2,00,000.00');
  });
  it('min decimals only pads to at least 2 (matches legacy minimumFractionDigits:2)', () => {
    expect(formatNumber(1234.5, { minDecimals: 2 })).toBe('1,234.50');
  });
  it('abs strips sign', () => {
    expect(formatNumber(-2500, { decimals: 2, abs: true })).toBe('2,500.00');
  });
  it('blankOnZero returns empty for 0 and empty input', () => {
    expect(formatNumber(0, { blankOnZero: true })).toBe('');
    expect(formatNumber('', { blankOnZero: true })).toBe('');
  });
  it('empty input without blankOnZero formats as zero', () => {
    expect(formatNumber('', { decimals: 2 })).toBe('0.00');
  });
});

describe('formatMoney', () => {
  it('prefix symbol with space by default', () => {
    expect(formatMoney(12500, { decimals: 0 })).toBe('₹ 12,500');
  });
  it('prefix symbol without space', () => {
    expect(formatMoney(12500, { decimals: 0, space: false })).toBe('₹12,500');
  });
  it('showSymbol false delegates to number', () => {
    expect(formatMoney(12500, { decimals: 2, showSymbol: false })).toBe('12,500.00');
  });
  it('blankOnZero yields empty (no stray symbol)', () => {
    expect(formatMoney(0, { blankOnZero: true })).toBe('');
  });
});

describe('formatDate', () => {
  it('short style → "DD Mon YYYY"', () => {
    expect(formatDate('2026-06-26', 'short')).toBe('26 Jun 2026');
  });
  it('numeric style → "DD/MM/YYYY"', () => {
    expect(formatDate('2026-06-26', 'numeric')).toBe('26/06/2026');
  });
  it('empty input → empty string', () => {
    expect(formatDate('', 'short')).toBe('');
  });
  it('invalid date → original string', () => {
    expect(formatDate('not-a-date', 'short')).toBe('not-a-date');
  });
  it('empty options object → en-IN locale default (unpadded), matching bare toLocaleDateString', () => {
    expect(formatDate('2026-06-05', {})).toBe('5/6/2026');
  });
});

describe('formatWords (indian-rupee)', () => {
  it('lakh/crore wording preserved', () => {
    expect(formatWords(12500)).toBe('Rupees Twelve Thousand Five Hundred Only');
    expect(formatWords(10000000)).toBe('Rupees One Crore Only');
    expect(formatWords(0)).toBe('Rupees Zero Only');
  });
});

describe('config swap (forward-looking)', () => {
  it('suffix symbol + western grouping', () => {
    setFormatConfig({ ...INR_CONFIG, symbol: 'AED', symbolPosition: 'suffix', locale: 'en-US' });
    expect(formatMoney(200000, { decimals: 2 })).toBe('200,000.00 AED');
  });
});

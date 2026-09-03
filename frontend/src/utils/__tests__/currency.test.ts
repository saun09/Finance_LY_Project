import {
  formatPaise,
  formatPaiseWithDecimals,
  formatPercent,
  paiseToRupeeInput,
  rupeeInputToPaise,
} from '../currency';

describe('formatPaise (Indian digit grouping)', () => {
  it('formats amounts under 1,000 with no grouping', () => {
    expect(formatPaise(50000)).toBe('₹500');
    expect(formatPaise(0)).toBe('₹0');
  });

  it('groups thousands with a single comma', () => {
    expect(formatPaise(120000_00)).toBe('₹1,20,000');
  });

  it('groups lakhs and crores the Indian way, not the Western way', () => {
    expect(formatPaise(12345678_00)).toBe('₹1,23,45,678');
    expect(formatPaise(1000000_00)).toBe('₹10,00,000');
  });

  it('floors any leftover paise rather than rounding', () => {
    expect(formatPaise(1099)).toBe('₹10');
    expect(formatPaise(1099)).not.toBe('₹11');
  });

  it('renders negative amounts with a leading minus before the rupee sign', () => {
    expect(formatPaise(-150000)).toBe('-₹1,500');
  });
});

describe('formatPaiseWithDecimals', () => {
  it('shows the paise remainder as two decimal digits', () => {
    expect(formatPaiseWithDecimals(150050)).toBe('₹1,500.50');
    expect(formatPaiseWithDecimals(100005)).toBe('₹1,000.05');
  });

  it('pads a single-digit remainder', () => {
    expect(formatPaiseWithDecimals(1005)).toBe('₹10.05');
  });
});

describe('paiseToRupeeInput', () => {
  it('converts paise to a plain rupee string for editing', () => {
    expect(paiseToRupeeInput(1500000)).toBe('15000');
  });

  it('rounds to the nearest rupee', () => {
    expect(paiseToRupeeInput(150049)).toBe('1500');
    expect(paiseToRupeeInput(150050)).toBe('1501');
  });

  it('returns an empty string for null/undefined so inputs render blank, not "0"', () => {
    expect(paiseToRupeeInput(null)).toBe('');
    expect(paiseToRupeeInput(undefined)).toBe('');
  });
});

describe('rupeeInputToPaise', () => {
  it('converts a whole-rupee string to integer paise', () => {
    expect(rupeeInputToPaise('15000')).toBe(1500000);
  });

  it('converts a decimal-rupee string to integer paise', () => {
    expect(rupeeInputToPaise('150.50')).toBe(15050);
  });

  it('strips thousands separators the user may have typed', () => {
    expect(rupeeInputToPaise('1,50,000')).toBe(15000000);
  });

  it('returns null for an empty or whitespace-only string', () => {
    expect(rupeeInputToPaise('')).toBeNull();
    expect(rupeeInputToPaise('   ')).toBeNull();
  });

  it('rejects negative numbers, letters, and malformed decimals', () => {
    expect(rupeeInputToPaise('-100')).toBeNull();
    expect(rupeeInputToPaise('abc')).toBeNull();
    expect(rupeeInputToPaise('100.5.5')).toBeNull();
    expect(rupeeInputToPaise('100.999')).toBeNull();
  });

  it('round-trips with paiseToRupeeInput for whole-rupee amounts', () => {
    const paise = rupeeInputToPaise('42000')!;
    expect(paiseToRupeeInput(paise)).toBe('42000');
  });
});

describe('formatPercent', () => {
  it('formats a numeric or decimal-string percentage with a trailing %', () => {
    expect(formatPercent(35)).toBe('35%');
    expect(formatPercent('35.00')).toBe('35%');
  });

  it('respects requested fraction digits', () => {
    expect(formatPercent(33.333, 1)).toBe('33.3%');
  });

  it('returns an em dash placeholder for non-finite input rather than "NaN%"', () => {
    expect(formatPercent('not-a-number')).toBe('—');
  });
});

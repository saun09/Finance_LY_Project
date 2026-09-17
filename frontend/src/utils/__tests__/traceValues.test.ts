import { asUnavailableSection, formatTraceValue, humanizeKey } from '../traceValues';

/**
 * The property under test throughout: a trace value may be made *readable*,
 * but the stored form must still be reachable on the returned object, so a
 * caller (or a test) can always compare the two. The stored value is no
 * longer printed beneath every row -- that restated things the reader could
 * already see -- but it is never discarded.
 */

describe('formatTraceValue', () => {
  it('leaves a value untouched when the server declared no unit', () => {
    const out = formatTraceValue(4560000, undefined);
    expect(out.display).toBe('4560000');
    expect(out.raw).toBe('4560000');
  });

  it('never guesses a unit from the value alone', () => {
    // 4560000 could be paise, a count, or basis points. Without a hint the
    // client must not decide -- guessing is how an audit trace starts lying.
    expect(formatTraceValue(4560000, undefined).display).toBe('4560000');
  });

  it('formats paise as rupees while keeping the stored paise reachable', () => {
    const out = formatTraceValue(4560000, 'paise');
    expect(out.display).toBe('₹45,600');
    expect(out.raw).toBe('4560000');
  });

  it('uses Indian digit grouping, matching the backend', () => {
    expect(formatTraceValue(12000000_00, 'paise').display).toBe('₹1,20,00,000');
  });

  it('formats percentages and percentage points distinctly', () => {
    expect(formatTraceValue('40.00', 'percent').display).toBe('40%');
    expect(formatTraceValue('2.50', 'percent_points').display).toBe('2.5 pct points');
  });

  it('shows basis points as both a percentage and the stored bps', () => {
    expect(formatTraceValue(1500, 'basis_points').display).toBe('15% (1500 bps)');
  });

  it('pluralizes months correctly', () => {
    expect(formatTraceValue(1, 'months').display).toBe('1 month');
    expect(formatTraceValue(9, 'months').display).toBe('9 months');
  });

  it('labels a tier as a tier rather than a bare number', () => {
    expect(formatTraceValue(3, 'tier').display).toBe('Tier 3');
  });

  it('renders null as an em dash rather than inventing a zero', () => {
    expect(formatTraceValue(null, 'paise').display).toBe('—');
    expect(formatTraceValue(undefined, 'paise').display).toBe('—');
  });

  it('falls back to the raw string when a hinted value is not numeric', () => {
    const out = formatTraceValue('not a number', 'paise');
    expect(out.display).toBe('not a number');
    expect(out.raw).toBe('not a number');
  });

  it('renders booleans readably', () => {
    expect(formatTraceValue(true, undefined).display).toBe('Yes');
    expect(formatTraceValue(false, undefined).display).toBe('No');
  });

  it('does not invent precision the stored value did not have', () => {
    expect(formatTraceValue('0.30', 'ratio').display).toBe('0.3');
    expect(formatTraceValue('5.0', 'score').display).toBe('5');
  });
});

describe('humanizeKey', () => {
  it('turns snake_case into words without changing meaning', () => {
    expect(humanizeKey('total_recoverable_annual_paise')).toBe('total recoverable annual paise');
  });
});

describe('asUnavailableSection', () => {
  it('recognizes the server marker for a section that could not be rendered', () => {
    const section = asUnavailableSection({
      __unavailable__: true,
      missing_fields: ['unlock_conditions'],
      recorded_values: { binding_constraints: ['buffer'] },
    });
    expect(section).not.toBeNull();
    expect(section!.missing_fields).toEqual(['unlock_conditions']);
    expect(section!.recorded_values).toEqual({ binding_constraints: ['buffer'] });
  });

  it('treats an ordinary reasoning section as available', () => {
    expect(asUnavailableSection({ capacity_ceiling: 3 })).toBeNull();
    expect(asUnavailableSection([1, 2, 3])).toBeNull();
    expect(asUnavailableSection(null)).toBeNull();
  });

  it('defaults missing marker fields rather than throwing', () => {
    const section = asUnavailableSection({ __unavailable__: true });
    expect(section).toEqual({ missing_fields: [], recorded_values: {} });
  });
});

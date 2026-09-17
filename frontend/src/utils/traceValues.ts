import type { ValueHint } from '../api/types';
import { formatPaise } from './currency';

/**
 * Rendering values inside a Module 9 reasoning trace.
 *
 * The tension this resolves: the trace is an audit artifact, so it must stay
 * faithful to exactly what was stored -- but `total_recoverable_annual_paise:
 * 4560000` is not transparency to anyone who doesn't already know the money
 * rule. Transparency that can't be read isn't transparency.
 *
 * The resolution is that the SERVER declares the unit for each leaf
 * (`value_hints`, versioned by `value_hint_rules_version`). The client
 * formats only what it was told the unit of, never what it guessed from a
 * key name, and always keeps the raw value visible alongside. So a reader
 * gets "₹45,600" and an auditor still gets "4560000" -- neither is traded
 * away for the other.
 */

export interface FormattedTraceValue {
  /** What to show prominently. Equals `raw` when there is no usable hint. */
  display: string;
  /** The stored value, verbatim. Shown as a secondary line whenever it
   * differs from `display`, so nothing is ever only paraphrased. */
  raw: string;
  /** True when `raw` should be shown alongside `display`. */
  showRaw: boolean;
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function rawString(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

/** Format one leaf using the server-declared unit, if any. */
export function formatTraceValue(value: unknown, hint: ValueHint | undefined): FormattedTraceValue {
  const raw = rawString(value);
  if (value === null || value === undefined || hint === undefined) {
    return { display: raw, raw, showRaw: false };
  }

  const n = asNumber(value);
  if (n === null) return { display: raw, raw, showRaw: false };

  switch (hint) {
    case 'paise':
      // The only paise -> rupee conversion path, same as everywhere else.
      return { display: formatPaise(n), raw, showRaw: true };
    case 'percent':
      return { display: `${trimZeros(n)}%`, raw, showRaw: false };
    case 'percent_points':
      return { display: `${trimZeros(n)} pct points`, raw, showRaw: false };
    case 'basis_points':
      return { display: `${trimZeros(n / 100)}% (${n} bps)`, raw, showRaw: false };
    case 'months':
      return { display: `${trimZeros(n)} month${n === 1 ? '' : 's'}`, raw, showRaw: false };
    case 'count':
      return { display: String(n), raw, showRaw: false };
    case 'tier':
      return { display: `Tier ${n}`, raw, showRaw: false };
    case 'score':
    case 'ratio':
      return { display: trimZeros(n), raw, showRaw: false };
    case 'version':
    case 'date':
    default:
      return { display: raw, raw, showRaw: false };
  }
}

/** 40.00 -> "40", 2.50 -> "2.5". Keeps the number readable without
 * inventing precision the stored value didn't have. */
function trimZeros(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return String(Number(n.toFixed(4)));
}

/** snake_case -> readable words, for reasoning keys the server sends raw. */
export function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ');
}

/** The marker the server writes in place of a section it could not honestly
 * render (see UNAVAILABLE_KEY in backend transparency.py). */
export const UNAVAILABLE_KEY = '__unavailable__';

export interface UnavailableSection {
  missing_fields: string[];
  recorded_values: Record<string, unknown>;
}

export function asUnavailableSection(value: unknown): UnavailableSection | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (record[UNAVAILABLE_KEY] !== true) return null;
  return {
    missing_fields: Array.isArray(record.missing_fields) ? (record.missing_fields as string[]) : [],
    recorded_values:
      typeof record.recorded_values === 'object' && record.recorded_values !== null
        ? (record.recorded_values as Record<string, unknown>)
        : {},
  };
}

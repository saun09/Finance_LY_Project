/**
 * Money boundary rules (see master prompt Section 23 and the backend's own
 * "Currency is INR... never use floats for money math" convention):
 *
 * - The backend stores and returns ALL money as integer paise. Every
 *   number named `*_paise` in api/types.ts is paise, never rupees.
 * - This file is the ONLY place paise <-> rupee conversion happens.
 *   Screens must never do `value / 100` inline -- always call
 *   `paiseToRupeeInput` / `rupeeInputToPaise` / `formatPaise`.
 * - Indian digit grouping (₹1,20,000, not ₹120,000) mirrors the backend's
 *   own `_indian_grouping` in app/services/risk_profile.py exactly, so a
 *   figure reads identically whether it was formatted server-side (e.g.
 *   inside an unlock-condition message string) or client-side.
 */

/** Groups a non-negative integer string of digits the Indian way:
 * last 3 digits, then groups of 2 (e.g. "12000000" -> "1,20,00,000"). */
function groupIndian(digits: string): string {
  if (digits.length <= 3) return digits;
  const last3 = digits.slice(-3);
  let rest = digits.slice(0, -3);
  const groups: string[] = [];
  while (rest.length > 2) {
    groups.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest.length > 0) groups.unshift(rest);
  return `${groups.join(',')},${last3}`;
}

/** paise (integer) -> "₹1,20,000" (whole rupees, floor of any leftover paise) */
export function formatPaise(paise: number): string {
  const sign = paise < 0 ? '-' : '';
  const rupees = Math.floor(Math.abs(paise) / 100);
  return `${sign}₹${groupIndian(String(rupees))}`;
}

/** paise -> "₹1,20,000.50" when the paise remainder matters (rare; most
 * screens should prefer formatPaise's whole-rupee display) */
export function formatPaiseWithDecimals(paise: number): string {
  const sign = paise < 0 ? '-' : '';
  const abs = Math.abs(paise);
  const rupees = Math.floor(abs / 100);
  const remainder = abs % 100;
  return `${sign}₹${groupIndian(String(rupees))}.${String(remainder).padStart(2, '0')}`;
}

/** For a <CurrencyInput>: paise from the API -> the rupee string to show
 * in a text field (e.g. 1500000 -> "15000"). Never shows paise to the user
 * -- all onboarding amounts are whole-rupee entry, matching the app's
 * actual UX (nobody types paise). */
export function paiseToRupeeInput(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return '';
  return String(Math.round(paise / 100));
}

/** The inverse, for submitting a form: rupee text input -> integer paise
 * for the API body. Rejects anything that isn't a plain non-negative
 * integer/decimal rupee amount rather than silently coercing. */
export function rupeeInputToPaise(input: string): number | null {
  const trimmed = input.trim().replace(/,/g, '');
  if (trimmed === '') return null;
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  const rupees = Number(trimmed);
  if (!Number.isFinite(rupees)) return null;
  return Math.round(rupees * 100);
}

/** A Decimal-string percentage from the backend (e.g. "35.00") -> "35%" */
export function formatPercent(value: string | number, fractionDigits = 0): string {
  const n = typeof value === 'string' ? Number(value) : value;
  if (!Number.isFinite(n)) return '—';
  return `${n.toFixed(fractionDigits)}%`;
}

/** "12.5" -> 1250 basis points (100 bps = 1%), for the EMI interest-rate
 * field -- annual_rate_bps is what the API expects, but nobody types a
 * loan's rate in basis points. Same digit/decimal-place validation shape
 * as rupeeInputToPaise, just at 100x scale instead of paise's 100x. */
export function percentInputToBps(input: string): number | null {
  const trimmed = input.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  const percent = Number(trimmed);
  if (!Number.isFinite(percent)) return null;
  return Math.round(percent * 100);
}

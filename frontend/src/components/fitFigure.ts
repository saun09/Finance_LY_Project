import { StyleSheet, type TextStyle } from 'react-native';
import { TYPE } from '../theme/tokens';

/** Every glyph in IBM Plex Mono (the app's figure font) advances exactly
 * 0.6em; the extra margin covers the rupee sign and sub-pixel rounding. */
const MONO_ADVANCE_EM = 0.625;
const MIN_FONT_SIZE = 13;

/** Font size that lets `text` fit on one line in `availableWidth`, never
 * larger than the variant's own size and never below a readable minimum.
 *
 * Long figures ("-₹1,24,80,771", "+10.0 pts") in a half-width card used to
 * be cut off with "…" because the figure is held to one line -- a number
 * must never wrap mid-digit, and must never be silently truncated either.
 * Measuring the space actually available (rather than guessing from the
 * string length) makes the shrink right on every screen width, web
 * included, where `adjustsFontSizeToFit` doesn't exist.
 *
 * Returns undefined (leave the style alone) until the width is known, and
 * for non-monospace text, whose glyph widths can't be computed this way. */
export function fitFigureStyle(
  text: string,
  availableWidth: number,
  variant: keyof typeof TYPE,
  style?: TextStyle | TextStyle[] | null,
): TextStyle | undefined {
  if (availableWidth <= 0 || text.length === 0) return undefined;
  const flat = { ...TYPE[variant], ...(StyleSheet.flatten(style) ?? {}) } as TextStyle;
  if (!String(flat.fontFamily ?? '').includes('Mono')) return undefined;

  const baseSize = flat.fontSize ?? 15;
  const fitted = Math.floor(availableWidth / (text.length * MONO_ADVANCE_EM));
  if (fitted >= baseSize) return undefined;

  const size = Math.max(MIN_FONT_SIZE, fitted);
  const lineRatio = (flat.lineHeight ?? baseSize * 1.2) / baseSize;
  return { fontSize: size, lineHeight: Math.round(size * lineRatio) };
}

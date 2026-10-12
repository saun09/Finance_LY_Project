/**
 * "Ledger" design language: an editorial, financial-publication aesthetic
 * (warm parchment paper, deep ink, terracotta + petrol accents) rather
 * than a generic SaaS-blue/purple-gradient dashboard. Deliberately avoids
 * Inter/Roboto/system fonts — see FONTS below.
 *
 * Every screen should pull colors/spacing/type from here, never inline
 * hex values, so the whole app reads as one designed system.
 */

export const COLOR = {
  // base surfaces -- warm parchment, not clinical white
  paper: '#F6F1E7',
  paperRaised: '#FCF9F2',
  paperSunken: '#EDE6D6',
  // Light mode gets its lift from Card's drop shadow, not a gradient/
  // highlight -- these exist only so Palette's shape matches DARK_COLOR.
  cardGradientTop: '#FCF9F2',
  cardHighlight: 'rgba(33, 29, 24, 0)',

  // ink -- warm near-black, not pure #000
  ink: '#211D18',
  inkMuted: '#5C5648',
  inkFaint: '#8C8471',

  // brand: terracotta is the dominant, sharp accent
  terracotta: '#C1502E',
  terracottaDeep: '#9A3D22',
  terracottaSoft: '#F0DCCF',

  // secondary structural accent
  petrol: '#1F4B4C',
  petrolDeep: '#153434',
  petrolSoft: '#DCE9E7',

  // semantic -- muted, not neon; never the sole signal (paired with icons/labels)
  positive: '#3F6B4F',
  positiveSoft: '#DEE8DF',
  warning: '#B8842E',
  warningSoft: '#F1E4C9',
  danger: '#9E3B3B',
  dangerSoft: '#F1DBD8',

  border: '#DCD3BE',
  borderStrong: '#C7BB9E',

  overlay: 'rgba(33, 29, 24, 0.55)',
} as const;

/** The app's primary identity (Section "Restyle" brief): a premium, calm,
 * warm-dark fintech feel, forced on regardless of OS theme (see
 * ThemeContext) rather than a system-dependent alternate palette. Built
 * by deepening and polishing the existing warm-dark variant, not
 * replacing it with a generic cold navy/neon dashboard -- same "Ledger"
 * identity (warm near-black, terracotta + petrol), tuned so figures read
 * instantly against the surface and cards feel lifted without relying on
 * a shadow (which doesn't read on a dark ground). */
export const DARK_COLOR = {
  paper: '#14110C',
  paperRaised: '#231E16',
  paperSunken: '#0C0A07',
  // Top-of-card sheen for the gradient Card uses in dark mode, and the
  // hairline highlight along a card's top edge -- the "soft embossed
  // light" a premium dark card needs instead of a drop shadow.
  cardGradientTop: '#2B2519',
  cardHighlight: 'rgba(247, 238, 221, 0.07)',

  ink: '#F7EEDD',
  inkMuted: '#C7BBA1',
  inkFaint: '#8E8570',

  terracotta: '#E8835A',
  terracottaDeep: '#F4A97E',
  terracottaSoft: '#3D2416',

  petrol: '#5BB3AE',
  petrolDeep: '#8ED2CC',
  petrolSoft: '#17302E',

  positive: '#80C094',
  positiveSoft: '#1C3024',
  warning: '#E0B567',
  warningSoft: '#352911',
  danger: '#E08C8C',
  dangerSoft: '#381C1C',

  border: '#372F22',
  borderStrong: '#4F4432',

  overlay: 'rgba(0, 0, 0, 0.65)',
} as const;

// Fraunces: a soft, characterful variable serif for headings -- editorial,
// warm, distinctive. IBM Plex Sans for UI/body text. IBM Plex Mono for
// money figures -- tabular numerals give financial data a "ledger" feel.
export const FONT = {
  display: 'Fraunces_600SemiBold',
  displayItalic: 'Fraunces_500Medium_Italic',
  body: 'IBMPlexSans_400Regular',
  bodyMedium: 'IBMPlexSans_500Medium',
  bodySemiBold: 'IBMPlexSans_600SemiBold',
  mono: 'IBMPlexMono_500Medium',
  monoBold: 'IBMPlexMono_600SemiBold',
} as const;

export const SPACE = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const RADIUS = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
} as const;

export const TYPE = {
  // Large brand lockup for one-off hero moments (splash) -- not used in
  // regular screen headings, which top out at `display`.
  hero: { fontFamily: FONT.display, fontSize: 46, lineHeight: 52 },
  display: { fontFamily: FONT.display, fontSize: 30, lineHeight: 36 },
  displayItalic: { fontFamily: FONT.displayItalic, fontSize: 30, lineHeight: 36 },
  h1: { fontFamily: FONT.display, fontSize: 24, lineHeight: 30 },
  h2: { fontFamily: FONT.display, fontSize: 19, lineHeight: 25 },
  body: { fontFamily: FONT.body, fontSize: 15, lineHeight: 22 },
  bodyMedium: { fontFamily: FONT.bodyMedium, fontSize: 15, lineHeight: 22 },
  caption: { fontFamily: FONT.body, fontSize: 13, lineHeight: 18 },
  label: { fontFamily: FONT.bodySemiBold, fontSize: 12, lineHeight: 16, letterSpacing: 0.6 },
  figure: { fontFamily: FONT.mono, fontSize: 15, lineHeight: 20 },
  figureLarge: { fontFamily: FONT.monoBold, fontSize: 28, lineHeight: 32 },
} as const;

// A record shape (string values), not `typeof COLOR`'s exact literals --
// DARK_COLOR has the same keys with different hex values, which a
// literal-typed alias would reject as "insufficiently overlapping".
export type Palette = Record<keyof typeof COLOR, string>;

/** Which palette key represents each AssetClass in charts (allocation
 * donut, exposure breakdowns). Kept here, not invented per-screen, so
 * every chart that shows asset classes uses the same five hues. This is a
 * chart legend, not a semantic "good/bad" claim -- every segment is always
 * paired with a text label, never color alone. */
export const ASSET_CLASS_COLOR_KEY = {
  cash: 'petrol',
  debt: 'warning',
  equity: 'terracotta',
  real_assets: 'positive',
  alternatives: 'danger',
} as const satisfies Record<string, keyof Palette>;

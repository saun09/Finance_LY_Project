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

export const DARK_COLOR = {
  paper: '#17140F',
  paperRaised: '#211C15',
  paperSunken: '#0F0D09',

  ink: '#F3ECDE',
  inkMuted: '#C4B9A2',
  inkFaint: '#8C8371',

  terracotta: '#E07A50',
  terracottaDeep: '#F0A17C',
  terracottaSoft: '#3A2419',

  petrol: '#5FA3A1',
  petrolDeep: '#8CC4C2',
  petrolSoft: '#1B2E2C',

  positive: '#7FAE8C',
  positiveSoft: '#1E2B22',
  warning: '#D9AC5C',
  warningSoft: '#332A17',
  danger: '#D98787',
  dangerSoft: '#341D1D',

  border: '#3A3226',
  borderStrong: '#4E4534',

  overlay: 'rgba(0, 0, 0, 0.6)',
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

export type Palette = typeof COLOR;

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

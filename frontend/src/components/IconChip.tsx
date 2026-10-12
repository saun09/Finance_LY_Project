import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS } from '../theme/tokens';

type Tone = 'positive' | 'warning' | 'danger' | 'petrol' | 'terracotta' | 'neutral';

interface Props {
  name: keyof typeof Ionicons.glyphMap;
  tone?: Tone;
  size?: number;
}

const SOFT_KEY: Record<Tone, string> = {
  positive: 'positiveSoft',
  warning: 'warningSoft',
  danger: 'dangerSoft',
  petrol: 'petrolSoft',
  terracotta: 'terracottaSoft',
  neutral: 'paperSunken',
};

const FG_KEY: Record<Tone, string> = {
  positive: 'positive',
  warning: 'warning',
  danger: 'danger',
  petrol: 'petrol',
  terracotta: 'terracotta',
  neutral: 'inkFaint',
};

/** A small colored circular icon badge -- the "what this row/card is about"
 * glyph used throughout the redesigned, lower-text-density screens (each
 * metric gets a chip instead of a sentence of description). Always a
 * palette soft/tone pair, never an arbitrary hex, so it stays inside the
 * app's existing warm "Ledger" palette rather than introducing new colors. */
export function IconChip({ name, tone = 'neutral', size = 36 }: Props) {
  const { colors } = useAppTheme();
  const bg = (colors as Record<string, string>)[SOFT_KEY[tone]];
  const fg = (colors as Record<string, string>)[FG_KEY[tone]];
  return (
    <View style={[styles.chip, { width: size, height: size, borderRadius: RADIUS.pill, backgroundColor: bg }]}>
      <Ionicons name={name} size={Math.round(size * 0.52)} color={fg} />
    </View>
  );
}

const styles = StyleSheet.create({
  chip: { alignItems: 'center', justifyContent: 'center' },
});

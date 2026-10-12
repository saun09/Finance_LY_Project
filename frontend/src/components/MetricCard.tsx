import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Card } from './Card';
import { IconChip } from './IconChip';
import { InfoTooltip } from './InfoTooltip';
import { Text } from './Text';

interface Props {
  label: string;
  value: string;
  tone?: 'positive' | 'warning' | 'danger' | 'neutral';
  helper?: string;
  /** Glyph shown in a small colored chip above the label -- the "what this
   * metric is" visual anchor, replacing a sentence of description. */
  icon?: keyof typeof Ionicons.glyphMap;
  /** When given, renders an info icon that opens a modal explaining what
   * this metric is and how it's calculated -- e.g. "Net worth = cash +
   * holdings - what you owe". Keeps the card itself free of paragraph
   * text while the explanation stays one tap away, never invented copy. */
  info?: { title: string; description: string };
}

const TONE_ICON: Record<NonNullable<Props['tone']>, string> = {
  positive: '●',
  warning: '●',
  danger: '●',
  neutral: '●',
};

/** Two metric cards share one row at typical phone widths, which leaves
 * little room for a long rupee figure (crores, negative values) at the
 * default 28px mono size -- it would wrap mid-number instead of shrinking.
 * Step the size down for longer strings rather than letting it wrap. */
function figureSizeStyle(value: string) {
  if (value.length > 12) return { fontSize: 18, lineHeight: 22 };
  if (value.length > 9) return { fontSize: 22, lineHeight: 26 };
  return undefined;
}

/** A single financial figure: icon chip, label, big figure, optional
 * helper line and info tooltip. Tone is still shown via both color AND a
 * labeled dot (never color alone), matching Section 31's "do not rely
 * solely on colour" rule. Money always renders in the monospace figure
 * type. */
export function MetricCard({ label, value, tone = 'neutral', helper, icon, info }: Props) {
  const { colors } = useAppTheme();
  const toneColor = tone === 'neutral' ? colors.inkFaint : colors[tone];
  const chipTone = tone === 'neutral' ? 'petrol' : tone;

  return (
    <Card style={styles.card}>
      <View style={styles.headerRow}>
        {icon ? <IconChip name={icon} tone={chipTone} size={34} /> : null}
        <View style={styles.headerRight}>
          {tone !== 'neutral' && <Text style={{ color: toneColor }}>{TONE_ICON[tone]}</Text>}
          {info ? <InfoTooltip title={info.title} description={info.description} /> : null}
        </View>
      </View>
      <Text variant="label" tone="muted" style={styles.label}>
        {label.toUpperCase()}
      </Text>
      <Text variant="figureLarge" numberOfLines={1} style={figureSizeStyle(value)}>
        {value}
      </Text>
      {helper ? (
        <Text variant="caption" tone="muted" style={styles.helper}>
          {helper}
        </Text>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { flex: 1, minWidth: 150, gap: SPACE.xs },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  label: { marginTop: SPACE.xs },
  helper: { marginTop: SPACE.xs },
});

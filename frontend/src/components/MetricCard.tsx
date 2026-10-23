import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { AnimatedFigure } from './AnimatedFigure';
import { Card } from './Card';
import { fitFigureStyle } from './fitFigure';
import { IconChip } from './IconChip';
import { InfoTooltip } from './InfoTooltip';
import { ProgressBar } from './ProgressBar';
import { Text } from './Text';

interface Props {
  label: string;
  /** A ready-made string ("Tier 3 of 5") -- used as-is, no animation.
   * Prefer `animated` instead whenever the underlying value is a plain
   * number (money, a percent, a count): it gets the app's signature
   * count-up motion for free. Exactly one of `value`/`animated` is used. */
  value?: string;
  animated?: { target: number; formatter: (n: number) => string };
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
  /** 0-1. When given, renders a thin progress track under the figure --
   * the exact same fraction as the displayed value, never a separate or
   * rescaled number. */
  progressFraction?: number;
}

const TONE_ICON: Record<NonNullable<Props['tone']>, string> = {
  positive: '●',
  warning: '●',
  danger: '●',
  neutral: '●',
};

/** A single financial figure: icon chip, label, big figure, optional
 * helper line and info tooltip. Tone is still shown via both color AND a
 * labeled dot (never color alone), matching Section 31's "do not rely
 * solely on colour" rule. Money always renders in the monospace figure
 * type. */
export function MetricCard({ label, value, animated, tone = 'neutral', helper, icon, info, progressFraction }: Props) {
  const { colors } = useAppTheme();
  const toneColor = tone === 'neutral' ? colors.inkFaint : colors[tone];
  const chipTone = tone === 'neutral' ? 'petrol' : tone;
  // Two cards share a row on a phone, so a long figure (crores, a negative
  // net worth) is shrunk to the width actually available -- never wrapped
  // mid-number, never cut off with "…". AnimatedFigure does the same.
  const [figureWidth, setFigureWidth] = useState(0);
  const fitStyle = fitFigureStyle(value ?? '', figureWidth, 'figureLarge');

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
      {animated ? (
        <AnimatedFigure target={animated.target} formatter={animated.formatter} />
      ) : (
        <View onLayout={(e) => setFigureWidth(e.nativeEvent.layout.width)}>
          <Text variant="figureLarge" numberOfLines={1} style={fitStyle}>
            {value}
          </Text>
        </View>
      )}
      {progressFraction !== undefined ? (
        <View style={styles.progressWrap}>
          <ProgressBar fraction={progressFraction} tone={chipTone} duration={900} />
        </View>
      ) : null}
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
  progressWrap: { marginTop: SPACE.xs },
  helper: { marginTop: SPACE.xs },
});

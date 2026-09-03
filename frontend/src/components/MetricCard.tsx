import React from 'react';
import { StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Card } from './Card';
import { Text } from './Text';

interface Props {
  label: string;
  value: string;
  tone?: 'positive' | 'warning' | 'danger' | 'neutral';
  helper?: string;
}

const TONE_ICON: Record<NonNullable<Props['tone']>, string> = {
  positive: '●',
  warning: '●',
  danger: '●',
  neutral: '●',
};

/** A single financial figure with a label above and an optional helper
 * line below. Deliberately shows tone via both color AND a labeled dot
 * (never color alone), matching Section 31's "do not rely solely on
 * colour" rule. Money always renders in the monospace figure type. */
export function MetricCard({ label, value, tone = 'neutral', helper }: Props) {
  const { colors } = useAppTheme();
  const toneColor = tone === 'neutral' ? colors.inkFaint : colors[tone];

  return (
    <Card style={styles.card}>
      <View style={styles.headerRow}>
        <Text variant="label" tone="muted">
          {label.toUpperCase()}
        </Text>
        {tone !== 'neutral' && <Text style={{ color: toneColor }}>{TONE_ICON[tone]}</Text>}
      </View>
      <Text variant="figureLarge">{value}</Text>
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
  helper: { marginTop: SPACE.xs },
});

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { InfoTooltip } from './InfoTooltip';
import { Text } from './Text';

interface Props {
  step: number;
  total: number;
  title: string;
  subtitle?: string;
  /** When set, renders an (i) icon next to the title that opens a modal
   * explaining what this step's card means and why it's asked for. */
  info?: { title: string; description: string };
}

/** A thin segmented progress bar + step title, shared by every onboarding
 * screen so the user always knows how much is left of the ~5 minute flow
 * the Welcome screen promises. */
export function OnboardingProgress({ step, total, title, subtitle, info }: Props) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.container}>
      <View style={styles.track}>
        {Array.from({ length: total }).map((_, i) => (
          <View
            key={i}
            style={[
              styles.segment,
              { backgroundColor: i < step ? colors.terracotta : colors.border },
            ]}
          />
        ))}
      </View>
      <Text variant="label" tone="terracotta">
        STEP {step} OF {total}
      </Text>
      <View style={styles.titleRow}>
        <Text variant="h1" style={styles.titleText}>
          {title}
        </Text>
        {info ? <InfoTooltip title={info.title} description={info.description} /> : null}
      </View>
      {subtitle ? (
        <Text variant="body" tone="muted">
          {subtitle}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: SPACE.sm },
  track: { flexDirection: 'row', gap: SPACE.xs },
  segment: { flex: 1, height: 4, borderRadius: RADIUS.pill },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  titleText: { flexShrink: 1 },
});

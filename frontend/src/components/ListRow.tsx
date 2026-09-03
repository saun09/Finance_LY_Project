import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

interface Props {
  title: string;
  subtitle?: string;
  trailing?: string;
  onRemove?: () => void;
  removing?: boolean;
}

/** A compact row for an already-submitted onboarding item (an EMI, a
 * holding, an expense...) with an optional remove action. Used in the
 * "items you've added" list under each onboarding entry form. */
export function ListRow({ title, subtitle, trailing, onRemove, removing }: Props) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.row, { borderColor: colors.border }]}>
      <View style={styles.textCol}>
        <Text variant="bodyMedium">{title}</Text>
        {subtitle ? (
          <Text variant="caption" tone="faint">
            {subtitle}
          </Text>
        ) : null}
      </View>
      {trailing ? (
        <Text variant="figure" tone="ink">
          {trailing}
        </Text>
      ) : null}
      {onRemove ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Remove ${title}`}
          onPress={onRemove}
          disabled={removing}
          hitSlop={8}
          style={styles.removeButton}
        >
          <Text variant="bodyMedium" tone="danger">
            {removing ? '…' : '✕'}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.md,
    paddingVertical: SPACE.md,
    borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
  },
  textCol: { flex: 1, gap: 2 },
  removeButton: { paddingHorizontal: SPACE.xs, paddingVertical: SPACE.xs },
});

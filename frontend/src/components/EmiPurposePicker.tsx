import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import type { EmiPurpose } from '../api/types';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';
import { Text } from './Text';

const EMI_PURPOSE_OPTIONS: { value: EmiPurpose; label: string }[] = [
  { value: 'home', label: 'Home' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'personal', label: 'Personal' },
  { value: 'education', label: 'Education' },
  { value: 'credit_card', label: 'Credit card' },
  { value: 'electronics', label: 'Phone / Electronics' },
  { value: 'other', label: 'Other' },
];

export const EMI_PURPOSE_LABEL: Record<EmiPurpose, string> = Object.fromEntries(
  EMI_PURPOSE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<EmiPurpose, string>;

interface Props {
  value: EmiPurpose | null;
  onChange: (value: EmiPurpose | null) => void;
}

/** What the loan is for -- optional (nullable server-side), same
 * "not sure"-toggles-to-null pattern as HoldingTypePicker. */
export function EmiPurposePicker({ value, onChange }: Props) {
  const { colors } = useAppTheme();
  const skip = value === null;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text variant="label" tone="muted">
          WHAT IS THIS FOR?
        </Text>
        <Pressable onPress={() => onChange(null)} hitSlop={8}>
          <Text variant="caption" tone={skip ? 'terracotta' : 'faint'}>
            {skip ? '✓ Not sure' : "I'm not sure"}
          </Text>
        </Pressable>
      </View>
      <View style={styles.chipWrap}>
        {EMI_PURPOSE_OPTIONS.map((opt) => {
          const selected = opt.value === value;
          return (
            <Pressable
              key={opt.value}
              onPress={() => onChange(opt.value)}
              style={[
                styles.chip,
                { backgroundColor: selected ? colors.terracotta : colors.paper, borderColor: selected ? colors.terracotta : colors.border },
              ]}
            >
              <Text variant="caption" tone={selected ? 'onDark' : 'ink'}>
                {opt.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: SPACE.sm },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.xs },
  chip: {
    paddingHorizontal: SPACE.md,
    paddingVertical: SPACE.xs + 2,
    borderRadius: RADIUS.pill,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
});

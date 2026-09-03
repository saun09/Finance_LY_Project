import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

export interface ChoiceOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  label: string;
  options: ChoiceOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
}

/** A single-select group of chips for a str-Enum field (income stability,
 * employment type, insurance type, holding type...) -- deliberately not a
 * native <Picker>/dropdown, since most of these enums have few enough
 * options that seeing them all at once is clearer than hiding them. */
export function ChoiceGroup<T extends string>({ label, options, value, onChange }: Props<T>) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      <Text variant="label" tone="muted">
        {label.toUpperCase()}
      </Text>
      <View style={styles.wrap}>
        {options.map((opt) => {
          const selected = opt.value === value;
          return (
            <Pressable
              key={opt.value}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => onChange(opt.value)}
              style={[
                styles.chip,
                {
                  backgroundColor: selected ? colors.terracotta : colors.paper,
                  borderColor: selected ? colors.terracotta : colors.border,
                },
              ]}
            >
              <Text variant="bodyMedium" tone={selected ? 'onDark' : 'ink'}>
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
  container: { gap: SPACE.xs },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.sm },
  chip: {
    paddingHorizontal: SPACE.lg,
    paddingVertical: SPACE.sm,
    borderRadius: RADIUS.pill,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
});

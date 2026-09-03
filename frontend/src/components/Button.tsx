import React from 'react';
import { ActivityIndicator, GestureResponderEvent, Pressable, StyleSheet } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

interface Props {
  label: string;
  onPress?: (e: GestureResponderEvent) => void;
  variant?: 'primary' | 'secondary' | 'ghost';
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
}

export function Button({ label, onPress, variant = 'primary', disabled, loading, fullWidth }: Props) {
  const { colors } = useAppTheme();
  const isDisabled = disabled || loading;

  const bg = { primary: colors.terracotta, secondary: colors.petrolSoft, ghost: 'transparent' }[variant];
  const textTone = variant === 'primary' ? 'onDark' : variant === 'secondary' ? 'petrol' : 'terracotta';
  const border = variant === 'ghost' ? colors.borderStrong : 'transparent';

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled }}
      onPress={isDisabled ? undefined : onPress}
      style={({ pressed }) => [
        styles.base,
        { backgroundColor: bg, borderColor: border, opacity: isDisabled ? 0.55 : pressed ? 0.85 : 1 },
        fullWidth && styles.fullWidth,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? colors.paper : colors.terracotta} />
      ) : (
        <Text variant="bodyMedium" tone={textTone as any}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 52,
    paddingHorizontal: SPACE.xl,
    borderRadius: RADIUS.pill,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  fullWidth: {
    alignSelf: 'stretch',
  },
});

import React, { useRef } from 'react';
import { Animated, ActivityIndicator, GestureResponderEvent, Pressable, StyleSheet } from 'react-native';
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
  const scale = useRef(new Animated.Value(1)).current;

  const bg = { primary: colors.terracotta, secondary: colors.petrolSoft, ghost: 'transparent' }[variant];
  const textTone = variant === 'primary' ? 'onDark' : variant === 'secondary' ? 'petrol' : 'terracotta';
  const border = variant === 'ghost' ? colors.borderStrong : 'transparent';

  const pressIn = () => Animated.spring(scale, { toValue: 0.97, useNativeDriver: true, speed: 50, bounciness: 0 }).start();
  const pressOut = () => Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 30, bounciness: 6 }).start();

  return (
    <Animated.View style={[{ transform: [{ scale }] }, fullWidth && styles.fullWidth]}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled: isDisabled }}
        onPress={isDisabled ? undefined : onPress}
        onPressIn={pressIn}
        onPressOut={pressOut}
        style={(state) => {
          // react-native-web adds `focused` to this callback's state on
          // top of core RN's `pressed` -- not in the upstream type, read
          // defensively (same approach as MenuList).
          const focused = (state as { focused?: boolean }).focused;
          return [
            styles.base,
            {
              backgroundColor: bg,
              // `ink` (near-white in this dark theme) rather than a brand
              // accent -- the primary variant's own background IS
              // terracotta, so a terracotta ring would be invisible
              // exactly where focus visibility matters most.
              borderColor: focused && !isDisabled ? colors.ink : border,
              opacity: isDisabled ? 0.55 : state.pressed ? 0.85 : 1,
            },
            fullWidth && styles.fullWidth,
          ];
        }}
      >
        {loading ? (
          <ActivityIndicator color={variant === 'primary' ? colors.paper : colors.terracotta} />
        ) : (
          <Text variant="bodyMedium" tone={textTone as any}>
            {label}
          </Text>
        )}
      </Pressable>
    </Animated.View>
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

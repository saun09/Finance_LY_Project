import { Ionicons } from '@expo/vector-icons';
import React, { useRef } from 'react';
import { Animated, Pressable, StyleSheet } from 'react-native';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';
import { Text } from './Text';

interface Props {
  label: string;
  onPress: () => void;
}

/** A pill-shaped "+ Add X" button, anchored over scrolling content via
 * ScreenContainer's `floatingAction` slot -- opens a FormSheet instead of
 * an inline form living at the bottom of a list. Same press-scale spring
 * as Button, so every "something is about to happen" tap in the app
 * feels like the same spring. */
export function FloatingActionButton({ label, onPress }: Props) {
  const { colors } = useAppTheme();
  const reducedMotion = useReducedMotion();
  const scale = useRef(new Animated.Value(1)).current;

  const pressIn = () => {
    if (reducedMotion) return;
    Animated.spring(scale, { toValue: 0.96, useNativeDriver: true, speed: 50, bounciness: 0 }).start();
  };
  const pressOut = () => {
    if (reducedMotion) return;
    Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 30, bounciness: 6 }).start();
  };

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <Pressable
        onPress={onPress}
        onPressIn={pressIn}
        onPressOut={pressOut}
        accessibilityRole="button"
        accessibilityLabel={label}
        style={[styles.button, { backgroundColor: colors.terracotta }]}
      >
        <Ionicons name="add" size={18} color={colors.paper} />
        <Text variant="bodyMedium" tone="onDark">
          {label}
        </Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.xs,
    paddingHorizontal: SPACE.lg,
    paddingVertical: SPACE.sm + 2,
    borderRadius: RADIUS.pill,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 6,
  },
});

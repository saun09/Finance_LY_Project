import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { useAppTheme } from '../theme/ThemeContext';
import type { Palette } from '../theme/tokens';

interface Props {
  /** 0-1. Clamped defensively, but the caller is responsible for it being
   * a real ratio (e.g. final_tier/5, or the EMI-to-income ratio already
   * shown as text) -- this component never invents or rescales a value,
   * only renders whatever fraction it's given. */
  fraction: number;
  tone?: keyof Palette;
  duration?: number;
  height?: number;
}

/** A single filled track animating from 0 to `fraction` on mount (JS-
 * driven: width isn't native-driver-safe). Used for the Plan page's tier
 * indicator and the EMI-to-income ratio -- the same primitive for both,
 * so "a bar filling in" always means the same thing across the app.
 * Reduce-motion jumps straight to the final width. */
export function ProgressBar({ fraction, tone = 'petrol', duration = 700, height = 8 }: Props) {
  const { colors } = useAppTheme();
  const anim = useRef(new Animated.Value(0)).current;
  const reducedMotion = useReducedMotion();
  const clamped = Math.max(0, Math.min(1, fraction));

  useEffect(() => {
    if (reducedMotion) {
      anim.setValue(clamped);
      return;
    }
    anim.setValue(0);
    const animation = Animated.timing(anim, { toValue: clamped, duration, useNativeDriver: false });
    animation.start();
    return () => animation.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clamped, duration, reducedMotion]);

  const width = anim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });

  return (
    <View style={[styles.track, { height, borderRadius: height / 2, backgroundColor: colors.paperSunken }]}>
      <Animated.View style={[styles.fill, { height, borderRadius: height / 2, width, backgroundColor: colors[tone] }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: { overflow: 'hidden', width: '100%' },
  fill: {},
});

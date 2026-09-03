import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View, ViewStyle } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';

interface Props {
  width?: number | `${number}%`;
  height?: number;
  style?: ViewStyle;
}

/** A single pulsing placeholder block. Compose several to build a
 * screen's skeleton (see SkeletonCard below) -- never show stale/demo
 * data while loading (Section 19). */
export function Skeleton({ width = '100%', height = 16, style }: Props) {
  const { colors } = useAppTheme();
  const pulse = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.4, duration: 700, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [pulse]);

  return (
    <Animated.View
      style={[
        { width, height, backgroundColor: colors.borderStrong, borderRadius: RADIUS.sm, opacity: pulse },
        style,
      ]}
    />
  );
}

export function SkeletonCard() {
  return (
    <View style={styles.card}>
      <Skeleton width="40%" height={12} />
      <Skeleton width="70%" height={26} style={styles.spacedTop} />
      <Skeleton width="55%" height={12} style={styles.spacedTop} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: SPACE.lg, gap: SPACE.sm },
  spacedTop: { marginTop: SPACE.xs },
});

import React, { useEffect, useRef } from 'react';
import { Animated } from 'react-native';
import { useReducedMotion } from '../hooks/useReducedMotion';

interface Props {
  index?: number;
  children: React.ReactNode;
}

/** Wraps a card/section in a brief, staggered fade + rise on mount. Uses
 * core RN `Animated` (no reanimated/moti dependency) -- a small, tasteful
 * entrance rather than a gimmick: ~300ms, ~100ms stagger per index, native
 * driver on (opacity/translateY are both native-driver-safe). Re-mounts
 * (e.g. a screen re-focus) replay it, which is fine for a dashboard users
 * land on repeatedly. The `useEffect`'s only deps are `progress` (a ref,
 * stable identity) and `index` (stable per position), so a parent
 * re-render with the same index never restarts the animation -- it only
 * (re)plays on mount or if this instance's index genuinely changes. When
 * the OS/browser has reduce-motion on, content appears at its final
 * opacity/position immediately instead. */
export function Reveal({ index = 0, children }: Props) {
  const progress = useRef(new Animated.Value(0)).current;
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion) {
      progress.setValue(1);
      return;
    }
    Animated.timing(progress, {
      toValue: 1,
      duration: 300,
      delay: Math.min(index, 6) * 100,
      useNativeDriver: true,
    }).start();
  }, [progress, index, reducedMotion]);

  return (
    <Animated.View
      style={{
        opacity: progress,
        transform: [
          {
            translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }),
          },
        ],
      }}
    >
      {children}
    </Animated.View>
  );
}

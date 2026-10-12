import React, { useEffect, useRef } from 'react';
import { Animated } from 'react-native';

interface Props {
  index?: number;
  children: React.ReactNode;
}

/** Wraps a card/section in a brief, staggered fade + rise on mount. Uses
 * core RN `Animated` (no reanimated/moti dependency) -- a small, tasteful
 * entrance rather than a gimmick: ~220ms, ~40ms stagger per index, native
 * driver on. Re-mounts (e.g. a screen re-focus) replay it, which is fine
 * for a dashboard users land on repeatedly. */
export function Reveal({ index = 0, children }: Props) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(progress, {
      toValue: 1,
      duration: 260,
      delay: Math.min(index, 6) * 45,
      useNativeDriver: true,
    }).start();
  }, [progress, index]);

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

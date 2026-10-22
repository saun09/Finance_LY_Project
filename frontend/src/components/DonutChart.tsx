import React, { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import Svg, { Circle, G } from 'react-native-svg';
import { useReducedMotion } from '../hooks/useReducedMotion';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export interface DonutSegment {
  key: string;
  pct: number;
  color: string;
}

interface Props {
  segments: DonutSegment[];
  size?: number;
  strokeWidth?: number;
  trackColor: string;
  /** ~700-900ms reads as a deliberate reveal without feeling slow; also
   * the duration of the re-draw whenever `segments` itself changes (e.g.
   * swapping in a different dataset), not just on first mount. */
  duration?: number;
}

/** A ring chart built from stacked SVG stroke-dasharray circles -- one
 * <Circle> per segment, each offset to start where the previous ended.
 * Simpler and lighter than a path-arc approach for a single ring, and
 * react-native-svg is already a project dependency.
 *
 * Each segment's dasharray is fixed (its true final arc length); what
 * animates is only `strokeDashoffset`, sliding from "fully retracted"
 * (offset shifted forward by exactly the segment's own length, so none of
 * it is visible yet) down to its true offset -- the standard SVG
 * stroke-dashoffset "draw-on" technique, which keeps every segment
 * anchored at its correct starting angle throughout instead of animating
 * segments sliding past each other. */
export function DonutChart({ segments, size = 180, strokeWidth = 24, trackColor, duration = 800 }: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;
  const reducedMotion = useReducedMotion();
  const progress = useRef(new Animated.Value(reducedMotion ? 1 : 0)).current;

  let cumulativePct = 0;
  const withOffsets = segments
    .filter((s) => s.pct > 0)
    .map((s) => {
      const offsetPct = cumulativePct;
      cumulativePct += s.pct;
      return { ...s, offsetPct };
    });

  // Re-draws from 0 whenever the actual data changes (not on every
  // unrelated re-render), so swapping in a different segment set animates
  // the same way a first mount does.
  const dataKey = withOffsets.map((s) => `${s.key}:${s.pct}:${s.offsetPct}`).join('|');
  useEffect(() => {
    if (reducedMotion) {
      progress.setValue(1);
      return;
    }
    progress.setValue(0);
    const anim = Animated.timing(progress, { toValue: 1, duration, useNativeDriver: false });
    anim.start();
    return () => anim.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey, duration, reducedMotion]);

  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size}>
        <G rotation={-90} originX={center} originY={center}>
          <Circle
            cx={center}
            cy={center}
            r={radius}
            stroke={trackColor}
            strokeWidth={strokeWidth}
            fill="none"
          />
          {withOffsets.map((s) => {
            const dash = (s.pct / 100) * circumference;
            const finalOffset = -((s.offsetPct / 100) * circumference);
            const animatedOffset = progress.interpolate({
              inputRange: [0, 1],
              outputRange: [finalOffset + dash, finalOffset],
            });
            return (
              <AnimatedCircle
                key={s.key}
                cx={center}
                cy={center}
                r={radius}
                stroke={s.color}
                strokeWidth={strokeWidth}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={animatedOffset}
                strokeLinecap="butt"
                fill="none"
              />
            );
          })}
        </G>
      </Svg>
    </View>
  );
}

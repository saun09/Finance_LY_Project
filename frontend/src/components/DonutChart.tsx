import React from 'react';
import { View } from 'react-native';
import Svg, { Circle, G } from 'react-native-svg';

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
}

/** A ring chart built from stacked SVG stroke-dasharray circles -- one
 * <Circle> per segment, each offset to start where the previous ended.
 * Simpler and lighter than a path-arc approach for a single ring, and
 * react-native-svg is already a project dependency. */
export function DonutChart({ segments, size = 180, strokeWidth = 24, trackColor }: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let cumulativePct = 0;
  const withOffsets = segments
    .filter((s) => s.pct > 0)
    .map((s) => {
      const offsetPct = cumulativePct;
      cumulativePct += s.pct;
      return { ...s, offsetPct };
    });

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
            return (
              <Circle
                key={s.key}
                cx={center}
                cy={center}
                r={radius}
                stroke={s.color}
                strokeWidth={strokeWidth}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-((s.offsetPct / 100) * circumference)}
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

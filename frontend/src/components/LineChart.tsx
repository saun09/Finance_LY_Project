import React, { useState } from 'react';
import { LayoutChangeEvent, StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';
import { useAppTheme } from '../theme/ThemeContext';
import { SPACE } from '../theme/tokens';
import { Text } from './Text';

export interface ChartPoint {
  label: string;
  value: number;
}

interface Props {
  points: ChartPoint[];
  formatValue: (value: number) => string;
  height?: number;
}

/** A hand-rolled SVG line chart (react-native-svg is already a dependency
 * for icon-free assets elsewhere -- no charting library needed for a
 * single series). Renders a filled area under a straight-segment line,
 * with the first/last values and their labels called out directly rather
 * than a dense tick-axis, matching the app's editorial, low-chrome style. */
export function LineChart({ points, formatValue, height = 140 }: Props) {
  const { colors } = useAppTheme();
  const [width, setWidth] = useState(0);

  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);

  if (points.length < 2 || width === 0) {
    return <View style={{ height }} onLayout={onLayout} />;
  }

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const padTop = 12;
  const padBottom = 12;
  const plotHeight = height - padTop - padBottom;

  const stepX = width / (points.length - 1);
  const coords = points.map((p, i) => {
    const x = i * stepX;
    const y = padTop + plotHeight - ((p.value - min) / span) * plotHeight;
    return { x, y };
  });

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ');
  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${height} L ${coords[0].x} ${height} Z`;

  const first = points[0];
  const last = points[points.length - 1];
  const trendPositive = last.value >= first.value;

  return (
    <View>
      <View style={styles.headerRow}>
        <Text variant="caption" tone="faint">
          {first.label}
        </Text>
        <Text variant="figure" tone={trendPositive ? 'positive' : 'danger'}>
          {formatValue(last.value)}
        </Text>
        <Text variant="caption" tone="faint">
          {last.label}
        </Text>
      </View>
      <View onLayout={onLayout} style={{ height }}>
        <Svg width={width} height={height}>
          <Defs>
            <LinearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.terracotta} stopOpacity={0.22} />
              <Stop offset="1" stopColor={colors.terracotta} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Line x1={0} y1={height - padBottom} x2={width} y2={height - padBottom} stroke={colors.border} strokeWidth={1} />
          <Path d={areaPath} fill="url(#areaFill)" />
          <Path d={linePath} fill="none" stroke={colors.terracotta} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
          {coords.map((c, i) => (
            <Circle
              key={i}
              cx={c.x}
              cy={c.y}
              r={i === coords.length - 1 ? 4 : 2.5}
              fill={i === coords.length - 1 ? colors.terracotta : colors.paperRaised}
              stroke={colors.terracotta}
              strokeWidth={1.5}
            />
          ))}
        </Svg>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: SPACE.sm },
});

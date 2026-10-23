import React from 'react';
import { StyleSheet, View, ViewProps } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';

interface CardProps extends ViewProps {
  raised?: boolean;
  padded?: boolean;
}

/** The base surface for nearly every screen: a flat, tonally-distinct
 * panel with a delicate hairline border -- elevation comes from the
 * color step between `paper` (the screen) and `paperRaised` (the card),
 * not from a shadow or a gradient. A drop shadow barely reads against a
 * dark ground and a gradient reads as a "glow", which this app's premium
 * identity is deliberately restrained rather than showy -- subtle tonal
 * depth, not a visual effect calling attention to itself. Light mode
 * keeps a soft, low, warm-toned shadow since it has a plain white-ish
 * ground to cast it on. */
export function Card({ raised, padded = true, style, children, ...rest }: CardProps) {
  const { colors, dark } = useAppTheme();
  return (
    <View
      style={[
        styles.base,
        { backgroundColor: colors.paperRaised, borderColor: raised ? colors.borderStrong : colors.border },
        !dark && styles.shadow,
        raised && !dark && styles.shadowStrong,
        padded && styles.padded,
        style,
      ]}
      {...rest}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: RADIUS.lg,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  padded: {
    padding: SPACE.lg,
  },
  shadow: {
    shadowColor: '#3A2E1A',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 14,
    elevation: 2,
  },
  shadowStrong: {
    shadowOpacity: 0.14,
    shadowRadius: 20,
    elevation: 4,
  },
});

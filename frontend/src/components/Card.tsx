import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import { StyleSheet, View, ViewProps } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';

interface CardProps extends ViewProps {
  raised?: boolean;
  padded?: boolean;
}

/** The base surface for nearly every screen. In light mode: a warm paper
 * card with a soft, low, warm-toned shadow. In dark mode -- the app's
 * actual default now -- a drop shadow doesn't read against a dark
 * ground, so elevation instead comes from a subtle top-lit gradient
 * (cardGradientTop -> paperRaised) plus a faint top-edge highlight line,
 * the "soft embossed light" a premium dark card needs. */
export function Card({ raised, padded = true, style, children, ...rest }: CardProps) {
  const { colors, dark } = useAppTheme();
  // Several screens tint a Card for a semantic callout (warningSoft,
  // positiveSoft, etc.) by passing backgroundColor through `style`. That
  // flat tint is the whole point of those cards -- blending it with the
  // premium gradient below would muddy the signal, so an explicit
  // override always wins and skips the gradient entirely.
  const explicitBg = (StyleSheet.flatten(style) as { backgroundColor?: string } | undefined)?.backgroundColor;

  if (dark && !explicitBg) {
    return (
      <LinearGradient
        colors={[colors.cardGradientTop, colors.paperRaised]}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
        style={[
          styles.base,
          { borderColor: raised ? colors.borderStrong : colors.border },
          padded && styles.padded,
          style,
        ]}
        {...rest}
      >
        <View style={[styles.highlightLine, { backgroundColor: colors.cardHighlight }]} pointerEvents="none" />
        {children}
      </LinearGradient>
    );
  }

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
    overflow: 'hidden',
  },
  highlightLine: {
    position: 'absolute',
    top: 0,
    left: SPACE.lg,
    right: SPACE.lg,
    height: StyleSheet.hairlineWidth * 2,
    zIndex: 1,
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

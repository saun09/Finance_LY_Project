import React, { useEffect, useRef, useState } from 'react';
import { Animated } from 'react-native';
import { useReducedMotion } from '../hooks/useReducedMotion';
import type { TYPE } from '../theme/tokens';
import { Text } from './Text';

interface Props {
  target: number;
  formatter: (n: number) => string;
  duration?: number;
  variant?: keyof typeof TYPE;
  tone?: React.ComponentProps<typeof Text>['tone'];
  style?: React.ComponentProps<typeof Text>['style'];
}

/** The app's signature motion: a figure fades + scales in (~450ms, native
 * driver) while counting up from 0 to its real value (700-900ms, JS-
 * driven since it animates displayed text) -- through the same formatter
 * the static value would use (formatPaise, formatPercent, ...), so
 * "-₹37,000" is reached by animating the underlying number, not any
 * string trickery. Both run once per mount/target-change: the effect's
 * deps are `target`/`duration`/`reducedMotion` only, so a parent
 * re-render with the same target never restarts it. Reduce-motion skips
 * straight to the final value and full opacity/scale -- the number is
 * still always correct, just not animated getting there. */
export function AnimatedFigure({ target, formatter, duration = 900, variant = 'figureLarge', tone, style }: Props) {
  const countAnim = useRef(new Animated.Value(0)).current;
  const entrance = useRef(new Animated.Value(0)).current;
  const [display, setDisplay] = useState(0);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion) {
      countAnim.setValue(target);
      setDisplay(target);
      entrance.setValue(1);
      return;
    }

    countAnim.setValue(0);
    entrance.setValue(0);
    const id = countAnim.addListener(({ value }) => setDisplay(value));
    const countUp = Animated.timing(countAnim, { toValue: target, duration, useNativeDriver: false });
    const fadeScale = Animated.timing(entrance, { toValue: 1, duration: 450, useNativeDriver: true });
    Animated.parallel([countUp, fadeScale]).start();

    return () => {
      countAnim.removeListener(id);
      countUp.stop();
      fadeScale.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration, reducedMotion]);

  return (
    <Animated.View
      style={{
        opacity: entrance,
        transform: [{ scale: entrance.interpolate({ inputRange: [0, 1], outputRange: [0.92, 1] }) }],
      }}
    >
      <Text variant={variant} tone={tone} numberOfLines={1} style={style}>
        {formatter(display)}
      </Text>
    </Animated.View>
  );
}

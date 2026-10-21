import React, { useEffect, useRef, useState } from 'react';
import { Animated } from 'react-native';
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

/** The app's signature motion: a figure counts up from 0 to its real
 * value on mount/update, through the same formatter the static value
 * would use (formatPaise, formatPercent, ...) -- so "-₹37,000" is reached
 * by animating the underlying number, not by any string trickery. This is
 * deliberately the one place motion carries meaning on its own: a number
 * landing on its final value *is* the emphasis, which is the point of
 * leaning on animation instead of more on-screen text. `useNativeDriver`
 * is off because this drives displayed text, not a transform/opacity. */
export function AnimatedFigure({ target, formatter, duration = 900, variant = 'figureLarge', tone, style }: Props) {
  const anim = useRef(new Animated.Value(0)).current;
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    anim.setValue(0);
    const id = anim.addListener(({ value }) => setDisplay(value));
    const animation = Animated.timing(anim, {
      toValue: target,
      duration,
      useNativeDriver: false,
    });
    animation.start();
    return () => {
      anim.removeListener(id);
      animation.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration]);

  return (
    <Text variant={variant} tone={tone} numberOfLines={1} style={style}>
      {formatter(display)}
    </Text>
  );
}

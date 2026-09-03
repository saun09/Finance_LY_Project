import React from 'react';
import { Text as RNText, TextProps } from 'react-native';
import { TYPE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';

type Variant = keyof typeof TYPE;
type Tone = 'ink' | 'muted' | 'faint' | 'terracotta' | 'petrol' | 'positive' | 'warning' | 'danger' | 'onDark';

interface Props extends TextProps {
  variant?: Variant;
  tone?: Tone;
}

/** Every piece of text in the app should go through this component so
 * typography (Fraunces for display, IBM Plex for everything else) and
 * color stay centralized -- no ad hoc fontFamily/fontSize in screens. */
export function Text({ variant = 'body', tone = 'ink', style, children, ...rest }: Props) {
  const { colors } = useAppTheme();
  const toneColor: Record<Tone, string> = {
    ink: colors.ink,
    muted: colors.inkMuted,
    faint: colors.inkFaint,
    terracotta: colors.terracotta,
    petrol: colors.petrol,
    positive: colors.positive,
    warning: colors.warning,
    danger: colors.danger,
    onDark: colors.paper,
  };
  return (
    <RNText style={[TYPE[variant], { color: toneColor[tone] }, style]} {...rest}>
      {children}
    </RNText>
  );
}

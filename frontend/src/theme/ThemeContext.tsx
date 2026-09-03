import React, { createContext, useContext, useMemo } from 'react';
import { useColorScheme } from 'react-native';
import { COLOR, DARK_COLOR, Palette } from './tokens';

const ThemeCtx = createContext<{ colors: Palette; dark: boolean }>({ colors: COLOR, dark: false });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const scheme = useColorScheme();
  const dark = scheme === 'dark';
  const value = useMemo(() => ({ colors: (dark ? DARK_COLOR : COLOR) as Palette, dark }), [dark]);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export function useAppTheme() {
  return useContext(ThemeCtx);
}

import React, { createContext, useContext, useMemo } from 'react';
import { DARK_COLOR, Palette } from './tokens';

const ThemeCtx = createContext<{ colors: Palette; dark: boolean }>({ colors: DARK_COLOR as Palette, dark: true });

/** The warm-dark palette is the app's actual brand identity now (the
 * "premium, calm, warm-dark fintech" restyle), not a system-preference
 * fallback -- forced on regardless of OS theme, same as a dark-first
 * fintech app (Cash App, Revolut) would do. The light palette in
 * tokens.ts is kept, not deleted, in case a future settings toggle wants
 * it back; nothing currently reads `useColorScheme()`. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const dark = true;
  const value = useMemo(() => ({ colors: DARK_COLOR as Palette, dark }), []);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export function useAppTheme() {
  return useContext(ThemeCtx);
}

import { QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { queryClient } from './src/api/queryClient';
import { DemoUserProvider } from './src/context/DemoUserContext';
import { OnboardingStatusProvider } from './src/context/OnboardingStatusContext';
import { RootNavigator } from './src/navigation/RootNavigator';
import { ThemeProvider, useAppTheme } from './src/theme/ThemeContext';
import { useAppFonts } from './src/theme/useAppFonts';

/**
 * Font loading uses expo-font's `useFonts` hook (via @expo-google-fonts
 * packages) rather than SDK 57's newer build-time config-plugin approach.
 * That's a deliberate tradeoff: the config plugin requires local font
 * files + `expo prebuild` (leaving the managed workflow, needing a native
 * Android/iOS build), while `useFonts` works directly in Expo Go --
 * simpler to demo from a phone with no native build step, which matters
 * more here than shaving the font-loading flash on first launch.
 */
function AppShell() {
  const fontsLoaded = useAppFonts();
  const { colors, dark } = useAppTheme();

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.paper }}>
        <ActivityIndicator color={colors.terracotta} />
      </View>
    );
  }

  return (
    <>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <RootNavigator />
    </>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <DemoUserProvider>
            <OnboardingStatusProvider>
              <AppShell />
            </OnboardingStatusProvider>
          </DemoUserProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

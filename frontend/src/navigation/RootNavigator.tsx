import { NavigationContainer, DarkTheme, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { AuthStack } from './AuthStack';
import { OnboardingStack } from './OnboardingStack';
import { MainTabs } from './MainTabs';
import type { RootStackParamList } from './types';
import { useDemoUser } from '../context/DemoUserContext';
import { useOnboardingStatus } from '../context/OnboardingStatusContext';
import { useAppTheme } from '../theme/ThemeContext';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const { isAuthenticated, ready: authReady } = useDemoUser();
  const { completed, loading: onboardingLoading } = useOnboardingStatus();
  const { colors, dark } = useAppTheme();

  const navTheme = {
    ...(dark ? DarkTheme : DefaultTheme),
    colors: {
      ...(dark ? DarkTheme.colors : DefaultTheme.colors),
      background: colors.paper,
      card: colors.paperRaised,
      text: colors.ink,
      border: colors.border,
      primary: colors.terracotta,
    },
  };

  // Onboarding status is per-account and only meaningful once signed in --
  // don't block on it (or trigger its lookup) while logged out.
  if (!authReady || (isAuthenticated && onboardingLoading)) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.paper }}>
        <ActivityIndicator color={colors.terracotta} />
      </View>
    );
  }

  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isAuthenticated ? (
          <Stack.Screen name="Auth" component={AuthStack} />
        ) : completed ? (
          <Stack.Screen name="Main" component={MainTabs} />
        ) : (
          <Stack.Screen name="Onboarding" component={OnboardingStack} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}

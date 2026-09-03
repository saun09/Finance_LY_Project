import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { WelcomeScreen } from '../screens/onboarding/WelcomeScreen';
import { ProfileScreen } from '../screens/onboarding/ProfileScreen';
import { ExpensesScreen } from '../screens/onboarding/ExpensesScreen';
import { DebtScreen } from '../screens/onboarding/DebtScreen';
import { InsuranceScreen } from '../screens/onboarding/InsuranceScreen';
import { HoldingsScreen } from '../screens/onboarding/HoldingsScreen';
import { ReviewScreen } from '../screens/onboarding/ReviewScreen';
import { SnapshotScreen } from '../screens/onboarding/SnapshotScreen';
import type { OnboardingStackParamList } from './types';

const Stack = createNativeStackNavigator<OnboardingStackParamList>();

export function OnboardingStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Welcome" component={WelcomeScreen} />
      <Stack.Screen name="Profile" component={ProfileScreen} />
      <Stack.Screen name="Expenses" component={ExpensesScreen} />
      <Stack.Screen name="Debt" component={DebtScreen} />
      <Stack.Screen name="Insurance" component={InsuranceScreen} />
      <Stack.Screen name="Holdings" component={HoldingsScreen} />
      <Stack.Screen name="Review" component={ReviewScreen} />
      <Stack.Screen name="Snapshot" component={SnapshotScreen} />
    </Stack.Navigator>
  );
}

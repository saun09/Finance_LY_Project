import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { InsightsScreen } from '../screens/insights/InsightsScreen';
import { LeaksScreen } from '../screens/insights/LeaksScreen';
import { DebtScreen } from '../screens/insights/DebtScreen';
import { PersonalizationScreen } from '../screens/insights/PersonalizationScreen';
import { TransparencyScreen } from '../screens/insights/TransparencyScreen';
import { TransparencyDetailScreen } from '../screens/insights/TransparencyDetailScreen';
import type { InsightsStackParamList } from './types';

const Stack = createNativeStackNavigator<InsightsStackParamList>();

export function InsightsStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Insights" component={InsightsScreen} />
      <Stack.Screen name="Debt" component={DebtScreen} />
      <Stack.Screen name="Leaks" component={LeaksScreen} />
      <Stack.Screen name="Personalization" component={PersonalizationScreen} />
      <Stack.Screen name="Transparency" component={TransparencyScreen} />
      <Stack.Screen name="TransparencyDetail" component={TransparencyDetailScreen} />
    </Stack.Navigator>
  );
}

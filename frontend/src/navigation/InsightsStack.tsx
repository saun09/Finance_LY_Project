import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import type { InsightsStackParamList } from './types';

const Stack = createNativeStackNavigator<InsightsStackParamList>();

export function InsightsStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Insights">{() => <PlaceholderScreen title="Insights" phase="Phase 5" />}</Stack.Screen>
      <Stack.Screen name="Debt">{() => <PlaceholderScreen title="Debt" phase="Phase 5" />}</Stack.Screen>
      <Stack.Screen name="Leaks">{() => <PlaceholderScreen title="Leaks" phase="Phase 5" />}</Stack.Screen>
      <Stack.Screen name="Personalization">
        {() => <PlaceholderScreen title="Personalization" phase="Phase 5" />}
      </Stack.Screen>
      <Stack.Screen name="Transparency">
        {() => <PlaceholderScreen title="Transparency" phase="Phase 6" />}
      </Stack.Screen>
      <Stack.Screen name="TransparencyDetail">
        {() => <PlaceholderScreen title="Transparency Detail" phase="Phase 6" />}
      </Stack.Screen>
    </Stack.Navigator>
  );
}

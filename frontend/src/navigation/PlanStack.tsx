import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import type { PlanStackParamList } from './types';

const Stack = createNativeStackNavigator<PlanStackParamList>();

export function PlanStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="RiskProfile">
        {() => <PlaceholderScreen title="Risk Profile" phase="Phase 4" />}
      </Stack.Screen>
      <Stack.Screen name="RiskQuestionnaire">
        {() => <PlaceholderScreen title="Risk Questionnaire" phase="Phase 4" />}
      </Stack.Screen>
      <Stack.Screen name="Allocation">
        {() => <PlaceholderScreen title="Allocation" phase="Phase 4" />}
      </Stack.Screen>
    </Stack.Navigator>
  );
}

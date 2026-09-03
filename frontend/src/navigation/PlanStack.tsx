import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { RiskProfileScreen } from '../screens/plan/RiskProfileScreen';
import { RiskQuestionnaireScreen } from '../screens/plan/RiskQuestionnaireScreen';
import { AllocationScreen } from '../screens/plan/AllocationScreen';
import type { PlanStackParamList } from './types';

const Stack = createNativeStackNavigator<PlanStackParamList>();

export function PlanStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="RiskProfile" component={RiskProfileScreen} />
      <Stack.Screen name="RiskQuestionnaire" component={RiskQuestionnaireScreen} />
      <Stack.Screen name="Allocation" component={AllocationScreen} />
    </Stack.Navigator>
  );
}

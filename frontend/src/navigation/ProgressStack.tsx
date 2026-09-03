import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import type { ProgressStackParamList } from './types';

const Stack = createNativeStackNavigator<ProgressStackParamList>();

export function ProgressStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Progress">{() => <PlaceholderScreen title="Progress" phase="Phase 8" />}</Stack.Screen>
    </Stack.Navigator>
  );
}

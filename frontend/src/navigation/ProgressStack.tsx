import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { ProgressScreen } from '../screens/progress/ProgressScreen';
import type { ProgressStackParamList } from './types';

const Stack = createNativeStackNavigator<ProgressStackParamList>();

export function ProgressStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Progress" component={ProgressScreen} />
    </Stack.Navigator>
  );
}

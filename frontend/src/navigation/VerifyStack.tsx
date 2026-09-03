import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import type { VerifyStackParamList } from './types';

const Stack = createNativeStackNavigator<VerifyStackParamList>();

export function VerifyStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="RumourVerification">
        {() => <PlaceholderScreen title="Verify" phase="Phase 7" />}
      </Stack.Screen>
    </Stack.Navigator>
  );
}

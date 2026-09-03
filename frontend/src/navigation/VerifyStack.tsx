import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { RumourVerificationScreen } from '../screens/verify/RumourVerificationScreen';
import type { VerifyStackParamList } from './types';

const Stack = createNativeStackNavigator<VerifyStackParamList>();

export function VerifyStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="RumourVerification" component={RumourVerificationScreen} />
    </Stack.Navigator>
  );
}

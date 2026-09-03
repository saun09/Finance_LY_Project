import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { ProfileHomeScreen } from '../screens/profile/ProfileHomeScreen';
import { ExpensesManageScreen } from '../screens/profile/ExpensesManageScreen';
import { DebtManageScreen } from '../screens/profile/DebtManageScreen';
import { InsuranceManageScreen } from '../screens/profile/InsuranceManageScreen';
import { HoldingsManageScreen } from '../screens/profile/HoldingsManageScreen';
import { SettingsScreen } from '../screens/profile/SettingsScreen';
import type { ProfileStackParamList } from './types';

const Stack = createNativeStackNavigator<ProfileStackParamList>();

export function ProfileStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="ProfileHome" component={ProfileHomeScreen} />
      <Stack.Screen name="ExpensesManage" component={ExpensesManageScreen} />
      <Stack.Screen name="DebtManage" component={DebtManageScreen} />
      <Stack.Screen name="InsuranceManage" component={InsuranceManageScreen} />
      <Stack.Screen name="HoldingsManage" component={HoldingsManageScreen} />
      <Stack.Screen name="Settings" component={SettingsScreen} />
    </Stack.Navigator>
  );
}

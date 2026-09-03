import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { PlaceholderScreen } from '../screens/PlaceholderScreen';
import { SettingsScreen } from '../screens/profile/SettingsScreen';
import type { ProfileStackParamList } from './types';

const Stack = createNativeStackNavigator<ProfileStackParamList>();

export function ProfileStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="ProfileHome">{() => <PlaceholderScreen title="Profile" phase="Phase 9" />}</Stack.Screen>
      <Stack.Screen name="ExpensesManage">
        {() => <PlaceholderScreen title="Expenses" phase="Phase 9" />}
      </Stack.Screen>
      <Stack.Screen name="DebtManage">{() => <PlaceholderScreen title="Debts" phase="Phase 9" />}</Stack.Screen>
      <Stack.Screen name="InsuranceManage">
        {() => <PlaceholderScreen title="Insurance" phase="Phase 9" />}
      </Stack.Screen>
      <Stack.Screen name="HoldingsManage">
        {() => <PlaceholderScreen title="Holdings" phase="Phase 9" />}
      </Stack.Screen>
      <Stack.Screen name="Settings" component={SettingsScreen} />
    </Stack.Navigator>
  );
}

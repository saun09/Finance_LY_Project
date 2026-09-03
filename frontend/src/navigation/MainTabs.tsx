import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { HomeStack } from './HomeStack';
import { PlanStack } from './PlanStack';
import { InsightsStack } from './InsightsStack';
import { VerifyStack } from './VerifyStack';
import { ProgressStack } from './ProgressStack';
import { ProfileStack } from './ProfileStack';
import type { MainTabParamList } from './types';
import { useAppTheme } from '../theme/ThemeContext';
import { FONT, RADIUS } from '../theme/tokens';

const Tab = createBottomTabNavigator<MainTabParamList>();

const TAB_LABEL: Record<keyof MainTabParamList, string> = {
  HomeTab: 'Home',
  PlanTab: 'Plan',
  InsightsTab: 'Insights',
  VerifyTab: 'Verify',
  ProgressTab: 'Progress',
  ProfileTab: 'Profile',
};

/** Deliberately no icon library: a distinctive, editorial tab bar reads
 * on typography + a small active-tab dot rather than a generic 6-icon
 * row (Ionicons/MaterialIcons on every other RN app). */
function TabIcon({ focused, color }: { focused: boolean; color: string }) {
  return (
    <View style={[styles.dot, { backgroundColor: focused ? color : 'transparent' }]} />
  );
}

export function MainTabs() {
  const { colors } = useAppTheme();
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.terracotta,
        tabBarInactiveTintColor: colors.inkFaint,
        tabBarStyle: { backgroundColor: colors.paperRaised, borderTopColor: colors.border, height: 64, paddingTop: 8 },
        tabBarLabelStyle: { fontFamily: FONT.bodySemiBold, fontSize: 11, letterSpacing: 0.3 },
        tabBarLabel: TAB_LABEL[route.name],
        tabBarIcon: ({ focused, color }) => <TabIcon focused={focused} color={color} />,
      })}
    >
      <Tab.Screen name="HomeTab" component={HomeStack} />
      <Tab.Screen name="PlanTab" component={PlanStack} />
      <Tab.Screen name="InsightsTab" component={InsightsStack} />
      <Tab.Screen name="VerifyTab" component={VerifyStack} />
      <Tab.Screen name="ProgressTab" component={ProgressStack} />
      <Tab.Screen name="ProfileTab" component={ProfileStack} />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  dot: { width: 5, height: 5, borderRadius: RADIUS.pill, marginBottom: 2 },
});

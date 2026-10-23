import { Ionicons } from '@expo/vector-icons';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { HomeStack } from './HomeStack';
import { PlanStack } from './PlanStack';
import { InsightsStack } from './InsightsStack';
import { VerifyStack } from './VerifyStack';
import { ProgressStack } from './ProgressStack';
import { ProfileStack } from './ProfileStack';
import type { MainTabParamList } from './types';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { useAppTheme } from '../theme/ThemeContext';
import { FONT, RADIUS } from '../theme/tokens';

const Tab = createBottomTabNavigator<MainTabParamList>();

type TabKey = keyof MainTabParamList;
type IconName = keyof typeof Ionicons.glyphMap;

const TAB_LABEL: Record<TabKey, string> = {
  HomeTab: 'Home',
  PlanTab: 'Plan',
  InsightsTab: 'Insights',
  VerifyTab: 'Verify',
  ProgressTab: 'Progress',
  ProfileTab: 'Profile',
};

// Filled for the active tab, outline for every inactive one -- same
// visual language IconChip/MenuList already use elsewhere, via this app's
// one icon set (@expo/vector-icons' Ionicons) rather than a new library.
const TAB_ICON: Record<TabKey, { outline: IconName; filled: IconName }> = {
  HomeTab: { outline: 'home-outline', filled: 'home' },
  PlanTab: { outline: 'compass-outline', filled: 'compass' },
  InsightsTab: { outline: 'bulb-outline', filled: 'bulb' },
  VerifyTab: { outline: 'shield-checkmark-outline', filled: 'shield-checkmark' },
  ProgressTab: { outline: 'trending-up-outline', filled: 'trending-up' },
  ProfileTab: { outline: 'person-outline', filled: 'person' },
};

/** A small dot above the icon marks the active tab (the bar's original,
 * deliberately-typographic "you are here" marker, kept); the icon itself
 * now also switches outline -> filled and pops slightly on activation --
 * a one-time spring on focus change, not a continuous animation, so it
 * stays within this app's usual restrained-motion rule. */
function TabIcon({ routeName, focused, color }: { routeName: TabKey; focused: boolean; color: string }) {
  const reducedMotion = useReducedMotion();
  const scale = useRef(new Animated.Value(focused ? 1.08 : 1)).current;

  useEffect(() => {
    if (reducedMotion) {
      scale.setValue(focused ? 1.08 : 1);
      return;
    }
    Animated.spring(scale, { toValue: focused ? 1.08 : 1, useNativeDriver: true, speed: 20, bounciness: 6 }).start();
  }, [focused, reducedMotion, scale]);

  const icon = TAB_ICON[routeName];

  return (
    <View style={styles.iconWrap}>
      <View style={[styles.dot, { backgroundColor: focused ? color : 'transparent' }]} />
      <Animated.View style={{ transform: [{ scale }] }}>
        <Ionicons name={focused ? icon.filled : icon.outline} size={22} color={color} />
      </Animated.View>
    </View>
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
        tabBarIcon: ({ focused, color }) => <TabIcon routeName={route.name} focused={focused} color={color} />,
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
  iconWrap: { alignItems: 'center', gap: 2 },
  dot: { width: 5, height: 5, borderRadius: RADIUS.pill },
});

import React, { Children, isValidElement } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View, ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Reveal } from './Reveal';

interface Props {
  children: React.ReactNode;
  scroll?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  contentStyle?: ViewStyle;
  /** Every scrolling screen staggers its top-level sections in on mount
   * by default (the app's one consistent motion language) -- set false
   * for a screen where that reads as noise (e.g. one already mid-flow). */
  animate?: boolean;
  /** A floating action button (or similar), anchored bottom-right over the
   * scrolling content rather than scrolling away with it -- e.g. a manage
   * screen's "+ Add X" that opens a FormSheet. Positioned within this
   * SafeAreaView, so it sits above this screen's own content area without
   * needing to know the tab bar's height. */
  floatingAction?: React.ReactNode;
}

/** Consistent safe-area handling + background across every screen
 * (Section 25: SafeAreaView/insets, no clipped content under the status
 * bar or nav bar). Pull-to-refresh is opt-in via onRefresh so any
 * API-driven screen gets it for free.
 *
 * `scrollContent`'s bottom padding (TAB_BAR_CLEARANCE) is deliberately
 * larger than the tab bar's own 64px height: MainTabs sets a fixed
 * numeric `tabBarStyle.height`, which suppresses React Navigation's
 * automatic safe-area bottom inset on the bar itself, so the bar can
 * occupy more than 64px on a device with a home indicator/gesture area.
 * Reserving only 64px of scroll padding would let the last card's bottom
 * edge sit behind the bar on exactly those devices -- the generous flat
 * value here is the simple, crash-proof fix (vs. reading the live bar
 * height via useBottomTabBarHeight(), which throws when a screen using
 * ScreenContainer isn't nested under the tab navigator, e.g. Auth/Onboarding).
 *
 * Scrolling screens also get the staggered Reveal entrance for free here,
 * one wrap per top-level child -- so every screen picks up the app's
 * signature motion without hand-wrapping each section itself. Only
 * applied when `scroll` (direct children stack top-to-bottom with no
 * flex-grow expectations); a `scroll={false}` screen often has a child
 * that needs to flex-fill the remaining space, which an extra wrapper
 * View would break, so those opt out automatically. */
const TAB_BAR_CLEARANCE = 112;

export function ScreenContainer({ children, scroll = true, onRefresh, refreshing, contentStyle, animate = true, floatingAction }: Props) {
  const { colors } = useAppTheme();
  const Wrapper = scroll ? ScrollView : View;
  const wrapperProps = scroll
    ? {
        contentContainerStyle: [styles.scrollContent, contentStyle],
        refreshControl: onRefresh ? (
          <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.terracotta} />
        ) : undefined,
        keyboardShouldPersistTaps: 'handled' as const,
      }
    : { style: [styles.flexContent, contentStyle] };

  const content =
    scroll && animate
      ? Children.map(children, (child, i) => (
          <Reveal index={i} key={isValidElement(child) && child.key != null ? child.key : i}>
            {child}
          </Reveal>
        ))
      : children;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.paper }]} edges={['top', 'left', 'right']}>
      <Wrapper {...(wrapperProps as any)}>{content}</Wrapper>
      {floatingAction ? <View style={styles.floatingActionWrap}>{floatingAction}</View> : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scrollContent: { padding: SPACE.lg, paddingBottom: TAB_BAR_CLEARANCE, gap: SPACE.lg },
  flexContent: { flex: 1, padding: SPACE.lg, gap: SPACE.lg },
  floatingActionWrap: { position: 'absolute', right: SPACE.lg, bottom: SPACE.lg },
});

import React from 'react';
import { RefreshControl, ScrollView, StyleSheet, View, ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';

interface Props {
  children: React.ReactNode;
  scroll?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  contentStyle?: ViewStyle;
}

/** Consistent safe-area handling + background across every screen
 * (Section 25: SafeAreaView/insets, no clipped content under the status
 * bar or nav bar). Pull-to-refresh is opt-in via onRefresh so any
 * API-driven screen gets it for free. */
export function ScreenContainer({ children, scroll = true, onRefresh, refreshing, contentStyle }: Props) {
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

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.paper }]} edges={['top', 'left', 'right']}>
      <Wrapper {...(wrapperProps as any)}>{children}</Wrapper>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scrollContent: { padding: SPACE.lg, paddingBottom: SPACE.xxxl, gap: SPACE.lg },
  flexContent: { flex: 1, padding: SPACE.lg, gap: SPACE.lg },
});

import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Card } from '../../components/Card';
import { IconChip } from '../../components/IconChip';
import { Text } from '../../components/Text';
import { Button } from '../../components/Button';
import { Reveal } from '../../components/Reveal';
import { SectionHeader } from '../../components/SectionHeader';
import { useDemoUser } from '../../context/DemoUserContext';
import { useOnboardingStatus } from '../../context/OnboardingStatusContext';
import { useChevronRotation } from '../../hooks/useChevronRotation';
import { API_BASE_URL } from '../../api/client';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE } from '../../theme/tokens';

export function SettingsScreen() {
  const { colors } = useAppTheme();
  const { username, userId, logout } = useDemoUser();
  const { resetOnboarding } = useOnboardingStatus();
  const [devInfoOpen, setDevInfoOpen] = useState(false);
  const chevronRotation = useChevronRotation(devInfoOpen);

  return (
    <ScreenContainer>
      <Text variant="display">Settings</Text>

      <Card>
        <View style={styles.accountRow}>
          <IconChip name="person-circle-outline" tone="petrol" size={44} />
          <View style={styles.accountCopy}>
            <Text variant="label" tone="muted">
              DEMO ACCOUNT
            </Text>
            <Text variant="h2">{username ?? userId}</Text>
            <Text variant="caption" tone="faint">
              This app runs on sample data for a chosen demo persona — nothing here is a real account.
            </Text>
          </View>
        </View>
        <Button label="Log out" variant="ghost" onPress={logout} />
      </Card>

      <Card>
        <SectionHeader title="Onboarding" />
        <Text variant="caption" tone="muted" style={styles.spacedTop}>
          Replays the onboarding flow for this account on this device. Does not delete anything on the
          backend.
        </Text>
        <Button label="Restart onboarding on this device" variant="ghost" onPress={resetOnboarding} />
      </Card>

      <Card>
        <Pressable
          onPress={() => setDevInfoOpen((v) => !v)}
          style={styles.devHeader}
          accessibilityRole="button"
          accessibilityState={{ expanded: devInfoOpen }}
          accessibilityLabel="Developer info"
        >
          <Ionicons name="code-slash-outline" size={18} color={colors.inkFaint} />
          <Text variant="caption" tone="faint" style={styles.devTitle}>
            Developer info
          </Text>
          <Animated.View style={{ transform: [{ rotate: chevronRotation }] }}>
            <Ionicons name="chevron-down" size={18} color={colors.inkFaint} />
          </Animated.View>
        </Pressable>
        {devInfoOpen ? (
          <Reveal>
            <View style={styles.devBody}>
              <Text variant="caption" tone="faint">
                API base URL
              </Text>
              <Text variant="caption" tone="muted">
                {API_BASE_URL}
              </Text>
              <Text variant="caption" tone="faint">
                Internal user ID
              </Text>
              <Text variant="caption" tone="muted">
                {userId}
              </Text>
            </View>
          </Reveal>
        ) : null}
      </Card>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.md, marginBottom: SPACE.md },
  accountCopy: { flex: 1, gap: 2 },
  spacedTop: { marginTop: SPACE.xs, marginBottom: SPACE.xs },
  devHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  devTitle: { flex: 1 },
  devBody: { marginTop: SPACE.sm, gap: SPACE.xs },
});

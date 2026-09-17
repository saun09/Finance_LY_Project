import React from 'react';
import { StyleSheet } from 'react-native';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Card } from '../../components/Card';
import { Text } from '../../components/Text';
import { Button } from '../../components/Button';
import { SectionHeader } from '../../components/SectionHeader';
import { useDemoUser } from '../../context/DemoUserContext';
import { useOnboardingStatus } from '../../context/OnboardingStatusContext';
import { API_BASE_URL } from '../../api/client';
import { SPACE } from '../../theme/tokens';

export function SettingsScreen() {
  const { username, userId, logout } = useDemoUser();
  const { resetOnboarding } = useOnboardingStatus();

  return (
    <ScreenContainer>
      <Text variant="display">Settings</Text>

      <Card>
        <SectionHeader title="Account" />
        <Text variant="body" tone="muted" style={styles.spacedTop}>
          Signed in as
        </Text>
        <Text variant="figure">{username ?? userId}</Text>
        <Button label="Log out" variant="ghost" onPress={logout} />
      </Card>

      <Card>
        <SectionHeader title="Connection" />
        <Text variant="body" tone="muted" style={styles.spacedTop}>
          API base URL
        </Text>
        <Text variant="figure">{API_BASE_URL}</Text>
      </Card>

      <Card>
        <SectionHeader title="Onboarding" />
        <Text variant="caption" tone="muted" style={styles.spacedTop}>
          Replays the onboarding flow for this account on this device. Does not delete anything on the
          backend.
        </Text>
        <Button label="Restart onboarding on this device" variant="ghost" onPress={resetOnboarding} />
      </Card>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  spacedTop: { marginTop: SPACE.xs, marginBottom: SPACE.xs },
});

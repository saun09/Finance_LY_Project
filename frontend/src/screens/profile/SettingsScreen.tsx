import React, { useState } from 'react';
import { TextInput, StyleSheet } from 'react-native';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Card } from '../../components/Card';
import { Text } from '../../components/Text';
import { Button } from '../../components/Button';
import { SectionHeader } from '../../components/SectionHeader';
import { useDemoUser } from '../../context/DemoUserContext';
import { useOnboardingStatus } from '../../context/OnboardingStatusContext';
import { API_BASE_URL } from '../../api/client';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE, RADIUS } from '../../theme/tokens';

/**
 * The backend has no authentication system (verified directly against
 * app/main.py) -- so this is a plain, labeled demo-user switcher, not a
 * fake login screen. Only technical detail shown is the API base URL,
 * for verifying connectivity during a demo; no backend config is exposed.
 */
export function SettingsScreen() {
  const { colors } = useAppTheme();
  const { userId, setUserId } = useDemoUser();
  const { resetOnboarding } = useOnboardingStatus();
  const [draft, setDraft] = useState(userId);

  return (
    <ScreenContainer>
      <Text variant="display">Settings</Text>

      <Card>
        <SectionHeader title="Demo user" subtitle="The backend has no login system yet" />
        <Text variant="caption" tone="muted" style={styles.spacedTop}>
          All data is scoped to this id. Change it to demo a different user's data, or to start a fresh
          onboarding flow.
        </Text>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="demo-user"
          placeholderTextColor={colors.inkFaint}
          style={[
            styles.input,
            { borderColor: colors.border, color: colors.ink, backgroundColor: colors.paperSunken },
          ]}
        />
        <Button label="Save user id" onPress={() => setUserId(draft)} />
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
          Replays the onboarding flow for this user id on this device. Does not delete anything on the
          backend.
        </Text>
        <Button label="Restart onboarding on this device" variant="ghost" onPress={resetOnboarding} />
      </Card>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  input: {
    minHeight: 48,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderRadius: RADIUS.md,
    paddingHorizontal: SPACE.md,
    marginVertical: SPACE.md,
  },
  spacedTop: { marginTop: SPACE.xs, marginBottom: SPACE.xs },
});

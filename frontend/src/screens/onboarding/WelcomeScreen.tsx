import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from '../../components/Text';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ScreenContainer } from '../../components/ScreenContainer';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Welcome'>;

export function WelcomeScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();

  return (
    <ScreenContainer scroll={false} contentStyle={styles.container}>
      <View style={styles.top}>
        <Text variant="label" tone="terracotta">
          PERSONAL FINANCE, PLANNED
        </Text>
        <Text variant="display" style={styles.headline}>
          Understand your finances.{'\n'}Build a plan.{'\n'}
          <Text variant="displayItalic" tone="terracotta" style={styles.headline}>
            Make better decisions.
          </Text>
        </Text>
      </View>

      <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
        <Text variant="bodyMedium" tone="petrol">
          This app helps you plan — it never buys, sells, or executes anything on your behalf, and it never
          recommends a specific stock, fund, or scheme. Guidance stays at the category level: cash, debt,
          equity, real assets, alternatives.
        </Text>
      </Card>

      <View style={styles.bottom}>
        <Button label="Get started" fullWidth onPress={() => navigation.navigate('Profile')} />
        <Text variant="caption" tone="faint" style={styles.footnote}>
          Takes about 5 minutes. You can edit everything later.
        </Text>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: { justifyContent: 'space-between' },
  top: { gap: SPACE.md, marginTop: SPACE.xxl },
  headline: { marginTop: SPACE.sm },
  bottom: { gap: SPACE.sm },
  footnote: { textAlign: 'center' },
});

import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { View } from 'react-native';
import { MenuList } from '../../components/MenuList';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { usePersonalization } from '../../hooks/usePersonalization';
import type { InsightsStackParamList } from '../../navigation/types';
import { formatPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<InsightsStackParamList, 'Insights'>;

export function InsightsScreen() {
  const navigation = useNavigation<Nav>();
  const debtLeak = useDebtLeak();
  const personalization = usePersonalization();

  const leaksSubtitle = debtLeak.data
    ? debtLeak.data.total_recoverable_annual_paise > 0
      ? `${formatPaise(debtLeak.data.total_recoverable_annual_paise)}/year recoverable`
      : 'Nothing flagged right now'
    : 'Recoverable costs and idle cash';

  const debtSubtitle = debtLeak.data?.avalanche_snowball
    ? `${debtLeak.data.avalanche_snowball.avalanche.months_to_clear_all} months to clear all loans`
    : 'Payoff strategy comparison';

  const personalizationSubtitle =
    personalization.data && !personalization.error
      ? `${Number(personalization.data.offset_pct_points) >= 0 ? '+' : ''}${Number(personalization.data.offset_pct_points).toFixed(1)} pt offset from ${personalization.data.edits_considered} past decisions`
      : 'How your habits tilt your target';

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Your insights
        </Text>
        <Text variant="display">Beyond the numbers</Text>
      </View>

      <MenuList
        items={[
          { key: 'leaks', title: 'Recoverable costs', subtitle: leaksSubtitle, onPress: () => navigation.navigate('Leaks') },
          { key: 'debt', title: 'Debt payoff', subtitle: debtSubtitle, onPress: () => navigation.navigate('Debt') },
          {
            key: 'personalization',
            title: 'Personalization',
            subtitle: personalizationSubtitle,
            onPress: () => navigation.navigate('Personalization'),
          },
          {
            key: 'transparency',
            title: 'Transparency',
            subtitle: 'See exactly how each figure was calculated',
            onPress: () => navigation.navigate('Transparency'),
          },
        ]}
      />
    </ScreenContainer>
  );
}

import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import type { HoldingOut, HoldingType } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { HoldingTypePicker } from '../../components/HoldingTypePicker';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Holdings'>;

export function HoldingsScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();

  const [items, setItems] = useState<HoldingOut[]>([]);
  const [description, setDescription] = useState('');
  const [valueInput, setValueInput] = useState('');
  const [holdingType, setHoldingType] = useState<HoldingType | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const value_paise = rupeeInputToPaise(valueInput);
      if (!description.trim() || value_paise === null) throw new Error('validation');
      return onboardingApi.postHolding(userId, { description: description.trim(), value_paise, holding_type: holdingType });
    },
    onSuccess: (created) => {
      setItems((prev) => [...prev, created]);
      setDescription('');
      setValueInput('');
      setHoldingType(null);
    },
    onError: (err) => {
      setFormError(err instanceof Error && err.message === 'validation' ? 'Enter a description and a value.' : toApiError(err).message);
    },
  });

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={5}
        total={7}
        title="What do you hold?"
        subtitle="Savings, investments, retirement accounts, gold, property — anything with value."
      />

      {items.length > 0 ? (
        <Card>
          {items.map((item) => (
            <ListRow
              key={item.id}
              title={item.description}
              subtitle={item.holding_type ?? 'Type not specified'}
              trailing={formatPaise(item.value_paise)}
            />
          ))}
        </Card>
      ) : null}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD A HOLDING
        </Text>
        <TextField label="Description" value={description} onChangeText={setDescription} placeholder="HDFC Flexicap SIP" />
        <TextField label="Current value" value={valueInput} onChangeText={setValueInput} placeholder="250000" keyboardType="numeric" prefix="₹" />
        <HoldingTypePicker value={holdingType} onChange={setHoldingType} />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add holding"
          variant="secondary"
          loading={addMutation.isPending}
          onPress={() => {
            setFormError(null);
            addMutation.mutate();
          }}
        />
      </Card>

      <View style={styles.footer}>
        <Button label="Continue" fullWidth onPress={() => navigation.navigate('Review')} />
        {items.length === 0 ? (
          <Text variant="caption" tone="faint" style={styles.footnote}>
            No holdings yet is fine — this just measures where you're starting from.
          </Text>
        ) : null}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  formCard: { gap: SPACE.md },
  footer: { marginTop: SPACE.md, gap: SPACE.sm },
  footnote: { textAlign: 'center' },
});

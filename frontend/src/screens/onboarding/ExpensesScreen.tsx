import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import type { ExpenseFrequency, ExpenseItemOut } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { Toggle } from '../../components/Toggle';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Expenses'>;

const FREQUENCY_OPTIONS: { value: ExpenseFrequency; label: string }[] = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'annual', label: 'Annual' },
  { value: 'one_time', label: 'One-time' },
];

export function ExpensesScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();
  const { colors } = useAppTheme();

  const [items, setItems] = useState<ExpenseItemOut[]>([]);
  const [category, setCategory] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [frequency, setFrequency] = useState<ExpenseFrequency | null>(null);
  const [isEssential, setIsEssential] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const amount_paise = rupeeInputToPaise(amountInput);
      if (!category.trim() || amount_paise === null || !frequency) {
        throw new Error('validation');
      }
      return onboardingApi.postExpenseItem(userId, {
        category: category.trim(),
        amount_paise,
        frequency,
        is_essential: isEssential,
      });
    },
    onSuccess: (created) => {
      setItems((prev) => [...prev, created]);
      setCategory('');
      setAmountInput('');
      setFrequency(null);
      setIsEssential(true);
    },
    onError: (err) => {
      setFormError(err instanceof Error && err.message === 'validation'
        ? 'Enter a category, a valid amount, and a frequency.'
        : toApiError(err).message);
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (itemId: string) => {
      setRemovingId(itemId);
      await onboardingApi.removeExpenseItem(userId, itemId);
      return itemId;
    },
    onSuccess: (itemId) => setItems((prev) => prev.filter((i) => i.id !== itemId)),
    onSettled: () => setRemovingId(null),
  });

  const amountValid = amountInput.trim() === '' || rupeeInputToPaise(amountInput) !== null;

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={2}
        total={7}
        title="What do you spend monthly?"
        subtitle="Add each recurring expense one at a time — rent, groceries, subscriptions, EMIs are tracked separately."
      />

      <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
        <Text variant="caption" tone="petrol">
          Expenses are entered manually. This app does not connect to your bank or read your statements
          automatically.
        </Text>
      </Card>

      {items.length > 0 ? (
        <Card>
          {items.map((item) => (
            <ListRow
              key={item.id}
              title={item.category}
              subtitle={`${item.frequency}${item.is_essential ? ' · essential' : ''}`}
              trailing={formatPaise(item.amount_paise)}
              onRemove={() => removeMutation.mutate(item.id)}
              removing={removingId === item.id}
            />
          ))}
        </Card>
      ) : null}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD AN EXPENSE
        </Text>
        <TextField label="Category" value={category} onChangeText={setCategory} placeholder="Rent" />
        <TextField
          label="Amount"
          value={amountInput}
          onChangeText={setAmountInput}
          placeholder="15000"
          keyboardType="numeric"
          prefix="₹"
          error={!amountValid ? 'Enter a valid amount.' : undefined}
        />
        <ChoiceGroup label="Frequency" options={FREQUENCY_OPTIONS} value={frequency} onChange={setFrequency} />
        <Toggle
          label="Essential"
          description="Can't be cut without real hardship (rent, groceries, EMIs)."
          value={isEssential}
          onChange={setIsEssential}
        />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add expense"
          variant="secondary"
          loading={addMutation.isPending}
          onPress={() => {
            setFormError(null);
            addMutation.mutate();
          }}
        />
      </Card>

      <View style={styles.footer}>
        <Button label="Continue" fullWidth onPress={() => navigation.navigate('Debt')} />
        {items.length === 0 ? (
          <Text variant="caption" tone="faint" style={styles.footnote}>
            You can add expenses later too, but the plan will be more accurate the more you add now.
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

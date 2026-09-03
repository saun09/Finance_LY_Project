import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import type { EmiOut } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';
import { formatPaise, percentInputToBps, rupeeInputToPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Debt'>;

export function DebtScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();

  const [items, setItems] = useState<EmiOut[]>([]);
  const [lender, setLender] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [tenureInput, setTenureInput] = useState('');
  const [rateInput, setRateInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const amount_paise = rupeeInputToPaise(amountInput);
      const remaining_tenure_months = /^\d+$/.test(tenureInput.trim()) ? Number(tenureInput.trim()) : null;
      const annual_rate_bps = percentInputToBps(rateInput);
      if (!lender.trim() || amount_paise === null || remaining_tenure_months === null || annual_rate_bps === null) {
        throw new Error('validation');
      }
      return onboardingApi.postEmi(userId, {
        lender: lender.trim(),
        amount_paise,
        remaining_tenure_months,
        annual_rate_bps,
      });
    },
    onSuccess: (created) => {
      setItems((prev) => [...prev, created]);
      setLender('');
      setAmountInput('');
      setTenureInput('');
      setRateInput('');
    },
    onError: (err) => {
      setFormError(
        err instanceof Error && err.message === 'validation'
          ? 'Enter a lender, a monthly EMI amount, remaining months, and an interest rate.'
          : toApiError(err).message,
      );
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (emiId: string) => {
      setRemovingId(emiId);
      return onboardingApi.closeEmi(userId, emiId);
    },
    onSuccess: (_result, emiId) => setItems((prev) => prev.filter((i) => i.id !== emiId)),
    onSettled: () => setRemovingId(null),
  });

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={3}
        total={7}
        title="Any loans or EMIs?"
        subtitle="Home loans, car loans, personal loans, credit-card EMIs — skip this step if you have none."
      />

      {items.length > 0 ? (
        <Card>
          {items.map((item) => (
            <ListRow
              key={item.id}
              title={item.lender}
              subtitle={`${item.remaining_tenure_months} months left · ${(item.annual_rate_bps / 100).toFixed(2)}% p.a.`}
              trailing={`${formatPaise(item.amount_paise)}/mo`}
              onRemove={() => removeMutation.mutate(item.id)}
              removing={removingId === item.id}
            />
          ))}
        </Card>
      ) : null}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD A LOAN
        </Text>
        <TextField label="Lender" value={lender} onChangeText={setLender} placeholder="HDFC Bank" />
        <TextField
          label="Monthly EMI"
          value={amountInput}
          onChangeText={setAmountInput}
          placeholder="18000"
          keyboardType="numeric"
          prefix="₹"
        />
        <TextField
          label="Remaining tenure (months)"
          value={tenureInput}
          onChangeText={setTenureInput}
          placeholder="36"
          keyboardType="numeric"
        />
        <TextField
          label="Interest rate (annual %)"
          value={rateInput}
          onChangeText={setRateInput}
          placeholder="9.5"
          keyboardType="decimal-pad"
        />
        {formError ? <InlineError message={formError} /> : null}
        <Button label="Add loan" variant="secondary" loading={addMutation.isPending} onPress={() => {
          setFormError(null);
          addMutation.mutate();
        }} />
      </Card>

      <View style={styles.footer}>
        <Button label="Continue" fullWidth onPress={() => navigation.navigate('Insurance')} />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  formCard: { gap: SPACE.md },
  footer: { marginTop: SPACE.md },
});

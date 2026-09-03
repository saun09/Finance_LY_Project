import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { onboardingApi } from '../../api/onboarding';
import type { EmploymentType, IncomeStability } from '../../api/types';
import { Button } from '../../components/Button';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { InlineError } from '../../components/InlineError';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { toApiError } from '../../api/client';
import type { OnboardingStackParamList } from '../../navigation/types';
import { rupeeInputToPaise } from '../../utils/currency';
import { SPACE } from '../../theme/tokens';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Profile'>;

const INCOME_STABILITY_OPTIONS: { value: IncomeStability; label: string }[] = [
  { value: 'regular', label: 'Regular' },
  { value: 'irregular', label: 'Irregular' },
];

const EMPLOYMENT_OPTIONS: { value: EmploymentType; label: string }[] = [
  { value: 'salaried', label: 'Salaried' },
  { value: 'self_employed', label: 'Self-employed' },
  { value: 'business_owner', label: 'Business owner' },
  { value: 'freelancer', label: 'Freelancer' },
  { value: 'unemployed', label: 'Unemployed' },
  { value: 'other', label: 'Other' },
];

export function ProfileScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();

  const [incomeInput, setIncomeInput] = useState('');
  const [cashInput, setCashInput] = useState('');
  const [dependentsInput, setDependentsInput] = useState('0');
  const [incomeStability, setIncomeStability] = useState<IncomeStability | null>(null);
  const [employmentType, setEmploymentType] = useState<EmploymentType | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const income_paise = rupeeInputToPaise(incomeInput);
      const cash_balance_paise = cashInput.trim() === '' ? 0 : rupeeInputToPaise(cashInput);
      const dependents_count = Number(dependentsInput || '0');
      if (income_paise === null || cash_balance_paise === null || !incomeStability || !employmentType) {
        throw new Error('validation');
      }
      return onboardingApi.putProfile(userId, {
        income_paise,
        income_stability: incomeStability,
        employment_type: employmentType,
        dependents_count,
        cash_balance_paise,
      });
    },
    onSuccess: () => navigation.navigate('Expenses'),
    onError: (err) => {
      if (err instanceof Error && err.message === 'validation') {
        setSubmitError('Please fill in every field with a valid amount before continuing.');
      } else {
        setSubmitError(toApiError(err).message);
      }
    },
  });

  const incomeValid = rupeeInputToPaise(incomeInput) !== null;
  const dependentsValid = /^\d+$/.test(dependentsInput.trim());
  const canContinue = incomeValid && incomeStability !== null && employmentType !== null && dependentsValid;

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={1}
        total={7}
        title="Tell us about your income"
        subtitle="This sets the baseline everything else is measured against."
      />

      <TextField
        label="Monthly income"
        value={incomeInput}
        onChangeText={setIncomeInput}
        placeholder="60000"
        keyboardType="numeric"
        prefix="₹"
        helperText="Take-home, after tax, in whole rupees."
      />

      <ChoiceGroup
        label="Income stability"
        options={INCOME_STABILITY_OPTIONS}
        value={incomeStability}
        onChange={setIncomeStability}
      />

      <ChoiceGroup
        label="Employment type"
        options={EMPLOYMENT_OPTIONS}
        value={employmentType}
        onChange={setEmploymentType}
      />

      <TextField
        label="Dependents"
        value={dependentsInput}
        onChangeText={setDependentsInput}
        placeholder="0"
        keyboardType="numeric"
        helperText="People financially dependent on you."
        error={!dependentsValid ? 'Enter a whole number.' : undefined}
      />

      <TextField
        label="Cash & bank balance"
        value={cashInput}
        onChangeText={setCashInput}
        placeholder="150000"
        keyboardType="numeric"
        prefix="₹"
        helperText="Liquid cash and savings-account balance right now."
      />

      {submitError ? <InlineError message={submitError} /> : null}

      <View style={styles.footer}>
        <Button
          label="Continue"
          fullWidth
          disabled={!canContinue}
          loading={mutation.isPending}
          onPress={() => {
            setSubmitError(null);
            mutation.mutate();
          }}
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  footer: { marginTop: SPACE.md },
});

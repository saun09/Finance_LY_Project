import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { invalidateFinancialData, qk } from '../../api/queryClient';
import type { EmploymentType, IncomeStability } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { InlineError } from '../../components/InlineError';
import { MenuList } from '../../components/MenuList';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useEmis, useExpenses, useHoldings, useInsurancePolicies, useProfile } from '../../hooks/useProfileManagement';
import { SPACE } from '../../theme/tokens';
import type { ProfileStackParamList } from '../../navigation/types';
import { paiseToRupeeInput, rupeeInputToPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<ProfileStackParamList, 'ProfileHome'>;

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

export function ProfileHomeScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const profile = useProfile();
  const emis = useEmis();
  const expenses = useExpenses();
  const insurance = useInsurancePolicies();
  const holdings = useHoldings();

  const [incomeInput, setIncomeInput] = useState('');
  const [cashInput, setCashInput] = useState('');
  const [dependentsInput, setDependentsInput] = useState('0');
  const [incomeStability, setIncomeStability] = useState<IncomeStability | null>(null);
  const [employmentType, setEmploymentType] = useState<EmploymentType | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!profile.data || dirty) return;
    setIncomeInput(paiseToRupeeInput(profile.data.income_paise));
    setCashInput(paiseToRupeeInput(profile.data.cash_balance_paise));
    setDependentsInput(String(profile.data.dependents_count));
    setIncomeStability(profile.data.income_stability);
    setEmploymentType(profile.data.employment_type);
  }, [profile.data, dirty]);

  const saveMutation = useMutation({
    mutationFn: () => {
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
    onSuccess: () => {
      setDirty(false);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: qk.profile(userId) });
      invalidateFinancialData(queryClient, userId);
      setTimeout(() => setSaved(false), 2500);
    },
    onError: (err) =>
      setSaveError(err instanceof Error && err.message === 'validation' ? 'Fill in every field with a valid amount.' : toApiError(err).message),
  });

  const activeEmiCount = emis.data?.filter((e) => e.closed_at === null).length ?? null;
  const activeExpenseCount = expenses.data?.filter((e) => e.removed_at === null).length ?? null;

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Profile
        </Text>
        <Text variant="display">Your details</Text>
      </View>

      {profile.isPending ? (
        <SkeletonCard />
      ) : profile.error ? (
        <Card>
          <Text variant="bodyMedium" tone="danger">
            {profile.error.message}
          </Text>
        </Card>
      ) : (
        <Card style={styles.formCard}>
          <SectionHeader title="Income & household" />
          <TextField
            label="Monthly income"
            value={incomeInput}
            onChangeText={(v) => {
              setIncomeInput(v);
              setDirty(true);
            }}
            keyboardType="numeric"
            prefix="₹"
          />
          <ChoiceGroup
            label="Income stability"
            options={INCOME_STABILITY_OPTIONS}
            value={incomeStability}
            onChange={(v) => {
              setIncomeStability(v);
              setDirty(true);
            }}
          />
          <ChoiceGroup
            label="Employment type"
            options={EMPLOYMENT_OPTIONS}
            value={employmentType}
            onChange={(v) => {
              setEmploymentType(v);
              setDirty(true);
            }}
          />
          <TextField
            label="Dependents"
            value={dependentsInput}
            onChangeText={(v) => {
              setDependentsInput(v);
              setDirty(true);
            }}
            keyboardType="numeric"
          />
          <TextField
            label="Cash & bank balance"
            value={cashInput}
            onChangeText={(v) => {
              setCashInput(v);
              setDirty(true);
            }}
            keyboardType="numeric"
            prefix="₹"
          />

          {saveError ? <InlineError message={saveError} /> : null}
          {saved ? (
            <Text variant="caption" tone="positive">
              Saved.
            </Text>
          ) : null}

          <Button
            label="Save changes"
            fullWidth
            disabled={!dirty}
            loading={saveMutation.isPending}
            onPress={() => {
              setSaveError(null);
              saveMutation.mutate();
            }}
          />
        </Card>
      )}

      <MenuList
        items={[
          {
            key: 'expenses',
            title: 'Expenses',
            subtitle: activeExpenseCount === null ? 'Manage recurring expenses' : `${activeExpenseCount} active`,
            onPress: () => navigation.navigate('ExpensesManage'),
          },
          {
            key: 'debt',
            title: 'Loans & EMIs',
            subtitle: activeEmiCount === null ? 'Manage loans' : `${activeEmiCount} active`,
            onPress: () => navigation.navigate('DebtManage'),
          },
          {
            key: 'insurance',
            title: 'Insurance',
            subtitle: insurance.data ? `${insurance.data.length} polic${insurance.data.length === 1 ? 'y' : 'ies'}` : 'Manage insurance',
            onPress: () => navigation.navigate('InsuranceManage'),
          },
          {
            key: 'holdings',
            title: 'Holdings',
            subtitle: holdings.data ? `${holdings.data.length} holding${holdings.data.length === 1 ? '' : 's'}` : 'Manage holdings',
            onPress: () => navigation.navigate('HoldingsManage'),
          },
          { key: 'settings', title: 'Settings', subtitle: 'Demo user, API connection', onPress: () => navigation.navigate('Settings') },
        ]}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  formCard: { gap: SPACE.md },
});

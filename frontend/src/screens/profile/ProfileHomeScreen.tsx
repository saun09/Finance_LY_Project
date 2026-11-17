import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { invalidateFinancialData, qk } from '../../api/queryClient';
import type { EmploymentType, IncomeStability } from '../../api/types';
import { AvatarBadge, initialsFrom } from '../../components/AvatarBadge';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { InlineError } from '../../components/InlineError';
import { MenuList } from '../../components/MenuList';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useEmis, useExpenses, useHoldings, useInsurancePolicies, useProfile } from '../../hooks/useProfileManagement';
import { useRiskProfileLatest } from '../../hooks/useRiskProfile';
import { useAppTheme } from '../../theme/ThemeContext';
import { Palette, RADIUS, SPACE } from '../../theme/tokens';
import type { ProfileStackParamList } from '../../navigation/types';
import { paiseToRupeeInput, rupeeInputToPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<ProfileStackParamList, 'ProfileHome'>;

type BadgeTone = 'petrol' | 'positive' | 'warning' | 'terracotta';

const TIER_TONE: Record<number, BadgeTone> = { 1: 'petrol', 2: 'petrol', 3: 'positive', 4: 'warning', 5: 'terracotta' };
const TIER_SOFT: Record<number, keyof Palette> = { 1: 'petrolSoft', 2: 'petrolSoft', 3: 'positiveSoft', 4: 'warningSoft', 5: 'terracottaSoft' };

/** Age is always derived fresh from the stored date of birth, never a
 * static number a profile could store and forget to update. */
function ageFromDob(dob: string): number | null {
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const monthDiff = now.getMonth() - d.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

function Pill({ label, tone, softTone }: { label: string; tone: BadgeTone; softTone: keyof Palette }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.pill, { backgroundColor: colors[softTone] }]}>
      <Text variant="caption" tone={tone}>
        {label}
      </Text>
    </View>
  );
}

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
  const { userId, username } = useDemoUser();
  const { colors } = useAppTheme();
  const queryClient = useQueryClient();
  const profile = useProfile();
  const emis = useEmis();
  const expenses = useExpenses();
  const insurance = useInsurancePolicies();
  const holdings = useHoldings();
  const riskProfile = useRiskProfileLatest();

  const [incomeInput, setIncomeInput] = useState('');
  const [cashInput, setCashInput] = useState('');
  const [dependentsInput, setDependentsInput] = useState('0');
  const [incomeStability, setIncomeStability] = useState<IncomeStability | null>(null);
  const [employmentType, setEmploymentType] = useState<EmploymentType | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [fullNameInput, setFullNameInput] = useState('');
  const [emailInput, setEmailInput] = useState('');
  const [dobInput, setDobInput] = useState('');
  const [phoneInput, setPhoneInput] = useState('');
  const [identityDirty, setIdentityDirty] = useState(false);
  const [identitySaveError, setIdentitySaveError] = useState<string | null>(null);
  const [identitySaved, setIdentitySaved] = useState(false);

  useEffect(() => {
    if (!profile.data || dirty) return;
    setIncomeInput(paiseToRupeeInput(profile.data.income_paise));
    setCashInput(paiseToRupeeInput(profile.data.cash_balance_paise));
    setDependentsInput(String(profile.data.dependents_count));
    setIncomeStability(profile.data.income_stability);
    setEmploymentType(profile.data.employment_type);
  }, [profile.data, dirty]);

  useEffect(() => {
    if (!profile.data || identityDirty) return;
    setFullNameInput(profile.data.full_name ?? '');
    setEmailInput(profile.data.email ?? '');
    setDobInput(profile.data.date_of_birth ?? '');
    setPhoneInput(profile.data.phone_number ?? '');
  }, [profile.data, identityDirty]);

  const dobValid = dobInput.trim() === '' || /^\d{4}-\d{2}-\d{2}$/.test(dobInput.trim());
  const emailLooksValid = emailInput.trim() === '' || emailInput.includes('@');

  const identitySaveMutation = useMutation({
    mutationFn: () =>
      onboardingApi.putProfileIdentity(userId, {
        full_name: fullNameInput.trim() || null,
        email: emailInput.trim() || null,
        date_of_birth: dobInput.trim() || null,
        phone_number: phoneInput.trim() || null,
      }),
    onSuccess: () => {
      setIdentityDirty(false);
      setIdentitySaved(true);
      queryClient.invalidateQueries({ queryKey: qk.profile(userId) });
      setTimeout(() => setIdentitySaved(false), 2500);
    },
    onError: (err) => setIdentitySaveError(toApiError(err).message),
  });

  const age = profile.data?.date_of_birth ? ageFromDob(profile.data.date_of_birth) : null;
  const displayName = profile.data?.full_name?.trim() || username || 'Add your name';
  const tier = riskProfile.data?.final_tier;

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
        // ScreenContainer only puts its own gap between ITS direct children
        // -- this whole block is one of those, so without an explicit gap
        // here the cards below would render flush against each other (same
        // bug already fixed on several other screens this session).
        <View style={styles.resultsGroup}>
          <Reveal index={0}>
            <LinearGradient
              colors={[colors.terracottaSoft, colors.paperRaised]}
              start={{ x: 0, y: 0 }}
              end={{ x: 0.7, y: 1 }}
              style={[styles.heroCard, { borderColor: colors.borderStrong }]}
            >
              <View style={styles.heroRow}>
                <AvatarBadge initials={initialsFrom(profile.data!.full_name, username)} />
                <View style={styles.heroTextCol}>
                  <Text variant="h2">{displayName}</Text>
                  {profile.data!.email ? (
                    <Text variant="caption" tone="muted">
                      {profile.data!.email}
                    </Text>
                  ) : (
                    <Text variant="caption" tone="faint">
                      Add your email below
                    </Text>
                  )}
                  {age !== null ? (
                    <Text variant="caption" tone="faint">
                      {age} yrs old
                    </Text>
                  ) : null}
                </View>
              </View>
              <View style={styles.badgeRow}>
                {tier !== undefined ? (
                  <Pill label={`Tier ${tier} risk profile`} tone={TIER_TONE[tier] ?? 'petrol'} softTone={TIER_SOFT[tier] ?? 'petrolSoft'} />
                ) : null}
                <Pill
                  label={profile.data!.onboarding_completed_at ? 'Onboarding complete' : 'Onboarding in progress'}
                  tone={profile.data!.onboarding_completed_at ? 'positive' : 'warning'}
                  softTone={profile.data!.onboarding_completed_at ? 'positiveSoft' : 'warningSoft'}
                />
              </View>
            </LinearGradient>
          </Reveal>

          <Reveal index={1}>
            <Card style={styles.formCard}>
              <SectionHeader title="Personal information" subtitle="Never shown to anyone else -- only you can see or edit this" />
              <TextField
                label="Full name"
                value={fullNameInput}
                onChangeText={(v) => {
                  setFullNameInput(v);
                  setIdentityDirty(true);
                }}
                placeholder="e.g. Asha Rao"
              />
              <TextField
                label="Email"
                value={emailInput}
                onChangeText={(v) => {
                  setEmailInput(v);
                  setIdentityDirty(true);
                }}
                placeholder="e.g. asha.rao@email.com"
                keyboardType="email-address"
                autoCapitalize="none"
                error={!emailLooksValid ? 'Enter a valid email address.' : undefined}
              />
              <TextField
                label="Date of birth"
                value={dobInput}
                onChangeText={(v) => {
                  setDobInput(v);
                  setIdentityDirty(true);
                }}
                placeholder="YYYY-MM-DD"
                helperText={dobInput.trim() && dobValid ? `That makes you ${ageFromDob(dobInput.trim())} yrs old` : undefined}
                error={!dobValid ? 'Use the format YYYY-MM-DD.' : undefined}
              />
              <TextField
                label="Phone number"
                value={phoneInput}
                onChangeText={(v) => {
                  setPhoneInput(v);
                  setIdentityDirty(true);
                }}
                placeholder="e.g. +91 98765 43210"
                keyboardType="phone-pad"
              />

              {identitySaveError ? <InlineError message={identitySaveError} /> : null}
              {identitySaved ? (
                <Text variant="caption" tone="positive">
                  Saved.
                </Text>
              ) : null}

              <Button
                label="Save changes"
                fullWidth
                disabled={!identityDirty || !dobValid || !emailLooksValid}
                loading={identitySaveMutation.isPending}
                onPress={() => {
                  setIdentitySaveError(null);
                  identitySaveMutation.mutate();
                }}
              />
            </Card>
          </Reveal>

          <Reveal index={2}>
            <Card style={styles.formCard}>
              <SectionHeader title="Financial & household" />
              <TextField
                label="Monthly income"
                value={incomeInput}
                onChangeText={(v) => {
                  setIncomeInput(v);
                  setDirty(true);
                }}
                keyboardType="numeric"
                prefix="₹"
                formatAsCurrency
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
                formatAsCurrency
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
          </Reveal>
        </View>
      )}

      <View style={styles.resultsGroup}>
        <SectionHeader title="Linked portfolio & liabilities" />
        <MenuList
          items={[
          {
            key: 'expenses',
            title: 'Expenses',
            subtitle: activeExpenseCount === null ? 'Manage recurring expenses' : `${activeExpenseCount} active`,
            onPress: () => navigation.navigate('ExpensesManage'),
            icon: 'receipt-outline',
            iconTone: 'petrol',
          },
          {
            key: 'debt',
            title: 'Loans & EMIs',
            subtitle: activeEmiCount === null ? 'Manage loans' : `${activeEmiCount} active`,
            onPress: () => navigation.navigate('DebtManage'),
            icon: 'business-outline',
            iconTone: 'warning',
          },
          {
            key: 'insurance',
            title: 'Insurance',
            subtitle: insurance.data ? `${insurance.data.length} polic${insurance.data.length === 1 ? 'y' : 'ies'}` : 'Manage insurance',
            onPress: () => navigation.navigate('InsuranceManage'),
            icon: 'shield-checkmark-outline',
            iconTone: 'positive',
          },
          {
            key: 'holdings',
            title: 'Holdings',
            subtitle: holdings.data ? `${holdings.data.length} holding${holdings.data.length === 1 ? '' : 's'}` : 'Manage holdings',
            onPress: () => navigation.navigate('HoldingsManage'),
            icon: 'trending-up-outline',
            iconTone: 'terracotta',
          },
          {
            key: 'calls',
            title: 'Your calls',
            subtitle: 'Transcripts of your calls with Nudge',
            onPress: () => navigation.navigate('YourCalls'),
            icon: 'call-outline',
            iconTone: 'terracotta',
          },
          {
            key: 'settings',
            title: 'Settings',
            subtitle: 'Account & app preferences',
            onPress: () => navigation.navigate('Settings'),
            icon: 'settings-outline',
            iconTone: 'petrol',
          },
        ]}
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  resultsGroup: { gap: SPACE.lg },
  formCard: { gap: SPACE.md },
  heroCard: { gap: SPACE.md, borderRadius: RADIUS.lg, borderWidth: StyleSheet.hairlineWidth * 1.5, padding: SPACE.lg },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.md },
  heroTextCol: { flex: 1, gap: 2 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.sm },
  pill: { paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: RADIUS.pill, alignSelf: 'flex-start' },
});

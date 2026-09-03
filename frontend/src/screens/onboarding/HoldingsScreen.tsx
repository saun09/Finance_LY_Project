import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import type { HoldingOut, HoldingType } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { RADIUS, SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Holdings'>;

/** Grouped purely for readability while entering data -- 24 raw options in
 * one flat list is unscannable. The grouping is cosmetic only; the actual
 * cash/debt/equity/real-assets/alternatives classification is the
 * backend's own HOLDING_TYPE_PROFILES_V1 table, never recomputed here. */
const HOLDING_TYPE_GROUPS: { group: string; options: { value: HoldingType; label: string }[] }[] = [
  {
    group: 'Cash & bank',
    options: [
      { value: 'savings_account', label: 'Savings account' },
      { value: 'liquid_or_overnight_fund', label: 'Liquid / overnight fund' },
      { value: 'fixed_deposit', label: 'Fixed deposit' },
      { value: 'recurring_deposit', label: 'Recurring deposit' },
    ],
  },
  {
    group: 'Retirement',
    options: [
      { value: 'ppf', label: 'PPF' },
      { value: 'epf', label: 'EPF' },
      { value: 'nps', label: 'NPS' },
    ],
  },
  {
    group: 'Debt & equity funds',
    options: [
      { value: 'debt_mutual_fund', label: 'Debt mutual fund' },
      { value: 'direct_equity', label: 'Direct equity (stocks)' },
      { value: 'equity_mutual_fund', label: 'Equity mutual fund' },
      { value: 'elss', label: 'ELSS' },
    ],
  },
  {
    group: 'Hybrid funds',
    options: [
      { value: 'hybrid_mutual_fund_aggressive', label: 'Hybrid — aggressive' },
      { value: 'hybrid_mutual_fund_balanced', label: 'Hybrid — balanced' },
      { value: 'hybrid_mutual_fund_conservative', label: 'Hybrid — conservative' },
    ],
  },
  {
    group: 'Gold & real assets',
    options: [
      { value: 'gold_etf', label: 'Gold ETF' },
      { value: 'sovereign_gold_bond', label: 'Sovereign gold bond' },
      { value: 'physical_gold', label: 'Physical gold' },
      { value: 'real_estate_direct', label: 'Real estate (direct)' },
      { value: 'reit_invit', label: 'REIT / InvIT' },
    ],
  },
  {
    group: 'Alternatives & insurance-linked',
    options: [
      { value: 'p2p_lending', label: 'P2P lending' },
      { value: 'cryptocurrency', label: 'Cryptocurrency' },
      { value: 'unlisted_equity_or_aif', label: 'Unlisted equity / AIF' },
      { value: 'ulip', label: 'ULIP' },
      { value: 'endowment_or_moneyback_policy', label: 'Endowment / moneyback policy' },
    ],
  },
];

export function HoldingsScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();
  const { colors } = useAppTheme();

  const [items, setItems] = useState<HoldingOut[]>([]);
  const [description, setDescription] = useState('');
  const [valueInput, setValueInput] = useState('');
  const [holdingType, setHoldingType] = useState<HoldingType | null>(null);
  const [skipType, setSkipType] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const value_paise = rupeeInputToPaise(valueInput);
      if (!description.trim() || value_paise === null || (!skipType && !holdingType)) {
        throw new Error('validation');
      }
      return onboardingApi.postHolding(userId, {
        description: description.trim(),
        value_paise,
        holding_type: skipType ? null : holdingType,
      });
    },
    onSuccess: (created) => {
      setItems((prev) => [...prev, created]);
      setDescription('');
      setValueInput('');
      setHoldingType(null);
      setSkipType(false);
    },
    onError: (err) => {
      setFormError(
        err instanceof Error && err.message === 'validation'
          ? 'Enter a description, a value, and either a type or "not sure".'
          : toApiError(err).message,
      );
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
        <TextField
          label="Description"
          value={description}
          onChangeText={setDescription}
          placeholder="HDFC Flexicap SIP"
        />
        <TextField
          label="Current value"
          value={valueInput}
          onChangeText={setValueInput}
          placeholder="250000"
          keyboardType="numeric"
          prefix="₹"
        />

        <View style={styles.typeHeaderRow}>
          <Text variant="label" tone="muted">
            TYPE
          </Text>
          <Pressable onPress={() => { setSkipType((v) => !v); setHoldingType(null); }} hitSlop={8}>
            <Text variant="caption" tone={skipType ? 'terracotta' : 'faint'}>
              {skipType ? '✓ Not sure' : "I'm not sure"}
            </Text>
          </Pressable>
        </View>

        {!skipType &&
          HOLDING_TYPE_GROUPS.map((g) => (
            <View key={g.group} style={styles.group}>
              <Text variant="caption" tone="faint">
                {g.group.toUpperCase()}
              </Text>
              <View style={styles.chipWrap}>
                {g.options.map((opt) => {
                  const selected = opt.value === holdingType;
                  return (
                    <Pressable
                      key={opt.value}
                      onPress={() => setHoldingType(opt.value)}
                      style={[
                        styles.chip,
                        {
                          backgroundColor: selected ? colors.terracotta : colors.paper,
                          borderColor: selected ? colors.terracotta : colors.border,
                        },
                      ]}
                    >
                      <Text variant="caption" tone={selected ? 'onDark' : 'ink'}>
                        {opt.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}

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
  typeHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  group: { gap: SPACE.xs },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.xs },
  chip: {
    paddingHorizontal: SPACE.md,
    paddingVertical: SPACE.xs + 2,
    borderRadius: RADIUS.pill,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  footer: { marginTop: SPACE.md, gap: SPACE.sm },
  footnote: { textAlign: 'center' },
});

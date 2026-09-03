import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import type { HoldingType } from '../api/types';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';
import { Text } from './Text';

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

interface Props {
  value: HoldingType | null;
  onChange: (value: HoldingType | null) => void;
}

/** holding_type is nullable server-side (Module 4 requires it before
 * classifying, but Module 2 doesn't demand it up front) -- "not sure"
 * toggles to null rather than forcing a guess. */
export function HoldingTypePicker({ value, onChange }: Props) {
  const { colors } = useAppTheme();
  const skipType = value === null;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text variant="label" tone="muted">
          TYPE
        </Text>
        <Pressable onPress={() => onChange(null)} hitSlop={8}>
          <Text variant="caption" tone={skipType ? 'terracotta' : 'faint'}>
            {skipType ? '✓ Not sure' : "I'm not sure"}
          </Text>
        </Pressable>
      </View>

      {HOLDING_TYPE_GROUPS.map((g) => (
        <View key={g.group} style={styles.group}>
          <Text variant="caption" tone="faint">
            {g.group.toUpperCase()}
          </Text>
          <View style={styles.chipWrap}>
            {g.options.map((opt) => {
              const selected = opt.value === value;
              return (
                <Pressable
                  key={opt.value}
                  onPress={() => onChange(opt.value)}
                  style={[
                    styles.chip,
                    { backgroundColor: selected ? colors.terracotta : colors.paper, borderColor: selected ? colors.terracotta : colors.border },
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: SPACE.sm },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  group: { gap: SPACE.xs },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.xs },
  chip: {
    paddingHorizontal: SPACE.md,
    paddingVertical: SPACE.xs + 2,
    borderRadius: RADIUS.pill,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
});

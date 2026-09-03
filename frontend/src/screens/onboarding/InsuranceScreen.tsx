import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import type { InsurancePolicyOut, InsuranceType } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
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

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Insurance'>;

const POLICY_TYPE_OPTIONS: { value: InsuranceType; label: string }[] = [
  { value: 'life', label: 'Life' },
  { value: 'health', label: 'Health' },
];

export function InsuranceScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();

  const [items, setItems] = useState<InsurancePolicyOut[]>([]);
  const [policyType, setPolicyType] = useState<InsuranceType | null>(null);
  const [sumAssuredInput, setSumAssuredInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const sum_assured_paise = rupeeInputToPaise(sumAssuredInput);
      if (!policyType || sum_assured_paise === null) throw new Error('validation');
      return onboardingApi.postInsurancePolicy(userId, { policy_type: policyType, sum_assured_paise });
    },
    onSuccess: (created) => {
      setItems((prev) => [...prev, created]);
      setPolicyType(null);
      setSumAssuredInput('');
    },
    onError: (err) => {
      setFormError(
        err instanceof Error && err.message === 'validation'
          ? 'Choose a policy type and enter the sum assured.'
          : toApiError(err).message,
      );
    },
  });

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={4}
        total={7}
        title="Life & health insurance"
        subtitle="Sum assured only, not premiums — this checks whether you're adequately covered, not what you pay."
      />

      {items.length > 0 ? (
        <Card>
          {items.map((item) => (
            <ListRow
              key={item.id}
              title={item.policy_type === 'life' ? 'Life insurance' : 'Health insurance'}
              trailing={formatPaise(item.sum_assured_paise)}
            />
          ))}
        </Card>
      ) : null}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD A POLICY
        </Text>
        <ChoiceGroup label="Type" options={POLICY_TYPE_OPTIONS} value={policyType} onChange={setPolicyType} />
        <TextField
          label="Sum assured"
          value={sumAssuredInput}
          onChangeText={setSumAssuredInput}
          placeholder="1000000"
          keyboardType="numeric"
          prefix="₹"
        />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add policy"
          variant="secondary"
          loading={addMutation.isPending}
          onPress={() => {
            setFormError(null);
            addMutation.mutate();
          }}
        />
      </Card>

      <View style={styles.footer}>
        <Button label="Continue" fullWidth onPress={() => navigation.navigate('Holdings')} />
        {items.length === 0 ? (
          <Text variant="caption" tone="faint" style={styles.footnote}>
            No policies yet? That's useful to know too — it can surface as a real gap in your plan.
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

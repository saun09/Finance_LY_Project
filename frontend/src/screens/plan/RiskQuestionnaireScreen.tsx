import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { riskProfileApi } from '../../api/riskProfile';
import { qk } from '../../api/queryClient';
import { Button } from '../../components/Button';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useDemoUser } from '../../context/DemoUserContext';
import { useQuestionnaire } from '../../hooks/useRiskProfile';
import { SPACE } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';

type Nav = NativeStackNavigationProp<PlanStackParamList, 'RiskQuestionnaire'>;

export function RiskQuestionnaireScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data: questionnaire, isPending, error, refetch } = useQuestionnaire();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const submitMutation = useMutation({
    mutationFn: () => riskProfileApi.submitAnswers(userId, answers),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.riskProfileLatest(userId) });
      queryClient.invalidateQueries({ queryKey: qk.allocation(userId) });
      navigation.navigate('RiskProfile');
    },
    onError: (err) => setSubmitError(toApiError(err).message),
  });

  if (isPending) {
    return (
      <ScreenContainer>
        <Text variant="display">Risk questionnaire</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (error || !questionnaire) {
    return (
      <ScreenContainer>
        <Text variant="display">Risk questionnaire</Text>
        <ErrorState message={error?.message ?? 'Could not load the questionnaire.'} onRetry={() => refetch()} />
      </ScreenContainer>
    );
  }

  const allAnswered = questionnaire.questions.every((q) => answers[q.id]);

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Risk questionnaire · v{questionnaire.version}
        </Text>
        <Text variant="display">A few questions</Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          Your answers set your stated risk tolerance — this is then checked against what your finances can
          actually support.
        </Text>
      </View>

      {questionnaire.questions.map((q) => (
        <ChoiceGroup
          key={q.id}
          label={q.text}
          uppercaseLabel={false}
          options={q.options}
          value={answers[q.id] ?? null}
          onChange={(value) => setAnswers((prev) => ({ ...prev, [q.id]: value }))}
        />
      ))}

      {submitError ? <InlineError message={submitError} /> : null}

      <View style={styles.footer}>
        <Button
          label="Submit answers"
          fullWidth
          disabled={!allAnswered}
          loading={submitMutation.isPending}
          onPress={() => {
            setSubmitError(null);
            submitMutation.mutate();
          }}
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },
  footer: { marginTop: SPACE.md },
});

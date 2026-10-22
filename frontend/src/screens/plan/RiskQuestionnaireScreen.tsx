import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { riskProfileApi } from '../../api/riskProfile';
import { qk } from '../../api/queryClient';
import { Button } from '../../components/Button';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ProgressBar } from '../../components/ProgressBar';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useDemoUser } from '../../context/DemoUserContext';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useQuestionnaire } from '../../hooks/useRiskProfile';
import { useAppTheme } from '../../theme/ThemeContext';
import { RADIUS, SPACE } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';

type Nav = NativeStackNavigationProp<PlanStackParamList, 'RiskQuestionnaire'>;

/** One selectable answer: a full-width row, not a wrapped pill, so each
 * option reads as its own tappable target instead of competing for space
 * in a crowded wrap. Selection is shown three ways at once (border,
 * background tint, and the trailing icon) -- never color alone -- with a
 * small spring scale for a tactile "this one" feel. */
function OptionCard({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const { colors } = useAppTheme();
  const reducedMotion = useReducedMotion();
  const scale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (reducedMotion) {
      scale.setValue(selected ? 1.02 : 1);
      return;
    }
    Animated.spring(scale, { toValue: selected ? 1.02 : 1, useNativeDriver: true, speed: 20, bounciness: 6 }).start();
  }, [selected, reducedMotion, scale]);

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <Pressable
        onPress={onPress}
        accessibilityRole="radio"
        accessibilityState={{ selected }}
        style={[
          styles.optionCard,
          { backgroundColor: selected ? colors.terracottaSoft : colors.paperRaised, borderColor: selected ? colors.terracotta : colors.border },
        ]}
      >
        <Text variant="bodyMedium" style={styles.optionLabel}>
          {label}
        </Text>
        <Ionicons name={selected ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={selected ? colors.terracotta : colors.inkFaint} />
      </Pressable>
    </Animated.View>
  );
}

/** Fade + a short horizontal slide, direction-aware (forward moves in
 * from the right, back from the left) -- replayed on every step change by
 * keying the wrapper on the question id. Respects reduced motion. */
function useStepTransition(step: number, direction: 1 | -1) {
  const reducedMotion = useReducedMotion();
  const anim = useRef(new Animated.Value(reducedMotion ? 1 : 0)).current;

  useEffect(() => {
    if (reducedMotion) {
      anim.setValue(1);
      return;
    }
    anim.setValue(0);
    const animation = Animated.timing(anim, { toValue: 1, duration: 320, useNativeDriver: true });
    animation.start();
    return () => animation.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, reducedMotion]);

  return {
    opacity: anim,
    transform: [{ translateX: anim.interpolate({ inputRange: [0, 1], outputRange: [direction * 24, 0] }) }],
  };
}

export function RiskQuestionnaireScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data: questionnaire, isPending, error, refetch } = useQuestionnaire();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);

  const submitMutation = useMutation({
    mutationFn: () => riskProfileApi.submitAnswers(userId, answers),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.riskProfileLatest(userId) });
      queryClient.invalidateQueries({ queryKey: qk.allocation(userId) });
      navigation.navigate('RiskProfile');
    },
    onError: (err) => setSubmitError(toApiError(err).message),
  });

  const total = questionnaire?.questions.length ?? 0;
  const currentQuestion = questionnaire?.questions[step];
  const transitionStyle = useStepTransition(step, direction);

  if (isPending) {
    return (
      <ScreenContainer>
        <Text variant="display">Risk questionnaire</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (error || !questionnaire || !currentQuestion) {
    return (
      <ScreenContainer>
        <Text variant="display">Risk questionnaire</Text>
        <ErrorState message={error?.message ?? 'Could not load the questionnaire.'} onRetry={() => refetch()} />
      </ScreenContainer>
    );
  }

  const isLastStep = step === total - 1;
  const canAdvance = !!answers[currentQuestion.id];
  const progressFraction = (step + 1) / total;
  const progressPct = Math.round(progressFraction * 100);

  const goNext = () => {
    if (isLastStep) {
      setSubmitError(null);
      submitMutation.mutate();
      return;
    }
    setDirection(1);
    setStep((s) => Math.min(s + 1, total - 1));
  };

  const goBack = () => {
    setDirection(-1);
    setStep((s) => Math.max(s - 1, 0));
  };

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Risk questionnaire
        </Text>
        <Text variant="display">A few questions</Text>
        {step === 0 ? (
          <Text variant="body" tone="muted" style={styles.subtitle}>
            Your answers set your stated risk tolerance — this is then checked against what your finances can
            actually support.
          </Text>
        ) : null}
      </View>

      <View style={styles.progressWrap}>
        <View style={styles.progressLabelRow}>
          <Text variant="label" tone="muted">
            QUESTION {step + 1} OF {total}
          </Text>
          <Text variant="label" tone="terracotta">
            {progressPct}% COMPLETED
          </Text>
        </View>
        <ProgressBar fraction={progressFraction} tone="terracotta" duration={400} height={6} />
      </View>

      <Animated.View key={currentQuestion.id} style={[styles.questionBlock, transitionStyle]}>
        <Text variant="h1" style={styles.questionPrompt}>
          {currentQuestion.text}
        </Text>
        <View style={styles.optionList}>
          {currentQuestion.options.map((opt) => (
            <OptionCard
              key={opt.value}
              label={opt.label}
              selected={answers[currentQuestion.id] === opt.value}
              onPress={() => setAnswers((prev) => ({ ...prev, [currentQuestion.id]: opt.value }))}
            />
          ))}
        </View>
      </Animated.View>

      {submitError ? <InlineError message={submitError} /> : null}

      <View style={styles.footer}>
        {step > 0 ? (
          <View style={styles.footerRow}>
            <Button label="Back" variant="ghost" onPress={goBack} />
            <View style={styles.footerContinue}>
              <Button
                label={isLastStep ? 'Submit answers' : 'Continue'}
                fullWidth
                disabled={!canAdvance}
                loading={isLastStep && submitMutation.isPending}
                onPress={goNext}
              />
            </View>
          </View>
        ) : (
          <Button
            label={isLastStep ? 'Submit answers' : 'Continue'}
            fullWidth
            disabled={!canAdvance}
            loading={isLastStep && submitMutation.isPending}
            onPress={goNext}
          />
        )}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },

  progressWrap: { gap: SPACE.xs },
  progressLabelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },

  questionBlock: { gap: SPACE.lg },
  questionPrompt: {},
  optionList: { gap: SPACE.sm },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: SPACE.sm,
    paddingHorizontal: SPACE.lg,
    paddingVertical: SPACE.md,
    borderRadius: RADIUS.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  optionLabel: { flex: 1 },

  footer: { marginTop: SPACE.md, gap: SPACE.sm },
  footerRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  footerContinue: { flex: 1 },
});

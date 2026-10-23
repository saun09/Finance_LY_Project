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
import { IconChip } from '../../components/IconChip';
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
 * keying the wrapper on a step identifier. Respects reduced motion. */
function useStepTransition(stepKey: string, direction: 1 | -1) {
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
  }, [stepKey, reducedMotion]);

  return {
    opacity: anim,
    transform: [{ translateX: anim.interpolate({ inputRange: [0, 1], outputRange: [direction * 24, 0] }) }],
  };
}

export function RiskQuestionnaireScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data: questionnaire, isPending, error, refetch } = useQuestionnaire();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  // True right after the last "main" question is answered -- a one-time
  // fork in the flow (quick estimate vs. keep going for a precise score),
  // not a numbered step of its own.
  const [awaitingModeChoice, setAwaitingModeChoice] = useState(false);

  const submit = (answerSet: Record<string, string>) => {
    setSubmitError(null);
    submitMutation.mutate(answerSet);
  };

  const submitMutation = useMutation({
    mutationFn: (answerSet: Record<string, string>) => riskProfileApi.submitAnswers(userId, answerSet),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.riskProfileLatest(userId) });
      queryClient.invalidateQueries({ queryKey: qk.allocation(userId) });
      navigation.navigate('RiskProfile');
    },
    onError: (err) => setSubmitError(toApiError(err).message),
  });

  // The 4 "main" questions first, the 3 optional ones after -- so a quick
  // submission is always "the first N answers so far", with no separate
  // subsetting needed at submit time. Safe empty fallbacks while
  // `questionnaire` hasn't loaded yet, so every hook below (useStepTransition)
  // is still called on every render regardless of loading/error state --
  // conditionally returning before a hook call is what React's rules
  // actually forbid, not computing a derived empty value.
  const requiredIds = questionnaire?.required_question_ids ?? [];
  const orderedQuestions = questionnaire
    ? [
        ...requiredIds
          .map((id) => questionnaire.questions.find((q) => q.id === id))
          .filter((q): q is NonNullable<typeof q> => !!q),
        ...questionnaire.questions.filter((q) => !requiredIds.includes(q.id)),
      ]
    : [];
  const total = orderedQuestions.length;
  const requiredCount = requiredIds.length;
  const currentQuestion = orderedQuestions[step];
  const transitionStyle = useStepTransition(awaitingModeChoice ? 'mode-choice' : (currentQuestion?.id ?? 'loading'), direction);

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
  const isLastRequiredStep = step === requiredCount - 1;
  const canAdvance = !!answers[currentQuestion.id];
  const progressFraction = (step + 1) / total;
  const progressPct = Math.round(progressFraction * 100);

  const goNext = () => {
    if (isLastStep) {
      submit(answers);
      return;
    }
    setDirection(1);
    if (isLastRequiredStep) {
      setAwaitingModeChoice(true);
      return;
    }
    setStep((s) => s + 1);
  };

  const goBack = () => {
    if (awaitingModeChoice) {
      setDirection(-1);
      setAwaitingModeChoice(false);
      return;
    }
    setDirection(-1);
    setStep((s) => Math.max(s - 1, 0));
  };

  const continueToOptional = () => {
    setDirection(1);
    setAwaitingModeChoice(false);
    setStep(requiredCount);
  };

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Risk questionnaire
        </Text>
        <Text variant="display">A few questions</Text>
        {step === 0 && !awaitingModeChoice ? (
          <Text variant="body" tone="muted" style={styles.subtitle}>
            Your answers set your stated risk tolerance — this is then checked against what your finances can
            actually support.
          </Text>
        ) : null}
      </View>

      <View style={styles.progressWrap}>
        <View style={styles.progressLabelRow}>
          <Text variant="label" tone="muted">
            {awaitingModeChoice ? 'MAIN QUESTIONS DONE' : `QUESTION ${step + 1} OF ${total}`}
          </Text>
          <Text variant="label" tone="terracotta">
            {progressPct}% COMPLETED
          </Text>
        </View>
        <ProgressBar fraction={progressFraction} tone="terracotta" duration={400} height={6} />
      </View>

      {awaitingModeChoice ? (
        <Animated.View style={[styles.decisionBlock, transitionStyle]}>
          <IconChip name="flash-outline" tone="terracotta" size={48} />
          <Text variant="h1" style={styles.decisionTitle}>
            You've answered the main questions
          </Text>
          <Text variant="body" tone="muted" style={styles.decisionBody}>
            A trained model can estimate your risk tier from just these 4 answers right now, or you can answer 3
            more questions for a precise, formula-based score instead of an estimate.
          </Text>
          <Button label="Get my estimate now" fullWidth loading={submitMutation.isPending} onPress={() => submit(answers)} />
          <Button label="Answer 3 more for precision" variant="ghost" fullWidth onPress={continueToOptional} />
        </Animated.View>
      ) : (
        <Animated.View style={[styles.questionBlock, transitionStyle]}>
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
      )}

      {submitError ? <InlineError message={submitError} /> : null}

      {!awaitingModeChoice ? (
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
      ) : (
        <Pressable onPress={goBack} style={styles.decisionBackLink} accessibilityRole="button" accessibilityLabel="Back">
          <Ionicons name="chevron-back" size={16} color={colors.inkFaint} />
          <Text variant="caption" tone="muted">
            Back
          </Text>
        </Pressable>
      )}
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

  decisionBlock: { alignItems: 'center', gap: SPACE.sm, paddingVertical: SPACE.lg },
  decisionTitle: { textAlign: 'center' },
  decisionBody: { textAlign: 'center', marginBottom: SPACE.sm },
  decisionBackLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 2, marginTop: SPACE.md, paddingVertical: SPACE.sm },

  footer: { marginTop: SPACE.md, gap: SPACE.sm },
  footerRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  footerContinue: { flex: 1 },
});

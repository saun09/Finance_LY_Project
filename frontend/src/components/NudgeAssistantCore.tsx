import { Ionicons } from '@expo/vector-icons';
import { ConversationProvider, useConversation } from '@elevenlabs/react';
import { useQueryClient } from '@tanstack/react-query';
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Modal, PanResponder, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { CallTranscript, type TranscriptLine } from './CallTranscript';
import { Text } from './Text';
import { nudgeApi } from '../api/nudge';
import { qk } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';
import { useAppTheme } from '../theme/ThemeContext';
import { RADIUS, SPACE } from '../theme/tokens';

/**
 * The Nudge voice assistant, shared by every platform. `@elevenlabs/react-native`
 * is only a re-export of `@elevenlabs/react`, so the same hook drives the
 * conversation on Android, iOS and web; the platform entry points
 * (NudgeAssistant.native.tsx / NudgeAssistant.web.tsx) only add their own
 * setup and how to ask for the microphone.
 */

/** Resolves to null once the microphone may be used, or to a message to
 * show the user when it can't. */
export type RequestMicrophone = () => Promise<string | null>;

const NUDGE_AGENT_ID = 'agent_7901m5jcp9ngfzb8ssr55wcvmhf4';

/**
 * Must match the client tool configured on the ElevenLabs agent (name
 * `search_user_finances`, one required string parameter `query`, "Wait for
 * response" on). The agent calls it for details the session briefing left
 * out; the backend answers with TF-IDF retrieval over the user's own
 * records and past Nudge conversations (backend/app/services/nudge_knowledge.py).
 */
const SEARCH_TOOL_NAME = 'search_user_finances';

/**
 * Per-screen opening lines (`firstMessage` below) are sent as a session
 * override, which ElevenLabs refuses -- closing the session with "Override
 * for field 'first_message' is not allowed by config" -- unless the agent's
 * Security settings allow overriding the first message. Off by default so
 * Nudge works with the agent as configured; with it off the agent opens
 * with its own first message and the screen's focus still arrives as a
 * contextual update. Flip to true only after enabling that override.
 */
const FIRST_MESSAGE_OVERRIDE_ENABLED = false;

type NudgeSurface = 'home' | 'progress' | 'insights' | 'risk-profile' | 'allocation';
type NudgeContext = {
  surface: NudgeSurface;
  details?: string;
};
type NudgeAssistantValue = {
  openNudge: (context: NudgeContext) => void;
};

const NudgeAssistantContext = createContext<NudgeAssistantValue | null>(null);

// `guidance` is shown to the user; `agentFocus` is sent to the agent as a
// contextual update alongside the financial briefing.
const SURFACE_COPY: Record<NudgeSurface, { title: string; firstMessage: string; guidance: string; agentFocus: string }> = {
  home: {
    title: 'Talk to Nudge',
    firstMessage: "Hi, I'm Nudge. What would you like to make clearer about your finances today?",
    guidance:
      'Ask a money question or talk through a decision. Nudge knows your loans, expenses, savings and goals from the app, so its advice fits your whole situation.',
    agentFocus: 'The user opened Nudge from the Home screen for a general money question or help getting organized.',
  },
  progress: {
    title: 'Plan a life event',
    firstMessage: 'What life event are you planning for, and roughly when do you expect it?',
    guidance:
      'Nudge will help organize the event, timing, estimated cost, and savings goal, checked against your current surplus and loans. Review the summary yourself; Nudge cannot save it to the app yet.',
    agentFocus:
      'The user wants to plan a life event. Help them pin down the event, timing, estimated cost and a monthly savings goal, and check that goal against their monthly surplus, loan EMIs and emergency buffer. You cannot save the plan into the app, so summarize it at the end for them to note down.',
  },
  insights: {
    title: 'Learn with Nudge',
    firstMessage: 'What financial concept or recommendation would you like me to explain?',
    guidance: 'Ask about any financial idea. Nudge explains in plain language, using your own numbers as examples where it helps.',
    agentFocus:
      'The user wants a financial concept explained in plain language with short examples; where it helps, relate the example to their own numbers.',
  },
  'risk-profile': {
    title: 'Understand your risk profile',
    firstMessage: 'What would you like to understand about your risk profile?',
    guidance: 'Nudge can explain the risk-profile details shown on this page and how your finances shape them.',
    agentFocus: 'The user wants to understand their risk profile, as shown on the page they opened Nudge from.',
  },
  allocation: {
    title: 'Understand your target mix',
    firstMessage: 'What would you like to know about your target allocation?',
    guidance: 'Nudge can explain the target allocation shown on this page and how it fits with your loans and savings.',
    agentFocus: 'The user wants to understand their target allocation, as shown on the page they opened Nudge from.',
  },
};

export function useNudgeAssistant() {
  const value = useContext(NudgeAssistantContext);
  if (!value) throw new Error('useNudgeAssistant must be used within NudgeAssistantProvider');
  return value;
}

export function NudgeAssistantCoreProvider({
  children,
  requestMicrophone,
}: {
  children: React.ReactNode;
  requestMicrophone: RequestMicrophone;
}) {
  return (
    <ConversationProvider>
      <NudgeAssistantContent requestMicrophone={requestMicrophone}>{children}</NudgeAssistantContent>
    </ConversationProvider>
  );
}

function NudgeAssistantContent({
  children,
  requestMicrophone,
}: {
  children: React.ReactNode;
  requestMicrophone: RequestMicrophone;
}) {
  const [context, setContext] = useState<NudgeContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  // the live call's lines, shown as they're spoken; kept after hanging up
  // so the user can finish reading, cleared when the sheet closes
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  // whether this call is being stored (false if the backend was unreachable)
  const [savingCall, setSavingCall] = useState(false);
  const lineCounterRef = useRef(0);
  const transcriptScrollRef = useRef<ScrollView>(null);
  const sentContextRef = useRef<string | null>(null);
  const queryClient = useQueryClient();
  const { userId } = useDemoUser();
  const { colors } = useAppTheme();
  const copy = context ? SURFACE_COPY[context.surface] : SURFACE_COPY.home;

  // Refs, not state: the SDK callbacks and client tool below run outside
  // React's render cycle and must always see the current session's ids.
  const userIdRef = useRef(userId);
  userIdRef.current = userId;
  // backend id of the stored conversation (null when nothing is being saved)
  const storedConversationIdRef = useRef<string | null>(null);
  const elevenLabsConversationIdRef = useRef<string | null>(null);
  // the financial briefing waiting to be sent once the session connects
  const pendingBriefingRef = useRef<string | null>(null);

  const saveMessage = (role: 'user' | 'agent', text: string) => {
    const conversationId = storedConversationIdRef.current;
    if (!conversationId || !userIdRef.current || !text.trim()) return;
    // a failed save must never interrupt the call itself
    nudgeApi.addMessage(userIdRef.current, conversationId, role, text).catch(() => {});
  };

  const finishStoredConversation = () => {
    const conversationId = storedConversationIdRef.current;
    storedConversationIdRef.current = null;
    const user = userIdRef.current;
    if (conversationId && user) {
      nudgeApi
        .endConversation(user, conversationId, elevenLabsConversationIdRef.current)
        .then(() => queryClient.invalidateQueries({ queryKey: qk.nudgeCalls(user) }))
        .catch(() => {});
    }
    elevenLabsConversationIdRef.current = null;
  };

  const searchUserFinances = async (parameters: { query?: unknown }) => {
    const query = typeof parameters?.query === 'string' ? parameters.query.trim() : '';
    if (!query) return `Call ${SEARCH_TOOL_NAME} again with a short "query" describing what to look up.`;
    if (!userIdRef.current) return 'The user is not signed in, so no personal financial records are available.';
    try {
      const result = await nudgeApi.search(userIdRef.current, {
        query,
        conversation_id: storedConversationIdRef.current,
      });
      return result.result_text;
    } catch {
      return "The app's records could not be reached right now. Answer from the context you already have and tell the user you could not check the details.";
    }
  };

  const conversation = useConversation({
    overrides: FIRST_MESSAGE_OVERRIDE_ENABLED ? { agent: { firstMessage: copy.firstMessage } } : undefined,
    onConnect: ({ conversationId }) => {
      elevenLabsConversationIdRef.current = conversationId;
    },
    onMessage: ({ role, message }) => {
      if (!message.trim()) return;
      lineCounterRef.current += 1;
      const line = { id: `live-${lineCounterRef.current}`, role, text: message.trim() };
      setTranscript((lines) => [...lines, line]);
      saveMessage(role, message);
    },
    onDisconnect: () => finishStoredConversation(),
    // the SDK's message is often just "Server error: Unknown error"; the
    // actual reason ElevenLabs gave travels in the context argument
    onError: (message, errorContext) => {
      const detail = errorContext?.debugMessage ?? errorContext?.errorType;
      setError(detail ? `${String(message)} (${detail})` : String(message));
    },
  });

  const contextUpdate = useMemo(() => {
    if (!context) return null;
    const focus = SURFACE_COPY[context.surface].agentFocus;
    return context.details ? `${focus}\n\nPage details: ${context.details}` : focus;
  }, [context]);

  useEffect(() => {
    if (conversation.status !== 'connected') {
      sentContextRef.current = null;
      return;
    }
    try {
      if (pendingBriefingRef.current) {
        conversation.sendContextualUpdate(pendingBriefingRef.current);
        pendingBriefingRef.current = null;
      }
      if (contextUpdate && sentContextRef.current !== contextUpdate) {
        conversation.sendContextualUpdate(contextUpdate);
        sentContextRef.current = contextUpdate;
      }
    } catch (contextError) {
      setError(contextError instanceof Error ? contextError.message : 'Could not share context with Nudge.');
    }
  }, [contextUpdate, conversation.status, conversation.sendContextualUpdate]);

  const openNudge = (nextContext: NudgeContext) => {
    setError(null);
    setContext(nextContext);
  };

  const startConversation = async () => {
    setError(null);
    try {
      const microphoneError = await requestMicrophone();
      if (microphoneError) {
        setError(microphoneError);
        return;
      }
      const surface = context?.surface ?? 'home';
      pendingBriefingRef.current = null;
      setTranscript([]);
      setSavingCall(false);
      if (userIdRef.current) {
        try {
          const stored = await nudgeApi.startConversation(userIdRef.current, surface);
          storedConversationIdRef.current = stored.id;
          setSavingCall(true);
          const { briefing } = await nudgeApi.briefing(userIdRef.current, surface, stored.id);
          pendingBriefingRef.current = briefing;
        } catch {
          // still let the user talk -- Nudge just answers without their records
          setError("Couldn't load your financial details, so Nudge will answer generally and this conversation may not be saved.");
        }
      }
      await conversation.startSession({
        agentId: NUDGE_AGENT_ID,
        clientTools: { [SEARCH_TOOL_NAME]: searchUserFinances },
      });
    } catch (startError) {
      finishStoredConversation();
      setError(startError instanceof Error ? startError.message : 'Could not connect to Nudge. Please try again.');
    }
  };

  /** Hangs up but leaves the sheet (and transcript) open. */
  const hangUp = async () => {
    try {
      if (conversation.status !== 'disconnected') await conversation.endSession();
      finishStoredConversation();
    } catch (endError) {
      setError(endError instanceof Error ? endError.message : 'Could not end the conversation cleanly.');
    }
  };

  // Drag the grab handle down to dismiss, like any pull-up sheet.
  const sheetDrag = useRef(new Animated.Value(0)).current;

  const closeSheet = async () => {
    await hangUp();
    setContext(null);
    setError(null);
    setTranscript([]);
    sheetDrag.setValue(0);
  };

  const closeSheetRef = useRef(closeSheet);
  closeSheetRef.current = closeSheet;
  const handlePan = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_e, g) => g.dy > 4,
      onPanResponderMove: (_e, g) => sheetDrag.setValue(Math.max(0, g.dy)),
      onPanResponderRelease: (_e, g) => {
        if (g.dy > 120 || g.vy > 1.2) void closeSheetRef.current();
        else Animated.spring(sheetDrag, { toValue: 0, useNativeDriver: true }).start();
      },
    }),
  ).current;

  // once a call has started, the sheet becomes a full-height transcript
  const showTranscript = conversation.status === 'connected' || conversation.status === 'connecting' || transcript.length > 0;
  const pendingLabel =
    conversation.status === 'connecting'
      ? 'Connecting…'
      : conversation.status === 'connected'
        ? conversation.isSpeaking
          ? 'Nudge is speaking…'
          : 'Listening…'
        : null;

  return (
    <NudgeAssistantContext.Provider value={{ openNudge }}>
      {children}
      <Modal
        visible={context !== null}
        transparent
        animationType="slide"
        onRequestClose={() => void closeSheet()}
      >
          <View style={styles.backdrop}>
            <Animated.View
              style={[
                styles.sheet,
                showTranscript && styles.sheetExpanded,
                { backgroundColor: colors.paperRaised, borderColor: colors.border, transform: [{ translateY: sheetDrag }] },
              ]}
            >
              <View {...handlePan.panHandlers} style={styles.handleArea} accessibilityLabel="Drag down to close">
                <View style={[styles.handle, { backgroundColor: colors.borderStrong }]} />
              </View>

              <View style={styles.titleRow}>
                <View style={styles.titleCopy}>
                  <Text variant="caption" tone="muted">NUDGE · VOICE ASSISTANT</Text>
                  <Text variant="h1">{copy.title}</Text>
                </View>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Close Nudge"
                  hitSlop={12}
                  onPress={() => void closeSheet()}
                  style={styles.closeButton}
                >
                  <Ionicons name="close" size={22} color={colors.ink} />
                </Pressable>
              </View>

              {showTranscript ? (
                <>
                  <View style={[styles.liveRow, { borderColor: colors.border }]}>
                    <View
                      style={[
                        styles.liveDot,
                        { backgroundColor: conversation.status === 'connected' ? colors.positive : colors.inkFaint },
                      ]}
                    />
                    <Text variant="caption" tone="muted" style={styles.liveText}>
                      {conversation.status === 'connected'
                        ? 'Live transcript'
                        : conversation.status === 'connecting'
                          ? 'Connecting to Nudge…'
                          : savingCall
                            ? 'Call ended · saved to Your calls in Profile'
                            : 'Call ended · not saved'}
                    </Text>
                  </View>
                  <ScrollView
                    ref={transcriptScrollRef}
                    style={styles.transcriptScroll}
                    contentContainerStyle={styles.transcriptContent}
                    onContentSizeChange={() => transcriptScrollRef.current?.scrollToEnd({ animated: true })}
                  >
                    {transcript.length === 0 && !pendingLabel ? (
                      <Text variant="caption" tone="faint">Nothing was said in this call.</Text>
                    ) : (
                      <CallTranscript lines={transcript} pendingLabel={pendingLabel} />
                    )}
                  </ScrollView>
                </>
              ) : (
                <>
                  <Text variant="body" tone="muted">{copy.guidance}</Text>
                  {context?.details ? (
                    <View style={[styles.detailsBox, { backgroundColor: colors.paperSunken }]}>
                      <Text variant="caption">{context.details}</Text>
                    </View>
                  ) : null}

                  <View style={[styles.statusCard, { borderColor: colors.border }]}>
                    <Ionicons name="mic-outline" size={24} color={colors.terracotta} />
                    <View style={styles.statusCopy}>
                      <Text variant="bodyMedium">Ready when you are</Text>
                      <Text variant="caption" tone="faint">
                        Starting sends your voice, a summary of your finances in the app (loans, expenses, savings,
                        insurance, risk profile) and your recent Nudge conversations to ElevenLabs. Calls are
                        transcribed and saved to Your calls in Profile.
                      </Text>
                    </View>
                  </View>
                </>
              )}

              {error ? <Text variant="caption" tone="danger">{error}</Text> : null}

              <View style={styles.actions}>
                {conversation.status === 'connected' ? (
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => void conversation.setMuted(!conversation.isMuted)}
                    style={[styles.actionButton, styles.actionFlex, { backgroundColor: colors.petrolSoft }]}
                  >
                    <Ionicons name={conversation.isMuted ? 'mic-off-outline' : 'mic-outline'} size={20} color={colors.petrol} />
                    <Text variant="bodyMedium" tone="petrol">
                      {conversation.isMuted ? 'Unmute' : 'Mute'}
                    </Text>
                  </Pressable>
                ) : null}

                <Pressable
                  accessibilityRole="button"
                  accessibilityState={{ disabled: conversation.status === 'connecting' }}
                  disabled={conversation.status === 'connecting'}
                  onPress={() => (conversation.status === 'connected' ? void hangUp() : void startConversation())}
                  style={[
                    styles.actionButton,
                    styles.actionFlex,
                    { backgroundColor: conversation.status === 'connected' ? colors.dangerSoft : colors.terracotta },
                    conversation.status === 'connecting' && styles.disabledButton,
                  ]}
                >
                  <Ionicons
                    name={conversation.status === 'connected' ? 'call-outline' : 'mic-outline'}
                    size={20}
                    color={conversation.status === 'connected' ? colors.danger : colors.paper}
                  />
                  <Text
                    variant="bodyMedium"
                    style={{ color: conversation.status === 'connected' ? colors.danger : colors.paper }}
                  >
                    {conversation.status === 'connected'
                      ? 'End call'
                      : conversation.status === 'connecting'
                        ? 'Connecting…'
                        : transcript.length > 0
                          ? 'Start a new call'
                          : 'Start voice conversation'}
                  </Text>
                </Pressable>
              </View>
            </Animated.View>
          </View>
      </Modal>
    </NudgeAssistantContext.Provider>
  );
}

export function NudgeEntryButton({
  surface,
  details,
}: {
  surface: NudgeSurface;
  details?: string;
}) {
  const { openNudge } = useNudgeAssistant();
  const { colors } = useAppTheme();
  const copy = SURFACE_COPY[surface];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={copy.title}
      onPress={() => openNudge({ surface, details })}
      style={({ pressed }) => [
        styles.entry,
        { backgroundColor: colors.paperRaised, borderColor: colors.border },
        pressed && styles.pressed,
      ]}
    >
      <View style={[styles.entryIcon, { backgroundColor: colors.terracottaSoft }]}>
        <Ionicons name={surface === 'progress' ? 'calendar-outline' : 'chatbubble-ellipses-outline'} size={21} color={colors.terracotta} />
      </View>
      <View style={styles.entryCopy}>
        <Text variant="bodyMedium">{copy.title}</Text>
        <Text variant="caption" tone="muted">
          {surface === 'progress'
            ? 'Talk through timing, costs, and a savings goal'
            : surface === 'insights'
              ? 'Ask about a financial concept in plain language'
            : surface === 'risk-profile'
              ? 'Get a plain-language explanation'
              : surface === 'allocation'
                ? 'Ask about your recommended mix'
                : 'Ask a question or get help organizing'}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color={colors.inkFaint} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.66)',
  },
  sheet: {
    borderTopLeftRadius: RADIUS.lg,
    borderTopRightRadius: RADIUS.lg,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: SPACE.xl,
    paddingBottom: SPACE.xxl,
    gap: SPACE.lg,
    maxHeight: '92%',
  },
  sheetExpanded: { height: '88%' },
  handleArea: { alignItems: 'center', paddingTop: SPACE.sm, paddingBottom: SPACE.xs },
  handle: { width: 44, height: 5, borderRadius: 3 },
  liveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.sm,
    paddingBottom: SPACE.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  liveDot: { width: 8, height: 8, borderRadius: 4 },
  liveText: { flex: 1 },
  transcriptScroll: { flex: 1 },
  transcriptContent: { paddingVertical: SPACE.sm },
  actions: { flexDirection: 'row', gap: SPACE.md },
  actionFlex: { flex: 1 },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  titleCopy: { gap: SPACE.xs },
  closeButton: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  detailsBox: { borderRadius: RADIUS.md, padding: SPACE.md },
  statusCard: { flexDirection: 'row', alignItems: 'center', gap: SPACE.md, borderWidth: 1, borderRadius: RADIUS.md, padding: SPACE.md },
  statusCopy: { flex: 1, gap: SPACE.xs },
  actionButton: {
    minHeight: 52,
    borderRadius: RADIUS.pill,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACE.sm,
    paddingHorizontal: SPACE.lg,
  },
  disabledButton: { opacity: 0.6 },
  entry: {
    minHeight: 72,
    borderRadius: RADIUS.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.md,
    padding: SPACE.md,
  },
  entryIcon: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center', borderRadius: RADIUS.md },
  entryCopy: { flex: 1, gap: 2 },
  pressed: { opacity: 0.82 },
});

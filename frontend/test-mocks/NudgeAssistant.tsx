// Jest stand-in for src/components/NudgeAssistant: screen tests shouldn't
// load the ElevenLabs/LiveKit SDKs or open a voice session.
import React from 'react';
import { Pressable, Text } from 'react-native';

type NudgeSurface = 'home' | 'progress' | 'insights' | 'risk-profile' | 'allocation';

export function useNudgeAssistant() {
  return { openNudge: () => {} };
}

export function NudgeAssistantProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function NudgeEntryButton({ surface }: { surface: NudgeSurface; details?: string }) {
  return (
    <Pressable accessibilityRole="button" testID={`nudge-entry-${surface}`}>
      <Text>Nudge</Text>
    </Pressable>
  );
}

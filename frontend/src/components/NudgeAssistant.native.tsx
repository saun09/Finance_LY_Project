// Identifies the session to ElevenLabs as the React Native SDK; the hooks
// themselves come from @elevenlabs/react via NudgeAssistantCore.
import '@elevenlabs/react-native';
import { registerGlobals } from '@livekit/react-native';
import React from 'react';
import { PermissionsAndroid, Platform } from 'react-native';
import { NudgeAssistantCoreProvider, type RequestMicrophone } from './NudgeAssistantCore';

export { NudgeEntryButton, useNudgeAssistant } from './NudgeAssistantCore';

registerGlobals();

const requestMicrophone: RequestMicrophone = async () => {
  // iOS shows its own prompt from NSMicrophoneUsageDescription on first use
  if (Platform.OS !== 'android') return null;
  const permission = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO, {
    title: 'Microphone access',
    message: 'Nudge needs microphone access for a voice conversation.',
    buttonNegative: 'Cancel',
    buttonPositive: 'Allow',
  });
  return permission === PermissionsAndroid.RESULTS.GRANTED
    ? null
    : 'Microphone access was not granted. You can enable it in your device settings and try again.';
};

export function NudgeAssistantProvider({ children }: { children: React.ReactNode }) {
  return <NudgeAssistantCoreProvider requestMicrophone={requestMicrophone}>{children}</NudgeAssistantCoreProvider>;
}

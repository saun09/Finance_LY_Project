import React from 'react';
import { NudgeAssistantCoreProvider, type RequestMicrophone } from './NudgeAssistantCore';

export { NudgeEntryButton, useNudgeAssistant } from './NudgeAssistantCore';

/**
 * Asks the browser up front so a refusal, or a page the browser won't
 * give a microphone to at all, shows a clear message instead of a failed
 * connection. Browsers only expose the microphone on secure origins:
 * http://localhost works, but opening the dev server via a LAN IP over
 * plain http leaves `navigator.mediaDevices` undefined.
 */
const requestMicrophone: RequestMicrophone = async () => {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    return 'This browser page cannot use the microphone. Open the app at http://localhost (or over https) and try again.';
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    // only checking permission here -- the SDK opens its own stream
    stream.getTracks().forEach((track) => track.stop());
    return null;
  } catch {
    return 'Microphone access was blocked. Allow it from the address bar and try again.';
  }
};

export function NudgeAssistantProvider({ children }: { children: React.ReactNode }) {
  return <NudgeAssistantCoreProvider requestMicrophone={requestMicrophone}>{children}</NudgeAssistantCoreProvider>;
}

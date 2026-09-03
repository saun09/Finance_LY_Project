import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useDemoUser } from './DemoUserContext';

/**
 * There is no GET /users/{id}/profile endpoint on the backend (only PUT,
 * which upserts) and no session/auth to ask "who is this and are they
 * onboarded". Rather than inventing a fake auth flow, this is a local,
 * per-demo-user-id flag: set once POST /complete-onboarding actually
 * succeeds against the real backend, so it always reflects a real
 * completed call, never a guess. Switching the demo user id (Settings)
 * naturally re-triggers onboarding for a different/fresh id.
 *
 * This lives in context, not a plain hook, because RootNavigator (which
 * decides Onboarding vs Main) and the screen that calls markCompleted()
 * (SnapshotScreen) are different components -- a plain hook would give
 * each its own isolated useState, so completing onboarding would never
 * make RootNavigator itself re-render.
 */
function key(userId: string) {
  return `onboarding_complete_${userId}`;
}

interface OnboardingStatusContextValue {
  completed: boolean | null;
  markCompleted: () => Promise<void>;
  resetOnboarding: () => Promise<void>;
  loading: boolean;
}

const OnboardingStatusCtx = createContext<OnboardingStatusContextValue | null>(null);

export function OnboardingStatusProvider({ children }: { children: React.ReactNode }) {
  const { userId, ready: userReady } = useDemoUser();
  const [completed, setCompleted] = useState<boolean | null>(null);

  useEffect(() => {
    if (!userReady) return;
    let cancelled = false;
    setCompleted(null);
    AsyncStorage.getItem(key(userId)).then((v) => {
      if (!cancelled) setCompleted(v === 'true');
    });
    return () => {
      cancelled = true;
    };
  }, [userId, userReady]);

  const markCompleted = useCallback(async () => {
    await AsyncStorage.setItem(key(userId), 'true');
    setCompleted(true);
  }, [userId]);

  const resetOnboarding = useCallback(async () => {
    await AsyncStorage.removeItem(key(userId));
    setCompleted(false);
  }, [userId]);

  return (
    <OnboardingStatusCtx.Provider
      value={{ completed, markCompleted, resetOnboarding, loading: !userReady || completed === null }}
    >
      {children}
    </OnboardingStatusCtx.Provider>
  );
}

export function useOnboardingStatus() {
  const ctx = useContext(OnboardingStatusCtx);
  if (!ctx) throw new Error('useOnboardingStatus must be used within an OnboardingStatusProvider');
  return ctx;
}

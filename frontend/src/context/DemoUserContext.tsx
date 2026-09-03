import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

/**
 * The backend has no authentication system (confirmed: no auth
 * middleware anywhere in app/main.py). Per Section 27, this is a clean
 * dev/demo configuration, not fake auth: a plain user_id string, editable
 * from the Settings screen, persisted locally so a demo doesn't reset
 * between app launches. Nothing here simulates a login flow.
 */

const STORAGE_KEY = 'demo_user_id';
const DEFAULT_USER_ID = 'demo-user';

interface DemoUserContextValue {
  userId: string;
  setUserId: (id: string) => Promise<void>;
  ready: boolean;
}

const DemoUserCtx = createContext<DemoUserContextValue>({
  userId: DEFAULT_USER_ID,
  setUserId: async () => {},
  ready: false,
});

export function DemoUserProvider({ children }: { children: React.ReactNode }) {
  const [userId, setUserIdState] = useState(DEFAULT_USER_ID);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((stored) => {
        if (stored) setUserIdState(stored);
      })
      .finally(() => setReady(true));
  }, []);

  const setUserId = useCallback(async (id: string) => {
    const trimmed = id.trim();
    if (!trimmed) return;
    setUserIdState(trimmed);
    await AsyncStorage.setItem(STORAGE_KEY, trimmed);
  }, []);

  return <DemoUserCtx.Provider value={{ userId, setUserId, ready }}>{children}</DemoUserCtx.Provider>;
}

export function useDemoUser() {
  return useContext(DemoUserCtx);
}

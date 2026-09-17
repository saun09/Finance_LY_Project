import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { authApi } from '../api/auth';
import { toApiError } from '../api/client';

/**
 * Real, password-checked accounts (see backend/app/services/auth_service.py)
 * gate entry into the app -- login/signup genuinely fail on a wrong
 * password. Every other endpoint in the app still trusts the user_id in
 * its URL path exactly as before this existed; this only decides whether
 * RootNavigator shows the app at all, and which user_id it uses once it
 * does. The name `DemoUserContext` predates real auth and every existing
 * screen already reads `userId` from here -- kept as-is to avoid a
 * pointless rename across ~25 files that only ever needed the user_id.
 */

const STORAGE_KEY = 'auth_session_v1';

interface StoredSession {
  userId: string;
  username: string;
}

interface DemoUserContextValue {
  userId: string;
  username: string | null;
  isAuthenticated: boolean;
  ready: boolean;
  signup: (username: string, password: string) => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const DemoUserCtx = createContext<DemoUserContextValue>({
  userId: '',
  username: null,
  isAuthenticated: false,
  ready: false,
  signup: async () => {},
  login: async () => {},
  logout: async () => {},
});

export function DemoUserProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((stored) => {
        if (stored) setSession(JSON.parse(stored) as StoredSession);
      })
      .finally(() => setReady(true));
  }, []);

  const persist = useCallback(async (next: StoredSession) => {
    setSession(next);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const signup = useCallback(
    async (username: string, password: string) => {
      try {
        const user = await authApi.signup({ username: username.trim(), password });
        await persist({ userId: user.user_id, username: user.username });
      } catch (err) {
        throw toApiError(err);
      }
    },
    [persist],
  );

  const login = useCallback(
    async (username: string, password: string) => {
      try {
        const user = await authApi.login({ username: username.trim(), password });
        await persist({ userId: user.user_id, username: user.username });
      } catch (err) {
        throw toApiError(err);
      }
    },
    [persist],
  );

  const logout = useCallback(async () => {
    setSession(null);
    await AsyncStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <DemoUserCtx.Provider
      value={{
        userId: session?.userId ?? '',
        username: session?.username ?? null,
        isAuthenticated: session !== null,
        ready,
        signup,
        login,
        logout,
      }}
    >
      {children}
    </DemoUserCtx.Provider>
  );
}

export function useDemoUser() {
  return useContext(DemoUserCtx);
}

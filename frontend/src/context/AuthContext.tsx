import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { fetchMe, getSession, login as apiLogin, logout as apiLogout, setSession } from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  initialising: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => getSession()?.user ?? null);
  const [initialising, setInitialising] = useState<boolean>(() => Boolean(getSession()));

  useEffect(() => {
    if (!getSession()) {
      setInitialising(false);
      return;
    }
    let cancelled = false;
    fetchMe()
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch(() => {
        if (!cancelled) {
          setSession(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setInitialising(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await apiLogin(email, password);
    setUser(session.user);
    return session.user;
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const can = useCallback(
    (permission: string) => Boolean(user?.permissions.includes(permission)),
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, initialising, signIn, signOut, can }),
    [user, initialising, signIn, signOut, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside an AuthProvider");
  return context;
}

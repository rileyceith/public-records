import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { api, setAccessToken } from "../../lib/api";
import type { User } from "../../lib/types";

// Crossfades between the landing page and the app when the browser supports it.
function withTransition(update: () => void) {
  const start = (document as Document & { startViewTransition?: (cb: () => void) => unknown }).startViewTransition;
  if (!start || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    update();
    return;
  }
  start.call(document, () => flushSync(update));
}

interface AuthContextValue {
  user: User | null;
  isAdmin: boolean;
  isStaff: boolean;
  canAudit: boolean;
  isVerifiedCitizen: boolean;
  signIn(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAdmin: user?.role === "admin",
      isStaff: user?.role === "admin" || user?.role === "clerk",
      canAudit: user?.role === "admin" || user?.role === "auditor",
      isVerifiedCitizen: user?.role === "citizen" && user.is_verified,
      async signIn(email, password) {
        const session = await api.login(email, password);
        setAccessToken(session.access_token);
        withTransition(() => setUser(session.user));
      },
      async signOut() {
        try {
          await api.logout();
        } finally {
          setAccessToken(null);
          withTransition(() => setUser(null));
        }
      },
    }),
    [user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}

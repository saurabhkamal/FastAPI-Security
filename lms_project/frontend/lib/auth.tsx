"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { decodeJwt } from "./jwt";
import { Role } from "./types";

interface Session {
  token: string;
  role: Role;
  userId: string;
  email: string;
}

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = "lms_session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // One-time hydration of client-only localStorage into React state on
    // mount; the resulting extra render pass is expected and unavoidable
    // here since localStorage doesn't exist during server rendering.
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSession(JSON.parse(raw));
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    setLoading(false);
  }, []);

  function login(token: string) {
    const payload = decodeJwt(token);
    if (!payload) return;
    const next: Session = {
      token,
      role: payload.role as Role,
      userId: payload.sub,
      email: payload.email,
    };
    setSession(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function logout() {
    setSession(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <AuthContext.Provider value={{ session, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

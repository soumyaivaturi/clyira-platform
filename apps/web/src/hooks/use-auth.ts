"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authApi } from "@/lib/api";

function _persistToken(token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem("clyira_token", token);
  // Cookie for Next.js middleware — 8h to match JWT expiry
  document.cookie = `clyira_token=${token}; path=/; max-age=${60 * 60 * 8}; SameSite=Lax`;
}

function _clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("clyira_token");
  document.cookie = "clyira_token=; path=/; max-age=0";
}

interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  company_id: string;
  department?: string;
  onboarding_complete: boolean;
  terms_accepted_at: string | null;
  force_password_change: boolean;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; company_name: string }) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
  acceptTerms: () => Promise<void>;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const res = await authApi.login(email, password);
          const { access_token, user } = res.data;
          _persistToken(access_token);
          set({ token: access_token, user, isLoading: false });
        } catch (err) {
          set({ isLoading: false });
          throw err;
        }
      },

      register: async (data) => {
        set({ isLoading: true });
        try {
          const res = await authApi.register(data.email, data.password, data.full_name, data.company_name);
          const { access_token, user } = res.data;
          _persistToken(access_token);
          set({ token: access_token, user, isLoading: false });
        } catch (err) {
          set({ isLoading: false });
          throw err;
        }
      },

      logout: () => {
        _clearToken();
        set({ token: null, user: null });
      },

      refreshMe: async () => {
        try {
          const res = await authApi.me();
          set({ user: res.data });
        } catch {
          get().logout();
        }
      },

      acceptTerms: async () => {
        await authApi.acceptTerms();
        await get().refreshMe();
      },
    }),
    {
      name: "clyira-auth",
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);

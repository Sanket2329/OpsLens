import { create } from "zustand";
import { api, clearToken, getToken, setToken, type User } from "./api";

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  bootstrap: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    organization_name: string;
    name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  logout: () => void;
  /** Persist name change to the backend and update local state. */
  updateProfile: (data: { name: string }) => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  token: null,
  loading: true,

  bootstrap: async () => {
    const token = getToken();
    if (!token) {
      set({ loading: false, token: null, user: null });
      return;
    }
    try {
      const user = await api.get<User>("/api/v1/auth/me");
      set({ user, token, loading: false });
    } catch {
      clearToken();
      set({ user: null, token: null, loading: false });
    }
  },

  login: async (email, password) => {
    const res = await api.post<{ access_token: string }>("/api/v1/auth/login", {
      email,
      password,
    });
    setToken(res.access_token);
    const user = await api.get<User>("/api/v1/auth/me");
    set({ user, token: res.access_token });
  },

  register: async (data) => {
    const res = await api.post<{ access_token: string }>(
      "/api/v1/auth/register",
      data,
    );
    setToken(res.access_token);
    const user = await api.get<User>("/api/v1/auth/me");
    set({ user, token: res.access_token });
  },

  logout: () => {
    clearToken();
    set({ user: null, token: null });
    if (typeof window !== "undefined") window.location.href = "/login";
  },

  updateProfile: async ({ name }) => {
    const updated = await api.patch<User>("/api/v1/auth/me", { name });
    set({ user: updated });
  },
}));

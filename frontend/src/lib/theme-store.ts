import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "dark" | "light";

interface ThemeState {
  theme: Theme;
  toggle: () => void;
  setTheme: (theme: Theme) => void;
}

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "dark",
      toggle: () =>
        set((state) => {
          const next = state.theme === "dark" ? "light" : "dark";
          applyTheme(next);
          return { theme: next };
        }),
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
    }),
    { name: "opslens-theme" },
  ),
);

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "light") {
    root.classList.remove("dark");
    root.classList.add("light");
  } else {
    root.classList.remove("light");
    root.classList.add("dark");
  }
}

/** Call once on app boot to restore persisted theme. */
export function initTheme() {
  const stored = localStorage.getItem("opslens-theme");
  let theme: Theme = "dark";
  try {
    theme = stored ? (JSON.parse(stored)?.state?.theme ?? "dark") : "dark";
  } catch {
    theme = "dark";
  }
  applyTheme(theme);
}

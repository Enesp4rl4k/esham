"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";
const KEY = "esham-theme";

/** Sistem tercihine uyar; kullanıcı seçimi localStorage'da tutulur. İlk boyama layout'taki satır içi betikle yapılır. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  }, []);

  const flip = () => {
    const next: Theme = theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {}
    setTheme(next);
  };

  return (
    <button
      type="button"
      onClick={flip}
      className="inline-flex items-center justify-center w-11 h-11 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-colors"
      aria-label={theme === "light" ? "Koyu temaya geç" : "Açık temaya geç"}
      title={theme === "light" ? "Koyu tema" : "Açık tema"}
    >
      {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
    </button>
  );
}

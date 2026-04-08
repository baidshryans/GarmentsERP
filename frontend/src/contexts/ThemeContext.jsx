import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "erp.theme";
const DEFAULT_THEME = "violet";

export const THEMES = {
  violet: { label: "Violet", swatch: "#7c7ff0" },
  indigo: { label: "Indigo", swatch: "#6d28d9" },
};

const ThemeContext = createContext({ theme: DEFAULT_THEME, setTheme: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === "undefined") return DEFAULT_THEME;
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = (next) => {
    if (THEMES[next]) setThemeState(next);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

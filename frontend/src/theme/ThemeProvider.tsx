import { useEffect } from "react";
import type { ReactNode } from "react";
import { ACTIVE_THEME, THEMES } from "./themes";
import "./tokens.css";

/**
 * Applies the active semester theme by stamping data-theme on <html>, which
 * activates the matching [data-theme] token block in tokens.css.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const theme = THEMES[ACTIVE_THEME] ? ACTIVE_THEME : "stranger-things";
    document.documentElement.dataset.theme = theme;
  }, []);
  return <>{children}</>;
}

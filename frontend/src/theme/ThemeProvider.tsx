import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { ThemeConfig } from "../types/passport";
import { DEFAULT_THEME, resolveThemeCopy } from "./themes";
import "./tokens.css";

/**
 * Applies the active challenge's theme (US-13 / FR-B4).
 *
 * Two layers, so a re-skin never needs a deploy (NFR-6):
 *  1. `data-theme` on <html> activates that theme's static token block in
 *     tokens.css — the baseline, and the fallback when the server sends no config.
 *  2. The server-sent palette is applied over it as inline custom properties.
 *
 * The theme rides along on the passport response, so `applyTheme` is called by
 * whichever container just fetched it rather than being fetched here.
 */

interface ThemeState {
  themeId: string;
  config: ThemeConfig | null;
}

interface ThemeContextValue extends ThemeState {
  applyTheme: (themeId: string, config: ThemeConfig | null) => void;
}

// Default is a no-op so a component using useTheme() renders fine unwrapped.
const ThemeContext = createContext<ThemeContextValue>({
  themeId: DEFAULT_THEME,
  config: null,
  applyTheme: () => {},
});

// A palette key becomes a CSS custom-property name, so keep it to a plain token.
const SAFE_KEY = /^[a-z][a-z0-9-]*$/;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ThemeState>({
    themeId: DEFAULT_THEME,
    config: null,
  });
  // Property names applied last pass, so switching themes leaves none behind.
  const appliedKeys = useRef<string[]>([]);

  const applyTheme = useCallback(
    (themeId: string, config: ThemeConfig | null) => {
      setState({ themeId, config });
    },
    [],
  );

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = state.themeId || DEFAULT_THEME;

    for (const key of appliedKeys.current) root.style.removeProperty(key);
    appliedKeys.current = [];

    for (const [key, value] of Object.entries(state.config?.palette ?? {})) {
      if (!SAFE_KEY.test(key)) continue;
      const property = `--wp-${key}`;
      root.style.setProperty(property, value);
      appliedKeys.current.push(property);
    }
  }, [state]);

  const value = useMemo(() => ({ ...state, applyTheme }), [state, applyTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

/**
 * The themed copy for screens with no passport of their own (sign-in, landing).
 * A component holding a passport should call resolveThemeCopy on it directly
 * rather than wait for the round-trip through this context.
 */
export function useThemeCopy(): { appTitle: string; tagline: string } {
  const { themeId, config } = useTheme();
  return resolveThemeCopy(themeId, config);
}

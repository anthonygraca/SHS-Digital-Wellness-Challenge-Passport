/**
 * Admin-facing theme types (US-13 / FR-B4). Snake_case to match the API, like
 * the other admin types in types/challenge.ts. The student app reads the
 * resolved theme off the passport instead — see ThemeConfig in types/passport.ts.
 */

export interface Theme {
  id: string;
  name: string;
  /** CSS custom-property suffix -> value, e.g. { primary: "#ff4438" }. */
  palette: Record<string, string>;
  logo_url: string | null;
  hero_url: string | null;
  app_title: string;
  tagline: string;
  copy_tone: string;
  created_at: string;
  updated_at: string;
}

/** Partial edit; `palette` replaces the stored map wholesale. */
export interface ThemeUpdate {
  name?: string;
  palette?: Record<string, string>;
  logo_url?: string | null;
  hero_url?: string | null;
  app_title?: string;
  tagline?: string;
  copy_tone?: string;
}

/**
 * Semester theme registry. Re-skinning is config: add a [data-theme] block in
 * tokens.css plus an entry here — zero component edits. ACTIVE_THEME will later
 * be sourced from the backend challenge/theme config (FR-B4).
 */
export interface ThemeMeta {
  id: string;
  label: string;
  appTitle: string;
  tagline: string;
}

export const THEMES: Record<string, ThemeMeta> = {
  "stranger-things": {
    id: "stranger-things",
    label: "Stranger Things",
    appTitle: "Wellness Passport",
    tagline: "Step through the first portal — survival starts with protection.",
  },
  "harry-potter": {
    id: "harry-potter",
    label: "Harry Potter",
    appTitle: "Wellness Passport",
    tagline: "Solemnly swear to look after your wellbeing.",
  },
};

export const ACTIVE_THEME = "stranger-things";

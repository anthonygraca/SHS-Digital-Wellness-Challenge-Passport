/**
 * Semester theme registry. Re-skinning is config: the live theme — palette,
 * assets and copy — comes from the backend on the passport response (FR-B4), and
 * these entries are the fallback copy used before one has been fetched or when a
 * challenge has no theme. The matching [data-theme] blocks in tokens.css are the
 * companion color fallback.
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

/** Applied until a challenge's theme is known (and when it has none). */
export const DEFAULT_THEME = "stranger-things";

export const DEFAULT_APP_TITLE = "Wellness Passport";

/** The copy to render: the server's theme first, then the registry, then defaults. */
export function resolveThemeCopy(
  themeId: string,
  config: { appTitle: string; tagline: string } | null,
): { appTitle: string; tagline: string } {
  const fallback = THEMES[themeId];
  return {
    appTitle: config?.appTitle || fallback?.appTitle || DEFAULT_APP_TITLE,
    tagline: config?.tagline || fallback?.tagline || "",
  };
}

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { ThemeConfig } from "../types/passport";
import { ThemeProvider, useTheme, useThemeCopy } from "./ThemeProvider";

/**
 * US-13 (FR-B4 / NFR-6): the theme is applied from server-sent configuration, so
 * a re-skin ships no code. These cover what the provider actually does to the DOM.
 */

function config(overrides: Partial<ThemeConfig> = {}): ThemeConfig {
  return {
    id: "stranger-things",
    palette: { primary: "#ff4438", "hero-a": "#4a0f0a" },
    logoUrl: null,
    heroUrl: null,
    appTitle: "Wellness Passport",
    tagline: "Step through the first portal.",
    copyTone: "dark, retro-80s",
    ...overrides,
  };
}

/** Buttons that apply a theme, plus the copy the provider resolves. */
function Harness({ themes }: { themes: [string, ThemeConfig | null][] }) {
  const { applyTheme } = useTheme();
  const { appTitle, tagline } = useThemeCopy();
  return (
    <>
      {themes.map(([id, cfg], i) => (
        <button key={i} type="button" onClick={() => applyTheme(id, cfg)}>
          apply-{i}
        </button>
      ))}
      <p>title:{appTitle}</p>
      <p>tagline:{tagline}</p>
    </>
  );
}

function styleOf(property: string) {
  return document.documentElement.style.getPropertyValue(property);
}

afterEach(() => {
  document.documentElement.style.cssText = "";
  delete document.documentElement.dataset.theme;
});

describe("ThemeProvider", () => {
  it("applies the theme's id and palette to the document", async () => {
    render(
      <ThemeProvider>
        <Harness themes={[["stranger-things", config()]]} />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByText("apply-0"));

    expect(document.documentElement.dataset.theme).toBe("stranger-things");
    expect(styleOf("--wp-primary")).toBe("#ff4438");
    expect(styleOf("--wp-hero-a")).toBe("#4a0f0a");
  });

  it("renders the theme's copy", async () => {
    render(
      <ThemeProvider>
        <Harness themes={[["stranger-things", config()]]} />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByText("apply-0"));

    expect(screen.getByText("tagline:Step through the first portal.")).toBeInTheDocument();
  });

  it("drops tokens the previous theme set when switching themes", async () => {
    // Scenario 2: switching re-skins from config alone — no stale colors survive.
    const harry = config({
      id: "harry-potter",
      palette: { primary: "#7d2e2e" }, // deliberately no hero-a
      tagline: "Solemnly swear.",
    });
    render(
      <ThemeProvider>
        <Harness themes={[["stranger-things", config()], ["harry-potter", harry]]} />
      </ThemeProvider>,
    );

    await userEvent.click(screen.getByText("apply-0"));
    expect(styleOf("--wp-hero-a")).toBe("#4a0f0a");

    await userEvent.click(screen.getByText("apply-1"));
    expect(document.documentElement.dataset.theme).toBe("harry-potter");
    expect(styleOf("--wp-primary")).toBe("#7d2e2e");
    expect(styleOf("--wp-hero-a")).toBe("");
    expect(screen.getByText("tagline:Solemnly swear.")).toBeInTheDocument();
  });

  it("falls back to the default theme when a challenge has none", async () => {
    render(
      <ThemeProvider>
        <Harness themes={[["stranger-things", config()], ["", null]]} />
      </ThemeProvider>,
    );

    await userEvent.click(screen.getByText("apply-0"));
    await userEvent.click(screen.getByText("apply-1"));

    // The static token block still skins the app; the inline overrides are gone.
    expect(document.documentElement.dataset.theme).toBe("stranger-things");
    expect(styleOf("--wp-primary")).toBe("");
  });

  it("ignores palette keys that are not plain CSS tokens", async () => {
    render(
      <ThemeProvider>
        <Harness
          themes={[
            ["x", config({ palette: { "bad;key": "red", primary: "#00ff00" } })],
          ]}
        />
      </ThemeProvider>,
    );
    await userEvent.click(screen.getByText("apply-0"));

    expect(styleOf("--wp-bad;key")).toBe("");
    expect(styleOf("--wp-primary")).toBe("#00ff00");
  });

  it("uses the registry copy before a theme has been fetched", () => {
    render(
      <ThemeProvider>
        <Harness themes={[]} />
      </ThemeProvider>,
    );
    // Default theme is stranger-things, whose registry entry supplies the copy.
    expect(screen.getByText("title:Wellness Passport")).toBeInTheDocument();
  });
});

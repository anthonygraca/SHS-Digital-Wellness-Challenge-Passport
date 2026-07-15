import { describe, expect, it } from "vitest";
import { manifest } from "./manifest";

/**
 * Binds Scenario 1 of docs/features.md § US-6 as far as a unit test honestly can.
 *
 * "Then I am offered an 'install to home screen' option" is a judgement the browser
 * makes about the built app, and jsdom has no install pipeline — so the scenario
 * itself is verified by hand against a preview build (see the PR's test steps).
 * What is mechanically checkable, and what actually broke this story, is the
 * manifest that decision is made from: the app shipped `icons: []` and so could
 * never be offered. These pin Chrome's documented install criteria and the files
 * they name, which is the part a regression would silently undo.
 */
describe("Web app manifest (US-6 / FR-C4)", () => {
  it("Scenario: App is installable — meets Chrome's documented install criteria", () => {
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBeTruthy();

    const png = (size: string) =>
      manifest.icons.find(
        (i) => i.sizes === size && i.type === "image/png" && i.purpose === "any",
      );
    // The threshold Chrome states outright: a 192x192 and a 512x512.
    expect(png("192x192")).toBeDefined();
    expect(png("512x512")).toBeDefined();
  });

  it("Scenario: App is installable — launching from the home screen opens full-screen", () => {
    expect(manifest.display).toBe("standalone");
  });

  it("opens on the passport, which is the one screen that renders offline", () => {
    // "/" routes via the landing, which fetches enrollment status unconditionally
    // and would show an error card on an offline launch.
    expect(manifest.start_url).toBe("/passport");
    // Without an explicit scope it would be inferred from start_url's directory,
    // putting /home and /admin outside the installed app.
    expect(manifest.scope).toBe("/");
  });

  it("ships a maskable icon so Android does not letterbox it", () => {
    const maskable = manifest.icons.find((i) => i.purpose === "maskable");
    expect(maskable).toBeDefined();
    expect(maskable?.sizes).toBe("512x512");
  });

  it("ships every icon file the manifest points at", () => {
    // The regression that made this story necessary was a manifest whose icons did
    // not exist on disk — `vite build` emits that happily, and only a real install
    // attempt surfaces it. import.meta.glob is eager and resolves at transform time,
    // so a renamed or deleted PNG fails here instead of on a student's phone.
    // (Not fs: @types/node is not a dependency and tsconfig pins `types`.)
    const shipped = new Set(
      Object.keys(import.meta.glob("../../public/icons/*.png")).map((p) =>
        p.replace("../../public", ""),
      ),
    );
    for (const icon of manifest.icons) {
      expect(shipped).toContain(icon.src);
    }
  });
});

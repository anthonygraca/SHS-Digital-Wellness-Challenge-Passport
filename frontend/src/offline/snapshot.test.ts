import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearOfflineSnapshot,
  readPassportSnapshot,
  readSessionSnapshot,
  writePassportSnapshot,
  writeSessionSnapshot,
} from "./snapshot";
import type { Passport } from "../types/passport";
import type { Session } from "../types/session";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

const asSession = (over: Partial<Session> = {}): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  ...over,
});

const asPassport = (): Passport => ({
  challengeName: "Stranger Things Wellness Challenge",
  theme: "stranger-things",
  themeConfig: null,
  totalWeeks: 7,
  completedWeeks: 3,
  remainingWeeks: 4,
  requiredTotal: 7,
  requiredCompleted: 3,
  prizeEligible: false,
  weeks: [],
});

describe("Offline snapshot (US-6 / FR-C4)", () => {
  it("round-trips the session and the passport", () => {
    writeSessionSnapshot(asSession());
    writePassportSnapshot(asPassport());

    expect(readSessionSnapshot()).toEqual(asSession());
    expect(readPassportSnapshot()?.completedWeeks).toBe(3);
  });

  it("reads back nothing when nothing was written", () => {
    expect(readSessionSnapshot()).toBeNull();
    expect(readPassportSnapshot()).toBeNull();
  });

  it("clears both keys together, so a session never outlives its passport", () => {
    writeSessionSnapshot(asSession());
    writePassportSnapshot(asPassport());

    clearOfflineSnapshot();

    expect(readSessionSnapshot()).toBeNull();
    expect(readPassportSnapshot()).toBeNull();
  });

  it("ignores a corrupt payload rather than throwing", () => {
    // A truncated write or a hand-edited key must read as "nothing cached", not
    // crash the render that asked for it.
    localStorage.setItem("wp.offline.passport.v1", "{not json");
    localStorage.setItem("wp.offline.session.v1", "{not json");

    expect(readPassportSnapshot()).toBeNull();
    expect(readSessionSnapshot()).toBeNull();
  });

  it("ignores a payload of the wrong shape", () => {
    // Guards against a snapshot written by an older build reaching PassportView and
    // white-screening it on a missing field.
    localStorage.setItem("wp.offline.passport.v1", JSON.stringify({ weeks: "nope" }));
    localStorage.setItem("wp.offline.session.v1", JSON.stringify({ subject: 42 }));

    expect(readPassportSnapshot()).toBeNull();
    expect(readSessionSnapshot()).toBeNull();
  });

  it("survives storage being unavailable", () => {
    // localStorage throws outright in Safari private mode and when the quota is
    // gone. Offline viewing may degrade; the app may not fall over.
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });

    expect(() => writePassportSnapshot(asPassport())).not.toThrow();
    expect(readPassportSnapshot()).toBeNull();
  });
});

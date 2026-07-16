import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionProvider, useSession } from "./SessionProvider";
import type { Bootstrap } from "../types/bootstrap";
import type { Passport } from "../types/passport";
import type { Session } from "../types/session";
import {
  readPassportSnapshot,
  readSessionSnapshot,
  writePassportSnapshot,
  writeSessionSnapshot,
} from "../offline/snapshot";

const api = vi.hoisted(() => ({ fetchBootstrap: vi.fn(), logout: vi.fn() }));
vi.mock("../api/bootstrap", () => ({ fetchBootstrap: api.fetchBootstrap }));
vi.mock("./auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./auth")>()),
  logout: api.logout,
}));

afterEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

const asSession = (over: Partial<Session> = {}): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  ...over,
});

const asPassport = (over: Partial<Passport> = {}): Passport => ({
  challengeName: "Stranger Things Challenge",
  theme: "",
  themeConfig: null,
  totalWeeks: 2,
  completedWeeks: 1,
  remainingWeeks: 1,
  requiredTotal: 2,
  requiredCompleted: 1,
  prizeEligible: false,
  weeks: [],
  ...over,
});

const asBootstrap = (over: Partial<Bootstrap> = {}): Bootstrap => ({
  session: asSession(),
  enrollment: { active_challenge: { id: 1, name: "Stranger Things" }, enrolled: true },
  passport: asPassport(),
  ...over,
});

/** Surfaces the whole context so tests can assert on it through the DOM. */
function Probe() {
  const { session, enrollment, passport, loading, signOut } = useSession();
  if (loading) return <p>loading</p>;
  return (
    <>
      <p>session:{session ? session.subject : "none"}</p>
      <p>enrolled:{enrollment ? String(enrollment.enrolled) : "none"}</p>
      <p>passport:{passport ? passport.challengeName : "none"}</p>
      <button type="button" onClick={() => void signOut()}>
        sign out
      </button>
    </>
  );
}

const renderProbe = () =>
  render(
    <SessionProvider>
      <Probe />
    </SessionProvider>,
  );

/**
 * The offline network failure mode. `fetch` REJECTS when there is no connection —
 * it does not resolve with a !res.ok response — so fetchBootstrap's own
 * empty-on-failure guard never gets a chance to run.
 */
const offline = () => new TypeError("Failed to fetch");

describe("SessionProvider (US-6 / FR-C4)", () => {
  it("stops loading when the network is unreachable, instead of hanging forever", async () => {
    api.fetchBootstrap.mockRejectedValue(offline());

    renderProbe();

    // The regression: an uncaught rejection in refresh() skipped setLoading(false),
    // stranding every screen on "Loading…" with no way out but a reload.
    expect(await screen.findByText("session:none")).toBeInTheDocument();
    expect(screen.queryByText("loading")).toBeNull();
  });

  it("exposes the session when the server answers", async () => {
    api.fetchBootstrap.mockResolvedValue(asBootstrap());

    renderProbe();

    expect(await screen.findByText("session:abc@csub.edu")).toBeInTheDocument();
  });

  it("signs out locally even when the server cannot be told", async () => {
    api.fetchBootstrap.mockResolvedValue(asBootstrap());
    api.logout.mockRejectedValue(offline());

    renderProbe();
    await screen.findByText("session:abc@csub.edu");
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));

    // Shared device: a sign-out that throws must not leave the student signed in.
    expect(await screen.findByText("session:none")).toBeInTheDocument();
  });

  it("falls back to the cached session when the server is unreachable", async () => {
    writeSessionSnapshot(asSession());
    api.fetchBootstrap.mockRejectedValue(offline());

    renderProbe();

    // Offline, the passport must not come from here wearing a live face — Passport
    // reads the snapshot itself, which is how it knows to mark the screen stale.
    expect(await screen.findByText("session:abc@csub.edu")).toBeInTheDocument();
    expect(screen.getByText("passport:none")).toBeInTheDocument();
  });
});

describe("SessionProvider first-render seeds", () => {
  it("publishes the enrollment and passport that came with the session", async () => {
    api.fetchBootstrap.mockResolvedValue(asBootstrap());

    renderProbe();

    // The point of the whole change: one request, and Landing and Passport both have
    // their answer without a hop of their own.
    expect(await screen.findByText("enrolled:true")).toBeInTheDocument();
    expect(screen.getByText("passport:Stranger Things Challenge")).toBeInTheDocument();
  });

  it("caches both snapshots, so the seeded passport survives going offline", async () => {
    api.fetchBootstrap.mockResolvedValue(asBootstrap());

    renderProbe();
    await screen.findByText("session:abc@csub.edu");

    // Passport no longer fetches when it was seeded, so if this provider did not
    // write the snapshot, nothing would — and US-6 would break silently.
    expect(readSessionSnapshot()?.subject).toBe("abc@csub.edu");
    expect(readPassportSnapshot()?.challengeName).toBe("Stranger Things Challenge");
  });

  it("an authoritative signed-out answer clears the cache", async () => {
    writeSessionSnapshot(asSession());
    writePassportSnapshot(asPassport());
    api.fetchBootstrap.mockResolvedValue({
      session: null,
      enrollment: null,
      passport: null,
    });

    renderProbe();
    await screen.findByText("session:none");

    // "The server says nobody is signed in" must not be survivable by the fallback,
    // or an ended session would resurrect itself on the next load.
    expect(readSessionSnapshot()).toBeNull();
    expect(readPassportSnapshot()).toBeNull();
  });

  it("keeps a good passport snapshot when the student simply is not enrolled", async () => {
    writePassportSnapshot(asPassport());
    api.fetchBootstrap.mockResolvedValue(
      asBootstrap({ passport: null, enrollment: { active_challenge: null, enrolled: false } }),
    );

    renderProbe();
    await screen.findByText("session:abc@csub.edu");

    // A null passport beside a live session means "not enrolled", not "your progress
    // is gone" — only a signed-out answer clears the cache.
    expect(readPassportSnapshot()).not.toBeNull();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionProvider, useSession } from "./SessionProvider";
import type { Session } from "../types/session";

const api = vi.hoisted(() => ({
  fetchSession: vi.fn(),
  logout: vi.fn(),
}));
vi.mock("./auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./auth")>()),
  fetchSession: api.fetchSession,
  logout: api.logout,
}));

afterEach(() => {
  vi.clearAllMocks();
});

const asSession = (over: Partial<Session> = {}): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  student_id: 1,
  ...over,
});

/** Surfaces the whole context so tests can assert on it through the DOM. */
function Probe() {
  const { session, loading, signOut } = useSession();
  if (loading) return <p>loading</p>;
  return (
    <>
      <p>session:{session ? session.subject : "none"}</p>
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
 * it does not resolve with a !res.ok response — so fetchSession's own
 * null-on-failure guard never gets a chance to run.
 */
const offline = () => new TypeError("Failed to fetch");

describe("SessionProvider (US-6 / FR-C4)", () => {
  it("stops loading when the network is unreachable, instead of hanging forever", async () => {
    api.fetchSession.mockRejectedValue(offline());

    renderProbe();

    // The regression: an uncaught rejection in refresh() skipped setLoading(false),
    // stranding every screen on "Loading…" with no way out but a reload.
    expect(await screen.findByText("session:none")).toBeInTheDocument();
    expect(screen.queryByText("loading")).toBeNull();
  });

  it("exposes the session when the server answers", async () => {
    api.fetchSession.mockResolvedValue(asSession());

    renderProbe();

    expect(await screen.findByText("session:abc@csub.edu")).toBeInTheDocument();
  });

  it("signs out locally even when the server cannot be told", async () => {
    api.fetchSession.mockResolvedValue(asSession());
    api.logout.mockRejectedValue(offline());

    renderProbe();
    await screen.findByText("session:abc@csub.edu");
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));

    // Shared device: a sign-out that throws must not leave the student signed in.
    expect(await screen.findByText("session:none")).toBeInTheDocument();
  });
});

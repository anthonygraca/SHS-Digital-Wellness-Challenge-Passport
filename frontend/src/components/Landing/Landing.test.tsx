import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Session } from "../../types/session";
import type { EnrollmentStatus } from "../../types/enrollment";
import { Landing } from "./Landing";

const state = vi.hoisted(() => ({
  session: null as Session | null,
  enrollment: null as EnrollmentStatus | null,
  loading: false,
}));
const signOut = vi.fn();

const api = vi.hoisted(() => ({
  fetchEnrollmentStatus: vi.fn(),
  enroll: vi.fn(),
}));

vi.mock("../../auth/SessionProvider", () => ({
  useSession: () => ({ ...state, signOut, refresh: vi.fn() }),
}));
vi.mock("react-router-dom", () => ({
  Navigate: ({ to }: { to: string }) => <div>redirect:{to}</div>,
}));
vi.mock("../../api/enrollment", () => ({
  fetchEnrollmentStatus: api.fetchEnrollmentStatus,
  enroll: api.enroll,
}));

afterEach(() => {
  state.session = null;
  state.enrollment = null;
  state.loading = false;
  vi.clearAllMocks();
});

const asSession = (over: Partial<Session>): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  ...over,
});

const asStatus = (over: Partial<EnrollmentStatus> = {}): EnrollmentStatus => ({
  active_challenge: { id: 1, name: "Stranger Things Challenge" },
  enrolled: false,
  ...over,
});

describe("Landing eligibility gate (US-2 / FR-A3)", () => {
  it("current student sees the signed-in content and a Join CTA", async () => {
    state.session = asSession({ isCurrentStudent: true });
    api.fetchEnrollmentStatus.mockResolvedValue(asStatus());

    render(<Landing />);

    expect(
      await screen.findByRole("heading", { name: /you're signed in/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /join the stranger things challenge/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/not eligible to join/i)).toBeNull();
  });

  it("non-current student is blocked with the friendly eligibility card", async () => {
    state.session = asSession({ affiliation: "alum", isCurrentStudent: false });

    render(<Landing />);

    expect(
      await screen.findByRole("heading", { name: /not eligible to join/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^join the/i })).toBeNull();
    // A blocked user is never asked what they could join.
    expect(api.fetchEnrollmentStatus).not.toHaveBeenCalled();
  });
});

describe("Landing challenge enrollment (US-3 / FR-C1)", () => {
  it("labels the CTA with the active challenge's theme", async () => {
    state.session = asSession({});
    api.fetchEnrollmentStatus.mockResolvedValue(
      asStatus({ active_challenge: { id: 7, name: "Harry Potter Challenge" } }),
    );

    render(<Landing />);

    expect(
      await screen.findByRole("button", { name: /join the harry potter challenge/i }),
    ).toBeInTheDocument();
  });

  it("enrolls on tap and takes the student to their passport", async () => {
    state.session = asSession({});
    api.fetchEnrollmentStatus.mockResolvedValue(asStatus());
    api.enroll.mockResolvedValue({ challenge_id: 1, enrolled_at: "2025-09-02T00:00:00Z" });

    render(<Landing />);
    await userEvent.click(
      await screen.findByRole("button", { name: /join the stranger things challenge/i }),
    );

    expect(api.enroll).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("redirect:/passport")).toBeInTheDocument();
  });

  it("already-enrolled student goes straight to the passport, without re-enrolling", async () => {
    state.session = asSession({});
    api.fetchEnrollmentStatus.mockResolvedValue(asStatus({ enrolled: true }));

    render(<Landing />);

    expect(await screen.findByText("redirect:/passport")).toBeInTheDocument();
    expect(api.enroll).not.toHaveBeenCalled();
  });

  it("no active challenge for the campus shows a message and no enroll action", async () => {
    state.session = asSession({});
    api.fetchEnrollmentStatus.mockResolvedValue(
      asStatus({ active_challenge: null, enrolled: false }),
    );

    render(<Landing />);

    expect(
      await screen.findByRole("heading", { name: /no active challenge/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^join the/i })).toBeNull();
  });

  it("surfaces a failed enrollment instead of pretending it worked", async () => {
    state.session = asSession({});
    api.fetchEnrollmentStatus.mockResolvedValue(asStatus());
    api.enroll.mockRejectedValue(new Error("boom"));

    render(<Landing />);
    await userEvent.click(
      await screen.findByRole("button", { name: /join the stranger things challenge/i }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("redirect:/passport")).toBeNull();
  });

  it("a failed status lookup is not reported as 'no active challenge'", async () => {
    state.session = asSession({});
    api.fetchEnrollmentStatus.mockRejectedValue(new Error("network down"));

    render(<Landing />);

    expect(
      await screen.findByRole("heading", { name: /something went wrong/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /no active challenge/i })).toBeNull();
  });
});

describe("Landing staff routing (US-11)", () => {
  // Staff have affiliation "staff", so isCurrentStudent is false. Before this
  // routing existed they hit the student eligibility gate and were shown
  // "not eligible to join", leaving the Challenge Builder reachable only by
  // typing /admin.
  it.each([
    ["staff", "staff@csub.edu"],
    ["admin", "admin@csub.edu"],
  ])("sends a %s session to the Challenge Builder", (affiliation, subject) => {
    state.session = asSession({ affiliation, subject, isCurrentStudent: false });

    render(<Landing />);

    expect(screen.getByText("redirect:/admin")).toBeInTheDocument();
    expect(screen.queryByText(/not eligible to join/i)).toBeNull();
  });

  it("does not ask the enrollment API about a staff session", () => {
    state.session = asSession({ affiliation: "staff", isCurrentStudent: false });

    render(<Landing />);

    // Staff are redirected before the student enroll flow runs; /enrollment is
    // gated on current-student and would 403 anyway.
    expect(api.fetchEnrollmentStatus).not.toHaveBeenCalled();
  });

  it("renders from the bootstrap seed without asking /enrollment again", async () => {
    state.session = asSession({});
    state.enrollment = asStatus({
      active_challenge: { id: 7, name: "Harry Potter Challenge" },
    });

    render(<Landing />);

    expect(
      await screen.findByRole("button", { name: /join the harry potter challenge/i }),
    ).toBeInTheDocument();
    // The hop this screen exists to stop making: the answer arrived with the session.
    expect(api.fetchEnrollmentStatus).not.toHaveBeenCalled();
  });

  it("redirects a seeded, already-enrolled student straight to the passport", async () => {
    state.session = asSession({});
    state.enrollment = asStatus({ enrolled: true });

    render(<Landing />);

    // No spinner in between: the first paint already knows where this student goes.
    expect(screen.getByText("redirect:/passport")).toBeInTheDocument();
    expect(api.fetchEnrollmentStatus).not.toHaveBeenCalled();
  });

  it("falls back to fetching when the session arrived without a seed", async () => {
    // Offline, or an eligible student whose bootstrap carried no enrollment. The
    // screen must still be able to answer for itself.
    state.session = asSession({});
    state.enrollment = null;
    api.fetchEnrollmentStatus.mockResolvedValue(asStatus());

    render(<Landing />);

    expect(
      await screen.findByRole("button", { name: /join the stranger things challenge/i }),
    ).toBeInTheDocument();
    expect(api.fetchEnrollmentStatus).toHaveBeenCalled();
  });

  it("keeps a plain student on the student flow", async () => {
    state.session = asSession({ affiliation: "student" });
    api.fetchEnrollmentStatus.mockResolvedValue({
      active_challenge: { id: 1, name: "Stranger Things Wellness Challenge" },
      enrolled: false,
    } as EnrollmentStatus);

    render(<Landing />);

    // Guards against the redirect loop: AdminRoute bounces non-admins /admin ->
    // /home, so a student must never be bounced /home -> /admin.
    expect(screen.queryByText("redirect:/admin")).toBeNull();
    expect(
      await screen.findByRole("button", { name: /join the/i }),
    ).toBeInTheDocument();
  });
});

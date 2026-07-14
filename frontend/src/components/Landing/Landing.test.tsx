import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Session } from "../../types/session";
import type { EnrollmentStatus } from "../../types/enrollment";
import { Landing } from "./Landing";

const state = vi.hoisted(() => ({
  session: null as Session | null,
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

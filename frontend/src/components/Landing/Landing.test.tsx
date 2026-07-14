import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Session } from "../../types/session";
import { Landing } from "./Landing";

const state = vi.hoisted(() => ({
  session: null as Session | null,
  loading: false,
}));
const signOut = vi.fn();

vi.mock("../../auth/SessionProvider", () => ({
  useSession: () => ({ ...state, signOut, refresh: vi.fn() }),
}));
vi.mock("react-router-dom", () => ({
  Navigate: ({ to }: { to: string }) => <div>redirect:{to}</div>,
}));

afterEach(() => {
  state.session = null;
  state.loading = false;
});

const asSession = (over: Partial<Session>): Session => ({
  subject: "abc@csub.edu",
  affiliation: "student",
  isCurrentStudent: true,
  ...over,
});

describe("Landing eligibility gate (US-2 / FR-A3)", () => {
  it("current student sees the signed-in content and a Join CTA", () => {
    state.session = asSession({ isCurrentStudent: true });
    render(<Landing />);
    expect(screen.getByRole("heading", { name: /you're signed in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /join the challenge/i })).toBeInTheDocument();
    expect(screen.queryByText(/not eligible to join/i)).toBeNull();
  });

  it("non-current student is blocked with the friendly eligibility card", () => {
    state.session = asSession({ affiliation: "alum", isCurrentStudent: false });
    render(<Landing />);
    expect(
      screen.getByRole("heading", { name: /not eligible to join/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /join the challenge/i })).toBeNull();
  });
});

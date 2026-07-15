import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoActiveChallenge } from "./NoActiveChallenge";

const signOut = vi.fn();

vi.mock("../../auth/SessionProvider", () => ({
  useSession: () => ({ session: null, loading: false, signOut, refresh: vi.fn() }),
}));

describe("NoActiveChallenge (US-3 / FR-C1)", () => {
  it("explains that the campus has nothing running", () => {
    render(<NoActiveChallenge />);
    expect(
      screen.getByRole("heading", { name: /no active challenge/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/check back soon/i)).toBeInTheDocument();
  });

  it("offers no enrollment action", () => {
    render(<NoActiveChallenge />);
    expect(screen.queryByRole("button", { name: /join/i })).toBeNull();
  });

  it("can sign out", async () => {
    render(<NoActiveChallenge />);
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(signOut).toHaveBeenCalledTimes(1);
  });
});

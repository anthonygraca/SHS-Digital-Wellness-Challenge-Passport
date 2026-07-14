import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EligibilityBlocked } from "./EligibilityBlocked";

const signOut = vi.fn();
vi.mock("../../auth/SessionProvider", () => ({
  useSession: () => ({ signOut }),
}));

describe("EligibilityBlocked (US-2 / FR-A3)", () => {
  it("shows a friendly eligibility message and no enroll action", () => {
    render(<EligibilityBlocked />);
    expect(
      screen.getByRole("heading", { name: /not eligible to join/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/limited to current students/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /join/i })).toBeNull();
  });

  it("lets the user sign out", async () => {
    render(<EligibilityBlocked />);
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(signOut).toHaveBeenCalledTimes(1);
  });
});

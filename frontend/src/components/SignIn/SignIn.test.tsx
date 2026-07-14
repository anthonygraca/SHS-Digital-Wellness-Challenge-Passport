import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SignIn } from "./SignIn";

describe("SignIn (US-1 / FR-A1, FR-A2)", () => {
  it("renders the single campus SSO action", () => {
    render(<SignIn onSignIn={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /sign in with campus sso/i }),
    ).toBeInTheDocument();
  });

  it("exposes NO credential inputs (no ID, no password)", () => {
    const { container } = render(<SignIn onSignIn={vi.fn()} />);
    // Hard constraint: authentication is SSO-only — there is nothing to type.
    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(
      screen.queryByLabelText(/password|id number|student id/i),
    ).toBeNull();
  });

  it("shows the SAML / no-ID-number caption", () => {
    render(<SignIn onSignIn={vi.fn()} />);
    expect(
      screen.getByText(/saml single sign-on · no id number needed/i),
    ).toBeInTheDocument();
  });

  it("triggers sign-in exactly once on click", async () => {
    const onSignIn = vi.fn();
    render(<SignIn onSignIn={onSignIn} />);
    await userEvent.click(
      screen.getByRole("button", { name: /sign in with campus sso/i }),
    );
    expect(onSignIn).toHaveBeenCalledTimes(1);
  });
});

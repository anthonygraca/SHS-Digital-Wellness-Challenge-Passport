import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SignIn } from "./SignIn";

// SignIn renders <VersionStamp/>, which fetches /api/version on mount (#64).
// Stubbed so these tests stay hermetic and make no network call; the stamp's own
// behaviour is covered in VersionStamp.test.tsx.
const api = vi.hoisted(() => ({ fetchVersion: vi.fn() }));
vi.mock("../../api/version", () => ({ fetchVersion: api.fetchVersion }));

describe("SignIn (US-1 / FR-A1, FR-A2)", () => {
  it("still renders when the version endpoint is unreachable", async () => {
    // The stamp is diagnostic garnish; it must never break sign-in.
    api.fetchVersion.mockRejectedValue(new Error("network down"));
    render(<SignIn onSignIn={vi.fn()} />);
    expect(
      await screen.findByRole("button", { name: /sign in with campus sso/i }),
    ).toBeInTheDocument();
  });

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

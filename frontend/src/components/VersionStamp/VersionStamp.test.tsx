import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { VersionStamp } from "./VersionStamp";

const api = vi.hoisted(() => ({ fetchVersion: vi.fn() }));
vi.mock("../../api/version", () => ({ fetchVersion: api.fetchVersion }));

afterEach(() => {
  vi.clearAllMocks();
});

describe("VersionStamp (#64)", () => {
  it("shows the version and the deployed commit", async () => {
    api.fetchVersion.mockResolvedValue({
      version: "0.1.0",
      gitSha: "a1b2c3d",
      builtAt: "2026-07-15T12:00:00Z",
    });
    render(<VersionStamp />);
    expect(await screen.findByTestId("version-stamp")).toHaveTextContent(
      "v0.1.0 · a1b2c3d",
    );
  });

  it("keeps the -dirty marker, which is the point of it", async () => {
    // A -dirty tag means the image was built from an uncommitted tree and does
    // not correspond to any commit. Hiding that would defeat the stamp.
    api.fetchVersion.mockResolvedValue({
      version: "0.1.0",
      gitSha: "a1b2c3d-dirty",
      builtAt: "2026-07-15T12:00:00Z",
    });
    render(<VersionStamp />);
    expect(await screen.findByTestId("version-stamp")).toHaveTextContent(
      "a1b2c3d-dirty",
    );
  });

  it("renders nothing for an unstamped build", async () => {
    api.fetchVersion.mockResolvedValue({
      version: "0.1.0",
      gitSha: "unknown",
      builtAt: "unknown",
    });
    const { container } = render(<VersionStamp />);
    await waitFor(() => expect(api.fetchVersion).toHaveBeenCalled());
    expect(screen.queryByTestId("version-stamp")).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it("stays silent when the endpoint fails", async () => {
    // Hard constraint: a diagnostic garnish must never break the screen it is on.
    api.fetchVersion.mockRejectedValue(new Error("network down"));
    const { container } = render(<VersionStamp />);
    await waitFor(() => expect(api.fetchVersion).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

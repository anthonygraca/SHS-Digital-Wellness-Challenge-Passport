import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { OfflineBanner } from "./OfflineBanner";

describe("OfflineBanner (US-6 / FR-C4)", () => {
  it("stays out of the way when the data on screen is live", () => {
    const { container } = render(<OfflineBanner online stale={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("says we're offline and that progress is the last synced copy", () => {
    render(<OfflineBanner online={false} stale />);
    expect(
      screen.getByText(/you're offline\. showing your last synced progress/i),
    ).toBeInTheDocument();
  });

  it("shows while offline even before anything has gone stale", () => {
    // The connection is the student's answer to "why is my check-in refused?", so
    // the banner must be up the moment we go offline, not only once a fetch fails.
    render(<OfflineBanner online={false} stale={false} />);
    expect(screen.getByRole("status", { name: /offline/i })).toBeInTheDocument();
  });

  it("does not claim we're offline when a refresh failed but the connection looks up", () => {
    // The captive-portal case: navigator.onLine says yes, every fetch says no.
    // Saying "you're offline" here would be a guess.
    render(<OfflineBanner online stale />);
    expect(
      screen.getByText(/couldn't refresh — showing your last synced progress/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/you're offline/i)).toBeNull();
  });

  it("announces politely, as status rather than an alert", () => {
    // Matches the prize indicator: information, not an error, and it must not
    // interrupt a screen reader mid-sentence. Named explicitly, since a status
    // region takes no accessible name from its contents.
    render(<OfflineBanner online={false} stale />);
    expect(screen.getByRole("status", { name: /offline/i })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

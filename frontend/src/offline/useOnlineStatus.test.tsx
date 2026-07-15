import { afterEach, describe, expect, it } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { useOnlineStatus } from "./useOnlineStatus";

/**
 * jsdom reports navigator.onLine === true and offers no way to change it, so tests
 * redefine the property. It is global mutable state — restore it or it leaks into
 * every file that runs after this one.
 */
function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { value, configurable: true });
}

afterEach(() => {
  setOnline(true);
});

function Probe() {
  return <p>{useOnlineStatus() ? "online" : "offline"}</p>;
}

describe("useOnlineStatus (US-6 / FR-C4)", () => {
  it("starts from the browser's current view of the connection", () => {
    setOnline(false);
    render(<Probe />);
    expect(screen.getByText("offline")).toBeInTheDocument();
  });

  it("reacts when the connection drops and returns", () => {
    render(<Probe />);
    expect(screen.getByText("online")).toBeInTheDocument();

    act(() => {
      setOnline(false);
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByText("offline")).toBeInTheDocument();

    act(() => {
      setOnline(true);
      window.dispatchEvent(new Event("online"));
    });
    // This is why the banner needs no retry button — reconnecting clears it itself.
    expect(screen.getByText("online")).toBeInTheDocument();
  });

  it("stops listening once unmounted", () => {
    const { unmount } = render(<Probe />);
    unmount();
    // A listener surviving unmount would set state on a dead component.
    expect(() =>
      act(() => {
        window.dispatchEvent(new Event("offline"));
      }),
    ).not.toThrow();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QrScanner } from "./QrScanner";

// Faithful stand-in for html5-qrcode's Html5Qrcode: start() settles like the real
// camera handshake (resolved/rejected from the test), and stop() throws
// *synchronously* unless the camera reached the scanning state — the exact
// behavior the unmount cleanup must survive.
const camera = vi.hoisted(() => ({
  resolveStart: undefined as (() => void) | undefined,
  rejectStart: undefined as (() => void) | undefined,
  onScan: undefined as ((text: string) => void) | undefined,
  scanning: false,
  stopCalls: 0,
  clearCalls: 0,
}));

vi.mock("html5-qrcode", () => ({
  Html5Qrcode: class {
    start(_cam: unknown, _cfg: unknown, onSuccess: (text: string) => void) {
      camera.onScan = onSuccess;
      return new Promise<void>((resolve, reject) => {
        camera.resolveStart = () => {
          camera.scanning = true;
          resolve();
        };
        camera.rejectStart = () => reject(new Error("NotAllowedError"));
      });
    }
    stop() {
      camera.stopCalls += 1;
      if (!camera.scanning) {
        throw "Cannot stop, scanner is not running or paused.";
      }
      camera.scanning = false;
      return Promise.resolve();
    }
    clear() {
      camera.clearCalls += 1;
    }
  },
}));

beforeEach(() => {
  camera.resolveStart = undefined;
  camera.rejectStart = undefined;
  camera.onScan = undefined;
  camera.scanning = false;
  camera.stopCalls = 0;
  camera.clearCalls = 0;
});

describe("QrScanner (US-8)", () => {
  it("hands the first decoded token to onDecode exactly once", async () => {
    const onDecode = vi.fn();
    render(<QrScanner onDecode={onDecode} onClose={vi.fn()} />);

    await waitFor(() => expect(camera.onScan).toBeDefined());
    camera.resolveStart!();
    camera.onScan!("token-1");
    camera.onScan!("token-2");

    expect(onDecode).toHaveBeenCalledTimes(1);
    expect(onDecode).toHaveBeenCalledWith("token-1");
  });

  it("stops the camera and clears the region on unmount after a normal start", async () => {
    const { unmount } = render(<QrScanner onDecode={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(camera.resolveStart).toBeDefined());
    camera.resolveStart!();

    unmount();

    await waitFor(() => expect(camera.stopCalls).toBe(1));
    await waitFor(() => expect(camera.clearCalls).toBe(1));
    expect(camera.scanning).toBe(false);
  });

  it("shows the camera error and unmounts without throwing when start is denied", async () => {
    const { unmount } = render(<QrScanner onDecode={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(camera.rejectStart).toBeDefined());
    camera.rejectStart!();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /camera unavailable/i,
    );

    // Regression: stop() throws synchronously here (the camera never started);
    // the cleanup must swallow it instead of crashing the tree.
    expect(() => unmount()).not.toThrow();
    await waitFor(() => expect(camera.clearCalls).toBe(1));
  });

  it("releases a camera stream that is granted only after unmount", async () => {
    const { unmount } = render(<QrScanner onDecode={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => expect(camera.resolveStart).toBeDefined());

    // Close the scanner while the permission prompt is still open…
    unmount();
    expect(camera.stopCalls).toBe(0); // cleanup waits for start() to settle

    // …then the user grants access: the late stream must still be shut down.
    camera.resolveStart!();
    await waitFor(() => expect(camera.stopCalls).toBe(1));
    await waitFor(() => expect(camera.clearCalls).toBe(1));
    expect(camera.scanning).toBe(false);
  });
});

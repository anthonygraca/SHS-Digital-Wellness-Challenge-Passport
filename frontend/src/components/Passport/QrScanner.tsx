import { useEffect, useRef, useState } from "react";
import type { Html5Qrcode } from "html5-qrcode";
import styles from "./Passport.module.css";

const REGION_ID = "qr-scanner-region";

/**
 * Camera QR scanner for in-app event check-in (US-8). Wraps `html5-qrcode`,
 * decodes the first QR seen, and hands the raw token string to `onDecode` exactly
 * once. `html5-qrcode` is dynamically imported so it only loads (and touches the
 * camera) when the scanner actually opens — keeping it out of the initial bundle
 * and out of tests that never mount this component.
 */
export function QrScanner({
  onDecode,
  onClose,
}: {
  onDecode: (token: string) => void;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  // Keep the latest onDecode without restarting the camera on each render.
  const onDecodeRef = useRef(onDecode);
  onDecodeRef.current = onDecode;
  const decodedRef = useRef(false);

  useEffect(() => {
    let scanner: Html5Qrcode | null = null;
    let cancelled = false;

    const startPromise = import("html5-qrcode").then(({ Html5Qrcode }) => {
      if (cancelled) return;
      scanner = new Html5Qrcode(REGION_ID);
      return scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (decodedText) => {
          if (decodedRef.current) return;
          decodedRef.current = true;
          onDecodeRef.current(decodedText);
        },
        () => {
          // Per-frame "no QR in view" callbacks are normal — ignore them.
        },
      );
    });

    startPromise.catch(() => {
      if (!cancelled) {
        setError(
          "Camera unavailable — allow camera access, or ask the attendant.",
        );
      }
    });

    return () => {
      cancelled = true;
      // Shut down only after start() settles: unmounting mid-startup (permission
      // prompt still open) must not leave a just-granted camera stream running.
      // stop() throws *synchronously* when the camera never reached the scanning
      // state (e.g. permission denied), so it needs a try/catch, not just .catch().
      void startPromise
        .catch(() => {})
        .finally(() => {
          if (!scanner) return;
          try {
            scanner
              .stop()
              .catch(() => {})
              .finally(() => scanner?.clear());
          } catch {
            scanner.clear();
          }
        });
    };
  }, []);

  // Escape closes the scanner, matching the detail sheet.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        className={styles.sheet}
        role="dialog"
        aria-modal="true"
        aria-label="Scan event QR"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.sheetHandle} aria-hidden="true" />
        <button
          type="button"
          className={styles.close}
          onClick={onClose}
          aria-label="Close"
        >
          ✕
        </button>

        <h2 className={styles.sheetTitle}>Scan event QR</h2>
        <p className={styles.sheetCaption}>
          Point your camera at the QR under the event to check in.
        </p>

        <div id={REGION_ID} className={styles.qrRegion} />
        {error && (
          <p className={styles.scanError} role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

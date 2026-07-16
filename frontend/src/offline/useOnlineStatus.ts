import { useEffect, useState } from "react";

/**
 * Whether the browser currently believes it has a connection (US-6 / FR-C4).
 *
 * This drives what we *tell* the student — the offline banner and the refusal to
 * start a check-in — and nothing else. It deliberately does not drive the cache
 * fallback: `navigator.onLine === true` only means a network interface exists, so a
 * captive portal or a dead uplink still reports online. The fallback to the last
 * snapshot keys off an actually-rejected fetch instead, which cannot be fooled that
 * way. The two mechanisms answer different questions and are independent on purpose.
 */
export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return online;
}

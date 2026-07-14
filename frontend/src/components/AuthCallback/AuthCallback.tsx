import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useSession } from "../../auth/SessionProvider";
import { AuthError } from "../AuthError/AuthError";

type Phase = "checking" | "ok" | "failed";

/**
 * Post-SAML landing. The backend redirects here after the ACS step:
 *  - ?status=failed  → invalid assertion, no record created → retry prompt.
 *  - otherwise       → refresh the session; success routes to /home, and a
 *                      missing session also falls back to the retry prompt.
 */
export function AuthCallback() {
  const [params] = useSearchParams();
  const { refresh } = useSession();
  const failed = params.get("status") === "failed";
  const [phase, setPhase] = useState<Phase>(failed ? "failed" : "checking");

  useEffect(() => {
    if (failed) return;
    let active = true;
    void refresh().then((session) => {
      if (active) setPhase(session ? "ok" : "failed");
    });
    return () => {
      active = false;
    };
  }, [failed, refresh]);

  if (phase === "ok") return <Navigate to="/home" replace />;
  if (phase === "failed") return <AuthError />;
  return <div style={{ padding: 24 }}>Completing sign-in…</div>;
}

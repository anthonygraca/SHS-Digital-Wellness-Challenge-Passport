import { useEffect, useState } from "react";
import { fetchVersion } from "../../api/version";
import type { VersionInfo } from "../../types/version";
import styles from "./VersionStamp.module.css";

/**
 * Which build is this? (#64)
 *
 * release.sh tags every image with the git SHA it was built from, but a running
 * deployment had no way to say which SHA it was — you had to go read ECR. This
 * puts the answer on the screen, so "is the fix actually deployed?" and "which
 * commit is the stakeholder looking at?" are answerable by looking.
 *
 * Renders nothing rather than an error state, on purpose: this is diagnostic
 * garnish on the sign-in screen, and it must never be the reason a student
 * cannot sign in. If /api/version is unreachable or the build is unstamped,
 * showing nothing is strictly better than showing "unknown" — which reads as a
 * fault to a stakeholder and means nothing to a student.
 */
export function VersionStamp() {
  const [info, setInfo] = useState<VersionInfo | null>(null);

  useEffect(() => {
    let live = true;
    fetchVersion()
      .then((v) => live && setInfo(v))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  // "unknown" is what an unstamped build honestly reports (a plain docker build,
  // or local uvicorn). There is nothing useful to show for it.
  if (!info || info.gitSha === "unknown") return null;

  return (
    <p className={styles.stamp} data-testid="version-stamp">
      v{info.version} · {info.gitSha}
    </p>
  );
}

/** Build provenance reported by GET /api/version. */
export interface VersionInfo {
  version: string;
  /** Short git SHA, "-dirty" suffixed if the tree was dirty. "unknown" if unstamped. */
  gitSha: string;
  /** ISO-8601 build time, or "unknown" if unstamped. */
  builtAt: string;
}

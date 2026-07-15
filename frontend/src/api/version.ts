import type { VersionInfo } from "../types/version";
import { request } from "./http";

/** What the *server* is running — deliberately not what this bundle was built as.
 *
 * The service worker (vite.config.ts, registerType "autoUpdate") can serve a
 * bundle several deploys old, so a build-time constant here would report the
 * cached bundle's version rather than the deployment's. Ask the server. */
export function fetchVersion(): Promise<VersionInfo> {
  return request<VersionInfo>("/api/version");
}

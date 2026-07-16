import type { Theme, ThemeUpdate } from "../types/theme";
import { request } from "./http";

const PREFIX = "/api/themes";

export function listThemes(): Promise<Theme[]> {
  return request<Theme[]>(PREFIX);
}

export function getTheme(id: string): Promise<Theme> {
  return request<Theme>(`${PREFIX}/${id}`);
}

export function updateTheme(id: string, data: ThemeUpdate): Promise<Theme> {
  return request<Theme>(`${PREFIX}/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

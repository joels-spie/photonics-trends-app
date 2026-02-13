import type { AppConfigResponse } from "./types";

const runtimeApiBase = (window as any)?.photonicsRuntime?.apiBase as string | undefined;
const API_BASE = runtimeApiBase || import.meta.env.VITE_API_BASE || "";

function apiUrl(path: string): string {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}

export async function getConfig(): Promise<AppConfigResponse> {
  const res = await fetch(apiUrl("/api/config"));
  if (!res.ok) throw new Error("Failed to load config");
  return res.json();
}

export async function postJson<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

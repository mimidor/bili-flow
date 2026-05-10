import { api } from "../api";
import { buildQuery } from "../utils";

function qteasyPath(path: string): string {
  return path.startsWith("/qteasy") ? path : `/qteasy${path.startsWith("/") ? path : `/${path}`}`;
}

export const qteasyApi = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | null | undefined>) =>
    api.get<T>(`${qteasyPath(path)}${params ? buildQuery(params) : ""}`),
  post: <T>(path: string, body?: unknown) => api.post<T>(qteasyPath(path), body),
  put: <T>(path: string, body?: unknown) => api.put<T>(qteasyPath(path), body),
  patch: <T>(path: string, body?: unknown) => api.patch<T>(qteasyPath(path), body),
  delete: <T>(path: string) => api.delete<T>(qteasyPath(path)),
  raw: (path: string, init?: RequestInit) => api.raw(qteasyPath(path), init),
};

export function qteasyDownloadUrl(path: string, params?: Record<string, string | number | boolean | null | undefined>): string {
  return `${qteasyPath(path)}${params ? buildQuery(params) : ""}`;
}

export function qteasyUnwrap<T>(payload: unknown, fallback: T): T {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if ("data" in record && record.data !== null && record.data !== undefined) {
      return record.data as T;
    }
    if ("result" in record && record.result !== null && record.result !== undefined) {
      return record.result as T;
    }
  }
  return (payload as T) ?? fallback;
}

export function qteasyExtractItems<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) {
    return payload as T[];
  }
  if (!payload || typeof payload !== "object") {
    return [];
  }
  const record = payload as Record<string, unknown>;
  if (Array.isArray(record.items)) {
    return record.items as T[];
  }
  if (Array.isArray(record.data)) {
    return record.data as T[];
  }
  if (record.data && typeof record.data === "object") {
    const nested = record.data as Record<string, unknown>;
    if (Array.isArray(nested.items)) {
      return nested.items as T[];
    }
    if (Array.isArray(nested.data)) {
      return nested.data as T[];
    }
  }
  return [];
}

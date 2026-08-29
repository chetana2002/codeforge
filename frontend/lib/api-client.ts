import type { Envelope } from "@/types/api";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown> | null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  let body: Envelope<T> | null = null;
  try {
    body = (await response.json()) as Envelope<T>;
  } catch {
    // No JSON body (e.g. a network-level failure surfaced as an empty response).
  }

  if (!response.ok || body?.error) {
    throw new ApiClientError(
      response.status,
      body?.error?.code ?? "UNKNOWN_ERROR",
      body?.error?.message ?? "Something went wrong. Please try again.",
      body?.error?.details,
    );
  }

  if (body?.data === undefined || body?.data === null) {
    return body?.data as T;
  }
  return body.data;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "POST", body: json !== undefined ? JSON.stringify(json) : undefined }),
  patch: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "PATCH", body: json !== undefined ? JSON.stringify(json) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

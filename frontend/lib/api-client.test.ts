import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiClientError } from "@/lib/api-client";

function mockFetchOnce(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  );
}

describe("apiClient", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("unwraps the {data, error} envelope and returns just the data", async () => {
    mockFetchOnce({ data: { id: "abc123" }, error: null });
    const result = await apiClient.get<{ id: string }>("/projects/abc123");
    expect(result).toEqual({ id: "abc123" });
  });

  it("sends the request with credentials and a JSON content type", async () => {
    mockFetchOnce({ data: null, error: null });
    await apiClient.post("/projects", { name: "Test" });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/projects"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ name: "Test" }),
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
  });

  it("throws ApiClientError with the envelope's error details on a non-ok response", async () => {
    mockFetchOnce(
      { data: null, error: { code: "PROJECT_NOT_FOUND", message: "Project not found" } },
      404,
    );

    await expect(apiClient.get("/projects/missing")).rejects.toMatchObject({
      status: 404,
      code: "PROJECT_NOT_FOUND",
      message: "Project not found",
    });
  });

  it("throws a generic ApiClientError when the response has no JSON body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error("not json")),
      }),
    );

    const error = await apiClient.get("/anything").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiClientError);
    expect((error as ApiClientError).code).toBe("UNKNOWN_ERROR");
  });
});

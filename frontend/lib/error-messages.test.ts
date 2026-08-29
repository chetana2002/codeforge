import { describe, expect, it } from "vitest";

import { ApiClientError } from "@/lib/api-client";
import { getFriendlyErrorMessage } from "@/lib/error-messages";

describe("getFriendlyErrorMessage", () => {
  it("maps a known error code to its friendly message", () => {
    const error = new ApiClientError(409, "EMAIL_ALREADY_EXISTS", "raw backend message");
    expect(getFriendlyErrorMessage(error)).toBe(
      "An account with that email already exists. Try logging in instead.",
    );
  });

  it("falls back to the raw message for an unmapped code", () => {
    const error = new ApiClientError(500, "SOME_UNMAPPED_CODE", "backend-provided detail");
    expect(getFriendlyErrorMessage(error)).toBe("backend-provided detail");
  });

  it("surfaces the first field error for a validation failure", () => {
    const error = new ApiClientError(422, "VALIDATION_ERROR", "Request validation failed", {
      errors: [{ loc: ["body", "email"], msg: "field required" }],
    });
    expect(getFriendlyErrorMessage(error)).toBe("email: field required");
  });

  it("gives a generic message when a validation failure has no field errors", () => {
    const error = new ApiClientError(422, "VALIDATION_ERROR", "Request validation failed", {
      errors: [],
    });
    expect(getFriendlyErrorMessage(error)).toBe("Please check the form and try again.");
  });

  it("gives a generic message for a non-ApiClientError", () => {
    expect(getFriendlyErrorMessage(new Error("boom"))).toBe(
      "Something went wrong. Please try again.",
    );
    expect(getFriendlyErrorMessage("not even an error")).toBe(
      "Something went wrong. Please try again.",
    );
  });
});

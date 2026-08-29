import { ApiClientError } from "@/lib/api-client";

const FRIENDLY_MESSAGES: Record<string, string> = {
  EMAIL_ALREADY_EXISTS: "An account with that email already exists. Try logging in instead.",
  INVALID_CREDENTIALS: "That email or password isn't right. Please try again.",
  UNAUTHENTICATED: "Your session has expired. Please log in again.",
  SESSION_EXPIRED: "Your session has expired. Please log in again.",
  PROJECT_NOT_FOUND: "That project doesn't exist or you don't have access to it.",
  FILE_NOT_FOUND: "That file doesn't exist or you don't have access to it.",
  FILE_ALREADY_EXISTS: "A file or folder with that name already exists here.",
  PARENT_NOT_A_FOLDER: "You can't create items inside a file — only inside a folder.",
  INVALID_MOVE: "You can't move a folder into itself or one of its own subfolders.",
  RATE_LIMITED: "You're doing that too much — please wait a moment and try again.",
};

interface FieldError {
  loc?: unknown[];
  msg?: string;
}

export function getFriendlyErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === "VALIDATION_ERROR") {
      const fieldErrors = (error.details?.errors as FieldError[] | undefined) ?? [];
      const first = fieldErrors[0];
      if (first?.msg) {
        const field = Array.isArray(first.loc) ? first.loc.at(-1) : undefined;
        return typeof field === "string" ? `${field}: ${first.msg}` : first.msg;
      }
      return "Please check the form and try again.";
    }

    return FRIENDLY_MESSAGES[error.code] ?? error.message ?? "Something went wrong. Please try again.";
  }

  return "Something went wrong. Please try again.";
}

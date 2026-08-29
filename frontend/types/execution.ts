export type ExecutionStatus = "queued" | "running" | "success" | "failed" | "timeout" | "cancelled";

export interface Execution {
  id: string;
  project_id: string;
  file_id: string;
  user_id: string;
  language: string;
  status: ExecutionStatus;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  duration_ms: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExecutionSummary {
  id: string;
  project_id: string;
  file_id: string;
  language: string;
  status: ExecutionStatus;
  exit_code: number | null;
  duration_ms: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export const TERMINAL_STATUSES: ExecutionStatus[] = ["success", "failed", "timeout", "cancelled"];

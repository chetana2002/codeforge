"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { API_BASE_URL, apiClient } from "@/lib/api-client";
import type { Page } from "@/types/api";
import { type Execution, type ExecutionSummary, TERMINAL_STATUSES } from "@/types/execution";

const executionKey = (executionId: string) => ["executions", executionId] as const;

export interface ExecutionWithProject extends ExecutionSummary {
  project_name: string;
}

export interface ExecutionStats {
  total: number;
  successful: number;
  failed: number;
  last_activity_at: string | null;
}

export function useExecutionStats() {
  return useQuery({
    queryKey: ["executions", "stats"],
    queryFn: () => apiClient.get<ExecutionStats>("/executions/stats"),
  });
}

export function useMyExecutions(params: { page?: number; pageSize?: number } = {}) {
  const { page = 1, pageSize = 5 } = params;
  return useQuery({
    queryKey: ["executions", "list", page, pageSize],
    queryFn: () =>
      apiClient.get<Page<ExecutionWithProject>>(
        `/executions?page=${page}&page_size=${pageSize}`,
      ),
  });
}

export function useExecution(executionId: string | undefined) {
  return useQuery({
    queryKey: executionKey(executionId ?? ""),
    queryFn: () => apiClient.get<Execution>(`/executions/${executionId}`),
    enabled: Boolean(executionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || TERMINAL_STATUSES.includes(status)) return false;
      return 1000;
    },
  });
}

// Push-based complement to useExecution's polling: writes SSE events into
// the same query cache entry. Polling stays as a fallback for viewers whose
// network path doesn't support long-lived SSE.
export function useExecutionStream(executionId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!executionId) return;

    const source = new EventSource(`${API_BASE_URL}/executions/${executionId}/stream`, {
      withCredentials: true,
    });

    source.onmessage = (event) => {
      const execution = JSON.parse(event.data) as Execution;
      queryClient.setQueryData(executionKey(executionId), execution);
      if (TERMINAL_STATUSES.includes(execution.status)) {
        source.close();
      }
    };

    // EventSource auto-reconnects on error; nothing to do here.
    source.onerror = () => undefined;

    return () => source.close();
  }, [executionId, queryClient]);
}

export function useExecuteFile(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) =>
      apiClient.post<Execution>(`/projects/${projectId}/execute`, { file_id: fileId }),
    onSuccess: (execution) => {
      queryClient.setQueryData(executionKey(execution.id), execution);
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "executions"] });
    },
  });
}

export function useCancelExecution(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (executionId: string) =>
      apiClient.post<Execution>(`/executions/${executionId}/cancel`),
    onSuccess: (execution) => {
      queryClient.setQueryData(executionKey(execution.id), execution);
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "executions"] });
    },
  });
}

export function useProjectExecutions(
  projectId: string,
  params: { page?: number; pageSize?: number } = {},
) {
  const { page = 1, pageSize = 20 } = params;
  return useQuery({
    queryKey: ["projects", projectId, "executions", page, pageSize],
    queryFn: () =>
      apiClient.get<Page<ExecutionSummary>>(
        `/projects/${projectId}/executions?page=${page}&page_size=${pageSize}`,
      ),
    placeholderData: (previous) => previous,
  });
}

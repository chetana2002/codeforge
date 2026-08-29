"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Language, Page, Project, ProjectVisibility } from "@/types/api";

const PROJECTS_KEY = ["projects"] as const;
const projectKey = (id: string) => [...PROJECTS_KEY, id] as const;

export function useProjects(params: { page?: number; pageSize?: number; q?: string } = {}) {
  const { page = 1, pageSize = 20, q } = params;
  const search = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (q) search.set("q", q);

  return useQuery({
    queryKey: [...PROJECTS_KEY, "list", page, pageSize, q ?? ""],
    queryFn: () => apiClient.get<Page<Project>>(`/projects?${search.toString()}`),
    placeholderData: (previous) => previous,
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: projectKey(projectId ?? ""),
    queryFn: () => apiClient.get<Project>(`/projects/${projectId}`),
    enabled: Boolean(projectId),
  });
}

export interface CreateProjectInput {
  name: string;
  description?: string;
  language?: Language;
  visibility?: ProjectVisibility;
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateProjectInput) => apiClient.post<Project>("/projects", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

export interface UpdateProjectInput {
  name?: string;
  description?: string | null;
  language?: Language;
  visibility?: ProjectVisibility;
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateProjectInput) => apiClient.patch<Project>(`/projects/${projectId}`, input),
    onSuccess: (project) => {
      queryClient.setQueryData(projectKey(projectId), project);
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => apiClient.delete<{ deleted: boolean }>(`/projects/${projectId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_KEY });
    },
  });
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { FileNode, FileTreeNode, FileType } from "@/types/api";

const treeKey = (projectId: string) => ["files", projectId, "tree"] as const;
const fileKey = (projectId: string, fileId: string) => ["files", projectId, fileId] as const;

export function useFileTree(projectId: string) {
  return useQuery({
    queryKey: treeKey(projectId),
    queryFn: () => apiClient.get<FileTreeNode[]>(`/projects/${projectId}/files`),
  });
}

export function useFile(projectId: string, fileId: string | undefined) {
  return useQuery({
    queryKey: fileKey(projectId, fileId ?? ""),
    queryFn: () => apiClient.get<FileNode>(`/projects/${projectId}/files/${fileId}`),
    enabled: Boolean(fileId),
  });
}

export interface CreateFileInput {
  name: string;
  type: FileType;
  parent_id?: string | null;
  content?: string | null;
}

export function useCreateFile(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateFileInput) =>
      apiClient.post<FileNode>(`/projects/${projectId}/files`, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: treeKey(projectId) });
    },
  });
}

export interface UpdateFileInput {
  name?: string;
  parent_id?: string | null;
  content?: string | null;
}

export function useUpdateFile(projectId: string, fileId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateFileInput) =>
      apiClient.patch<FileNode>(`/projects/${projectId}/files/${fileId}`, input),
    onSuccess: (file) => {
      queryClient.setQueryData(fileKey(projectId, fileId), file);
      queryClient.invalidateQueries({ queryKey: treeKey(projectId) });
    },
  });
}

export function useDeleteFile(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) =>
      apiClient.delete<{ deleted: boolean }>(`/projects/${projectId}/files/${fileId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: treeKey(projectId) });
    },
  });
}

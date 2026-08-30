export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface Envelope<T> {
  data: T | null;
  error: ApiErrorDetail | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export type Language = "python" | "javascript" | "c" | "cpp" | "java";
export type ProjectVisibility = "private" | "public";

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  language: Language;
  visibility: ProjectVisibility;
  created_at: string;
  updated_at: string;
}

export type FileType = "file" | "folder";

export interface FileTreeNode {
  id: string;
  project_id: string;
  parent_id: string | null;
  name: string;
  type: FileType;
  created_at: string;
  updated_at: string;
}

export interface FileNode extends FileTreeNode {
  content: string | null;
}

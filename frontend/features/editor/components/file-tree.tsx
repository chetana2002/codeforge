"use client";

import {
  ChevronDown,
  ChevronRight,
  File as FileIcon,
  FilePlus,
  Folder,
  FolderPlus,
  Loader2,
  MoreHorizontal,
  Trash2,
} from "lucide-react";
import { createContext, useContext, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCreateFile,
  useDeleteFile,
  useFileTree,
  useUpdateFile,
} from "@/features/editor/hooks/use-files";
import { buildTree, type TreeNode } from "@/features/editor/lib/build-tree";
import { getFriendlyErrorMessage } from "@/lib/error-messages";
import { cn } from "@/lib/utils";
import type { FileType } from "@/types/api";

interface TreeContextValue {
  projectId: string;
  activeFileId: string | null;
  expanded: Set<string>;
  toggleExpanded: (id: string) => void;
  onSelectFile: (id: string) => void;
  renamingId: string | null;
  setRenamingId: (id: string | null) => void;
  creating: { parentId: string | null; type: FileType } | null;
  setCreating: (value: { parentId: string | null; type: FileType } | null) => void;
  deletingNode: TreeNode | null;
  setDeletingNode: (node: TreeNode | null) => void;
}

const TreeContext = createContext<TreeContextValue | null>(null);

function useTreeContext() {
  const ctx = useContext(TreeContext);
  if (!ctx) throw new Error("must be used within FileTree");
  return ctx;
}

function NewItemInput({ parentId, type }: { parentId: string | null; type: FileType }) {
  const { projectId, setCreating, onSelectFile } = useTreeContext();
  const createFile = useCreateFile(projectId);
  const [value, setValue] = useState("");

  const submit = () => {
    const name = value.trim();
    if (!name) {
      setCreating(null);
      return;
    }
    createFile.mutate(
      { name, type, parent_id: parentId },
      {
        onSuccess: (file) => {
          setCreating(null);
          if (type === "file") onSelectFile(file.id);
        },
        onError: (error) => toast.error(getFriendlyErrorMessage(error)),
      },
    );
  };

  return (
    <div className="flex items-center gap-1.5 px-2 py-1">
      {type === "folder" ? (
        <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
      ) : (
        <FileIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      <input
        autoFocus
        value={value}
        disabled={createFile.isPending}
        onChange={(e) => setValue(e.target.value)}
        onBlur={submit}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
          if (e.key === "Escape") setCreating(null);
        }}
        placeholder={type === "folder" ? "folder name" : "file.py"}
        className="min-w-0 flex-1 rounded border bg-background px-1 py-0.5 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
    </div>
  );
}

function RenameInput({ node }: { node: TreeNode }) {
  const { projectId, setRenamingId } = useTreeContext();
  const updateFile = useUpdateFile(projectId, node.id);
  const [value, setValue] = useState(node.name);

  const submit = () => {
    const name = value.trim();
    if (!name || name === node.name) {
      setRenamingId(null);
      return;
    }
    updateFile.mutate(
      { name },
      {
        onSuccess: () => setRenamingId(null),
        onError: (error) => {
          toast.error(getFriendlyErrorMessage(error));
          setRenamingId(null);
        },
      },
    );
  };

  return (
    <input
      autoFocus
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onFocus={(e) => e.target.select()}
      onBlur={submit}
      onKeyDown={(e) => {
        if (e.key === "Enter") submit();
        if (e.key === "Escape") setRenamingId(null);
      }}
      className="min-w-0 flex-1 rounded border bg-background px-1 py-0.5 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
    />
  );
}

function TreeRow({ node, depth }: { node: TreeNode; depth: number }) {
  const {
    activeFileId,
    expanded,
    toggleExpanded,
    onSelectFile,
    renamingId,
    setRenamingId,
    creating,
    setCreating,
    setDeletingNode,
  } = useTreeContext();

  const isFolder = node.type === "folder";
  const isOpen = expanded.has(node.id);
  const isActive = node.id === activeFileId;
  const isRenaming = renamingId === node.id;
  const isCreatingHere = creating?.parentId === node.id;

  return (
    <div>
      {isRenaming ? (
        <div className="flex items-center gap-1.5 px-2 py-1" style={{ paddingLeft: depth * 14 + 8 }}>
          {isFolder ? <Folder className="h-4 w-4 shrink-0" /> : <FileIcon className="h-4 w-4 shrink-0" />}
          <RenameInput node={node} />
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          onClick={() => (isFolder ? toggleExpanded(node.id) : onSelectFile(node.id))}
          style={{ paddingLeft: depth * 14 + 8 }}
          className={cn(
            "group flex items-center gap-1.5 rounded-md px-2 py-1 text-sm transition-colors hover:bg-muted/70",
            isActive && "bg-muted font-medium",
          )}
        >
          {isFolder ? (
            <>
              {isOpen ? (
                <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              )}
              <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
            </>
          ) : (
            <FileIcon className="ml-[18px] h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <span className="min-w-0 flex-1 truncate">{node.name}</span>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                onClick={(e) => e.stopPropagation()}
                className="hidden h-5 w-5 shrink-0 items-center justify-center rounded hover:bg-accent group-hover:flex"
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
              {isFolder && (
                <>
                  <DropdownMenuItem onClick={() => setCreating({ parentId: node.id, type: "file" })}>
                    <FilePlus className="mr-2 h-4 w-4" /> New file
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setCreating({ parentId: node.id, type: "folder" })}>
                    <FolderPlus className="mr-2 h-4 w-4" /> New folder
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuItem onClick={() => setRenamingId(node.id)}>Rename</DropdownMenuItem>
              <DropdownMenuItem variant="destructive" onClick={() => setDeletingNode(node)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      {isFolder && isOpen && (
        <div>
          {node.children.map((child) => (
            <TreeRow key={child.id} node={child} depth={depth + 1} />
          ))}
          {isCreatingHere && (
            <div style={{ paddingLeft: (depth + 1) * 14 }}>
              <NewItemInput parentId={node.id} type={creating!.type} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function FileTree({
  projectId,
  activeFileId,
  onSelectFile,
}: {
  projectId: string;
  activeFileId: string | null;
  onSelectFile: (fileId: string) => void;
}) {
  const { data: files, isLoading } = useFileTree(projectId);
  const deleteFile = useDeleteFile(projectId);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [creating, setCreating] = useState<{ parentId: string | null; type: FileType } | null>(null);
  const [deletingNode, setDeletingNode] = useState<TreeNode | null>(null);

  const tree = useMemo(() => buildTree(files ?? []), [files]);

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const contextValue: TreeContextValue = {
    projectId,
    activeFileId,
    expanded,
    toggleExpanded,
    onSelectFile,
    renamingId,
    setRenamingId,
    creating,
    setCreating,
    deletingNode,
    setDeletingNode,
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-1.5 p-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-full" />
        ))}
      </div>
    );
  }

  return (
    <TreeContext.Provider value={contextValue}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between px-2 py-1.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Files
          </span>
          <div className="flex items-center gap-0.5">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              title="New file"
              onClick={() => setCreating({ parentId: null, type: "file" })}
            >
              <FilePlus className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              title="New folder"
              onClick={() => setCreating({ parentId: null, type: "folder" })}
            >
              <FolderPlus className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto pb-2">
          {tree.length === 0 && creating === null && (
            <p className="px-3 py-4 text-sm text-muted-foreground">No files yet.</p>
          )}
          {tree.map((node) => (
            <TreeRow key={node.id} node={node} depth={0} />
          ))}
          {creating?.parentId === null && (
            <div style={{ paddingLeft: 8 }}>
              <NewItemInput parentId={null} type={creating.type} />
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={deletingNode !== null} onOpenChange={(open) => !open && setDeletingNode(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &quot;{deletingNode?.name}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              {deletingNode?.type === "folder"
                ? "This deletes the folder and everything inside it. This can't be undone."
                : "This can't be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteFile.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteFile.isPending}
              onClick={() => {
                if (!deletingNode) return;
                deleteFile.mutate(deletingNode.id, {
                  onSuccess: () => setDeletingNode(null),
                  onError: (error) => toast.error(getFriendlyErrorMessage(error)),
                });
              }}
            >
              {deleteFile.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TreeContext.Provider>
  );
}

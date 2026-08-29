"use client";

import { ArrowLeft, History, Loader2, PlayCircle, Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CodeEditor } from "@/features/editor/components/code-editor";
import { EditorTabs, type OpenTab } from "@/features/editor/components/editor-tabs";
import { FileTree } from "@/features/editor/components/file-tree";
import { TerminalPanel } from "@/features/editor/components/terminal-panel";
import { useFile, useFileTree, useUpdateFile } from "@/features/editor/hooks/use-files";
import {
  useExecuteFile,
  useExecution,
  useExecutionStream,
} from "@/features/executions/hooks/use-executions";
import { useProject } from "@/features/projects/hooks/use-projects";
import { getFriendlyErrorMessage } from "@/lib/error-messages";
import { TERMINAL_STATUSES } from "@/types/execution";

export default function ProjectIdePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const { data: project, isLoading: projectLoading } = useProject(projectId);

  const [openTabIds, setOpenTabIds] = useState<string[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [executionId, setExecutionId] = useState<string | null>(null);

  const activeFile = useFile(projectId, activeFileId ?? undefined);
  const updateFile = useUpdateFile(projectId, activeFileId ?? "");
  const executeFile = useExecuteFile(projectId);
  const execution = useExecution(executionId ?? undefined);
  useExecutionStream(executionId ?? undefined);
  const { data: fileTree } = useFileTree(projectId);
  const fileNamesById = useMemo(
    () => new Map((fileTree ?? []).map((f) => [f.id, f.name])),
    [fileTree],
  );

  const openFile = useCallback((fileId: string) => {
    setOpenTabIds((prev) => (prev.includes(fileId) ? prev : [...prev, fileId]));
    setActiveFileId(fileId);
  }, []);

  const closeTab = useCallback(
    (fileId: string) => {
      setOpenTabIds((prev) => prev.filter((id) => id !== fileId));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[fileId];
        return next;
      });
      if (activeFileId === fileId) {
        const remaining = openTabIds.filter((id) => id !== fileId);
        setActiveFileId(remaining.at(-1) ?? null);
      }
    },
    [activeFileId, openTabIds],
  );

  const saveActiveFile = useCallback(async (): Promise<void> => {
    if (!activeFileId) return;
    const draft = drafts[activeFileId];
    if (draft === undefined) return;

    try {
      await updateFile.mutateAsync({ content: draft });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[activeFileId];
        return next;
      });
    } catch (error) {
      toast.error(getFriendlyErrorMessage(error));
      throw error;
    }
  }, [activeFileId, drafts, updateFile]);

  const handleSave = useCallback(() => {
    saveActiveFile()
      .then(() => toast.success("Saved"))
      .catch(() => undefined);
  }, [saveActiveFile]);

  const handleRun = useCallback(async () => {
    if (!activeFileId) return;
    try {
      if (drafts[activeFileId] !== undefined) {
        await saveActiveFile();
      }
      const result = await executeFile.mutateAsync(activeFileId);
      setExecutionId(result.id);
    } catch (error) {
      toast.error(getFriendlyErrorMessage(error));
    }
  }, [activeFileId, drafts, executeFile, saveActiveFile]);

  const tabs: OpenTab[] = useMemo(
    () =>
      openTabIds.map((id) => ({
        id,
        name: fileNamesById.get(id) ?? activeFile.data?.name ?? "…",
        dirty: drafts[id] !== undefined,
      })),
    [openTabIds, fileNamesById, activeFile.data, drafts],
  );

  const editorValue =
    activeFileId !== null ? (drafts[activeFileId] ?? activeFile.data?.content ?? "") : "";

  const isExecutionInFlight =
    executeFile.isPending ||
    (execution.data !== undefined &&
      execution.data !== null &&
      !TERMINAL_STATUSES.includes(execution.data.status));

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button asChild variant="ghost" size="icon" className="h-8 w-8 shrink-0">
            <Link href="/projects">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <span className="font-semibold">CodeForge</span>
          <span className="text-muted-foreground">/</span>
          {projectLoading ? (
            <Skeleton className="h-5 w-32" />
          ) : (
            <span className="truncate font-medium">{project?.name}</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link href={`/projects/${projectId}/executions`}>
              <History className="mr-1.5 h-4 w-4" />
              History
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRun}
            disabled={!activeFileId || isExecutionInFlight}
          >
            {isExecutionInFlight ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <PlayCircle className="mr-1.5 h-4 w-4" />
            )}
            Run
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!activeFileId || drafts[activeFileId ?? ""] === undefined || updateFile.isPending}
          >
            {updateFile.isPending ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-1.5 h-4 w-4" />
            )}
            Save
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-64 shrink-0 border-r">
          <FileTree projectId={projectId} activeFileId={activeFileId} onSelectFile={openFile} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <EditorTabs tabs={tabs} activeFileId={activeFileId} onSelect={setActiveFileId} onClose={closeTab} />

          <div className="min-h-0 flex-1">
            {activeFileId === null ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Select a file to start editing.
              </div>
            ) : activeFile.isLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <CodeEditor
                fileName={activeFile.data?.name ?? ""}
                value={editorValue}
                onChange={(next) => setDrafts((prev) => ({ ...prev, [activeFileId]: next }))}
                onSave={handleSave}
              />
            )}
          </div>

          <div className="h-44 shrink-0 border-t bg-muted/20 px-4 py-2">
            <TerminalPanel
              fileName={activeFile.data?.name ?? null}
              execution={execution.data ?? null}
              isSubmitting={executeFile.isPending}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

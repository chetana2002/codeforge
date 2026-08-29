"use client";

import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ExecutionDetailDialog } from "@/features/executions/components/execution-detail-dialog";
import { ExecutionStatusBadge } from "@/features/executions/components/status-badge";
import { useProjectExecutions } from "@/features/executions/hooks/use-executions";
import { useProject } from "@/features/projects/hooks/use-projects";

export default function ExecutionHistoryPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const { data: project } = useProject(projectId);
  const [page, setPage] = useState(1);
  const { data, isLoading } = useProjectExecutions(projectId, { page, pageSize: 20 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="icon" className="h-8 w-8">
          <Link href={`/projects/${projectId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Execution history</h1>
          {project && <p className="text-sm text-muted-foreground">{project.name}</p>}
        </div>
      </div>

      {isLoading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 rounded-lg" />
          ))}
        </div>
      )}

      {!isLoading && data?.items.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <PlayCircle className="h-8 w-8 text-muted-foreground" />
          <div>
            <p className="font-medium">No executions yet</p>
            <p className="text-sm text-muted-foreground">
              Run code from inside the project to see execution history here.
            </p>
          </div>
        </div>
      )}

      {!isLoading && data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">Execution</th>
                  <th className="px-4 py-2 font-medium">Language</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Duration</th>
                  <th className="px-4 py-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((execution) => (
                  <tr
                    key={execution.id}
                    onClick={() => setSelectedId(execution.id)}
                    className="cursor-pointer transition-colors hover:bg-muted/50"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {execution.id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2.5">{execution.language}</td>
                    <td className="px-4 py-2.5">
                      <ExecutionStatusBadge status={execution.status} />
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {execution.duration_ms !== null ? `${execution.duration_ms}ms` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {formatDistanceToNow(new Date(execution.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.total_pages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      <ExecutionDetailDialog
        executionId={selectedId}
        open={selectedId !== null}
        onOpenChange={(open) => !open && setSelectedId(null)}
      />
    </div>
  );
}

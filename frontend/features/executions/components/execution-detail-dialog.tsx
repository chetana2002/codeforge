"use client";

import { formatDistanceToNow } from "date-fns";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ExecutionStatusBadge } from "@/features/executions/components/status-badge";
import { useExecution, useExecutionStream } from "@/features/executions/hooks/use-executions";

export function ExecutionDetailDialog({
  executionId,
  open,
  onOpenChange,
}: {
  executionId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: execution, isLoading } = useExecution(executionId ?? undefined);
  useExecutionStream(open ? (executionId ?? undefined) : undefined);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-mono text-sm">
            Execution {executionId?.slice(0, 8)}
          </DialogTitle>
          <DialogDescription>
            {execution && `Ran ${formatDistanceToNow(new Date(execution.created_at), { addSuffix: true })}`}
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {execution && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <ExecutionStatusBadge status={execution.status} />
              <span className="text-muted-foreground">Language: {execution.language}</span>
              {execution.duration_ms !== null && (
                <span className="text-muted-foreground">
                  Duration: {execution.duration_ms}ms
                </span>
              )}
              {execution.exit_code !== null && (
                <span className="text-muted-foreground">Exit code: {execution.exit_code}</span>
              )}
            </div>

            <div className="max-h-80 overflow-auto rounded-md border bg-muted/30 p-3 font-mono text-xs">
              {execution.stdout && (
                <pre className="whitespace-pre-wrap break-words">{execution.stdout}</pre>
              )}
              {execution.stderr && (
                <pre className="whitespace-pre-wrap break-words text-destructive">
                  {execution.stderr}
                </pre>
              )}
              {!execution.stdout && !execution.stderr && (
                <p className="text-muted-foreground">No output captured.</p>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

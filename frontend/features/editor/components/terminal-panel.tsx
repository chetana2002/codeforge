"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Execution } from "@/types/execution";

function formatDuration(ms: number | null): string {
  if (ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function StatusLine({ execution }: { execution: Execution }) {
  switch (execution.status) {
    case "queued":
      return (
        <p className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Queued…
        </p>
      );
    case "running":
      return (
        <p className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Running…
        </p>
      );
    case "success":
      return (
        <p className="flex items-center gap-2 text-emerald-500">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Execution successful
        </p>
      );
    case "failed":
      return (
        <p className="flex items-center gap-2 text-destructive">
          <XCircle className="h-3.5 w-3.5" />
          Execution failed
        </p>
      );
    case "timeout":
      return (
        <p className="flex items-center gap-2 text-destructive">
          <XCircle className="h-3.5 w-3.5" />
          Execution timed out
        </p>
      );
    case "cancelled":
      return (
        <p className="flex items-center gap-2 text-muted-foreground">
          <XCircle className="h-3.5 w-3.5" />
          Execution cancelled
        </p>
      );
  }
}

export function TerminalPanel({
  fileName,
  execution,
  isSubmitting,
}: {
  fileName: string | null;
  execution: Execution | null;
  isSubmitting: boolean;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <p className="mb-1 shrink-0 font-sans text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Terminal
      </p>

      <div className="min-h-0 flex-1 overflow-auto font-mono text-xs">
        {isSubmitting && !execution && (
          <p className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Starting…
          </p>
        )}

        {!isSubmitting && !execution && (
          <p className="text-muted-foreground">Run code to see output here.</p>
        )}

        {execution && (
          <div className="flex flex-col gap-2">
            <p className="text-muted-foreground">$ run {fileName ?? execution.file_id}</p>

            {execution.stdout && (
              <pre className="whitespace-pre-wrap break-words">{execution.stdout}</pre>
            )}
            {execution.stderr && (
              <pre className={cn("whitespace-pre-wrap break-words text-destructive")}>
                {execution.stderr}
              </pre>
            )}

            <StatusLine execution={execution} />

            {execution.duration_ms !== null && (
              <p className="text-muted-foreground">
                Execution time: {formatDuration(execution.duration_ms)}
                {execution.exit_code !== null && ` · Exit code: ${execution.exit_code}`}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

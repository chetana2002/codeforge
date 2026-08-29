import { Badge } from "@/components/ui/badge";
import type { ExecutionStatus } from "@/types/execution";

const STATUS_STYLES: Record<ExecutionStatus, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  success: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  failed: "bg-destructive/15 text-destructive",
  timeout: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  cancelled: "bg-muted text-muted-foreground",
};

const STATUS_LABELS: Record<ExecutionStatus, string> = {
  queued: "Queued",
  running: "Running",
  success: "Success",
  failed: "Failed",
  timeout: "Timeout",
  cancelled: "Cancelled",
};

export function ExecutionStatusBadge({ status }: { status: ExecutionStatus }) {
  return (
    <Badge variant="outline" className={STATUS_STYLES[status]}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}

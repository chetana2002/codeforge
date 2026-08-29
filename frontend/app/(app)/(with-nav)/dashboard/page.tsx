"use client";

import { formatDistanceToNow } from "date-fns";
import { CheckCircle2, Clock, FolderGit2, PlayCircle, XCircle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/features/auth/hooks/use-auth";
import { StatCard } from "@/features/dashboard/components/stat-card";
import { ExecutionStatusBadge } from "@/features/executions/components/status-badge";
import { useExecutionStats, useMyExecutions } from "@/features/executions/hooks/use-executions";
import { CreateProjectDialog } from "@/features/projects/components/create-project-dialog";
import { useProjects } from "@/features/projects/hooks/use-projects";

export default function DashboardPage() {
  const { data: user } = useCurrentUser();
  const { data: projects, isLoading } = useProjects({ page: 1, pageSize: 5 });
  const { data: stats, isLoading: statsLoading } = useExecutionStats();
  const { data: executions, isLoading: executionsLoading } = useMyExecutions({ pageSize: 5 });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome back{user?.email ? `, ${user.email.split("@")[0]}` : ""}
        </h1>
        <p className="text-muted-foreground">Here&apos;s what&apos;s happening across your projects.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          label="Total projects"
          value={isLoading ? "—" : (projects?.total ?? 0)}
          icon={FolderGit2}
        />
        <StatCard label="Executions" value={statsLoading ? "—" : (stats?.total ?? 0)} icon={PlayCircle} />
        <StatCard
          label="Successful"
          value={statsLoading ? "—" : (stats?.successful ?? 0)}
          icon={CheckCircle2}
        />
        <StatCard label="Failed" value={statsLoading ? "—" : (stats?.failed ?? 0)} icon={XCircle} />
        <StatCard
          label="Last activity"
          value={
            statsLoading
              ? "—"
              : stats?.last_activity_at
                ? formatDistanceToNow(new Date(stats.last_activity_at), { addSuffix: true })
                : "—"
          }
          icon={Clock}
        />
      </div>

      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Recent projects</h2>
          <div className="flex items-center gap-3">
            <Link href="/projects" className="text-sm text-muted-foreground hover:underline">
              View all
            </Link>
            <CreateProjectDialog />
          </div>
        </div>

        {isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        )}

        {!isLoading && projects?.items.length === 0 && (
          <div className="rounded-xl border border-dashed py-12 text-center text-muted-foreground">
            No projects yet — create one to get started.
          </div>
        )}

        {!isLoading && projects && projects.items.length > 0 && (
          <div className="flex flex-col divide-y rounded-xl border">
            {projects.items.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{project.name}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {project.description || "No description"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <Badge variant="secondary">{project.language}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Recent executions</h2>

        {executionsLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-lg" />
            ))}
          </div>
        )}

        {!executionsLoading && executions?.items.length === 0 && (
          <div className="rounded-xl border border-dashed py-12 text-center text-muted-foreground">
            No executions yet — run some code from inside a project to see it here.
          </div>
        )}

        {!executionsLoading && executions && executions.items.length > 0 && (
          <div className="flex flex-col divide-y rounded-xl border">
            {executions.items.map((execution) => (
              <Link
                key={execution.id}
                href={`/projects/${execution.project_id}/executions`}
                className="flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{execution.project_name}</p>
                  <p className="truncate font-mono text-xs text-muted-foreground">
                    {execution.language} · {execution.id.slice(0, 8)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <ExecutionStatusBadge status={execution.status} />
                  <span className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(execution.created_at), { addSuffix: true })}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

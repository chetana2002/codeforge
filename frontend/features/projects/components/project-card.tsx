"use client";

import { formatDistanceToNow } from "date-fns";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
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
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EditProjectDialog } from "@/features/projects/components/edit-project-dialog";
import { useDeleteProject } from "@/features/projects/hooks/use-projects";
import { getFriendlyErrorMessage } from "@/lib/error-messages";
import type { Project } from "@/types/api";

const LANGUAGE_LABELS: Record<Project["language"], string> = {
  python: "Python",
  javascript: "JavaScript",
};

export function ProjectCard({ project }: { project: Project }) {
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteProject = useDeleteProject();

  return (
    <>
      <Card className="flex flex-col transition-colors hover:border-foreground/20">
        <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
          <div className="min-w-0">
            <CardTitle className="truncate">
              <Link href={`/projects/${project.id}`} className="hover:underline">
                {project.name}
              </Link>
            </CardTitle>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setEditOpen(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                Rename / edit
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardHeader>
        <CardContent className="flex-1">
          <p className="line-clamp-2 text-sm text-muted-foreground">
            {project.description || "No description"}
          </p>
        </CardContent>
        <CardFooter className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{LANGUAGE_LABELS[project.language]}</Badge>
            {project.visibility === "public" && <Badge variant="outline">Public</Badge>}
          </div>
          <span>Updated {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}</span>
        </CardFooter>
      </Card>

      <EditProjectDialog project={project} open={editOpen} onOpenChange={setEditOpen} />

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &quot;{project.name}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the project, its files, and execution history. This
              can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                deleteProject.mutate(project.id, {
                  onSuccess: () => toast.success(`Deleted "${project.name}"`),
                  onError: (error) => toast.error(getFriendlyErrorMessage(error)),
                });
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

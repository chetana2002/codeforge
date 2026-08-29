"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateProject } from "@/features/projects/hooks/use-projects";
import { getFriendlyErrorMessage } from "@/lib/error-messages";
import type { Project } from "@/types/api";

const editProjectSchema = z.object({
  name: z.string().min(1, "Name is required").max(200),
  description: z.string().max(2000).optional(),
});

type EditProjectValues = z.infer<typeof editProjectSchema>;

export function EditProjectDialog({
  project,
  open,
  onOpenChange,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const updateProject = useUpdateProject(project.id);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EditProjectValues>({
    resolver: zodResolver(editProjectSchema),
    values: { name: project.name, description: project.description ?? "" },
  });

  const onSubmit = handleSubmit((values) => {
    updateProject.mutate(values, {
      onSuccess: () => {
        toast.success("Project updated");
        onOpenChange(false);
      },
      onError: (error) => toast.error(getFriendlyErrorMessage(error)),
    });
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>Edit project</DialogTitle>
            <DialogDescription>Update the name or description.</DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input id="edit-name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea id="edit-description" rows={3} {...register("description")} />
            </div>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={updateProject.isPending}>
              {updateProject.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

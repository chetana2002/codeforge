import { ProjectList } from "@/features/projects/components/project-list";

export const metadata = { title: "Projects — CodeForge" };

export default function ProjectsPage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
      <ProjectList />
    </div>
  );
}

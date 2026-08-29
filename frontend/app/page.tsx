import { Code2, PlayCircle, Shield } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

const FEATURES = [
  {
    icon: Code2,
    title: "Full IDE in the browser",
    description: "A Monaco-powered editor with a real file tree, tabs, and keyboard shortcuts.",
  },
  {
    icon: PlayCircle,
    title: "Run code instantly",
    description: "Execute Python and JavaScript and see stdout, stderr, and exit codes in real time.",
  },
  {
    icon: Shield,
    title: "Sandboxed execution",
    description: "Every run happens in an isolated, resource-limited container — never on the host.",
  },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-10 px-6 py-20 text-center">
      <div className="flex flex-col items-center gap-6">
        <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">CodeForge</h1>
        <p className="max-w-xl text-balance text-lg text-muted-foreground">
          Cloud IDE &amp; code execution platform. Write, run, and ship code in the browser with
          isolated, sandboxed execution.
        </p>
        <div className="flex gap-3">
          <Button asChild size="lg">
            <Link href="/register">Sign up free</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/login">Log in</Link>
          </Button>
        </div>
      </div>

      <div className="grid max-w-4xl grid-cols-1 gap-6 text-left sm:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, description }) => (
          <div key={title} className="flex flex-col gap-2 rounded-xl border p-5">
            <Icon className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">{title}</h3>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        ))}
      </div>

      <a
        href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"}/docs`}
        target="_blank"
        rel="noreferrer"
        className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
      >
        API documentation
      </a>
    </main>
  );
}

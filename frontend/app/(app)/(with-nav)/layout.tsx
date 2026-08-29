import { TopNav } from "@/components/top-nav";

export default function WithNavLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <TopNav />
      <main className="flex-1">{children}</main>
    </div>
  );
}

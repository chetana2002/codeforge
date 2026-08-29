"use client";

import { Circle, File as FileIcon, X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface OpenTab {
  id: string;
  name: string;
  dirty: boolean;
}

export function EditorTabs({
  tabs,
  activeFileId,
  onSelect,
  onClose,
}: {
  tabs: OpenTab[];
  activeFileId: string | null;
  onSelect: (fileId: string) => void;
  onClose: (fileId: string) => void;
}) {
  if (tabs.length === 0) return null;

  return (
    <div className="flex h-9 shrink-0 items-stretch overflow-x-auto border-b bg-muted/30">
      {tabs.map((tab) => {
        const isActive = tab.id === activeFileId;
        return (
          <button
            key={tab.id}
            onClick={() => onSelect(tab.id)}
            className={cn(
              "group flex shrink-0 items-center gap-2 border-r px-3 text-sm transition-colors",
              isActive ? "bg-background" : "text-muted-foreground hover:bg-muted/60",
            )}
          >
            <FileIcon className="h-3.5 w-3.5 shrink-0" />
            <span className="max-w-[140px] truncate">{tab.name}</span>
            <span
              role="button"
              tabIndex={-1}
              onClick={(e) => {
                e.stopPropagation();
                onClose(tab.id);
              }}
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded hover:bg-accent"
            >
              {tab.dirty && <Circle className="h-2 w-2 fill-current group-hover:hidden" />}
              <X className="hidden h-3 w-3 group-hover:block" />
            </span>
          </button>
        );
      })}
    </div>
  );
}

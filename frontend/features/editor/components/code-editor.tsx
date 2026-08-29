"use client";

import Editor, { type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

import { languageForFile } from "@/features/editor/lib/language-for-file";

export function CodeEditor({
  fileName,
  value,
  onChange,
  onSave,
}: {
  fileName: string;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
}) {
  const { resolvedTheme } = useTheme();
  const onSaveRef = useRef(onSave);
  useEffect(() => {
    onSaveRef.current = onSave;
  }, [onSave]);

  const handleMount: OnMount = (editor, monaco) => {
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      onSaveRef.current();
    });
  };

  return (
    <Editor
      key={fileName}
      language={languageForFile(fileName)}
      value={value}
      onChange={(next) => onChange(next ?? "")}
      onMount={handleMount}
      theme={resolvedTheme === "light" ? "light" : "vs-dark"}
      options={{
        minimap: { enabled: true },
        fontSize: 13,
        automaticLayout: true,
        scrollBeyondLastLine: false,
        tabSize: 4,
      }}
    />
  );
}

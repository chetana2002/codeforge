const EXTENSION_TO_MONACO_LANGUAGE: Record<string, string> = {
  py: "python",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  ts: "typescript",
  tsx: "typescript",
  json: "json",
  md: "markdown",
  html: "html",
  css: "css",
  yml: "yaml",
  yaml: "yaml",
  sh: "shell",
  txt: "plaintext",
};

export function languageForFile(fileName: string): string {
  const extension = fileName.split(".").pop()?.toLowerCase();
  if (!extension) return "plaintext";
  return EXTENSION_TO_MONACO_LANGUAGE[extension] ?? "plaintext";
}

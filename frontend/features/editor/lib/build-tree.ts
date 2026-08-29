import type { FileTreeNode } from "@/types/api";

export interface TreeNode extends FileTreeNode {
  children: TreeNode[];
}

export function buildTree(nodes: FileTreeNode[]): TreeNode[] {
  const byId = new Map<string, TreeNode>(nodes.map((node) => [node.id, { ...node, children: [] }]));
  const roots: TreeNode[] = [];

  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  const sortNodes = (list: TreeNode[]) => {
    list.sort((a, b) => {
      if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    list.forEach((n) => sortNodes(n.children));
  };
  sortNodes(roots);

  return roots;
}

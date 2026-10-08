interface TreeNode {
  name: string;
  path: string;
  isFile: boolean;
  children: Map<string, TreeNode>;
}

function buildTree(paths: string[]): TreeNode {
  const root: TreeNode = { name: "", path: "", isFile: false, children: new Map() };

  for (const path of paths) {
    const parts = path.split("/");
    let node = root;
    let accumulated = "";
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      accumulated = accumulated ? `${accumulated}/${part}` : part;
      const isFile = i === parts.length - 1;
      if (!node.children.has(part)) {
        node.children.set(part, { name: part, path: accumulated, isFile, children: new Map() });
      }
      node = node.children.get(part)!;
    }
  }

  return root;
}

function TreeNodeView({
  node,
  selectedPath,
  onSelect,
  depth,
}: {
  node: TreeNode;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  depth: number;
}) {
  const sortedChildren = Array.from(node.children.values()).sort((a, b) => {
    if (a.isFile !== b.isFile) return a.isFile ? 1 : -1; // directories first
    return a.name.localeCompare(b.name);
  });

  return (
    <ul className="wx-tree">
      {sortedChildren.map((child) => (
        <li key={child.path}>
          {child.isFile ? (
            <button
              type="button"
              onClick={() => onSelect(child.path)}
              className={`wx-tree__file${child.path === selectedPath ? " wx-tree__file--selected" : ""}`}
            >
              {child.name}
            </button>
          ) : (
            <>
              <div className="wx-tree__dir">{child.name}/</div>
              <TreeNodeView node={child} selectedPath={selectedPath} onSelect={onSelect} depth={depth + 1} />
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

export function FileTree({
  paths,
  selectedPath,
  onSelect,
}: {
  paths: string[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}) {
  const tree = buildTree(paths);
  return <TreeNodeView node={tree} selectedPath={selectedPath} onSelect={onSelect} depth={0} />;
}

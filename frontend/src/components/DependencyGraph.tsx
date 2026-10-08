import { useMemo, useState } from "react";
import { Background, BackgroundVariant, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { DependencyEdge } from "../graphql/operations";

const COLUMN_WIDTH = 220;
const ROW_HEIGHT = 60;

function layout(paths: string[]): Record<string, { x: number; y: number }> {
  // Simple, dependency-free layout: group by top-level directory into
  // columns, stack files within each column. Good enough to be readable
  // without pulling in a full graph-layout library for Day 2 scope.
  const columns = new Map<string, string[]>();
  for (const path of paths) {
    const top = path.includes("/") ? path.split("/")[0] : "(root)";
    if (!columns.has(top)) columns.set(top, []);
    columns.get(top)!.push(path);
  }

  const positions: Record<string, { x: number; y: number }> = {};
  let columnIndex = 0;
  for (const [, filesInColumn] of Array.from(columns.entries()).sort()) {
    filesInColumn.sort();
    filesInColumn.forEach((path, rowIndex) => {
      positions[path] = { x: columnIndex * COLUMN_WIDTH, y: rowIndex * ROW_HEIGHT };
    });
    columnIndex += 1;
  }
  return positions;
}

export function DependencyGraph({
  files,
  edges,
}: {
  files: { path: string; language: string | null }[];
  edges: DependencyEdge[];
}) {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const internalEdges = useMemo(() => edges.filter((e) => e.targetPath !== null), [edges]);

  const connectedPaths = useMemo(() => {
    if (!selectedPath) return null;
    const connected = new Set<string>([selectedPath]);
    for (const edge of internalEdges) {
      if (edge.sourcePath === selectedPath) connected.add(edge.targetPath!);
      if (edge.targetPath === selectedPath) connected.add(edge.sourcePath);
    }
    return connected;
  }, [selectedPath, internalEdges]);

  const positions = useMemo(() => layout(files.map((f) => f.path)), [files]);

  const nodes: Node[] = files.map((file) => ({
    id: file.path,
    position: positions[file.path] ?? { x: 0, y: 0 },
    data: { label: file.path.split("/").pop() },
    className: !connectedPaths || connectedPaths.has(file.path) ? undefined : "wx-graph-node--dim",
    style: {
      fontSize: 11,
      width: 180,
    },
    title: file.path,
  }));

  const flowEdges: Edge[] = internalEdges.map((edge, index) => ({
    id: `${edge.sourcePath}->${edge.targetPath}-${index}`,
    source: edge.sourcePath,
    target: edge.targetPath!,
    animated: Boolean(
      connectedPaths && (edge.sourcePath === selectedPath || edge.targetPath === selectedPath)
    ),
    style: {
      opacity:
        !connectedPaths || edge.sourcePath === selectedPath || edge.targetPath === selectedPath ? 1 : 0.1,
    },
  }));

  return (
    <div className="wx-graph-card">
      <div className="wx-hero__bg" aria-hidden="true" />
      <div className="wx-grain" aria-hidden="true" />
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        onNodeClick={(_event, node) => setSelectedPath(node.id === selectedPath ? null : node.id)}
        fitView
      >
        <Background variant={BackgroundVariant.Dots} color="rgba(157, 176, 192, 0.25)" gap={18} size={1} />
        <Controls />
      </ReactFlow>
    </div>
  );
}

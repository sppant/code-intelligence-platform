import { useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { DependencyEdge } from "../graphql/operations";
import { FileNode, type FileNodeData } from "./graph/FileNode";
import { LANGUAGE_COLORS, LANGUAGE_COLOR_FALLBACK } from "./graph/constants";
import { layoutWithDagre, selectTopConnectedPaths, NODE_CAP } from "./graph/layout";

const nodeTypes = { file: FileNode };

export function DependencyGraph({
  files,
  edges,
}: {
  files: { path: string; language: string | null }[];
  edges: DependencyEdge[];
}) {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [filterText, setFilterText] = useState("");

  const internalEdges = useMemo(
    () =>
      edges
        .filter((e): e is DependencyEdge & { targetPath: string } => e.targetPath !== null)
        .map((e) => ({ source: e.sourcePath, target: e.targetPath })),
    [edges],
  );

  const languageByPath = useMemo(() => new Map(files.map((f) => [f.path, f.language])), [files]);

  const { visiblePaths, wasCapped } = useMemo(() => {
    const allPaths = files.map((f) => f.path);
    const kept = selectTopConnectedPaths(allPaths, internalEdges, NODE_CAP);
    return { visiblePaths: kept, wasCapped: kept.size < allPaths.length };
  }, [files, internalEdges]);

  const visibleEdges = useMemo(
    () => internalEdges.filter((e) => visiblePaths.has(e.source) && visiblePaths.has(e.target)),
    [internalEdges, visiblePaths],
  );

  const outgoing = useMemo(() => {
    if (!selectedPath) return null;
    const set = new Set<string>();
    for (const e of visibleEdges) if (e.source === selectedPath) set.add(e.target);
    return set;
  }, [selectedPath, visibleEdges]);

  const incoming = useMemo(() => {
    if (!selectedPath) return null;
    const set = new Set<string>();
    for (const e of visibleEdges) if (e.target === selectedPath) set.add(e.source);
    return set;
  }, [selectedPath, visibleEdges]);

  const normalizedFilter = filterText.trim().toLowerCase();

  function stateFor(path: string): FileNodeData["state"] {
    if (selectedPath) {
      if (path === selectedPath) return "selected";
      if (outgoing?.has(path)) return "outgoing";
      if (incoming?.has(path)) return "incoming";
      return "dimmed";
    }
    if (normalizedFilter) {
      return path.toLowerCase().includes(normalizedFilter) ? "matched" : "dimmed";
    }
    return "default";
  }

  const positions = useMemo(
    () => layoutWithDagre([...visiblePaths], visibleEdges),
    [visiblePaths, visibleEdges],
  );

  const nodes: Node[] = [...visiblePaths].map((path) => ({
    id: path,
    type: "file",
    position: positions[path] ?? { x: 0, y: 0 },
    data: {
      label: path.split("/").pop() ?? path,
      path,
      language: languageByPath.get(path) ?? null,
      state: stateFor(path),
    } satisfies FileNodeData,
  }));

  const flowEdges: Edge[] = visibleEdges.map((edge, index) => {
    const isOutgoing = selectedPath !== null && edge.source === selectedPath;
    const isIncoming = selectedPath !== null && edge.target === selectedPath;
    const related = isOutgoing || isIncoming;
    const dimmed = selectedPath !== null && !related;
    const color = isOutgoing ? "var(--wx-teal-bright)" : isIncoming ? "var(--wx-orange)" : undefined;

    return {
      id: `${edge.source}->${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      animated: related,
      style: {
        opacity: dimmed ? 0.08 : related ? 1 : 0.5,
        stroke: color,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
    };
  });

  const languagesPresent = [...new Set(files.map((f) => f.language).filter((l): l is string => Boolean(l)))];

  return (
    <div>
      <div className="wx-graph-toolbar">
        <input
          type="search"
          placeholder="Filter files by path..."
          value={filterText}
          onChange={(e) => {
            setFilterText(e.target.value);
            setSelectedPath(null);
          }}
          aria-label="Filter graph by file path"
        />
        <div className="wx-graph-legend">
          {languagesPresent.map((lang) => (
            <span key={lang} className="wx-graph-legend__item">
              <span className="wx-graph-legend__dot" style={{ background: LANGUAGE_COLORS[lang] ?? LANGUAGE_COLOR_FALLBACK }} />
              {lang}
            </span>
          ))}
          <span className="wx-graph-legend__item">
            <span className="wx-graph-legend__dot" style={{ background: "var(--wx-teal-bright)" }} />
            depends on
          </span>
          <span className="wx-graph-legend__item">
            <span className="wx-graph-legend__dot" style={{ background: "var(--wx-orange)" }} />
            depended on by
          </span>
        </div>
      </div>

      {wasCapped && (
        <p className="wx-note" style={{ marginBottom: "0.75rem" }}>
          Showing the {NODE_CAP} most-connected of {files.length} files for readability and performance.
        </p>
      )}

      <div className="wx-graph-card">
        <div className="wx-hero__bg" aria-hidden="true" />
        <div className="wx-grain" aria-hidden="true" />
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onNodeClick={(_event, node) => {
            setFilterText("");
            setSelectedPath(node.id === selectedPath ? null : node.id);
          }}
          onPaneClick={() => setSelectedPath(null)}
          fitView
          minZoom={0.05}
        >
          <Background variant={BackgroundVariant.Dots} color="rgba(157, 176, 192, 0.25)" gap={18} size={1} />
          <Controls />
          <MiniMap
            pannable
            zoomable
            nodeColor={(n) => {
              const data = n.data as unknown as FileNodeData;
              return (data.language && LANGUAGE_COLORS[data.language]) || LANGUAGE_COLOR_FALLBACK;
            }}
            maskColor="rgba(14, 22, 32, 0.75)"
          />
        </ReactFlow>
      </div>
    </div>
  );
}

import dagre from "@dagrejs/dagre";

export const NODE_WIDTH = 190;
export const NODE_HEIGHT = 40;

const ISOLATED_GRID_GAP_X = 24;
const ISOLATED_GRID_GAP_Y = 16;

/**
 * Layered left-to-right layout: imports flow from source (left) to target
 * (right), so the graph reads the same direction as "A depends on B".
 *
 * Files with zero edges (no imports in or out -- commonly docs/config/CI
 * files in a real repo, often a large fraction of all files) are laid out
 * separately from the connected subgraph: dagre has no rank constraint for
 * a degree-0 node, so handing it hundreds of them stacks them all in a
 * single very tall column, blowing out the graph's bounding box and making
 * fitView zoom out until the real, connected part is unreadably tiny.
 * Instead, isolated files are arranged in a compact grid placed below the
 * connected cluster.
 */
export function layoutWithDagre(
  paths: string[],
  edges: { source: string; target: string }[],
): Record<string, { x: number; y: number }> {
  const degree = new Map<string, number>();
  for (const path of paths) degree.set(path, 0);
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }

  const connectedPaths = paths.filter((p) => (degree.get(p) ?? 0) > 0);
  const isolatedPaths = paths.filter((p) => (degree.get(p) ?? 0) === 0);

  const positions: Record<string, { x: number; y: number }> = {};
  let connectedWidth = NODE_WIDTH;
  let connectedBottom = 0;

  if (connectedPaths.length > 0) {
    const graph = new dagre.graphlib.Graph();
    graph.setGraph({ rankdir: "LR", nodesep: 28, ranksep: 110, marginx: 20, marginy: 20 });
    graph.setDefaultEdgeLabel(() => ({}));

    for (const path of connectedPaths) {
      graph.setNode(path, { width: NODE_WIDTH, height: NODE_HEIGHT });
    }
    for (const edge of edges) {
      graph.setEdge(edge.source, edge.target);
    }

    dagre.layout(graph);

    for (const path of connectedPaths) {
      const node = graph.node(path);
      const x = node ? node.x - NODE_WIDTH / 2 : 0;
      const y = node ? node.y - NODE_HEIGHT / 2 : 0;
      positions[path] = { x, y };
      connectedWidth = Math.max(connectedWidth, x + NODE_WIDTH);
      connectedBottom = Math.max(connectedBottom, y + NODE_HEIGHT);
    }
  }

  if (isolatedPaths.length > 0) {
    const columns = Math.max(1, Math.floor(connectedWidth / (NODE_WIDTH + ISOLATED_GRID_GAP_X)));
    const gridTop = connectedBottom + (connectedPaths.length > 0 ? 80 : 0);
    isolatedPaths.forEach((path, index) => {
      const col = index % columns;
      const row = Math.floor(index / columns);
      positions[path] = {
        x: col * (NODE_WIDTH + ISOLATED_GRID_GAP_X),
        y: gridTop + row * (NODE_HEIGHT + ISOLATED_GRID_GAP_Y),
      };
    });
  }

  return positions;
}

/**
 * Large repos (hundreds-thousands of files) would make an all-nodes dagre
 * layout + render slow and unreadable. Past this cap, keep only the most
 * structurally significant files (highest fan-in + fan-out) so the graph
 * stays fast and legible -- still a real subset of the real graph, not a
 * fabricated summary.
 */
export const NODE_CAP = 400;

export function selectTopConnectedPaths(
  paths: string[],
  edges: { source: string; target: string }[],
  cap: number,
): Set<string> {
  if (paths.length <= cap) return new Set(paths);

  const degree = new Map<string, number>();
  for (const path of paths) degree.set(path, 0);
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }

  const ranked = [...paths].sort((a, b) => (degree.get(b) ?? 0) - (degree.get(a) ?? 0));
  return new Set(ranked.slice(0, cap));
}

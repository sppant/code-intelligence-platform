import { Handle, Position, type NodeProps } from "@xyflow/react";
import { LANGUAGE_COLORS, LANGUAGE_COLOR_FALLBACK } from "./constants";

export type FileNodeState = "default" | "selected" | "outgoing" | "incoming" | "dimmed" | "matched";

export interface FileNodeData {
  label: string;
  path: string;
  language: string | null;
  state: FileNodeState;
  [key: string]: unknown;
}

export function FileNode({ data }: NodeProps & { data: FileNodeData }) {
  const color = (data.language && LANGUAGE_COLORS[data.language]) || LANGUAGE_COLOR_FALLBACK;

  return (
    <div className={`wx-file-node wx-file-node--${data.state}`} title={data.path}>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <span className="wx-file-node__dot" style={{ background: color }} />
      <span className="wx-file-node__label">{data.label}</span>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

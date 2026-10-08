// Mirrors the stage names backend/src/backend/jobs/tasks.py's on_progress
// callback writes (see analysis_engine.pipeline.run_pipeline's docstring
// for the authoritative stage list).
const STAGES: { key: string; label: string }[] = [
  { key: "cloning", label: "Cloning repository" },
  { key: "parsing_and_extracting", label: "Parsing source & extracting symbols" },
  { key: "resolving_imports", label: "Resolving dependency graph" },
  { key: "building_call_graph", label: "Building call graph" },
  { key: "persisting", label: "Saving results" },
];

export function AnalysisProgress({ currentStage }: { currentStage: string | null }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <ul className="wx-progress-list">
      {STAGES.map((stage, index) => {
        const isDone = currentIndex >= 0 && index < currentIndex;
        const isCurrent = index === currentIndex;
        const symbol = isDone ? "✓" : isCurrent ? "●" : "○";
        return (
          <li
            key={stage.key}
            className={isDone ? "wx-progress-list__done" : isCurrent ? "wx-progress-list__current" : undefined}
          >
            <span className="wx-progress-list__icon">{symbol}</span> {stage.label}
          </li>
        );
      })}
    </ul>
  );
}

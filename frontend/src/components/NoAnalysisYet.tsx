import { Link } from "react-router-dom";

export function NoAnalysisYet({ repositoryId }: { repositoryId: string }) {
  return (
    <p className="wx-empty">
      No completed analysis yet. Check the{" "}
      <Link to={`/repository/${repositoryId}`}>Overview tab</Link> for progress.
    </p>
  );
}

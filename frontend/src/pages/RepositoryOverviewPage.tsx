import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { client, summarizeError } from "../graphql/client";
import { REPOSITORY_OVERVIEW_QUERY, type Repository } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";
import { AnalysisProgress } from "../components/AnalysisProgress";
import { useJobPolling } from "../hooks/useJobPolling";

export function RepositoryOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [repository, setRepository] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchRepository = useCallback(() => {
    if (!id) return;
    client
      .query<{ repository: Repository | null }>(REPOSITORY_OVERVIEW_QUERY, { id })
      .toPromise()
      .then((result) => {
        setRepository(result.data?.repository ?? null);
        setLoading(false);
      });
  }, [id]);

  useEffect(() => {
    setLoading(true);
    fetchRepository();
  }, [fetchRepository]);

  const latestJob = repository?.latestJob ?? null;
  const jobInFlight = latestJob?.status === "pending" || latestJob?.status === "running";

  const { job: polledJob, pollError } = useJobPolling(jobInFlight ? latestJob!.id : null, () => {
    // Refetch regardless of outcome: on success this picks up the newly
    // completed analysis/statistics, on failure it picks up the updated
    // latestJob.errorMessage -- same query either way.
    fetchRepository();
  });

  if (!id) return null;
  if (loading) return <p className="wx-page">Loading...</p>;
  if (!repository) return <p className="wx-page">Repository not found.</p>;

  const stats = repository.latestAnalysis?.statistics;

  return (
    <main className="wx-page">
      <div className="wx-page__header">
        <p className="wx-eyebrow">Repository Overview</p>
        <h1>
          {repository.owner}/{repository.name}
        </h1>
        <a href={repository.url} target="_blank" rel="noreferrer" className="wx-page__url">
          {repository.url}
        </a>
      </div>

      <RepositoryNav repositoryId={id} />

      {!stats && jobInFlight && (
        <div className="wx-card">
          <p style={{ margin: "0 0 0.25rem" }}>Analysis in progress&hellip;</p>
          <AnalysisProgress currentStage={polledJob?.progress ?? latestJob?.progress ?? null} />
        </div>
      )}

      {!stats && !jobInFlight && latestJob?.status === "failed" && (
        <p className="wx-error" role="alert">
          Analysis failed: {summarizeError(latestJob.errorMessage ?? pollError ?? "Unknown error.")}
        </p>
      )}

      {!stats && !jobInFlight && latestJob?.status !== "failed" && <p className="wx-empty">No completed analysis yet.</p>}

      {stats && (
        <>
          <div className="wx-stat-grid">
            <StatCard label="Files" value={stats.totalFiles} />
            <StatCard label="Lines of code" value={stats.totalLines} />
            <StatCard label="Symbols" value={stats.totalSymbols} />
            <StatCard label="Dependency edges" value={stats.totalDependencyEdges} />
          </div>

          {repository.latestAnalysis?.isIncremental && (
            <p className="wx-note">
              Incremental analysis: {repository.latestAnalysis.filesReused}/
              {(repository.latestAnalysis.filesReused ?? 0) + (repository.latestAnalysis.filesReprocessed ?? 0)}{" "}
              files reused (unchanged since the last analysis).
            </p>
          )}

          <h2>Languages</h2>
          <ul className="wx-tag-row">
            {Object.entries(stats.languages).map(([language, count]) => (
              <li key={language} className="wx-tag">
                <strong>{language}</strong> · {count} file{count === 1 ? "" : "s"}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="wx-stat-card">
      <div className="wx-stat-card__value">{value}</div>
      <div className="wx-stat-card__label">{label}</div>
    </div>
  );
}

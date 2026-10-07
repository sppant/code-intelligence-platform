import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { client } from "../graphql/client";
import {
  ANALYSIS_JOB_STATUS_QUERY,
  ANALYZE_REPOSITORY_MUTATION,
  type AnalysisJob,
} from "../graphql/operations";
import { RepositoryInputForm } from "../components/RepositoryInputForm";

const EXAMPLE_REPOSITORIES = [
  "https://github.com/pallets/flask",
  "https://github.com/expressjs/express",
  "https://github.com/psf/requests",
];

const POLL_INTERVAL_MS = 2000;

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

export function LandingPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  function pollJob(jobId: string, repositoryId: string) {
    pollTimeout.current = setTimeout(async () => {
      const result = await client
        .query<{ analysisJob: AnalysisJob | null }>(ANALYSIS_JOB_STATUS_QUERY, { id: jobId })
        .toPromise();

      const latest = result.data?.analysisJob;
      if (!latest) return;
      setJob(latest);

      if (latest.status === "completed") {
        setIsPolling(false);
        navigate(`/repository/${repositoryId}`);
      } else if (latest.status === "failed") {
        setIsPolling(false);
        setError(latest.errorMessage ?? "Analysis failed.");
      } else {
        pollJob(jobId, repositoryId);
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleAnalyze(repoUrl: string) {
    setIsSubmitting(true);
    setError(null);
    setJob(null);
    if (pollTimeout.current) clearTimeout(pollTimeout.current);

    const result = await client
      .mutation<{ analyzeRepository: AnalysisJob }>(ANALYZE_REPOSITORY_MUTATION, { repoUrl })
      .toPromise();

    setIsSubmitting(false);

    if (result.error) {
      setError(result.error.message);
      return;
    }
    if (result.data) {
      setJob(result.data.analyzeRepository);
      setIsPolling(true);
      pollJob(result.data.analyzeRepository.id, result.data.analyzeRepository.repositoryId);
    }
  }

  return (
    <main>
      <h1>Code Intelligence</h1>
      <p>Understand any codebase.</p>

      <RepositoryInputForm onSubmit={handleAnalyze} isSubmitting={isSubmitting || isPolling} />

      <p>
        Try an example:{" "}
        {EXAMPLE_REPOSITORIES.map((url) => (
          <button
            key={url}
            type="button"
            onClick={() => handleAnalyze(url)}
            disabled={isSubmitting || isPolling}
          >
            {url.replace("https://github.com/", "")}
          </button>
        ))}
      </p>

      {error && <p role="alert">Error: {error}</p>}

      {job && isPolling && <ProgressChecklist currentStage={job.progress ?? null} />}

      {job && !isPolling && !error && (
        <p>
          Analysis job <code>{job.id}</code> status: <strong>{job.status}</strong>.
        </p>
      )}
    </main>
  );
}

function ProgressChecklist({ currentStage }: { currentStage: string | null }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <ul style={{ listStyle: "none", padding: 0, textAlign: "left", maxWidth: 320, margin: "1.5rem auto" }}>
      {STAGES.map((stage, index) => {
        const symbol = currentIndex < 0 ? "○" : index < currentIndex ? "✓" : index === currentIndex ? "●" : "○";
        return (
          <li key={stage.key} style={{ opacity: currentIndex >= 0 && index > currentIndex ? 0.5 : 1 }}>
            {symbol} {stage.label}
          </li>
        );
      })}
    </ul>
  );
}

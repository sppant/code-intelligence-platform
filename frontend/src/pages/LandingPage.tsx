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
    <section className="wx-hero">
      <div className="wx-hero__bg" aria-hidden="true" />
      <div className="wx-grain" aria-hidden="true" />
      <div className="wx-hero__content">
        <p className="wx-eyebrow">Code Intelligence Platform</p>
        <h1>
          Understand any <span className="wx-hero__highlight">codebase</span>, instantly.
        </h1>
        <p className="wx-hero__sub">
          Paste a public GitHub repository and get its architecture, dependency graph, and
          change-impact analysis — structurally derived, not guessed.
        </p>

        <RepositoryInputForm onSubmit={handleAnalyze} isSubmitting={isSubmitting || isPolling} />

        <div className="wx-chip-row">
          <span>Try an example:</span>
          {EXAMPLE_REPOSITORIES.map((url) => (
            <button
              key={url}
              type="button"
              className="wx-chip"
              onClick={() => handleAnalyze(url)}
              disabled={isSubmitting || isPolling}
            >
              {url.replace("https://github.com/", "")}
            </button>
          ))}
        </div>

        {error && (
          <p className="wx-error" role="alert">
            Error: {error}
          </p>
        )}

        {job && isPolling && <ProgressChecklist currentStage={job.progress ?? null} />}

        {job && !isPolling && !error && (
          <p className="wx-job-status">
            Analysis job <code>{job.id}</code> status: <strong>{job.status}</strong>.
          </p>
        )}
      </div>
    </section>
  );
}

function ProgressChecklist({ currentStage }: { currentStage: string | null }) {
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

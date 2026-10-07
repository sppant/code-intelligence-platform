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

      {job && (
        <p>
          Analysis job <code>{job.id}</code> created with status <strong>{job.status}</strong>.
        </p>
      )}
    </main>
  );
}

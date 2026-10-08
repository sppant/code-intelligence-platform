import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { client, formatError, summarizeError } from "../graphql/client";
import { ANALYZE_REPOSITORY_MUTATION, type AnalysisJob } from "../graphql/operations";
import { RepositoryInputForm } from "../components/RepositoryInputForm";
import { RepositoryHistory } from "../components/RepositoryHistory";
import { AnalysisProgress } from "../components/AnalysisProgress";
import { useJobPolling } from "../hooks/useJobPolling";

const EXAMPLE_REPOSITORIES = [
  "https://github.com/pallets/flask",
  "https://github.com/expressjs/express",
  "https://github.com/psf/requests",
];

export function LandingPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { job, pollError } = useJobPolling(activeJobId, (settled) => {
    setActiveJobId(null);
    if (settled.status === "completed") {
      navigate(`/repository/${settled.repositoryId}`);
    } else {
      setError(summarizeError(settled.errorMessage ?? "Analysis failed."));
    }
  });

  const isPolling = activeJobId !== null;
  const displayError = error ?? pollError;

  async function handleAnalyze(repoUrl: string) {
    setIsSubmitting(true);
    setError(null);
    setActiveJobId(null);

    const result = await client
      .mutation<{ analyzeRepository: AnalysisJob }>(ANALYZE_REPOSITORY_MUTATION, { repoUrl })
      .toPromise();

    setIsSubmitting(false);

    if (result.error) {
      setError(formatError(result.error));
      return;
    }
    if (result.data) {
      setActiveJobId(result.data.analyzeRepository.id);
    }
  }

  return (
    <>
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

          {displayError && (
            <p className="wx-error" role="alert">
              Error: {displayError}
            </p>
          )}

          {isPolling && <AnalysisProgress currentStage={job?.progress ?? null} />}
        </div>
      </section>

      <RepositoryHistory />
    </>
  );
}

import { useState } from "react";
import { client } from "../graphql/client";
import { ANALYZE_REPOSITORY_MUTATION, type AnalysisJob } from "../graphql/operations";
import { RepositoryInputForm } from "../components/RepositoryInputForm";

const EXAMPLE_REPOSITORIES = [
  "https://github.com/pallets/flask",
  "https://github.com/expressjs/express",
  "https://github.com/psf/requests",
];

export function LandingPage() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(repoUrl: string) {
    setIsSubmitting(true);
    setError(null);
    setJob(null);

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
    }
  }

  return (
    <main>
      <h1>Code Intelligence</h1>
      <p>Understand any codebase.</p>

      <RepositoryInputForm onSubmit={handleAnalyze} isSubmitting={isSubmitting} />

      <p>
        Try an example:{" "}
        {EXAMPLE_REPOSITORIES.map((url) => (
          <button key={url} type="button" onClick={() => handleAnalyze(url)} disabled={isSubmitting}>
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

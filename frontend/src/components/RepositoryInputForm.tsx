import { useState } from "react";

interface RepositoryInputFormProps {
  onSubmit: (repoUrl: string) => void;
  isSubmitting: boolean;
}

export function RepositoryInputForm({ onSubmit, isSubmitting }: RepositoryInputFormProps) {
  const [repoUrl, setRepoUrl] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (repoUrl.trim()) {
      onSubmit(repoUrl.trim());
    }
  }

  return (
    <form onSubmit={handleSubmit} className="wx-input-row">
      <input
        type="text"
        value={repoUrl}
        onChange={(event) => setRepoUrl(event.target.value)}
        placeholder="https://github.com/owner/repository"
        aria-label="GitHub repository URL"
      />
      <button type="submit" disabled={isSubmitting || !repoUrl.trim()}>
        {isSubmitting ? "Starting analysis..." : "Analyze Repository"}
      </button>
    </form>
  );
}

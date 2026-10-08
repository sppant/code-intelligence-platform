import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { client } from "../graphql/client";
import { REPOSITORIES_QUERY, type RepositorySummary } from "../graphql/operations";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function RepositoryHistory() {
  const [repositories, setRepositories] = useState<RepositorySummary[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    client
      .query<{ repositories: RepositorySummary[] }>(REPOSITORIES_QUERY, { limit: 12 })
      .toPromise()
      .then((result) => {
        if (cancelled) return;
        setRepositories(result.data?.repositories ?? []);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || !repositories || repositories.length === 0) return null;

  return (
    <section className="wx-page wx-history">
      <p className="wx-eyebrow">Recently analyzed</p>
      <h2 className="wx-history__title">Jump back into a repository</h2>
      <div className="wx-history-grid">
        {repositories.map((repo) => {
          const stats = repo.latestAnalysis?.statistics;
          const languages = stats ? Object.keys(stats.languages) : [];
          return (
            <Link key={repo.id} to={`/repository/${repo.id}`} className="wx-history-card">
              <div className="wx-history-card__header">
                <span className="wx-history-card__name">
                  {repo.owner}/{repo.name}
                </span>
                {repo.latestAnalysis && (
                  <span className="wx-history-card__time">{timeAgo(repo.latestAnalysis.createdAt)}</span>
                )}
              </div>
              {stats ? (
                <div className="wx-history-card__stats">
                  <span>{stats.totalFiles} files</span>
                  <span>{stats.totalLines.toLocaleString()} lines</span>
                  {languages.length > 0 && <span>{languages.join(", ")}</span>}
                </div>
              ) : (
                <div className="wx-history-card__stats wx-empty">No completed analysis yet</div>
              )}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

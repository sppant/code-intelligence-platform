import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { client } from "../graphql/client";
import { REPOSITORY_OVERVIEW_QUERY, type Repository } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";

export function RepositoryOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [repository, setRepository] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    client
      .query<{ repository: Repository | null }>(REPOSITORY_OVERVIEW_QUERY, { id })
      .toPromise()
      .then((result) => {
        setRepository(result.data?.repository ?? null);
        setLoading(false);
      });
  }, [id]);

  if (!id) return null;
  if (loading) return <p>Loading...</p>;
  if (!repository) return <p>Repository not found.</p>;

  const stats = repository.latestAnalysis?.statistics;

  return (
    <main style={{ maxWidth: 900, margin: "2rem auto", padding: "0 1.5rem" }}>
      <h1>
        {repository.owner}/{repository.name}
      </h1>
      <p>
        <a href={repository.url} target="_blank" rel="noreferrer">
          {repository.url}
        </a>
      </p>

      <RepositoryNav repositoryId={id} />

      {!stats && <p>No completed analysis yet.</p>}

      {stats && (
        <>
          <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", margin: "1.5rem 0" }}>
            <StatCard label="Files" value={stats.totalFiles} />
            <StatCard label="Lines of code" value={stats.totalLines} />
            <StatCard label="Symbols" value={stats.totalSymbols} />
            <StatCard label="Dependency edges" value={stats.totalDependencyEdges} />
          </div>

          <h2>Languages</h2>
          <ul>
            {Object.entries(stats.languages).map(([language, count]) => (
              <li key={language}>
                {language}: {count} file{count === 1 ? "" : "s"}
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
    <div style={{ border: "1px solid #ddd", borderRadius: 6, padding: "0.75rem 1.25rem", minWidth: 120 }}>
      <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{value}</div>
      <div style={{ color: "#666" }}>{label}</div>
    </div>
  );
}

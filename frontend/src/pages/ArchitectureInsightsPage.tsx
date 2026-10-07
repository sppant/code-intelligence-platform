import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { client } from "../graphql/client";
import { ARCHITECTURE_INSIGHTS_QUERY, type ArchitectureInsights } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";

interface RepositoryInsightsResult {
  name: string;
  latestAnalysis: { architectureInsights: ArchitectureInsights } | null;
}

export function ArchitectureInsightsPage() {
  const { id } = useParams<{ id: string }>();
  const [repository, setRepository] = useState<RepositoryInsightsResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    client
      .query<{ repository: RepositoryInsightsResult | null }>(ARCHITECTURE_INSIGHTS_QUERY, { id })
      .toPromise()
      .then((result) => {
        setRepository(result.data?.repository ?? null);
        setLoading(false);
      });
  }, [id]);

  if (!id) return null;
  if (loading) return <p>Loading...</p>;

  const insights = repository?.latestAnalysis?.architectureInsights;

  return (
    <main style={{ maxWidth: 900, margin: "2rem auto", padding: "0 1.5rem" }}>
      <h1>{repository?.name}</h1>
      <RepositoryNav repositoryId={id} />

      {!insights && <p>No completed analysis yet.</p>}

      {insights && (
        <>
          <h2>Circular dependencies</h2>
          {insights.cycles.length === 0 ? (
            <p>None found.</p>
          ) : (
            <ul>
              {insights.cycles.map((cycle, i) => (
                <li key={i}>
                  <code>{[...cycle, cycle[0]].join(" → ")}</code>
                </li>
              ))}
            </ul>
          )}

          <h2>Fan-in / fan-out</h2>
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>File</th>
                <th style={{ textAlign: "left" }}>Fan-in</th>
                <th style={{ textAlign: "left" }}>Fan-out</th>
              </tr>
            </thead>
            <tbody>
              {[...insights.fanInOut]
                .sort((a, b) => b.fanIn + b.fanOut - (a.fanIn + a.fanOut))
                .slice(0, 20)
                .map((f) => (
                  <tr key={f.path}>
                    <td>{f.path}</td>
                    <td>{f.fanIn}</td>
                    <td>{f.fanOut}</td>
                  </tr>
                ))}
            </tbody>
          </table>

          <h2>Large files</h2>
          {insights.largeFiles.length === 0 ? <p>None found.</p> : <ul>{insights.largeFiles.map((p) => <li key={p}>{p}</li>)}</ul>}

          <h2>Isolated files</h2>
          {insights.isolatedFiles.length === 0 ? (
            <p>None found.</p>
          ) : (
            <ul>
              {insights.isolatedFiles.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}

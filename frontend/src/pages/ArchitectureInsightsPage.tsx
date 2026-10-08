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
  if (loading) return <p className="wx-page">Loading...</p>;

  const insights = repository?.latestAnalysis?.architectureInsights;

  return (
    <main className="wx-page">
      <div className="wx-page__header">
        <p className="wx-eyebrow">Architecture Insights</p>
        <h1>{repository?.name}</h1>
      </div>
      <RepositoryNav repositoryId={id} />

      {!insights && <p className="wx-empty">No completed analysis yet.</p>}

      {insights && (
        <>
          <h2>Circular dependencies</h2>
          <div className="wx-card">
            {insights.cycles.length === 0 ? (
              <p className="wx-empty" style={{ margin: 0 }}>
                None found.
              </p>
            ) : (
              insights.cycles.map((cycle, i) => (
                <code key={i} className="wx-cycle">
                  {[...cycle, cycle[0]].join(" → ")}
                </code>
              ))
            )}
          </div>

          <h2>Fan-in / fan-out</h2>
          <div className="wx-card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Fan-in</th>
                  <th>Fan-out</th>
                </tr>
              </thead>
              <tbody>
                {[...insights.fanInOut]
                  .sort((a, b) => b.fanIn + b.fanOut - (a.fanIn + a.fanOut))
                  .slice(0, 20)
                  .map((f) => (
                    <tr key={f.path}>
                      <td>
                        <code>{f.path}</code>
                      </td>
                      <td>{f.fanIn}</td>
                      <td>{f.fanOut}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          <h2>Large files</h2>
          <div className="wx-card">
            {insights.largeFiles.length === 0 ? (
              <p className="wx-empty" style={{ margin: 0 }}>
                None found.
              </p>
            ) : (
              insights.largeFiles.map((p) => (
                <code key={p} className="wx-cycle">
                  {p}
                </code>
              ))
            )}
          </div>

          <h2>Isolated files</h2>
          <div className="wx-card">
            {insights.isolatedFiles.length === 0 ? (
              <p className="wx-empty" style={{ margin: 0 }}>
                None found.
              </p>
            ) : (
              insights.isolatedFiles.map((p) => (
                <code key={p} className="wx-cycle">
                  {p}
                </code>
              ))
            )}
          </div>
        </>
      )}
    </main>
  );
}

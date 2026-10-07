import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { client } from "../graphql/client";
import { IMPACT_ANALYSIS_QUERY, type ImpactAnalysis } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";

export function ImpactAnalysisPage() {
  const { id, symbolId } = useParams<{ id: string; symbolId: string }>();
  const [impact, setImpact] = useState<ImpactAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbolId) return;
    setLoading(true);
    client
      .query<{ impactAnalysis: ImpactAnalysis | null }>(IMPACT_ANALYSIS_QUERY, { symbolId })
      .toPromise()
      .then((result) => {
        setImpact(result.data?.impactAnalysis ?? null);
        setLoading(false);
      });
  }, [symbolId]);

  if (!id) return null;
  if (loading) return <p>Loading...</p>;

  return (
    <main style={{ maxWidth: 900, margin: "2rem auto", padding: "0 1.5rem" }}>
      <h1>Change Impact</h1>
      <RepositoryNav repositoryId={id} />

      {!impact && <p>Symbol not found.</p>}

      {impact && (
        <>
          <p>
            <Link to={`/repository/${id}/explorer`}>&larr; Back to Code Explorer</Link>
          </p>

          <h2>
            <code>{impact.symbol.name}</code>
          </h2>
          <p>
            {impact.symbol.kind} &middot; {impact.symbol.filePath}
          </p>

          <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", margin: "1.5rem 0" }}>
            <StatCard label="Direct callers" value={impact.directCallers.length} />
            <StatCard label="Affected symbols" value={impact.affectedSymbols.length} />
            <StatCard label="Affected files" value={impact.affectedFiles.length} />
            <StatCard label="Affected tests" value={impact.affectedTests.length} />
          </div>

          {impact.riskIndicators.length > 0 && (
            <div style={{ margin: "1rem 0" }}>
              {impact.riskIndicators.map((risk) => (
                <span
                  key={risk}
                  style={{
                    display: "inline-block",
                    border: "1px solid #c77",
                    color: "#c77",
                    borderRadius: 4,
                    padding: "0.2rem 0.6rem",
                    marginRight: "0.5rem",
                    marginBottom: "0.5rem",
                    fontSize: "0.85rem",
                  }}
                >
                  &#9888; {risk}
                </span>
              ))}
            </div>
          )}

          <h3>Direct callers</h3>
          {impact.directCallers.length === 0 ? (
            <p>None found.</p>
          ) : (
            <ul>
              {impact.directCallers.map((c, i) => (
                <li key={i}>
                  {c.symbolName ?? "(module level)"} &mdash; {c.filePath}
                </li>
              ))}
            </ul>
          )}

          <h3>Affected files</h3>
          {impact.affectedFiles.length === 0 ? <p>None found.</p> : <ul>{impact.affectedFiles.map((p) => <li key={p}>{p}</li>)}</ul>}

          <h3>Affected tests</h3>
          {impact.affectedTests.length === 0 ? (
            <p>No tests found among the affected files.</p>
          ) : (
            <ul>
              {impact.affectedTests.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
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

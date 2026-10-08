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
  if (loading) return <p className="wx-page">Loading...</p>;

  return (
    <main className="wx-page">
      <div className="wx-page__header">
        <p className="wx-eyebrow">Change Impact</p>
        <h1>Change Impact</h1>
      </div>
      <RepositoryNav repositoryId={id} />

      {!impact && <p className="wx-empty">Symbol not found.</p>}

      {impact && (
        <>
          <Link to={`/repository/${id}/explorer`} className="wx-back-link">
            &larr; Back to Code Explorer
          </Link>

          <h2>
            <code>{impact.symbol.name}</code>
          </h2>
          <p>
            {impact.symbol.kind} &middot; {impact.symbol.filePath}
          </p>

          <div className="wx-stat-grid">
            <StatCard label="Direct callers" value={impact.directCallers.length} />
            <StatCard label="Affected symbols" value={impact.affectedSymbols.length} />
            <StatCard label="Affected files" value={impact.affectedFiles.length} />
            <StatCard label="Affected tests" value={impact.affectedTests.length} />
          </div>

          {impact.riskIndicators.length > 0 && (
            <div style={{ margin: "0 0 1rem" }}>
              {impact.riskIndicators.map((risk) => (
                <span key={risk} className="wx-risk-chip">
                  &#9888; {risk}
                </span>
              ))}
            </div>
          )}

          <h3>Direct callers</h3>
          {impact.directCallers.length === 0 ? (
            <p className="wx-empty">None found.</p>
          ) : (
            <ul>
              {impact.directCallers.map((c, i) => (
                <li key={i}>
                  {c.symbolName ?? "(module level)"} &mdash; <code>{c.filePath}</code>
                </li>
              ))}
            </ul>
          )}

          <h3>Affected files</h3>
          {impact.affectedFiles.length === 0 ? (
            <p className="wx-empty">None found.</p>
          ) : (
            <ul>
              {impact.affectedFiles.map((p) => (
                <li key={p}>
                  <code>{p}</code>
                </li>
              ))}
            </ul>
          )}

          <h3>Affected tests</h3>
          {impact.affectedTests.length === 0 ? (
            <p className="wx-empty">No tests found among the affected files.</p>
          ) : (
            <ul>
              {impact.affectedTests.map((p) => (
                <li key={p}>
                  <code>{p}</code>
                </li>
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
    <div className="wx-stat-card">
      <div className="wx-stat-card__value">{value}</div>
      <div className="wx-stat-card__label">{label}</div>
    </div>
  );
}

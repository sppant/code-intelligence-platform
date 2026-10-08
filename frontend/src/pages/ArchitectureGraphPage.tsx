import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { client } from "../graphql/client";
import { REPOSITORY_GRAPH_QUERY, type DependencyEdge } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";
import { DependencyGraph } from "../components/DependencyGraph";
import { NoAnalysisYet } from "../components/NoAnalysisYet";

interface RepositoryGraphResult {
  name: string;
  latestAnalysis: {
    files: { path: string; language: string | null }[];
    dependencyEdges: DependencyEdge[];
  } | null;
}

export function ArchitectureGraphPage() {
  const { id } = useParams<{ id: string }>();
  const [repository, setRepository] = useState<RepositoryGraphResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    client
      .query<{ repository: RepositoryGraphResult | null }>(REPOSITORY_GRAPH_QUERY, { id })
      .toPromise()
      .then((result) => {
        setRepository(result.data?.repository ?? null);
        setLoading(false);
      });
  }, [id]);

  if (!id) return null;
  if (loading) return <p className="wx-page">Loading...</p>;
  if (!repository) return <p className="wx-page">Repository not found.</p>;

  const analysis = repository.latestAnalysis;

  return (
    <main className="wx-page wx-page--wide">
      <div className="wx-page__header">
        <p className="wx-eyebrow">Architecture Graph</p>
        <h1>{repository.name}</h1>
      </div>
      <RepositoryNav repositoryId={id} />

      {!analysis && <NoAnalysisYet repositoryId={id} />}
      {analysis && (
        <>
          <p>
            Click a node to highlight its direct dependencies (teal) and dependents (orange), or filter by
            path to spotlight matching files.
          </p>
          <DependencyGraph files={analysis.files} edges={analysis.dependencyEdges} />
        </>
      )}
    </main>
  );
}

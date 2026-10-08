import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { client } from "../graphql/client";
import { REPOSITORY_FILES_QUERY, type FileNode } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";
import { FileTree } from "../components/FileTree";
import { SymbolList } from "../components/SymbolList";
import { SymbolSearch } from "../components/SymbolSearch";
import { NoAnalysisYet } from "../components/NoAnalysisYet";

interface RepositoryFilesResult {
  name: string;
  latestAnalysis: { id: string; files: FileNode[] } | null;
}

export function CodeExplorerPage() {
  const { id } = useParams<{ id: string }>();
  const [repository, setRepository] = useState<RepositoryFilesResult | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    client
      .query<{ repository: RepositoryFilesResult | null }>(REPOSITORY_FILES_QUERY, { id })
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
  const selectedFile = analysis?.files.find((f) => f.path === selectedPath) ?? null;

  return (
    <main className="wx-page wx-page--wide">
      <div className="wx-page__header">
        <p className="wx-eyebrow">Code Explorer</p>
        <h1>{repository.name}</h1>
      </div>
      <RepositoryNav repositoryId={id} />

      {!analysis && <NoAnalysisYet repositoryId={id} />}

      {analysis && (
        <>
          <SymbolSearch analysisId={analysis.id} repositoryId={id} />

          <div style={{ display: "flex", gap: "1.5rem", marginTop: "1.5rem" }}>
            <div className="wx-card" style={{ flex: "0 0 280px", maxHeight: "70vh", overflowY: "auto" }}>
              <FileTree
                paths={analysis.files.map((f) => f.path)}
                selectedPath={selectedPath}
                onSelect={setSelectedPath}
              />
            </div>
            <div className="wx-card" style={{ flex: 1, minWidth: 0 }}>
              {selectedFile ? (
                <>
                  <h2 style={{ marginTop: 0, fontFamily: "var(--wx-font-mono)", fontSize: "1.05rem" }}>
                    {selectedFile.path}
                  </h2>
                  <p>
                    {selectedFile.language ?? "unknown"} · {selectedFile.lineCount} lines
                  </p>
                  <SymbolList symbols={selectedFile.symbols} repositoryId={id} />
                </>
              ) : (
                <p className="wx-empty">Select a file to view its symbols.</p>
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}

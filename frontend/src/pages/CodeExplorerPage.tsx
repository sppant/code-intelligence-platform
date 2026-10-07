import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { client } from "../graphql/client";
import { REPOSITORY_FILES_QUERY, type FileNode } from "../graphql/operations";
import { RepositoryNav } from "../components/RepositoryNav";
import { FileTree } from "../components/FileTree";
import { SymbolList } from "../components/SymbolList";
import { SymbolSearch } from "../components/SymbolSearch";

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
  if (loading) return <p>Loading...</p>;

  const analysis = repository?.latestAnalysis;
  const selectedFile = analysis?.files.find((f) => f.path === selectedPath) ?? null;

  return (
    <main style={{ maxWidth: 1100, margin: "2rem auto", padding: "0 1.5rem" }}>
      <h1>{repository?.name}</h1>
      <RepositoryNav repositoryId={id} />

      {!analysis && <p>No completed analysis yet.</p>}

      {analysis && (
        <>
          <SymbolSearch analysisId={analysis.id} />

          <div style={{ display: "flex", gap: "2rem", marginTop: "1.5rem" }}>
            <div style={{ flex: "0 0 280px", maxHeight: "70vh", overflowY: "auto" }}>
              <FileTree
                paths={analysis.files.map((f) => f.path)}
                selectedPath={selectedPath}
                onSelect={setSelectedPath}
              />
            </div>
            <div style={{ flex: 1 }}>
              {selectedFile ? (
                <>
                  <h2>{selectedFile.path}</h2>
                  <p>
                    {selectedFile.language ?? "unknown"} · {selectedFile.lineCount} lines
                  </p>
                  <SymbolList symbols={selectedFile.symbols} />
                </>
              ) : (
                <p>Select a file to view its symbols.</p>
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}

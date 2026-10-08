import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { client } from "../graphql/client";
import { SEARCH_SYMBOLS_QUERY, type SymbolResult } from "../graphql/operations";

export function SymbolSearch({ analysisId, repositoryId }: { analysisId: string; repositoryId: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SymbolResult[]>([]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }

    const timeout = setTimeout(() => {
      client
        .query<{ searchSymbols: SymbolResult[] }>(SEARCH_SYMBOLS_QUERY, { analysisId, query, kind: null })
        .toPromise()
        .then((result) => setResults(result.data?.searchSymbols ?? []));
    }, 250);

    return () => clearTimeout(timeout);
  }, [analysisId, query]);

  return (
    <div className="wx-search">
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search symbols..."
        aria-label="Search symbols"
      />
      {results.length > 0 && (
        <ul className="wx-search__results">
          {results.map((symbol) => (
            <li key={symbol.id} className="wx-search__result">
              <div className="wx-search__result-row">
                <code>{symbol.name}</code>
                <span className="wx-search__result-meta">{symbol.kind}</span>
              </div>
              <div className="wx-search__result-row wx-search__result-meta">
                <span className="wx-search__result-path">
                  {symbol.filePath}:{symbol.lineStart}
                </span>
                <Link to={`/repository/${repositoryId}/impact/${symbol.id}`}>View impact</Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

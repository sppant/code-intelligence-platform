import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { client } from "../graphql/client";
import { SEARCH_SYMBOLS_QUERY, type SymbolResult } from "../graphql/operations";

export function SymbolSearch({ analysisId, repositoryId }: { analysisId: string; repositoryId: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SymbolResult[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults(null);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timeout = setTimeout(() => {
      client
        .query<{ searchSymbols: SymbolResult[] }>(SEARCH_SYMBOLS_QUERY, { analysisId, query, kind: null })
        .toPromise()
        .then((result) => {
          setResults(result.data?.searchSymbols ?? []);
          setIsSearching(false);
        });
    }, 250);

    return () => clearTimeout(timeout);
  }, [analysisId, query]);

  const showDropdown = query.trim().length >= 2;

  return (
    <div className="wx-search">
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search symbols..."
        aria-label="Search symbols"
      />
      {showDropdown && (
        <ul className="wx-search__results">
          {isSearching && (
            <li className="wx-search__result wx-search__result--status">Searching&hellip;</li>
          )}
          {!isSearching && results && results.length === 0 && (
            <li className="wx-search__result wx-search__result--status">No symbols match &ldquo;{query}&rdquo;.</li>
          )}
          {!isSearching &&
            results?.map((symbol) => (
              <li key={symbol.id} className="wx-search__result">
                <div className="wx-search__result-row">
                  <code>{symbol.parent ? `${symbol.parent}.${symbol.name}` : symbol.name}</code>
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

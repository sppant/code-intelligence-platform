import { useEffect, useState } from "react";
import { client } from "../graphql/client";
import { SEARCH_SYMBOLS_QUERY, type SymbolResult } from "../graphql/operations";

export function SymbolSearch({ analysisId }: { analysisId: string }) {
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
    <div>
      <input
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search symbols..."
        aria-label="Search symbols"
      />
      {results.length > 0 && (
        <ul>
          {results.map((symbol) => (
            <li key={symbol.id}>
              <code>{symbol.name}</code> ({symbol.kind}) — {symbol.filePath}:{symbol.lineStart}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

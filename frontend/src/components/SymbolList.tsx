import { Link } from "react-router-dom";
import type { SymbolResult } from "../graphql/operations";

export function SymbolList({ symbols, repositoryId }: { symbols: SymbolResult[]; repositoryId: string }) {
  if (symbols.length === 0) {
    return <p>No symbols in this file.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>Name</th>
          <th style={{ textAlign: "left" }}>Kind</th>
          <th style={{ textAlign: "left" }}>Lines</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {symbols.map((symbol) => (
          <tr key={symbol.id}>
            <td>{symbol.name}</td>
            <td>{symbol.kind}</td>
            <td>
              {symbol.lineStart}–{symbol.lineEnd}
            </td>
            <td>
              <Link to={`/repository/${repositoryId}/impact/${symbol.id}`}>View impact</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

import { Client, cacheExchange, fetchExchange, type CombinedError } from "urql";

const graphqlUrl = import.meta.env.VITE_GRAPHQL_URL ?? "http://localhost:8000/graphql";

export const client = new Client({
  url: graphqlUrl,
  exchanges: [cacheExchange, fetchExchange],
});

/** Strips urql's "[GraphQL] "/"[Network] " source prefix for display to end users. */
export function formatError(error: CombinedError): string {
  return error.message.replace(/^\[(GraphQL|Network)\]\s*/, "");
}

/**
 * Job failures (e.g. a failed `git clone`) can carry a multi-line subprocess
 * stderr dump in their message -- useful server-side, too raw for a user-
 * facing card. Keep just the summary line and cap its length.
 */
export function summarizeError(message: string, maxLength = 200): string {
  const firstLine = message.split("\n")[0].trim();
  return firstLine.length > maxLength ? `${firstLine.slice(0, maxLength - 1)}…` : firstLine;
}

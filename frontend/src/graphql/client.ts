import { Client, cacheExchange, fetchExchange } from "urql";

const graphqlUrl = import.meta.env.VITE_GRAPHQL_URL ?? "http://localhost:8000/graphql";

export const client = new Client({
  url: graphqlUrl,
  exchanges: [cacheExchange, fetchExchange],
});

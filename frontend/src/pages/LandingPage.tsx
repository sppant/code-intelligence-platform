import { useEffect, useState } from "react";
import { client } from "../graphql/client";
import { HEALTH_QUERY } from "../graphql/operations";

export function LandingPage() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "error">("checking");

  useEffect(() => {
    client
      .query<{ health: string }>(HEALTH_QUERY, {})
      .toPromise()
      .then((result) => setApiStatus(result.data?.health === "ok" ? "ok" : "error"));
  }, []);

  return (
    <main>
      <h1>Code Intelligence</h1>
      <p>Understand any codebase.</p>
      <p>API status: {apiStatus}</p>
    </main>
  );
}

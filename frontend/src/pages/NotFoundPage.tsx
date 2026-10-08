import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="wx-page">
      <p className="wx-eyebrow">404</p>
      <h1>Page not found</h1>
      <p>
        <Link to="/">&larr; Back to Code Intelligence</Link>
      </p>
    </main>
  );
}

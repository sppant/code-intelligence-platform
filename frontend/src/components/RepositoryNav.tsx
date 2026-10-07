import { NavLink } from "react-router-dom";

export function RepositoryNav({ repositoryId }: { repositoryId: string }) {
  const base = `/repository/${repositoryId}`;
  const linkStyle = ({ isActive }: { isActive: boolean }) => ({
    fontWeight: isActive ? 700 : 400,
  });

  return (
    <nav style={{ display: "flex", gap: "1rem", margin: "1rem 0", borderBottom: "1px solid #ddd", paddingBottom: "0.5rem" }}>
      <NavLink to={base} end style={linkStyle}>
        Overview
      </NavLink>
      <NavLink to={`${base}/explorer`} style={linkStyle}>
        Code Explorer
      </NavLink>
      <NavLink to={`${base}/graph`} style={linkStyle}>
        Architecture Graph
      </NavLink>
    </nav>
  );
}

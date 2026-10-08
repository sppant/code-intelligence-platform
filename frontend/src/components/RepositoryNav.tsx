import { NavLink } from "react-router-dom";

export function RepositoryNav({ repositoryId }: { repositoryId: string }) {
  const base = `/repository/${repositoryId}`;
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? "wx-nav-tabs__active" : undefined;

  return (
    <nav className="wx-nav-tabs">
      <NavLink to={base} end className={linkClass}>
        Overview
      </NavLink>
      <NavLink to={`${base}/explorer`} className={linkClass}>
        Code Explorer
      </NavLink>
      <NavLink to={`${base}/graph`} className={linkClass}>
        Architecture Graph
      </NavLink>
      <NavLink to={`${base}/insights`} className={linkClass}>
        Insights
      </NavLink>
    </nav>
  );
}

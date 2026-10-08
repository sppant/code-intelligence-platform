import { Link, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <>
      <header className="wx-topbar">
        <Link to="/" className="wx-topbar__brand">
          <img src="/wx-logo.webp" alt="WebXDevelop" className="wx-topbar__logo" />
          <span className="wx-topbar__wordmark">
            <small>WebXDevelop</small> / <span className="wx-topbar__product">Code Intelligence</span>
          </span>
        </Link>
      </header>
      <div className="wx-shell">
        <Outlet />
      </div>
    </>
  );
}

import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { titleCase } from "../lib/format";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  permission: string;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: "◫", permission: "infrastructure:read", end: true },
  { to: "/resources", label: "Resources", icon: "▤", permission: "infrastructure:read" },
  { to: "/servers", label: "Servers", icon: "▥", permission: "infrastructure:read" },
  { to: "/deployments", label: "Deployments", icon: "⇅", permission: "deployment:read" },
  { to: "/compliance", label: "Compliance", icon: "✓", permission: "compliance:read" },
  { to: "/drift", label: "Drift", icon: "≠", permission: "drift:read" },
  { to: "/audit", label: "Audit trail", icon: "≡", permission: "audit:read" },
  { to: "/users", label: "Access", icon: "◎", permission: "user:read" },
];

const ROUTE_TITLES: Record<string, string> = {
  "/": "Platform overview",
  "/resources": "Infrastructure inventory",
  "/servers": "Server fleet",
  "/deployments": "Deployment pipeline",
  "/compliance": "Compliance posture",
  "/drift": "Configuration drift",
  "/audit": "Audit trail",
  "/users": "Identity and access",
};

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function Layout() {
  const { user, signOut, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [signingOut, setSigningOut] = useState(false);

  const visibleItems = NAV_ITEMS.filter((item) => can(item.permission));
  const title = ROUTE_TITLES[location.pathname] ?? "Control plane";

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await signOut();
      navigate("/login", { replace: true });
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">HC</div>
          <div>
            <div className="brand-name">Hybrid Cloud</div>
            <div className="brand-sub">Control plane</div>
          </div>
        </div>

        <nav className="nav" aria-label="Primary">
          <div className="nav-section">Operations</div>
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-line">
            <div className="avatar" aria-hidden="true">{user ? initials(user.full_name) : "?"}</div>
            <div style={{ minWidth: 0 }}>
              <div className="user-name" title={user?.email}>{user?.full_name ?? "Unknown"}</div>
              <div className="user-role">{user ? titleCase(user.role) : "—"}</div>
            </div>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleSignOut} disabled={signingOut}>
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">{title}</div>
          <div className="topbar-meta">
            <span className="chip">
              <span className="status-dot" aria-hidden="true" />
              API connected
            </span>
            <span className="chip">ap-south-1</span>
            <span className="mono">{user?.email}</span>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

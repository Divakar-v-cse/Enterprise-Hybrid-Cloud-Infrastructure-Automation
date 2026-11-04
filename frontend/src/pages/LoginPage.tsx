import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../lib/format";

const DEMO_ACCOUNTS = [
  { role: "admin", email: "admin@hccp.io", password: "Admin#2026" },
  { role: "operator", email: "operator@hccp.io", password: "Operator#2026" },
  { role: "approver", email: "approver@hccp.io", password: "Approver#2026" },
  { role: "viewer", email: "viewer@hccp.io", password: "Viewer#2026" },
];

export function LoginPage() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("admin@hccp.io");
  const [password, setPassword] = useState("Admin#2026");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  if (user) {
    return <Navigate to={redirectTo} replace />;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <section className="login-aside">
        <div>
          <div className="brand" style={{ padding: 0 }}>
            <div className="brand-mark" aria-hidden="true">HC</div>
            <div>
              <div className="brand-name">Enterprise Hybrid Cloud</div>
              <div className="brand-sub">Infrastructure automation</div>
            </div>
          </div>
          <h1 className="login-headline" style={{ marginTop: 40 }}>
            One control plane for Terraform, Ansible and AWS.
          </h1>
          <p className="login-sub">
            Inventory, deployment approvals, compliance evidence and configuration drift in a
            single auditable surface. Development and production stay isolated, with keyless
            GitHub Actions and role-based access.
          </p>
          <div className="login-points">
            <div className="login-point"><span>▸</span><span>Terraform modules for VPC, subnets, routing, IAM, compute and ALB</span></div>
            <div className="login-point"><span>▸</span><span>Ansible baselines for Linux and Windows Server, with rolling patching</span></div>
            <div className="login-point"><span>▸</span><span>Policy-as-code scoring and desired-state drift detection</span></div>
            <div className="login-point"><span>▸</span><span>Audited deployments with separation of duties</span></div>
          </div>
        </div>
        <div className="small muted">
          Terraform 1.6+ · Ansible 2.16+ · FastAPI · React · GitHub Actions
        </div>
      </section>

      <main className="login-main">
        <div className="login-card">
          <h2 style={{ fontSize: 20 }}>Sign in</h2>
          <p className="card-subtitle" style={{ marginBottom: 20 }}>
            Authenticate with your platform account to continue.
          </p>

          {error ? <div className="error-banner" role="alert">{error}</div> : null}

          <form onSubmit={handleSubmit} className="stack">
            <div className="field">
              <label htmlFor="email">Work email</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy} style={{ marginTop: 6 }}>
              {busy ? <span className="spinner" aria-hidden="true" /> : null}
              {busy ? "Authenticating…" : "Sign in"}
            </button>
          </form>

          <div className="demo-accounts">
            <div className="demo-title">Seeded demo accounts</div>
            <div className="demo-grid">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.role}
                  type="button"
                  className="demo-account"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(account.password);
                  }}
                >
                  <strong>{account.role}</strong>
                  {account.email}
                </button>
              ))}
            </div>
            <p className="small muted" style={{ marginTop: 10 }}>
              Seeded only when <code>HCCP_SEED_DEMO_DATA=true</code>. Disabled in production by
              configuration validation.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

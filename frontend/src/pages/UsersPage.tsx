import { useState } from "react";

import { apiRequest } from "../api/client";
import type { Role, User } from "../api/types";
import { Badge, ErrorBanner, Loading, Modal, PageHeader } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useApi, useMutation } from "../hooks/useApi";
import { relativeTime, titleCase } from "../lib/format";

const ROLES: Role[] = ["viewer", "operator", "approver", "admin"];

interface CreateUserForm {
  email: string;
  full_name: string;
  role: Role;
  password: string;
}

const EMPTY_FORM: CreateUserForm = { email: "", full_name: "", role: "viewer", password: "" };

export function UsersPage() {
  const { user, can } = useAuth();
  const { data, loading, error, reload } = useApi<User[]>("/users");
  const mutation = useMutation();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateUserForm>(EMPTY_FORM);

  async function changeRole(target: User, role: Role) {
    if (role === target.role) return;
    const updated = await mutation.run(() =>
      apiRequest<User>(`/users/${target.id}/role`, { method: "PATCH", body: { role } }),
    );
    if (updated) reload();
  }

  async function deactivate(target: User) {
    const updated = await mutation.run(() =>
      apiRequest<User>(`/users/${target.id}/deactivate`, { method: "POST" }),
    );
    if (updated) reload();
  }

  async function createUser(event: React.FormEvent) {
    event.preventDefault();
    const created = await mutation.run(() =>
      apiRequest<User>("/users", { method: "POST", body: form }),
    );
    if (created) {
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      reload();
    }
  }

  const canManage = can("user:manage");

  return (
    <>
      <PageHeader
        title="Identity and access"
        description="Role assignments are enforced server-side on every request. Viewer → operator → approver → admin, with separation of duties on production changes."
        actions={
          canManage ? (
            <button type="button" className="btn btn-primary" onClick={() => setCreateOpen(true)}>
              Add account
            </button>
          ) : null
        }
      />

      {error ? <ErrorBanner message={error} /> : null}
      {mutation.error ? <ErrorBanner message={mutation.error} onDismiss={mutation.clearError} /> : null}
      {loading && !data ? <Loading label="Loading accounts" /> : null}

      {data ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Role</th>
                <th>MFA</th>
                <th>Status</th>
                <th>Last sign-in</th>
                {canManage ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {data.map((account) => (
                <tr key={account.id}>
                  <td>
                    <div className="cell-strong">{account.full_name}</div>
                    <div className="cell-sub">{account.email}</div>
                  </td>
                  <td>
                    {canManage && account.id !== user?.id ? (
                      <select
                        className="input"
                        value={account.role}
                        onChange={(event) => changeRole(account, event.target.value as Role)}
                        aria-label={`Role for ${account.email}`}
                        disabled={mutation.busy}
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role}>
                            {titleCase(role)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <Badge tone={account.role === "admin" ? "violet" : "info"}>
                        {titleCase(account.role)}
                      </Badge>
                    )}
                  </td>
                  <td>
                    <Badge tone={account.mfa_enabled ? "success" : "danger"}>
                      {account.mfa_enabled ? "Enrolled" : "Missing"}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone={account.is_active ? "success" : "neutral"}>
                      {account.is_active ? "Active" : "Disabled"}
                    </Badge>
                  </td>
                  <td className="small muted">{relativeTime(account.last_login_at)}</td>
                  {canManage ? (
                    <td>
                      {account.id !== user?.id && account.is_active ? (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => deactivate(account)}
                          disabled={mutation.busy}
                        >
                          Disable
                        </button>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Modal
        open={createOpen}
        title="Provision an account"
        subtitle="Minimum 10 characters with upper, lower, digit and symbol."
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <button type="button" className="btn btn-ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </button>
            <button type="submit" form="user-form" className="btn btn-primary" disabled={mutation.busy}>
              {mutation.busy ? "Creating…" : "Create account"}
            </button>
          </>
        }
      >
        <form id="user-form" className="form-grid" onSubmit={createUser}>
          <div className="field full">
            <label htmlFor="user-email">Email</label>
            <input
              id="user-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              required
            />
          </div>
          <div className="field full">
            <label htmlFor="user-name">Full name</label>
            <input
              id="user-name"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              required
              minLength={2}
            />
          </div>
          <div className="field">
            <label htmlFor="user-role">Role</label>
            <select
              id="user-role"
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value as Role })}
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {titleCase(role)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="user-password">Temporary password</label>
            <input
              id="user-password"
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              required
              minLength={10}
              autoComplete="new-password"
            />
          </div>
        </form>
      </Modal>
    </>
  );
}

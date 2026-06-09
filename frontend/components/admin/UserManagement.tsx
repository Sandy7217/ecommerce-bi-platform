"use client";

import { useState } from "react";
import toast from "react-hot-toast";

import { RoleGuard } from "@/components/layout/RoleGuard";
import { Badge } from "@/components/ui/Badge";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiDelete, apiPost, apiPut } from "@/lib/api";
import { formatDate } from "@/lib/formatters";
import type { Role } from "@/types";

const roles: Role[] = ["super_admin", "admin", "manager", "analyst", "md", "viewer"];

export type UserRow = {
  user_id?: string;
  email?: string;
  name?: string;
  role?: Role;
  is_active?: boolean;
  last_login?: string;
  created_at?: string;
};

type CreateUserResponse = {
  status: string;
  user?: UserRow;
};

type UserManagementProps = {
  users: UserRow[];
  onReload: () => void;
};

export function UserManagement({ users, onReload }: UserManagementProps) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [sending, setSending] = useState(false);
  const [deleting, setDeleting] = useState<UserRow | null>(null);

  async function createUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSending(true);
    try {
      await apiPost<CreateUserResponse>("/admin/users", { email, name, role });
      toast.success(`Invite sent to ${email}`);
      setEmail("");
      setName("");
      setRole("viewer");
      onReload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Invite failed");
    } finally {
      setSending(false);
    }
  }

  async function updateUser(row: UserRow, patch: Partial<Pick<UserRow, "role" | "is_active">>) {
    if (!row.user_id) {
      toast.error("Missing user id");
      return;
    }
    try {
      await apiPut(`/admin/users/${row.user_id}`, patch);
      toast.success("User updated");
      onReload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Update failed");
    }
  }

  async function deleteUser() {
    if (!deleting?.user_id) return;
    try {
      await apiDelete(`/admin/users/${deleting.user_id}`);
      toast.success("User deleted");
      setDeleting(null);
      onReload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Delete failed");
    }
  }

  return (
    <RoleGuard access="user_management">
      <section className="space-y-4">
        <div>
          <div className="text-sm font-semibold text-ink">User Management</div>
          <div className="mt-1 text-xs text-muted">Create invites, manage roles, and control active dashboard access.</div>
        </div>

        <form className="grid gap-3 rounded-lg border border-line bg-white p-4 shadow-soft lg:grid-cols-[1fr_1fr_220px_auto]" onSubmit={createUser}>
          <input
            className="rounded border border-line px-3 py-2 text-sm outline-none transition duration-200 ease-in-out focus:border-teal"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email"
            required
            type="email"
            value={email}
          />
          <input
            className="rounded border border-line px-3 py-2 text-sm outline-none transition duration-200 ease-in-out focus:border-teal"
            onChange={(event) => setName(event.target.value)}
            placeholder="Name"
            type="text"
            value={name}
          />
          <select
            className="rounded border border-line px-3 py-2 text-sm outline-none transition duration-200 ease-in-out focus:border-teal"
            onChange={(event) => setRole(event.target.value as Role)}
            value={role}
          >
            {roles.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            className="rounded bg-ink px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
            disabled={sending}
            type="submit"
          >
            {sending ? "Sending..." : "Send Invite"}
          </button>
        </form>

        <DataTable
          rows={users}
          rowKey={(row, index) => row.user_id || row.email || String(index)}
          empty={<EmptyState title="No admin users" />}
          minWidth="980px"
          columns={[
            { key: "name", label: "Name", sortable: true, render: (row) => row.name || "NA" },
            { key: "email", label: "Email", sortable: true, copy: true, render: (row) => row.email || "Unknown" },
            {
              key: "role",
              label: "Role",
              sortable: true,
              render: (row) => (
                <select
                  aria-label={`Edit role for ${row.email || "user"}`}
                  className="rounded border border-line bg-white px-2 py-1 text-xs text-ink outline-none transition duration-200 ease-in-out focus:border-teal"
                  onChange={(event) => updateUser(row, { role: event.target.value as Role })}
                  value={row.role || "viewer"}
                >
                  {roles.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              ),
            },
            { key: "last_login", label: "Last Login", sortable: true, render: (row) => (row.last_login ? formatDate(row.last_login) : "NA") },
            {
              key: "is_active",
              label: "Status",
              sortable: true,
              render: (row) => <Badge tone={row.is_active === false ? "red" : "green"}>{row.is_active === false ? "Inactive" : "Active"}</Badge>,
            },
            {
              key: "actions",
              label: "Actions",
              render: (row) => (
                <div className="flex flex-wrap gap-2">
                  <button
                    className="rounded border border-line px-3 py-1.5 text-xs font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02]"
                    onClick={() => updateUser(row, { is_active: row.is_active === false })}
                    type="button"
                  >
                    {row.is_active === false ? "Reactivate" : "Deactivate"}
                  </button>
                  <button
                    className="rounded bg-danger px-3 py-1.5 text-xs font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02]"
                    onClick={() => setDeleting(row)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              ),
            },
          ]}
        />

        <ConfirmModal
          open={Boolean(deleting)}
          title="Delete user"
          body={`Delete ${deleting?.email || "this user"} from Supabase Auth and app roles?`}
          confirmLabel="Delete user"
          onClose={() => setDeleting(null)}
          onConfirm={deleteUser}
        />
      </section>
    </RoleGuard>
  );
}

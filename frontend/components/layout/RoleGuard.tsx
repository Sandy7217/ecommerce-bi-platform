"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import type { Role } from "@/types";
import { apiGet } from "@/lib/api";

const ROLE_ACCESS: Record<Role, string[]> = {
  super_admin: ["*"],
  admin: ["dashboard", "sales", "inventory", "categories", "ads", "returns", "regional", "assistant", "reports", "admin", "user_management"],
  manager: ["dashboard", "sales", "inventory", "categories", "ads", "returns", "regional", "assistant", "reports"],
  analyst: ["dashboard", "sales", "inventory", "ads", "returns", "regional"],
  md: ["dashboard", "sales", "inventory"],
  viewer: ["dashboard"]
};

type UserRoleRow = {
  email?: string;
  role?: Role;
  is_active?: boolean;
};

export function RoleGuard({ children, role, access }: { children: ReactNode; role?: Role; access: string }) {
  const [resolvedRole, setResolvedRole] = useState<Role>(role ?? "viewer");
  const [loading, setLoading] = useState(!role);

  useEffect(() => {
    if (role) {
      setResolvedRole(role);
      setLoading(false);
      return;
    }
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then(async (data) => {
        const email = data?.user?.email;
        if (!email) {
          setResolvedRole("viewer");
          setLoading(false);
          return;
        }
        try {
          const rows = await apiGet<UserRoleRow[]>("/admin/users");
          const match = rows.find((row) => row.email?.toLowerCase() === email.toLowerCase() && row.is_active !== false);
          setResolvedRole(match?.role ?? "viewer");
        } catch {
          setResolvedRole("viewer");
        } finally {
          setLoading(false);
        }
      })
      .catch(() => {
        setResolvedRole("viewer");
        setLoading(false);
      });
  }, [role]);

  if (loading) {
    return <div className="rounded-lg border border-line bg-white p-6 text-sm text-muted">Checking access...</div>;
  }

  const allowedRole = resolvedRole in ROLE_ACCESS ? resolvedRole : "viewer";
  const allowed = ROLE_ACCESS[allowedRole].includes("*") || ROLE_ACCESS[allowedRole].includes(access);
  if (!allowed) {
    return <div className="rounded-lg border border-line bg-white p-6 text-sm text-muted">This role does not have access to this page.</div>;
  }
  return <>{children}</>;
}

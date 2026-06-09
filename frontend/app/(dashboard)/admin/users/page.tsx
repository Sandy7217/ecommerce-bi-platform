"use client";

import Link from "next/link";

import { UserManagement, type UserRow } from "@/components/admin/UserManagement";
import { ErrorState } from "@/components/ui/ErrorState";
import { useApiData } from "@/lib/useApiData";

export default function AdminUsersPage() {
  const users = useApiData<UserRow[]>("/admin/users", []);

  if (users.error) {
    return <ErrorState message={users.error} onRetry={users.retry} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <Link className="rounded border border-line px-4 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02]" href="/admin">
          Admin overview
        </Link>
        <Link className="rounded border border-line px-4 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02]" href="/admin/settings">
          Settings
        </Link>
      </div>
      <UserManagement users={users.data} onReload={users.retry} />
    </div>
  );
}

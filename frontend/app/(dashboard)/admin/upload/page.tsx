import { UploadCenter, type UploadRow } from "@/components/admin/UploadCenter";
import { RoleGuard } from "@/components/layout/RoleGuard";
import { serverApiGet } from "@/lib/server-api";

async function safeGet<T>(path: string, fallback: T): Promise<T> {
  try {
    return await serverApiGet<T>(path);
  } catch {
    return fallback;
  }
}

export default async function UploadPage() {
  const uploadLog = await safeGet<UploadRow[]>("/admin/upload_log", []);

  return (
    <RoleGuard access="admin">
      <UploadCenter uploadLog={uploadLog} />
    </RoleGuard>
  );
}

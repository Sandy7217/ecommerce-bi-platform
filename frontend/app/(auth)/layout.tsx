import type { ReactNode } from "react";

import { ToastProvider } from "@/components/ui/ToastProvider";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="login-option3-bg flex min-h-screen items-center justify-center p-6">
      {children}
      <ToastProvider />
    </main>
  );
}

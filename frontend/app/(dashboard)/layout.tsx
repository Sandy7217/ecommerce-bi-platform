import type { ReactNode } from "react";
import { Suspense } from "react";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { BackToTop } from "@/components/ui/BackToTop";
import { PageTransition } from "@/components/ui/PageTransition";
import { ToastProvider } from "@/components/ui/ToastProvider";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas">
      <Sidebar />
      <div className="lg:pl-64">
        <Suspense fallback={<div className="sticky top-0 z-10 h-[73px] border-b border-line bg-white/90" />}>
          <Topbar />
        </Suspense>
        <main className="p-3 sm:p-4 lg:p-6">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>
      <ToastProvider />
      <BackToTop />
    </div>
  );
}

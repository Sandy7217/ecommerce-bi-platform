"use client";

import { Toaster } from "react-hot-toast";

export function ToastProvider() {
  return <Toaster position="top-right" toastOptions={{ duration: 3500, style: { border: "1px solid #dbe3ee", color: "#172033" } }} />;
}

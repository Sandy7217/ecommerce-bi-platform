"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" }).then((response) => {
      if (response.ok) window.location.replace("/");
    });
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const payload = await response.json().catch(() => ({}));
    setLoading(false);
    if (!response.ok) {
      toast.error(payload.error ?? "Unable to sign in");
      return;
    }
    toast.success("Signed in");
    window.location.replace("/");
  }

  return (
    <section className="w-full max-w-md rounded-lg border border-white/80 bg-white/95 p-6 shadow-soft backdrop-blur-xl">
      <div className="mb-6 text-center">
        <div className="text-3xl font-semibold tracking-wide text-ink">E-Commerce BI</div>
        <div className="text-xs uppercase tracking-[0.24em] text-muted">Portfolio Dashboard</div>
        <div className="mx-auto mt-4 h-px w-36 bg-teal/40" />
      </div>
      <h1 className="text-center text-base font-semibold text-ink">Sign in to E-Commerce BI</h1>
      <p className="mt-2 text-center text-sm text-muted">Use your Supabase Auth email and password.</p>
      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <input
          autoComplete="email"
          className="w-full rounded border border-line px-3 py-2 text-sm outline-none transition duration-200 ease-in-out focus:border-teal"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Email"
          required
          type="email"
          value={email}
        />
        <input
          autoComplete="current-password"
          className="w-full rounded border border-line px-3 py-2 text-sm outline-none transition duration-200 ease-in-out focus:border-teal"
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Password"
          required
          type="password"
          value={password}
        />
        <button
          className="w-full rounded bg-[#65724a] px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading}
          type="submit"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </section>
  );
}

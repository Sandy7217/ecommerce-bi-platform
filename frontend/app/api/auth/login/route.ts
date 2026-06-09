import { NextResponse } from "next/server";

import { setAuthCookies, signInWithPassword } from "@/lib/server-auth";

export async function POST(request: Request) {
  try {
    const { email, password } = (await request.json()) as { email?: string; password?: string };
    if (!email || !password) {
      return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
    }

    const session = await signInWithPassword(email, password);
    await setAuthCookies(session);
    return NextResponse.json({ user: session.user ?? null });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to sign in";
    const status = message.includes("configured") ? 500 : 401;
    return NextResponse.json({ error: message }, { status });
  }
}

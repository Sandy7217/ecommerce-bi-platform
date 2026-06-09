import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { ACCESS_COOKIE, REFRESH_COOKIE, getUserFromAccessToken, refreshSession, setAuthCookies } from "@/lib/server-auth";

export async function GET() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;

  if (accessToken) {
    const user = await getUserFromAccessToken(accessToken);
    if (user) return NextResponse.json({ user });
  }

  if (refreshToken) {
    const session = await refreshSession(refreshToken);
    if (session?.access_token) {
      await setAuthCookies(session);
      return NextResponse.json({ user: session.user ?? null });
    }
  }

  return NextResponse.json({ user: null }, { status: 401 });
}

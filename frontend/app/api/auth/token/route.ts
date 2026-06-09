import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, getUserFromAccessToken, refreshSession, setAuthCookies } from "@/lib/server-auth";

export async function GET() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (accessToken && (await getUserFromAccessToken(accessToken))) {
    return NextResponse.json({ access_token: accessToken });
  }

  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const session = await refreshSession(refreshToken);
  if (!session?.access_token) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }
  await setAuthCookies(session);
  return NextResponse.json({ access_token: session.access_token });
}

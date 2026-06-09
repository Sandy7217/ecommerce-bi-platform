import { type NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "commerce_bi_access_token";
const REFRESH_COOKIE = "commerce_bi_refresh_token";

async function getUserEmail(accessToken?: string) {
  const supabaseUrl = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_KEY;
  if (!supabaseUrl || !serviceKey || !accessToken) return null;

  const response = await fetch(`${supabaseUrl}/auth/v1/user`, {
    headers: {
      apikey: serviceKey,
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });
  if (!response.ok) return null;
  const user = (await response.json()) as { email?: string };
  return user.email ?? null;
}

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isLoginRoute = pathname === "/login";
  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  const userEmail = await getUserEmail(accessToken);

  if (!userEmail && !refreshToken && !isLoginRoute) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (userEmail && isLoginRoute) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next({ request });
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};

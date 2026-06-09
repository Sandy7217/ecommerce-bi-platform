import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

import { ACCESS_COOKIE, REFRESH_COOKIE, refreshSession, setAuthCookies } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.replace("http://localhost:8001", "http://127.0.0.1:8001");

const API_ROOT =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (configuredApiUrl ? `${configuredApiUrl}/api` : "http://127.0.0.1:8001/api");

const forwardedRequestHeaders = new Set(["accept", "content-type"]);
const responseHeaderBlocklist = new Set(["content-encoding", "content-length", "transfer-encoding"]);

function buildHeaders(headers: Headers, accessToken: string) {
  const nextHeaders = new Headers();
  headers.forEach((value, key) => {
    if (forwardedRequestHeaders.has(key.toLowerCase())) {
      nextHeaders.set(key, value);
    }
  });
  nextHeaders.set("Authorization", `Bearer ${accessToken}`);
  return nextHeaders;
}

async function resolvePath(context: RouteContext) {
  const params = await context.params;
  return params.path ?? [];
}

async function accessTokenFromSession() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (accessToken) return accessToken;

  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;

  const session = await refreshSession(refreshToken);
  if (!session?.access_token) return null;
  await setAuthCookies(session);
  return session.access_token;
}

async function retryAccessToken() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;
  const session = await refreshSession(refreshToken);
  if (!session?.access_token) return null;
  await setAuthCookies(session);
  return session.access_token;
}

async function backendFetch(request: NextRequest, target: URL, accessToken: string, body: ArrayBuffer | undefined) {
  return fetch(target, {
    method: request.method,
    headers: buildHeaders(request.headers, accessToken),
    body,
    cache: "no-store",
    redirect: "manual",
  });
}

async function proxy(request: NextRequest, context: RouteContext) {
  let accessToken = await accessTokenFromSession();
  if (!accessToken) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }
  const path = await resolvePath(context);
  const target = new URL(`${API_ROOT}/${path.map(encodeURIComponent).join("/")}`);
  target.search = request.nextUrl.search;
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();

  try {
    let response = await backendFetch(request, target, accessToken, body);
    if (response.status === 401) {
      const refreshedToken = await retryAccessToken();
      if (refreshedToken && refreshedToken !== accessToken) {
        accessToken = refreshedToken;
        response = await backendFetch(request, target, accessToken, body);
      }
    }

    const headers = new Headers(response.headers);
    responseHeaderBlocklist.forEach((header) => headers.delete(header));

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend request failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

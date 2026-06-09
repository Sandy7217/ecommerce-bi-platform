import { cookies } from "next/headers";
import { cache } from "react";

import { ACCESS_COOKIE, REFRESH_COOKIE, refreshSession } from "@/lib/server-auth";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.replace("http://localhost:8001", "http://127.0.0.1:8001").replace(/\/$/, "");
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

const SERVER_API_ROOT =
  configuredApiBaseUrl ??
  (configuredApiUrl ? `${configuredApiUrl}/api` : "http://127.0.0.1:8001/api");

const getServerAccessToken = cache(async function getServerAccessToken() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (accessToken) return accessToken;

  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;

  const session = await refreshSession(refreshToken);
  return session?.access_token ?? null;
});

const getRefreshedAccessToken = cache(async function getRefreshedAccessToken() {
  const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;
  const session = await refreshSession(refreshToken);
  return session?.access_token ?? null;
});

async function fetchWithToken(path: string, accessToken: string) {
  return fetch(`${SERVER_API_ROOT}${path}`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });
}

export async function serverApiGet<T>(path: string): Promise<T> {
  const accessToken = await getServerAccessToken();
  if (!accessToken) {
    throw new Error("Authentication required");
  }

  let response = await fetchWithToken(path, accessToken);
  if (response.status === 401) {
    const refreshedToken = await getRefreshedAccessToken();
    if (refreshedToken) {
      response = await fetchWithToken(path, refreshedToken);
    }
  }

  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }

  return (await response.json()) as T;
}

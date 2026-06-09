import { cookies } from "next/headers";

export const ACCESS_COOKIE = "commerce_bi_access_token";
export const REFRESH_COOKIE = "commerce_bi_refresh_token";

type SupabaseSession = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user?: {
    id: string;
    email?: string;
  };
};

export type AuthUser = {
  id: string;
  email?: string;
};

function getSupabaseConfig() {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !serviceKey) {
    throw new Error("Supabase server auth is not configured");
  }
  return { url, serviceKey };
}

async function supabaseAuthFetch(path: string, init: RequestInit = {}, bearer?: string) {
  const { url, serviceKey } = getSupabaseConfig();
  const headers = new Headers(init.headers);
  headers.set("apikey", serviceKey);
  headers.set("Authorization", `Bearer ${bearer ?? serviceKey}`);
  return fetch(`${url}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function signInWithPassword(email: string, password: string) {
  const response = await supabaseAuthFetch("/auth/v1/token?grant_type=password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.msg ?? payload.message ?? payload.error_description ?? "Unable to sign in");
  }
  return payload as SupabaseSession;
}

export async function refreshSession(refreshToken: string) {
  const response = await supabaseAuthFetch("/auth/v1/token?grant_type=refresh_token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return null;
  return (await response.json()) as SupabaseSession;
}

export async function getUserFromAccessToken(accessToken: string) {
  const response = await supabaseAuthFetch("/auth/v1/user", undefined, accessToken);
  if (!response.ok) return null;
  const user = (await response.json()) as AuthUser;
  return user.email ? user : null;
}

export async function setAuthCookies(session: SupabaseSession) {
  const cookieStore = await cookies();
  const secure = process.env.NODE_ENV === "production";
  cookieStore.set(ACCESS_COOKIE, session.access_token, {
    httpOnly: true,
    maxAge: session.expires_in,
    path: "/",
    sameSite: "lax",
    secure,
  });
  cookieStore.set(REFRESH_COOKIE, session.refresh_token, {
    httpOnly: true,
    maxAge: 60 * 60 * 24 * 30,
    path: "/",
    sameSite: "lax",
    secure,
  });
}

export async function clearAuthCookies() {
  const cookieStore = await cookies();
  cookieStore.delete(ACCESS_COOKIE);
  cookieStore.delete(REFRESH_COOKIE);
}

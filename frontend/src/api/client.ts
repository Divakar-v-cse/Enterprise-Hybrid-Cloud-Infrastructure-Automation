import type { ApiErrorPayload, LoginResponse, TokenPair, User } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const STORAGE_KEY = "hccp.session.v1";

export interface Session {
  accessToken: string;
  refreshToken: string;
  user: User;
  expiresAt: number;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, payload?: ApiErrorPayload) {
    super(payload?.error.message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = payload?.error.code ?? "unknown";
    this.requestId = payload?.error.request_id ?? "";
    this.details = payload?.error.details ?? {};
  }
}

export function loadSession(): Session | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.accessToken || !parsed.user) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function persistSession(session: Session | null): void {
  if (session) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function sessionFromLogin(payload: LoginResponse): Session {
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    user: payload.user,
    expiresAt: Date.now() + payload.expires_in * 1000,
  };
}

let currentSession: Session | null = loadSession();
let refreshInFlight: Promise<Session | null> | null = null;

export function getSession(): Session | null {
  return currentSession;
}

export function setSession(session: Session | null): void {
  currentSession = session;
  persistSession(session);
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return new ApiError(response.status, payload);
  } catch {
    return new ApiError(response.status);
  }
}

async function refreshSession(): Promise<Session | null> {
  if (!currentSession) return null;
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: currentSession?.refreshToken }),
      });
      if (!response.ok) {
        setSession(null);
        return null;
      }
      const tokens = (await response.json()) as TokenPair;
      const next: Session = {
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        user: currentSession!.user,
        expiresAt: Date.now() + tokens.expires_in * 1000,
      };
      setSession(next);
      return next;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  retryOnUnauthorised?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, retryOnUnauthorised = true } = options;

  // Refresh proactively when the token is within 30 seconds of expiry.
  if (currentSession && currentSession.expiresAt - Date.now() < 30_000 && retryOnUnauthorised) {
    await refreshSession();
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (currentSession) headers.Authorization = `Bearer ${currentSession.accessToken}`;

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  if (response.status === 401 && retryOnUnauthorised) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiRequest<T>(path, { ...options, retryOnUnauthorised: false });
    }
    setSession(null);
    throw new ApiError(401, {
      error: {
        code: "session_expired",
        message: "Your session expired. Sign in again.",
        request_id: "",
        details: {},
      },
    });
  }

  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<Session> {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await parseError(response);
  const payload = (await response.json()) as LoginResponse;
  const session = sessionFromLogin(payload);
  setSession(session);
  return session;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>("/auth/logout", { method: "POST" });
  } finally {
    setSession(null);
  }
}

export async function fetchMe(): Promise<User> {
  const user = await apiRequest<User>("/auth/me");
  if (currentSession) {
    setSession({ ...currentSession, user });
  }
  return user;
}

export function hasPermission(user: User | null, permission: string): boolean {
  return Boolean(user?.permissions.includes(permission));
}

export const API_BASE_URL = BASE_URL;

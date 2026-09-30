const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("oop_token");
}

export function setToken(token: string) {
  localStorage.setItem("oop_token", token);
}

export function clearToken() {
  localStorage.removeItem("oop_token");
}

async function fetchWithColdStartRetry(url: string, options: RequestInit): Promise<Response> {
  // Render free tier can take 30–90s to wake; retry a couple of times.
  const attempts = 3;
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fetch(url, options);
    } catch (err) {
      lastError = err;
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, 2500 * (i + 1)));
      }
    }
  }
  throw lastError;
}

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetchWithColdStartRetry(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach API at ${API_BASE}. Is Render awake? Refresh in ~30s if it was sleeping.`);
  }
  if (!res.ok) {
    const text = await res.text();
    let detail = text || res.statusText;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail || parsed.message || detail;
    } catch {
      /* plain text */
    }
    if (typeof detail === "string" && detail.length > 220) {
      detail = `${detail.slice(0, 220)}…`;
    }
    if (res.status === 401) {
      clearToken();
      throw new Error("Session expired — sign in again.");
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function rawRequest(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetchWithColdStartRetry(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach API at ${API_BASE}. Is Render awake? Refresh in ~30s if it was sleeping.`);
  }
  if (!res.ok) {
    const text = await res.text();
    let detail = text || res.statusText;
    try {
      detail = JSON.parse(text).detail || detail;
    } catch {
      /* plain text */
    }
    if (res.status === 401) {
      clearToken();
      throw new Error("Session expired — sign in again.");
    }
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return res;
}

export async function apiUpload<T = any>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await rawRequest(path, { method: "POST", body: form });
  return res.json();
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const res = await rawRequest(path);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string) {
  const data = await api<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

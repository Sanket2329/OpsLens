export type User = {
  id: string;
  email: string;
  name: string;
  organization_name?: string;
};

const TOKEN_KEY = "opslens_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

async function fetchWithAuth<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Use VITE_API_URL from env or fallback to empty string (relative path)
  const baseUrl = import.meta.env.VITE_API_URL || "";
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
      if (
        typeof window !== "undefined" &&
        window.location.pathname !== "/login"
      ) {
        window.location.href = "/login";
      }
    }
    let message = response.statusText;
    try {
      const errorData = await response.json();
      if (errorData.detail) message = errorData.detail;
    } catch (e) {
      // Ignore JSON parse error if response is not JSON
    }
    throw new Error(message);
  }

  if (response.status === 204) return null as T;
  return response.json();
}

export const baseUrl = import.meta.env.VITE_API_URL || "";

export const api = {
  baseUrl,
  get: <T>(path: string) => fetchWithAuth<T>(path, { method: "GET" }),
  post: <T>(path: string, data?: unknown) =>
    fetchWithAuth<T>(path, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),
  patch: <T>(path: string, data?: unknown) =>
    fetchWithAuth<T>(path, {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
    }),
  delete: <T>(path: string) => fetchWithAuth<T>(path, { method: "DELETE" }),
  del: <T>(path: string) => fetchWithAuth<T>(path, { method: "DELETE" }),
};

// Parallel API client for the admin panel — deliberately separate from src/api.ts's
// `authToken`/request(). Admin sessions are a different identity system end to end
// (db.admin_users, its own JWT), so they get their own token slot; mixing the two
// would risk an admin token leaking onto a consumer request or vice versa.
import Constants from "expo-constants";

const BASE = Constants.expoConfig?.extra?.backendUrl || process.env.EXPO_PUBLIC_BACKEND_URL || "";
export const ADMIN_API = `${BASE}/api`;

let adminToken: string | null = null;
export function setAdminToken(token: string | null) {
  adminToken = token;
}

async function request(path: string, options?: RequestInit) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (adminToken) headers.Authorization = `Bearer ${adminToken}`;
  const { headers: extraHeaders, ...rest } = options || {};
  const res = await fetch(`${ADMIN_API}${path}`, { headers: { ...headers, ...extraHeaders }, ...rest });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || "Não conseguimos completar isso agora. Tente novamente.");
  }
  return data;
}

export const adminApi = {
  get: (path: string) => request(path),
  post: (path: string, body?: object) => request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: (path: string, body?: object) => request(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: (path: string, body?: object) => request(path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined }),
};

export type AdminRole = "OWNER" | "MANAGER" | "SUPPORT" | "MAINTENANCE";

export type AdminMe = {
  id: string; name: string; email: string; role: AdminRole; active: boolean;
  totp_enabled: boolean; last_login_at: string | null; created_at: string;
  permissions: string[]; // ["*"] for full access
};

export function hasPermission(admin: AdminMe | null, key: string): boolean {
  if (!admin) return false;
  return admin.permissions.includes("*") || admin.permissions.includes(key);
}

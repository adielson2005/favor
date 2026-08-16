import Constants from "expo-constants";

const BASE = Constants.expoConfig?.extra?.backendUrl || process.env.EXPO_PUBLIC_BACKEND_URL || "";
export const API = `${BASE}/api`;

// Set once by AuthProvider on boot/login/logout — read here so the plain request() helper
// below can attach it without every call site having to know about auth.
let authToken: string | null = null;
export function setAuthToken(token: string | null) {
  authToken = token;
}

async function request(path: string, options?: RequestInit) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const res = await fetch(`${API}${path}`, { headers, ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || "Não conseguimos completar isso agora. Tente novamente.");
  }
  return data;
}

export const api = {
  get: (path: string) => request(path),
  post: (path: string, body?: object) => request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: (path: string, body: object) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
};

export type Category = { id: string; name: string; icon: string; active: boolean; subcategories: { id: string; name: string }[] };
export type Neighborhood = { id: string; name: string; kind: string; city_id: string };
export type City = { id: string; name: string; state_id: string; active: boolean };
export type StateRef = { id: string; name: string; uf: string; active: boolean };
export type User = {
  id: string; name: string; initials: string; bio?: string; rating: number; rating_count: number;
  jobs_done: number; verified_identity: boolean; verified_email: boolean; verified_phone: boolean;
  level: string; member_since?: string; is_admin?: boolean; neighborhood_id?: string; city_id?: string;
  preference?: "client" | "worker" | "both";
};
export type Order = {
  id: string; title: string; description: string; type: "favor" | "servico";
  category: { id: string; name: string; icon: string }; subcategory?: string;
  category_id: string; subcategory_id?: string; city_id: string; neighborhood_id?: string;
  neighborhood?: string; city?: string; date_label: string; time_label: string; budget: number;
  status: string; status_label: string; client_id: string; worker_id?: string;
  client?: User; worker?: User; proposals_count: number; fields: Record<string, string>;
  accepted_amount?: number; reviewed_by_client: boolean; reviewed_by_worker: boolean; created_at: string;
};
export type Proposal = { id: string; order_id: string; worker_id: string; amount: number; message: string; eta: string; status: string; worker?: User };
export type Message = { id: string; order_id: string; sender_id: string; type: "text" | "system" | "image"; text: string; image_b64?: string; created_at: string };

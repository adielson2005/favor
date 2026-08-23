import Constants from "expo-constants";

const BASE = Constants.expoConfig?.extra?.backendUrl || process.env.EXPO_PUBLIC_BACKEND_URL || "";
export const API = `${BASE}/api`;

// Set once by AuthProvider on boot/login/logout — read here so the plain request() helper
// below can attach it without every call site having to know about auth.
let authToken: string | null = null;
export function setAuthToken(token: string | null) {
  authToken = token;
}

// Screens fire their data-fetching effects on mount/focus regardless of whether
// AuthProvider has finished reading the token from storage yet. On a fresh deep link
// or page reload, that race sent requests with no Authorization header (silent 401,
// swallowed by callers as "empty"). Every request now waits for hydration to finish —
// AuthProvider resolves this exactly once, whether or not a token was found.
let resolveAuthReady: (() => void) | null = null;
export const authReadyPromise = new Promise<void>((resolve) => { resolveAuthReady = resolve; });
export function markAuthReady() {
  resolveAuthReady?.();
}

async function request(path: string, options?: RequestInit) {
  await authReadyPromise;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  // Merge, don't overwrite — {...options} after a plain {headers} would otherwise
  // silently drop the Authorization header whenever a caller passes its own headers.
  const { headers: extraHeaders, ...rest } = options || {};
  const res = await fetch(`${API}${path}`, { headers: { ...headers, ...extraHeaders }, ...rest });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || "Não conseguimos completar isso agora. Tente novamente.");
  }
  return data;
}

export const api = {
  get: (path: string) => request(path),
  post: (path: string, body?: object, headers?: Record<string, string>) =>
    request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined, headers }),
  patch: (path: string, body: object) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: (path: string, body?: object) => request(path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined }),
};

// A fresh key per user action — the backend dedupes on this, so a retried tap or a
// flaky connection can't turn one payment/deposit/withdrawal into two.
export function newIdempotencyKey() {
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export type Category = { id: string; name: string; icon: string; active: boolean; subcategories: { id: string; name: string }[] };
export type Neighborhood = { id: string; name: string; kind: string; city_id: string };
export type City = { id: string; name: string; state_id: string; active: boolean };
export type StateRef = { id: string; name: string; uf: string; active: boolean };
export type User = {
  id: string; name: string; initials: string; bio?: string; rating: number; rating_count: number;
  jobs_done: number; verified_identity: boolean; verified_email: boolean; verified_phone: boolean;
  level: string; member_since?: string; is_admin?: boolean; neighborhood_id?: string; city_id?: string;
  state_id?: string; preference?: "client" | "worker" | "both"; avatar_b64?: string | null;
  // Only present on the account owner's own view (private_user on the backend) —
  // never present when viewing someone else's profile.
  phone?: string | null; email_verified_at?: string | null; phone_verified_at?: string | null;
  account_status?: "PENDING_VERIFICATION" | "ACTIVE" | "SUSPENDED" | "BLOCKED";
  has_password?: boolean;
};

export type LinkedAccount = { provider: "GOOGLE" | "PASSWORD"; created_at: string };
export type Order = {
  id: string; title: string; description: string; type: "favor" | "servico";
  category: { id: string; name: string; icon: string }; subcategory?: string;
  category_id: string; subcategory_id?: string; city_id: string; neighborhood_id?: string;
  neighborhood?: string; city?: string; date_label: string; time_label: string; budget: number;
  status: string; status_label: string; client_id: string; worker_id?: string;
  client?: User; worker?: User; proposals_count: number; fields: Record<string, string>;
  accepted_amount?: number; reviewed_by_client: boolean; reviewed_by_worker: boolean; created_at: string;
  urgent: boolean; recurrence: "none" | "weekly" | "biweekly" | "monthly";
};
export type Proposal = { id: string; order_id: string; worker_id: string; amount: number; message: string; eta: string; status: string; worker?: User };
export type Message = { id: string; order_id: string; sender_id: string; type: "text" | "system" | "image"; text: string; image_b64?: string; created_at: string; warning?: string };

export type Wallet = { available: number; pending: number; processing: number; total_received: number; total_spent: number; currency: string };
export type WalletTransaction = {
  id: string; type: string; amount: number; direction: "IN" | "OUT" | "MOVE"; status: string; bucket: string;
  reference_type: string; reference_id: string; description: string; created_at: string;
};
export type Deposit = { id: string; amount: number; method: string; status: string; created_at: string };
export type BankAccount = {
  id: string; holder_name: string; bank_code: string; agency: string; account_type: string;
  is_primary: boolean; created_at: string; account_number_masked: string; document_masked: string;
};
export type Withdrawal = {
  id: string; amount: number; bank_account_id: string; status: string; risk_level: string;
  reason?: string; created_at: string;
};
export type Payment = {
  id: string; order_id: string; client_id: string; worker_id?: string; gross_amount: number;
  commission_amount: number; worker_net_amount: number; commission_percent: number;
  method: string; status: string; created_at: string;
};
export type Dispute = {
  id: string; order_id: string; target_type: string; reason: string; description: string;
  status: string; resolution: string; created_at: string;
};

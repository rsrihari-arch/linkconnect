const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
}

async function request(path: string, options?: RequestInit) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Request failed");
  }
  return res.json();
}

// Auth
export const signup = (email: string, password: string) =>
  request("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) });

export const verifyOTP = (email: string, code: string) =>
  request("/api/auth/verify", { method: "POST", body: JSON.stringify({ email, code }) });

export const login = (email: string, password: string) =>
  request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });

export const getMe = () => request("/api/auth/me");

// Accounts
export const createAccount = (email: string, password: string) =>
  request("/api/accounts/", { method: "POST", body: JSON.stringify({ email, password }) });

export const getAccounts = () => request("/api/accounts/");

export const loginAccount = (id: number) =>
  request(`/api/accounts/${id}/login`, { method: "POST" });

export const deleteAccount = (id: number) =>
  request(`/api/accounts/${id}`, { method: "DELETE" });

// Campaigns
export const createCampaign = (data: {
  account_id: number;
  name: string;
  daily_limit: number;
  message_template?: string;
}) => request("/api/campaigns/", { method: "POST", body: JSON.stringify(data) });

export const getCampaigns = () => request("/api/campaigns/");

export const getCampaign = (id: number) => request(`/api/campaigns/${id}`);

export const updateCampaign = (id: number, data: Record<string, unknown>) =>
  request(`/api/campaigns/${id}`, { method: "PUT", body: JSON.stringify(data) });

export const startCampaign = (id: number) =>
  request(`/api/campaigns/${id}/start`, { method: "POST" });

export const stopCampaign = (id: number) =>
  request(`/api/campaigns/${id}/stop`, { method: "POST" });

export const deleteCampaign = (id: number) =>
  request(`/api/campaigns/${id}`, { method: "DELETE" });

// Leads
export const uploadLeads = async (campaignId: number, file: File) => {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/campaigns/${campaignId}/leads/upload`, {
    method: "POST",
    body: form,
    headers,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Upload failed");
  }
  return res.json();
};

export const getLeads = (campaignId: number, skip = 0, limit = 100) =>
  request(`/api/campaigns/${campaignId}/leads?skip=${skip}&limit=${limit}`);

export const deleteLead = (campaignId: number, leadId: number) =>
  request(`/api/campaigns/${campaignId}/leads/${leadId}`, { method: "DELETE" });

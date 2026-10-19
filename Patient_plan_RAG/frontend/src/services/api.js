const BASE = "/api";

/** Readable message from an error response (FastAPI `detail` if present). */
export async function errorMessage(res) {
  const body = await res.text().catch(() => "");
  let detail = body;
  try {
    const parsed = JSON.parse(body).detail;
    if (typeof parsed === "string") detail = parsed;
    else if (Array.isArray(parsed))
      detail = parsed.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  } catch {
    // not JSON; keep the raw body
  }
  if (res.status === 429) {
    const wait = res.headers.get("Retry-After");
    if (wait) detail += ` (try again in ${wait}s)`;
  }
  return `${res.status}: ${detail || res.statusText}`;
}

/** Fired on any 401 so the app returns to the sign-in page. */
export const AUTH_REQUIRED_EVENT = "auth-required";

async function check(res) {
  if (res.status === 401) window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

// Session cookies are same-origin (the Vite dev server proxies /api).
async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  return check(res);
}

const post = (path, body) =>
  request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  // Health
  health: () => request("/health"),

  // Session
  me: () => request("/auth/me"),
  login: (username, password) => post("/auth/login", { username, password }),
  logout: () => post("/auth/logout"),
  changePassword: (currentPassword, newPassword) =>
    post("/auth/password", { current_password: currentPassword, new_password: newPassword }),

  // Admin (staff only)
  listUsers: () => request("/admin/users"),
  createUser: (username, role, planIds) =>
    post("/admin/users", { username, role, plan_ids: planIds }),
  updateUser: (username, changes) =>
    request(`/admin/users/${encodeURIComponent(username)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),
  resetPassword: (username) =>
    post(`/admin/users/${encodeURIComponent(username)}/reset-password`),

  // Dashboard
  dashboard: () => request("/dashboard"),

  // Policies
  listPolicies: () => request("/policies"),
  getPolicy: (id) => request(`/policies/${id}`),
  getPolicySummary: (id) => request(`/policies/${id}/summary`),
  getPolicyChunks: (id, page = 1) =>
    request(`/policies/${id}/chunks?page=${page}`),
  uploadPolicy: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/policies/upload`, {
      method: "POST",
      body: form,
    });
    return check(res);
  },

  // Chat
  chat: (question, policyId, conversationId) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        policy_id: policyId || null,
        conversation_id: conversationId || null,
      }),
    }),

  // Coverage
  assessCoverage: (serviceName, serviceCode, documentId) =>
    request("/coverage/assess", {
      method: "POST",
      body: JSON.stringify({
        service_name: serviceName,
        service_code: serviceCode,
        document_id: documentId,
      }),
    }),

  authChecklist: (serviceName, serviceCode, documentId, diagnosisCode) =>
    request("/coverage/auth-checklist", {
      method: "POST",
      body: JSON.stringify({
        service_name: serviceName,
        service_code: serviceCode,
        document_id: documentId,
        diagnosis_code: diagnosisCode || "",
      }),
    }),
};

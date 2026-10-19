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

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export const api = {
  // Health
  health: () => request("/health"),

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
    if (!res.ok) throw new Error(await errorMessage(res));
    return res.json();
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

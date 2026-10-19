const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${body}`);
  }
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
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  },

  // Chat
  chat: (question, policyId) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        policy_id: policyId || null,
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

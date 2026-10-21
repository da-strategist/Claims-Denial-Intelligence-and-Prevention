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
  register: (username, password) => post("/auth/register", { username, password }),
  logout: () => post("/auth/logout"),
  changePassword: (currentPassword, newPassword) =>
    post("/auth/password", { current_password: currentPassword, new_password: newPassword }),

  // Platform admin: hospitals and accounts
  listOrgs: () => request("/admin/orgs"),
  createOrg: (name, adminUsername) => post("/admin/orgs", { name, admin_username: adminUsername }),
  updateOrg: (orgId, changes) =>
    request(`/admin/orgs/${orgId}`, { method: "PATCH", body: JSON.stringify(changes) }),
  listUsers: () => request("/admin/users"),
  updateUser: (username, changes) =>
    request(`/admin/users/${encodeURIComponent(username)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),
  resetPassword: (username) =>
    post(`/admin/users/${encodeURIComponent(username)}/reset-password`),

  // Hospital: staff (hospital admins), patients, shared policies
  listStaff: () => request("/hospital/staff"),
  addStaff: (username, role) => post("/hospital/staff", { username, role }),
  updateStaff: (username, changes) =>
    request(`/hospital/staff/${encodeURIComponent(username)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),
  resetStaffPassword: (username) =>
    post(`/hospital/staff/${encodeURIComponent(username)}/reset-password`),
  listPatients: (includeArchived = false) =>
    request(`/hospital/patients${includeArchived ? "?include_archived=true" : ""}`),
  createPatient: (patient) => post("/hospital/patients", patient),
  getPatient: (id) => request(`/hospital/patients/${id}`),
  updatePatient: (id, changes) =>
    request(`/hospital/patients/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
  deletePatient: (id) => request(`/hospital/patients/${id}`, { method: "DELETE" }),
  listChecklists: (patientId) => request(`/hospital/patients/${patientId}/checklists`),
  saveChecklist: (patientId, checklist) => post(`/hospital/patients/${patientId}/checklists`, checklist),
  updateChecklist: (patientId, id, items) =>
    request(`/hospital/patients/${patientId}/checklists/${id}`, {
      method: "PATCH", body: JSON.stringify({ items }),
    }),
  deleteChecklist: (patientId, id) =>
    request(`/hospital/patients/${patientId}/checklists/${id}`, { method: "DELETE" }),
  hospitalOverview: () => request("/hospital/overview"),
  getHospitalProfile: () => request("/hospital/profile"),
  updateHospitalProfile: (profile) =>
    request("/hospital/profile", { method: "PATCH", body: JSON.stringify(profile) }),
  accessLog: () => request("/hospital/access-log"),
  listShared: () => request("/hospital/shared"),
  fileShared: (shareId, patientId) =>
    request(`/hospital/shared/${shareId}`, {
      method: "PATCH",
      body: JSON.stringify({ patient_id: patientId || null }),
    }),

  // Individuals: my account
  overview: () => request("/me/overview"),
  updateProfile: (fullName, phone) => request("/me/profile", {
    method: "PATCH", body: JSON.stringify({ full_name: fullName, phone }),
  }),
  listProviders: () => request("/me/providers"),
  addProvider: (provider) => post("/me/providers", provider),
  updateProvider: (id, provider) => request(`/me/providers/${id}`, {
    method: "PATCH", body: JSON.stringify(provider),
  }),
  deleteProvider: (id) => request(`/me/providers/${id}`, { method: "DELETE" }),
  sharingOverview: () => request("/me/sharing"),
  removeHospitalAccess: (orgId) => request(`/me/sharing/${orgId}`, { method: "DELETE" }),
  exportMyData: () => request("/me/export"),
  signOutEverywhere: () => post("/me/sign-out-everywhere"),
  deleteAccount: (confirmEmail) => request("/me", {
    method: "DELETE", body: JSON.stringify({ confirm_email: confirmEmail }),
  }),

  // Individuals: share a policy with a hospital
  hospitalDirectory: () => request("/shares/hospitals"),
  myShares: () => request("/shares"),
  share: (documentId, orgId) => post("/shares", { document_id: documentId, org_id: orgId }),
  unshare: (shareId) => request(`/shares/${shareId}`, { method: "DELETE" }),

  // Dashboard
  dashboard: () => request("/dashboard"),

  // Policies
  listPolicies: () => request("/policies"),
  getPolicy: (id) => request(`/policies/${id}`),
  getPolicySummary: (id) => request(`/policies/${id}/summary`),
  renamePolicy: (id, displayName) => request(`/policies/${id}`, {
    method: "PATCH", body: JSON.stringify({ display_name: displayName }),
  }),
  deletePolicy: (id) => request(`/policies/${id}`, { method: "DELETE" }),
  getPolicyChunks: (id, page = 1) =>
    request(`/policies/${id}/chunks?page=${page}`),
  uploadPolicy: async (file, patientId) => {
    const form = new FormData();
    form.append("file", file);
    if (patientId) form.append("patient_id", patientId);
    const res = await fetch(`${BASE}/policies/upload`, {
      method: "POST",
      body: form,
    });
    return check(res);
  },

  // Chat
  chat: (question, policyId, conversationId, patientId) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        policy_id: policyId || null,
        conversation_id: conversationId || null,
        patient_id: patientId || null,
      }),
    }),

  chatSuggestions: (policyId, patientId) => {
    const params = new URLSearchParams();
    if (policyId) params.set("policy_id", policyId);
    if (patientId) params.set("patient_id", patientId);
    return request(`/chat/suggestions?${params}`);
  },

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

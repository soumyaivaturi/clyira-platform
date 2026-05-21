import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("clyira_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status;
    if ((status === 401 || status === 403) && typeof window !== "undefined") {
      localStorage.removeItem("clyira_token");
      document.cookie = "clyira_token=; path=/; max-age=0";
      window.location.href = "/auth/login";
    }
    return Promise.reject(error);
  }
);

export default api;

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  register: (email: string, password: string, full_name: string, company_name: string) =>
    api.post("/auth/register", { email, password, full_name, company_name }),
  me: () => api.get("/auth/me"),
};

// ── Companies ─────────────────────────────────────────────────────────────────
export const companiesApi = {
  onboard: (data: { sub_sectors: string[]; agencies: string[]; markets: string[]; certifications?: string[] }) =>
    api.post("/companies/onboard", data),
  me: () => api.get("/companies/me"),
};

// ── Documents ─────────────────────────────────────────────────────────────────
export const documentsApi = {
  list: (params?: { document_category?: string; department_owner?: string; status_filter?: string }) =>
    api.get("/documents", { params }),
  get: (id: string) => api.get(`/documents/${id}`),
  upload: (formData: FormData, onProgress?: (pct: number) => void) =>
    api.post("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
      },
    }),
  create: (formData: FormData) =>
    api.post("/documents/create", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  addReferences: (documentId: string, formData: FormData) =>
    api.post(`/documents/${documentId}/references`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
};

// ── Assessments ───────────────────────────────────────────────────────────────
export const assessmentsApi = {
  run: (documentId: string, includeReferences = true) =>
    api.post("/assessments/run", { document_id: documentId, include_references: includeReferences }),
  get: (id: string) => api.get(`/assessments/${id}`),
  getFindings: (id: string, params?: { severity?: string; level?: string }) =>
    api.get(`/assessments/${id}/findings`, { params }),
  respondToFinding: (assessmentId: string, findingId: string, response_text: string, finding_status: string) =>
    api.patch(`/assessments/${assessmentId}/findings/${findingId}`, null, {
      params: { response_text, finding_status },
    }),
  getReport: (id: string) => api.get(`/assessments/${id}/report`),
};

// ── Readiness ─────────────────────────────────────────────────────────────────
export const readinessApi = {
  dashboard: () => api.get("/readiness/dashboard"),
  scores: (scope?: string) => api.get("/readiness/scores", { params: { scope } }),
  gaps: (department?: string) => api.get("/readiness/gaps", { params: { department } }),
  mockInspection: () => api.post("/readiness/mock-inspection"),
  enforcementAlerts: () => api.get("/readiness/enforcement-alerts"),
};

// ── Inspections ───────────────────────────────────────────────────────────────
export const inspectionsApi = {
  list: (status?: string) => api.get("/inspections", { params: status ? { insp_status: status } : {} }),
  create: (data: { title: string; agency?: string; inspection_type?: string; start_date?: string }) =>
    api.post("/inspections", data),
  get: (id: string) => api.get(`/inspections/${id}`),
  activate: (id: string) => api.patch(`/inspections/${id}/activate`),
  close: (id: string) => api.post(`/inspections/${id}/close`),
  createRequest: (id: string, data: { request_text: string; criticality?: string; category?: string }) =>
    api.post(`/inspections/${id}/requests`, data),
  listRequests: (id: string, status?: string) =>
    api.get(`/inspections/${id}/requests`, { params: status ? { req_status: status } : {} }),
  updateRequest: (id: string, reqId: string, data: { req_status?: string; response_text?: string }) =>
    api.patch(`/inspections/${id}/requests/${reqId}`, null, { params: data }),
  addScribeEntry: (id: string, data: { content: string; entry_type?: string; tags?: string[] }) =>
    api.post(`/inspections/${id}/scribe`, data),
  getLog: (id: string) => api.get(`/inspections/${id}/log`),
};

import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 60000,
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
    const url = error.config?.url ?? "";
    // Don't redirect on 401 from the login endpoint itself — let the form's catch handle it
    const isAuthAttempt = url.includes("/auth/login") || url.includes("/auth/register");
    if ((status === 401 || status === 403) && typeof window !== "undefined" && !isAuthAttempt) {
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
  updateProfile: (data: { full_name?: string; department?: string }) =>
    api.patch("/auth/me", data),
  changePassword: (current_password: string, new_password: string) =>
    api.patch("/auth/password", { current_password, new_password }),
  acceptTerms: () => api.post("/auth/accept-terms"),
};

// ── Companies ─────────────────────────────────────────────────────────────────
export const companiesApi = {
  onboard: (data: { sub_sectors: string[]; agencies: string[]; markets: string[]; certifications?: string[] }) =>
    api.post("/companies/onboard", data),
  me: () => api.get("/companies/me"),
  update: (data: { sub_sectors?: string[]; agencies?: string[]; markets?: string[]; certifications?: string[]; name?: string }) =>
    api.patch("/companies/me", data),
};

// ── Documents ─────────────────────────────────────────────────────────────────
export const documentsApi = {
  search: (q: string) => api.get("/documents/search", { params: { q } }),
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
  run: (documentId: string, includeReferences = true, regulatoryFrameworks?: string[]) =>
    api.post("/assessments/run", {
      document_id: documentId,
      include_references: includeReferences,
      ...(regulatoryFrameworks ? { regulatory_frameworks: regulatoryFrameworks } : {}),
    }, { timeout: 600000 }),
  get: (id: string) => api.get(`/assessments/${id}`),
  getFindings: (id: string, params?: { severity?: string; level?: string }) =>
    api.get(`/assessments/${id}/findings`, { params }),
  actionFinding: (
    assessmentId: string,
    findingId: string,
    finding_status: string,
    response_text?: string,
    dispute_reason?: string,
  ) =>
    api.patch(`/assessments/${assessmentId}/findings/${findingId}`, {
      finding_status,
      response_text: response_text || "",
      dispute_reason: dispute_reason || "",
    }),
  getLiveScore: (id: string) => api.get(`/assessments/${id}/live-score`),
  getReport: (id: string) => api.get(`/assessments/${id}/report`),
  recent: (limit = 8) => api.get("/assessments/recent", { params: { limit } }),
  bulkRun: (documentIds?: string[], includeReferences = true) =>
    api.post("/assessments/bulk-run", { document_ids: documentIds || null, include_references: includeReferences }),
  exportDocx: (id: string) =>
    api.get(`/assessments/${id}/export/docx`, { responseType: "blob", timeout: 60000 }),
  exportCsv: (id: string) =>
    api.get(`/assessments/${id}/export/csv`, { responseType: "blob", timeout: 30000 }),
  historyByDocument: (documentId: string) =>
    api.get(`/assessments/by-document/${documentId}`),
};

// ── Assistant ─────────────────────────────────────────────────────────────────
export const assistantApi = {
  draftFix: (document_id: string, finding_id: string, context_hint?: string) =>
    api.post("/assistant/author", { document_id, finding_id, context_hint: context_hint || "" }),
  ask: (document_id: string, question: string, assessment_id?: string) =>
    api.post("/assistant/qa", { document_id, question, assessment_id }),
};

// ── Audit Trail ───────────────────────────────────────────────────────────────
export const auditApi = {
  getLog: (params?: { event_type?: string; resource_type?: string; limit?: number; offset?: number }) =>
    api.get("/audit/log", { params }),
  getResourceLog: (resourceId: string) => api.get(`/audit/log/${resourceId}`),
};

// ── Document History ──────────────────────────────────────────────────────────
// (extends documentsApi — separate export to avoid circular ref)
export const documentHistoryApi = {
  getAssessmentHistory: (documentId: string) =>
    api.get(`/documents/${documentId}/assessment-history`),
};

// ── Readiness ─────────────────────────────────────────────────────────────────
export const readinessApi = {
  dashboard: () => api.get("/readiness/dashboard"),
  scores: (scope?: string) => api.get("/readiness/scores", { params: { scope } }),
  gaps: (department?: string) => api.get("/readiness/gaps", { params: { department } }),
  mockInspection: () => api.post("/readiness/mock-inspection"),
  enforcementAlerts: () => api.get("/readiness/enforcement-alerts"),
};

// ── Notifications ─────────────────────────────────────────────────────────────
export const notificationsApi = {
  alerts: () => api.get("/notifications/alerts"),
  testEmail: () => api.post("/notifications/test-email"),
};

// ── API Keys ──────────────────────────────────────────────────────────────────
export const apiKeysApi = {
  list: () => api.get("/api-keys"),
  create: (name: string, integration_type?: string) =>
    api.post("/api-keys", { name, integration_type }),
  revoke: (id: string) => api.delete(`/api-keys/${id}`),
};

// ── Evidence Fabric ───────────────────────────────────────────────────────────
export const evidenceApi = {
  upload: (formData: FormData) =>
    api.post("/evidence/import", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  mapColumns: (importId: string, entity_type: string, column_mapping: Record<string, string>) =>
    api.post(`/evidence/import/${importId}/map`, { entity_type, column_mapping }),
  ingest: (importId: string, rows: Record<string, string>[]) =>
    api.post(`/evidence/ingest/${importId}`, rows),
  listImports: () => api.get("/evidence/imports"),
  listObjects: (importId: string, limit = 100, offset = 0) =>
    api.get(`/evidence/imports/${importId}/objects`, { params: { limit, offset } }),
  deleteImport: (importId: string) => api.delete(`/evidence/imports/${importId}`),
};

// ── Electronic Signatures ─────────────────────────────────────────────────────
export const signaturesApi = {
  list: (documentId: string) => api.get(`/documents/${documentId}/signatures`),
  sign: (documentId: string, meaning: "authored" | "reviewed" | "approved", password: string) =>
    api.post(`/documents/${documentId}/signatures`, { meaning, password }),
};

// ── Inspections ───────────────────────────────────────────────────────────────
export const inspectionsApi = {
  list: (status?: string) => api.get("/inspections", { params: status ? { insp_status: status } : {} }),
  create: (data: { title: string; agency?: string; inspection_type?: string; start_date?: string }) =>
    api.post("/inspections", data),
  get: (id: string) => api.get(`/inspections/${id}`),
  activate: (id: string) => api.patch(`/inspections/${id}/activate`),
  close: (id: string) => api.post(`/inspections/${id}/close`),
  updatePhase: (id: string, phase: string) => api.patch(`/inspections/${id}/phase`, { phase }),

  // Requests
  createRequest: (id: string, data: {
    request_text: string; criticality?: string; category?: string;
    inspector_name?: string; inspector_department?: string; location?: string;
    assigned_to?: string;
  }) => api.post(`/inspections/${id}/requests`, data),
  listRequests: (id: string, status?: string) =>
    api.get(`/inspections/${id}/requests`, { params: status ? { req_status: status } : {} }),
  updateRequest: (id: string, reqId: string, data: {
    req_status?: string; response_text?: string; fulfillment_progress?: number; assigned_to?: string;
  }) => api.patch(`/inspections/${id}/requests/${reqId}`, null, { params: data }),
  getOverdueRequests: (id: string) => api.get(`/inspections/${id}/overdue-requests`),
  analyzeRequest: (inspectionId: string, requestId: string) =>
    api.post(`/inspections/${inspectionId}/requests/${requestId}/analyze`, {}, { timeout: 60000 }),

  // Request documents
  addRequestDocument: (id: string, reqId: string, data: { filename: string; file_path?: string; file_size_bytes?: number }) =>
    api.post(`/inspections/${id}/requests/${reqId}/documents`, data),
  listRequestDocuments: (id: string, reqId: string) =>
    api.get(`/inspections/${id}/requests/${reqId}/documents`),
  updateRequestDocument: (id: string, reqId: string, docId: string, status: string) =>
    api.patch(`/inspections/${id}/requests/${reqId}/documents/${docId}`, { status }),

  // Comments
  addComment: (id: string, reqId: string, content: string) =>
    api.post(`/inspections/${id}/requests/${reqId}/comments`, { content }),
  listComments: (id: string, reqId: string) =>
    api.get(`/inspections/${id}/requests/${reqId}/comments`),

  // Commitments
  createCommitment: (id: string, data: {
    commitment_text: string; committed_to?: string; deadline_at?: string;
  }) => api.post(`/inspections/${id}/commitments`, data),
  listCommitments: (id: string) => api.get(`/inspections/${id}/commitments`),
  updateCommitment: (id: string, cId: string, data: { status?: string; delivery_note?: string }) =>
    api.patch(`/inspections/${id}/commitments/${cId}`, data),

  // 483 Observations
  createObservation: (id: string, data: {
    observation_text: string; system_area?: string; cfr_citations?: string[];
    response_deadline?: string;
  }) => api.post(`/inspections/${id}/observations`, data),
  listObservations: (id: string) => api.get(`/inspections/${id}/observations`),
  draftObservationResponse: (id: string, obsId: string) =>
    api.post(`/inspections/${id}/observations/${obsId}/draft-response`, {}, { timeout: 90000 }),

  // Delivery log
  createDelivery: (id: string, data: {
    document_titles: string[]; delivered_to: string; delivery_method?: string;
    request_id?: string;
  }) => api.post(`/inspections/${id}/deliveries`, data),
  listDeliveries: (id: string) => api.get(`/inspections/${id}/deliveries`),

  // Inspector profiles
  addInspector: (id: string, data: {
    name: string; fda_district?: string; role?: string; focus_areas?: string[];
    email?: string; notes?: string;
  }) => api.post(`/inspections/${id}/inspectors`, data),
  listInspectors: (id: string) => api.get(`/inspections/${id}/inspectors`),
  deleteInspector: (id: string, inspId: string) => api.delete(`/inspections/${id}/inspectors/${inspId}`),

  // Intelligence
  runRiskAnalysis: (id: string) =>
    api.post(`/inspections/${id}/risk-analysis`, {}, { timeout: 90000 }),
  generateClosingSummary: (id: string) =>
    api.post(`/inspections/${id}/closing-summary`, {}, { timeout: 90000 }),
  generateCoverLetter: (id: string) =>
    api.post(`/inspections/${id}/cover-letter`, {}, { timeout: 90000 }),
  finalizeInspection: (id: string) =>
    api.post(`/inspections/${id}/finalize`),

  // Scribe + log
  addScribeEntry: (id: string, data: { content: string; entry_type?: string; tags?: string[] }) =>
    api.post(`/inspections/${id}/scribe`, data),
  getLog: (id: string) => api.get(`/inspections/${id}/log`),

  // Inspector briefing
  briefInspector: (inspectionId: string, inspectorId: string) =>
    api.post(`/inspections/${inspectionId}/inspectors/${inspectorId}/brief`, {}, { timeout: 90000 }),

  // Setup
  updateSetup: (id: string, data: Partial<{
    title: string; agency: string; inspection_type: string; start_date: string; end_date: string;
    sector: string; products_in_scope: string[]; departments_in_scope: string[];
    regulatory_frameworks: string[]; site_name: string; mode: string;
    inspection_scope: string[]; team_assignments: Record<string, string>;
    default_sla_settings: Record<string, number>;
  }>) => api.patch(`/inspections/${id}/setup`, data),

  // QA Release Gate
  qaActionRequest: (id: string, reqId: string, action: string, notes?: string) =>
    api.post(`/inspections/${id}/requests/${reqId}/qa`, { action, notes }),

  // Evidence packages
  listPackages: (id: string, requestId?: string) =>
    api.get(`/inspections/${id}/packages`, { params: requestId ? { request_id: requestId } : {} }),
  createPackage: (id: string, data: { title: string; description?: string; request_id?: string; legal_review_required?: boolean }) =>
    api.post(`/inspections/${id}/packages`, data),
  updatePackage: (id: string, pkgId: string, data: Partial<{ title: string; description: string; qa_notes: string; release_notes: string }>) =>
    api.patch(`/inspections/${id}/packages/${pkgId}`, data),
  addDocumentToPackage: (id: string, pkgId: string, params: { filename: string; document_id?: string; version?: string; approval_status?: string }) =>
    api.post(`/inspections/${id}/packages/${pkgId}/documents`, null, { params }),
  removeDocumentFromPackage: (id: string, pkgId: string, docId: string) =>
    api.delete(`/inspections/${id}/packages/${pkgId}/documents/${docId}`),
  submitPackageQA: (id: string, pkgId: string) =>
    api.post(`/inspections/${id}/packages/${pkgId}/submit-qa`),
  qaActionPackage: (id: string, pkgId: string, action: string, notes?: string, qa_checks?: Record<string, boolean>) =>
    api.post(`/inspections/${id}/packages/${pkgId}/qa`, { action, notes, qa_checks }),

  // SME Coach
  listSMEs: (id: string) => api.get(`/inspections/${id}/smes`),
  createSME: (id: string, data: { name: string; title?: string; department?: string; email?: string; topics?: string[] }) =>
    api.post(`/inspections/${id}/smes`, data),
  updateSME: (id: string, smeId: string, data: Partial<{
    name: string; title: string; department: string; room: string; availability: string;
    topics: string[]; prep_status: string; approved_talking_points: string[];
    do_not_volunteer: string[]; do_not_speculate: string[]; escalation_triggers: string[];
    likely_questions: {question: string; recommended_answer: string}[];
    known_weak_areas: string; notes: string;
  }>) => api.patch(`/inspections/${id}/smes/${smeId}`, data),
  deleteSME: (id: string, smeId: string) => api.delete(`/inspections/${id}/smes/${smeId}`),
  qaClearSME: (id: string, smeId: string) => api.post(`/inspections/${id}/smes/${smeId}/qa-clear`),
  aiCoachSME: (id: string, smeId: string) =>
    api.post(`/inspections/${id}/smes/${smeId}/coach`, {}, { timeout: 90000 }),
  logSMECall: (id: string, smeId: string, reason: string, notes?: string) =>
    api.post(`/inspections/${id}/smes/${smeId}/call-log`, null, { params: { reason, notes: notes || "" } }),

  // CAPAs
  listCAPAs: (id: string, status?: string) =>
    api.get(`/inspections/${id}/capas`, { params: status ? { status_filter: status } : {} }),
  createCAPA: (id: string, data: {
    title: string; description?: string; action_type?: string; owner_name?: string;
    department?: string; due_date?: string; criticality?: string;
    linked_observation_id?: string; linked_request_id?: string;
    effectiveness_check_required?: boolean;
  }) => api.post(`/inspections/${id}/capas`, data),
  updateCAPA: (id: string, capaId: string, data: Partial<{
    title: string; description: string; owner_name: string; department: string;
    due_date: string; criticality: string; status: string; completion_notes: string;
    effectiveness_check_notes: string; lesson_learned: string; qms_record_id: string;
  }>) => api.patch(`/inspections/${id}/capas/${capaId}`, data),
  deleteCAPA: (id: string, capaId: string) => api.delete(`/inspections/${id}/capas/${capaId}`),

  // Metrics + briefing
  getMetrics: (id: string) => api.get(`/inspections/${id}/metrics`),
  generateDailyBrief: (id: string) =>
    api.post(`/inspections/${id}/daily-brief`, {}, { timeout: 90000 }),

  // Post-inspection
  updatePostInspection: (id: string, data: { outcome?: string; final_483_count?: number; post_inspection_notes?: string; lessons_learned?: string[] }) =>
    api.patch(`/inspections/${id}/post-inspection`, data),
  getPostInspectionSummary: (id: string) =>
    api.get(`/inspections/${id}/post-inspection-summary`),

  // Potential findings tracker
  listPotentialFindings: (id: string, status?: string) =>
    api.get(`/inspections/${id}/potential-findings`, { params: status ? { status_filter: status } : {} }),
  createPotentialFinding: (id: string, data: {
    title: string; inspector_framing?: string; system_area?: string;
    cfr_citations?: string[]; confidence?: string; defense_summary?: string;
    linked_request_ids?: string[];
  }) => api.post(`/inspections/${id}/potential-findings`, data),
  updatePotentialFinding: (id: string, fid: string, data: Partial<{
    title: string; inspector_framing: string; system_area: string;
    cfr_citations: string[]; confidence: string; status: string;
    defense_summary: string; linked_request_ids: string[];
  }>) => api.patch(`/inspections/${id}/potential-findings/${fid}`, data),
  qaPotentialFinding: (id: string, fid: string) =>
    api.post(`/inspections/${id}/potential-findings/${fid}/qa-review`),
  deletePotentialFinding: (id: string, fid: string) =>
    api.delete(`/inspections/${id}/potential-findings/${fid}`),
  aiScanFindings: (id: string) =>
    api.post(`/inspections/${id}/potential-findings/ai-scan`, {}, { timeout: 90000 }),

  // Backroom chat
  sendMessage: (id: string, data: {
    content: string; room?: string; message_type?: string;
    linked_request_id?: string; linked_commitment_id?: string;
  }) => api.post(`/inspections/${id}/chat`, data),
  listMessages: (id: string, room?: string) =>
    api.get(`/inspections/${id}/chat`, { params: room ? { room } : {} }),
  convertMessageToRequest: (id: string, messageId: string) =>
    api.post(`/inspections/${id}/chat/${messageId}/convert`),

  // Team members
  listTeam: (id: string, room?: string) => api.get(`/inspections/${id}/team`, { params: room ? { room } : {} }),
  addTeamMember: (id: string, data: {
    name: string; room: string; role?: string; email?: string; phone?: string;
    title?: string; company?: string; functional_area?: string;
    topics?: string[]; fda_district?: string; focus_areas?: string[];
    approved_talking_points?: string[]; do_not_volunteer?: string[];
    known_weak_areas?: string; notes?: string; availability?: string;
  }) => api.post(`/inspections/${id}/team`, data),
  updateTeamMember: (id: string, memberId: string, data: Record<string, any>) =>
    api.patch(`/inspections/${id}/team/${memberId}`, data),
  deleteTeamMember: (id: string, memberId: string) => api.delete(`/inspections/${id}/team/${memberId}`),
  notifyTeam: (id: string, event_type: string, inspector_name?: string) =>
    api.post(`/inspections/${id}/notify-team`, { event_type, inspector_name }),

  // §9 Binder
  listBinder: (id: string) => api.get(`/inspections/${id}/binder`),
  seedBinder: (id: string) => api.post(`/inspections/${id}/binder/seed`),
  addBinderDoc: (id: string, data: { title: string; category?: string; filename?: string; version?: string; required?: boolean; notes?: string }) =>
    api.post(`/inspections/${id}/binder`, data),
  updateBinderDoc: (id: string, docId: string, data: Partial<{ title: string; status: string; filename: string; version: string; notes: string; delivered_to: string }>) =>
    api.patch(`/inspections/${id}/binder/${docId}`, data),
  deleteBinderDoc: (id: string, docId: string) => api.delete(`/inspections/${id}/binder/${docId}`),

  // §15 Enhanced observations
  updateObservation: (id: string, obsId: string, data: Partial<{
    obs_status: string; draft_response: string; legal_review_required: boolean;
    verbal_concern: boolean; verbal_concern_notes: string;
    root_cause_hypothesis: string; factual_accuracy_confirmed: boolean;
  }>) => api.patch(`/inspections/${id}/observations/${obsId}`, null, { params: data }),

  // §19 Lessons Learned
  getLessons: (id: string) => api.get(`/inspections/${id}/lessons`),
  addLesson: (id: string, lesson: string) => api.post(`/inspections/${id}/lessons`, { lesson }),
  deleteLesson: (id: string, index: number) => api.delete(`/inspections/${id}/lessons/${index}`),

  // §21 Safe Mode
  toggleSafeMode: (id: string) => api.post(`/inspections/${id}/safe-mode`),

  // §22 Alerts
  getAlerts: (id: string) => api.get(`/inspections/${id}/alerts`),

  // §23 Exports
  exportRequestsCsv: (id: string) => api.get(`/inspections/${id}/export/requests-csv`, { responseType: "blob" }),
  exportScribeTxt: (id: string) => api.get(`/inspections/${id}/export/scribe-txt`, { responseType: "blob" }),
  exportCommitmentsCsv: (id: string) => api.get(`/inspections/${id}/export/commitments-csv`, { responseType: "blob" }),
};

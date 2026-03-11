import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL + '/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getMe: () => api.get('/auth/me'),
};

// Company API
export const companyAPI = {
  get: () => api.get('/company'),
  create: (data) => api.post('/company', data),
  update: (data) => api.put('/company', data),
  generateValues: (narrative) => {
    const formData = new FormData();
    formData.append('narrative', narrative);
    return api.post('/company/generate-values', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// Jobs API
export const jobsAPI = {
  list: () => api.get('/jobs'),
  get: (id) => api.get(`/jobs/${id}`),
  create: (data) => api.post('/jobs', data),
  update: (id, data) => api.put(`/jobs/${id}`, data),
  delete: (id) => api.delete(`/jobs/${id}`),
  generateDescription: (title, context = '', mode = 'generate') => {
    const formData = new FormData();
    formData.append('title', title);
    formData.append('context', context);
    formData.append('mode', mode);
    return api.post('/jobs/generate-description', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  generatePlaybook: (id) => api.post(`/jobs/${id}/generate-playbook`),
};

// Candidates API
export const candidatesAPI = {
  list: () => api.get('/candidates'),
  search: (query = '', page = 1, limit = 20) =>
    api.get('/candidates/search', { params: { q: query, page, limit } }),
  get: (id) => api.get(`/candidates/${id}`),
  create: (data) => api.post('/candidates', data),
  update: (id, data) => api.put(`/candidates/${id}`, data),
  delete: (id) => api.delete(`/candidates/${id}`),
  reparse: (id) => api.post(`/candidates/${id}/reparse`),
  checkDuplicates: (emails) => api.post('/candidates/check-duplicates', emails),
  // Updated: uploadCV now supports duplicate detection and merge
  uploadCV: (file, candidateId = null, forceCreate = false, mergeTargetId = null) => {
    const formData = new FormData();
    formData.append('file', file);
    if (candidateId) {
      formData.append('candidate_id', candidateId);
    }
    if (forceCreate) {
      formData.append('force_create', 'true');
    }
    if (mergeTargetId) {
      formData.append('merge_target_id', mergeTargetId);
    }
    return api.post('/candidates/upload-cv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Updated: uploadEvidence now supports auto type detection
  uploadEvidence: (candidateId, file, evidenceType = 'auto') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('evidence_type', evidenceType);
    return api.post(`/candidates/${candidateId}/upload-evidence`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Delete specific evidence from candidate
  deleteEvidence: (candidateId, evidenceIndex) =>
    api.delete(`/candidates/${candidateId}/evidence/${evidenceIndex}`),
  // Replace candidate (delete old, create new)
  replace: (oldCandidateId, newName, newEmail, newPhone, newEvidence) =>
    api.post('/candidates/replace', {
      old_candidate_id: oldCandidateId,
      new_name: newName,
      new_email: newEmail,
      new_phone: newPhone,
      new_evidence: newEvidence
    }),
  // Enhanced duplicate detection
  detectDuplicates: (data) => api.post('/candidates/detect-duplicates', data),
  // Merge candidates
  merge: (sourceCandidateId, targetCandidateId) =>
    api.post('/candidates/merge', {
      source_candidate_id: sourceCandidateId,
      target_candidate_id: targetCandidateId
    }),
  // Get merge logs
  getMergeLogs: (limit = 50) =>
    api.get('/candidates/merge-logs', { params: { limit } }),
  // Upload ZIP file
  uploadZip: (file, forceCreate = false) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('force_create', forceCreate);
    return api.post('/candidates/upload-zip', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // ==================== TALENT TAGGING ====================
  // Extract tags from candidate evidence using AI
  extractTags: (candidateId) =>
    api.post(`/candidates/${candidateId}/extract-tags`),
  // Get candidate tags
  getTags: (candidateId) =>
    api.get(`/candidates/${candidateId}/tags`),
  // Add manual tag
  addTag: (candidateId, tagValue, layer) =>
    api.post(`/candidates/${candidateId}/tags`, { tag_value: tagValue, layer }),
  // Delete tag
  deleteTag: (candidateId, tagValue, layer) =>
    api.delete(`/candidates/${candidateId}/tags/${encodeURIComponent(tagValue)}`, { params: { layer } }),
  // Get tag library
  getTagLibrary: () => api.get('/tags/library'),
};

// Analysis API
export const analysisAPI = {
  runBatch: (jobId, candidateIds) =>
    api.post('/analysis/run', { job_id: jobId, candidate_ids: candidateIds }),
  runStream: (jobId, candidateIds) => {
    const token = localStorage.getItem('token');
    return fetch(`${API_URL}/analysis/run-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ job_id: jobId, candidate_ids: candidateIds }),
    });
  },
  getForJob: (jobId, minScore = null) => {
    const params = minScore ? { min_score: minScore } : {};
    return api.get(`/analysis/job/${jobId}`, { params });
  },
  get: (id) => api.get(`/analysis/${id}`),
  delete: (id) => api.delete(`/analysis/${id}`),
  bulkDelete: (ids) => api.post('/analysis/bulk-delete', { ids }),
  generatePDF: (data) => api.post('/analysis/generate-pdf', data, { responseType: 'blob' }),
};

// Settings API
export const settingsAPI = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
};

// Admin Settings API
export const adminSettingsAPI = {
  get: () => api.get('/admin-settings'),
  update: (data) => api.put('/admin-settings', data),
  resetPrompt: (promptKey) => api.post(`/admin-settings/reset/${promptKey}`),
};

// Dashboard API
export const dashboardAPI = {
  getStats: () => api.get('/dashboard/stats'),
  getRecentActivity: () => api.get('/dashboard/recent-activity'),
};

export default api;

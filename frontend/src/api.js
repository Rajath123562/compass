/**
 * COMPASS Frontend API Client
 * Real HTTP communication with FastAPI backend.
 */

const API_BASE = 'http://127.0.0.1:8000';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  const contentType = res.headers?.get ? (res.headers.get('content-type') || '') : 'application/json';
  let data = null;
  if (contentType.includes('application/json')) {
    data = await res.json();
  } else {
    data = await res.text();
  }

  if (!res.ok) {
    const errorMsg = data?.detail || (Array.isArray(data?.errors) ? data.errors.join(', ') : 'API request failed');
    const err = new Error(errorMsg);
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const api = {
  // Health & System
  getHealth: () => request('/api/health'),
  getSystemInfo: () => request('/api/system/info'),
  getActiveWindow: () => request('/api/system/active_window'),
  getDiagnostics: () => request('/api/system/diagnostics'),

  // Tasks
  createTask: (goal, metadata = {}) =>
    request('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ goal, metadata }),
    }),

  listTasks: (limit = 20) => request(`/api/tasks?limit=${limit}`),

  getTask: (taskId) => request(`/api/tasks/${taskId}`),

  transitionTask: (taskId, newState, reason = '') =>
    request(`/api/tasks/${taskId}/transition`, {
      method: 'POST',
      body: JSON.stringify({ new_state: newState, reason }),
    }),

  stopTask: (taskId) =>
    request(`/api/tasks/${taskId}/stop`, {
      method: 'POST',
    }),

  deleteTask: (taskId) =>
    request(`/api/tasks/${taskId}`, {
      method: 'DELETE',
    }),

  clearTasks: () =>
    request('/api/tasks', {
      method: 'DELETE',
    }),

  // Phase 3 & Gemini: Planner & AI
  getAIStatus: () => request('/api/ai/status'),
  getAIModels: (freeOnly = true) => request(`/api/ai/models?free_only=${freeOnly}`),
  getCircuitBreaker: () => request('/api/ai/circuit_breaker'),
  resetCircuitBreaker: () => request('/api/ai/circuit_breaker/reset', { method: 'POST' }),
  getGeminiStatus: () => request('/api/ai/gemini_status'),
  setGeminiConfig: (apiKey) =>
    request('/api/ai/gemini_config', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey }),
    }),
  getClaudeStatus: () => request('/api/ai/claude_status'),
  setClaudeConfig: (apiKey) =>
    request('/api/ai/claude_config', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey }),
    }),
  generatePlan: (goal, taskId = null) =>
    request('/api/planner/plan', {
      method: 'POST',
      body: JSON.stringify({ goal, task_id: taskId }),
    }),
  runTask: (taskId) =>
    request(`/api/tasks/${taskId}/run`, {
      method: 'POST',
    }),
  getTaskPlan: (taskId) => request(`/api/tasks/${taskId}/plan`),
  getPendingApproval: (taskId) => request(`/api/planner/pending-approval/${taskId}`),
  confirmAction: (taskId, decisionId, approved, reason = '') =>
    request(`/api/planner/confirm/${taskId}`, {
      method: 'POST',
      body: JSON.stringify({ decision_id: decisionId, approved, reason }),
    }),
    
  // Phase 7: Interactive Guide Chat & Undo
  sendChatMessage: (message) =>
    request(`/api/tasks/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  undoChatMessage: () =>
    request(`/api/tasks/undo`, {
      method: 'POST',
    }),

  // Phase 8: Autonomous Workflows (DAG)
  listWorkflows: (limit = 50, status = '') =>
    request(`/api/workflows?limit=${limit}${status ? `&status=${status}` : ''}`),
  getWorkflow: (workflowId) =>
    request(`/api/workflows/${workflowId}`),
  createWorkflow: (workflowData) =>
    request('/api/workflows', {
      method: 'POST',
      body: JSON.stringify(workflowData),
    }),
  startWorkflow: (workflowId) =>
    request(`/api/workflows/${workflowId}/start`, {
      method: 'POST',
    }),
  stopWorkflow: (workflowId, reason = 'User requested stop') =>
    request(`/api/workflows/${workflowId}/stop`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  pauseWorkflow: (workflowId) =>
    request(`/api/workflows/${workflowId}/pause`, {
      method: 'POST',
    }),
  resumeWorkflow: (workflowId) =>
    request(`/api/workflows/${workflowId}/resume`, {
      method: 'POST',
    }),
  recoverWorkflow: (workflowId) =>
    request(`/api/workflows/${workflowId}/recover`, {
      method: 'POST',
    }),

  // Streaming & Real-Time Events
  subscribeEvents: (path, onMessage, onError, onOpen) =>
    createEventSourceConnection(path, onMessage, onError, onOpen),
};

/**
 * Managed EventSource reconnection controller with bounded exponential backoff:
 * 1s -> 2s -> 4s -> 8s -> 15s max.
 */
export function createEventSourceConnection(path, onMessage, onError, onOpen) {
  const BACKOFF_SCHEDULE = [1000, 2000, 4000, 8000, 15000];
  let attempt = 0;
  let es = null;
  let closed = false;
  let timerId = null;

  function connect() {
    if (closed) return;
    const url = `${API_BASE}${path}`;
    try {
      es = new EventSource(url);

      es.onopen = (evt) => {
        attempt = 0;
        if (onOpen) onOpen(evt);
      };

      es.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (onMessage) onMessage(data, evt);
        } catch (e) {
          if (onMessage) onMessage(evt.data, evt);
        }
      };

      es.onerror = (err) => {
        if (closed) return;
        if (onError) onError(err);
        if (es) {
          try {
            es.close();
          } catch (e) {
            // ignore
          }
          es = null;
        }
        const delay = BACKOFF_SCHEDULE[Math.min(attempt, BACKOFF_SCHEDULE.length - 1)];
        attempt++;
        timerId = setTimeout(connect, delay);
      };
    } catch (err) {
      if (closed) return;
      if (onError) onError(err);
      const delay = BACKOFF_SCHEDULE[Math.min(attempt, BACKOFF_SCHEDULE.length - 1)];
      attempt++;
      timerId = setTimeout(connect, delay);
    }
  }

  connect();

  return {
    close: () => {
      closed = true;
      if (timerId) clearTimeout(timerId);
      if (es) {
        try {
          es.close();
        } catch (e) {
          // ignore
        }
        es = null;
      }
    },
    getAttemptCount: () => attempt,
  };
}

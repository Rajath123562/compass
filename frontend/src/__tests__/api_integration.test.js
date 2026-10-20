import test from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../api.js';

test('api.createTask formats requests with options and guidance_mode correctly', async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl = '';
  let capturedOptions = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ id: 'mock-task-1', goal: 'Test Goal', state: 'SUBMITTED' })
    };
  };

  try {
    const res = await api.createTask('Test Goal', { model_id: 'qwen2.5:3b', guidance_mode: 'assist' });
    assert.equal(res.id, 'mock-task-1');
    assert.equal(capturedUrl, 'http://127.0.0.1:8000/api/tasks');
    assert.equal(capturedOptions.method, 'POST');
    
    const parsedBody = JSON.parse(capturedOptions.body);
    assert.equal(parsedBody.goal, 'Test Goal');
    assert.equal(parsedBody.metadata.model_id, 'qwen2.5:3b');
    assert.equal(parsedBody.metadata.guidance_mode, 'assist');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('api.transitionTask sends valid payload to backend state engine', async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl = '';
  let capturedOptions = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ id: 'mock-task-1', state: 'STOPPED' })
    };
  };

  try {
    const res = await api.transitionTask('mock-task-1', 'STOPPED', 'User requested cancellation');
    assert.equal(capturedUrl, 'http://127.0.0.1:8000/api/tasks/mock-task-1/transition');
    assert.equal(capturedOptions.method, 'POST');
    
    const parsedBody = JSON.parse(capturedOptions.body);
    assert.equal(parsedBody.new_state, 'STOPPED');
    assert.equal(parsedBody.reason, 'User requested cancellation');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('api.confirmAction properly submits human-in-the-loop decisions', async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl = '';
  let capturedOptions = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({ status: 'success', decision: 'approved' })
    };
  };

  try {
    await api.confirmAction('task-99', 'dec-42', true, 'Operator verified target window');
    assert.equal(capturedUrl, 'http://127.0.0.1:8000/api/planner/confirm/task-99');
    assert.equal(capturedOptions.method, 'POST');
    
    const parsedBody = JSON.parse(capturedOptions.body);
    assert.equal(parsedBody.decision_id, 'dec-42');
    assert.equal(parsedBody.approved, true);
    assert.equal(parsedBody.reason, 'Operator verified target window');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('api.getDiagnostics and system info methods connect to real contracts', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url) => {
    if (url.includes('/api/system/info')) {
      return {
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({ os: 'Windows 11', cpu_percent: 12.5, memory_used_mb: 480 })
      };
    }
    if (url.includes('/api/system/diagnostics')) {
      return {
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({ timestamp: '2026-10-18T10:00:00Z', status: 'HEALTHY', events: [] })
      };
    }
    return { ok: true, headers: { get: () => 'application/json' }, json: async () => ({}) };
  };

  try {
    const sys = await api.getSystemInfo();
    assert.equal(sys.os, 'Windows 11');
    assert.equal(sys.cpu_percent, 12.5);

    const diag = await api.getDiagnostics();
    assert.equal(diag.status, 'HEALTHY');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

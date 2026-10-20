import test from 'node:test';
import assert from 'node:assert/strict';
import { api, createEventSourceConnection } from '../api.js';

test('api client exports required endpoints', () => {
  assert.equal(typeof api.getHealth, 'function');
  assert.equal(typeof api.createTask, 'function');
  assert.equal(typeof api.listTasks, 'function');
  assert.equal(typeof api.getTask, 'function');
  assert.equal(typeof api.stopTask, 'function');
  assert.equal(typeof api.generatePlan, 'function');
  assert.equal(typeof api.confirmAction, 'function');
  assert.equal(typeof api.sendChatMessage, 'function');
  assert.equal(typeof api.undoChatMessage, 'function');
  assert.equal(typeof api.listWorkflows, 'function');
  assert.equal(typeof api.startWorkflow, 'function');
  assert.equal(typeof api.stopWorkflow, 'function');
  assert.equal(typeof api.subscribeEvents, 'function');
  assert.equal(typeof api.getGeminiStatus, 'function');
  assert.equal(typeof api.setGeminiConfig, 'function');
  assert.equal(typeof api.getClaudeStatus, 'function');
  assert.equal(typeof api.setClaudeConfig, 'function');
});

test('createEventSourceConnection backoff and controller lifecycle', (t) => {
  // Mock EventSource globally for testing environment
  const originalEventSource = globalThis.EventSource;
  
  let instances = [];
  globalThis.EventSource = class MockEventSource {
    constructor(url) {
      this.url = url;
      this.closed = false;
      instances.push(this);
    }
    close() {
      this.closed = true;
    }
  };

  try {
    const conn = createEventSourceConnection(
      '/api/events/test',
      (data) => {},
      (err) => {},
      (evt) => {}
    );

    assert.ok(conn);
    assert.equal(typeof conn.close, 'function');
    assert.equal(typeof conn.getAttemptCount, 'function');
    assert.equal(instances.length, 1);
    assert.equal(instances[0].url, 'http://127.0.0.1:8000/api/events/test');

    // Simulate error to trigger backoff
    instances[0].onerror(new Error('Network disconnected'));
    assert.equal(conn.getAttemptCount(), 1);

    conn.close();
    assert.equal(instances[0].closed, true);
  } finally {
    globalThis.EventSource = originalEventSource;
  }
});

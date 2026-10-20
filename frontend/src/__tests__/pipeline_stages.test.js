import test from 'node:test';
import assert from 'node:assert/strict';

// Stage pipeline progression logic matching TaskStateCard
const PIPELINE_STAGES = [
  { id: 'SUBMITTED', label: 'Instruction Ingested', order: 0 },
  { id: 'PLANNING', label: 'Semantic Planning', order: 1 },
  { id: 'AWAITING_APPROVAL', label: 'Safety Gate Review', order: 2 },
  { id: 'EXECUTING', label: 'Input Execution', order: 3 },
  { id: 'ACTION_EXECUTED', label: 'Windows Event Fired', order: 4 },
  { id: 'VERIFYING', label: 'OCR & State Check', order: 5 },
  { id: 'RECOVERING', label: 'Self-Correction Loop', order: 6 },
  { id: 'COMPLETED', label: 'Verified Complete', order: 7 },
  { id: 'FAILED', label: 'Terminal State', order: 8 },
];

function getStageIndex(state) {
  const normalized = (state || '').toUpperCase();
  const index = PIPELINE_STAGES.findIndex(s => s.id === normalized);
  return index >= 0 ? index : 0;
}

function isTerminalState(state) {
  const normalized = (state || '').toUpperCase();
  return [
    'COMPLETED',
    'TASK_COMPLETED',
    'FAILED',
    'TASK_FAILED',
    'STOPPED',
    'CANCELLED',
    'BLOCKED',
    'SAFETY_BLOCKED',
    'UNVERIFIED',
    'AI_UNAVAILABLE'
  ].includes(normalized);
}

function isVerifiedSuccessful(task) {
  if (!task) return false;
  const state = (task.state || '').toUpperCase();
  if (state !== 'COMPLETED' && state !== 'TASK_COMPLETED') return false;
  
  // Look for successful verification evidence in events
  const hasVerificationSuccess = (task.events || []).some(
    e => e.event_type === 'step_verified' || 
         (e.event_type === 'task_completed' && e.payload?.verification_passed !== false)
  );
  return hasVerificationSuccess || !task.events || task.events.length === 0;
}

test('pipeline stage indexing works correctly', () => {
  assert.equal(getStageIndex('SUBMITTED'), 0);
  assert.equal(getStageIndex('PLANNING'), 1);
  assert.equal(getStageIndex('AWAITING_APPROVAL'), 2);
  assert.equal(getStageIndex('EXECUTING'), 3);
  assert.equal(getStageIndex('ACTION_EXECUTED'), 4);
  assert.equal(getStageIndex('VERIFYING'), 5);
  assert.equal(getStageIndex('RECOVERING'), 6);
  assert.equal(getStageIndex('COMPLETED'), 7);
  assert.equal(getStageIndex('FAILED'), 8);
  // Unknown falls back to 0
  assert.equal(getStageIndex('UNKNOWN_STATE'), 0);
});

test('terminal state identification is exhaustive and honest', () => {
  assert.equal(isTerminalState('COMPLETED'), true);
  assert.equal(isTerminalState('TASK_COMPLETED'), true);
  assert.equal(isTerminalState('FAILED'), true);
  assert.equal(isTerminalState('TASK_FAILED'), true);
  assert.equal(isTerminalState('STOPPED'), true);
  assert.equal(isTerminalState('CANCELLED'), true);
  assert.equal(isTerminalState('BLOCKED'), true);
  assert.equal(isTerminalState('SAFETY_BLOCKED'), true);
  assert.equal(isTerminalState('UNVERIFIED'), true);
  assert.equal(isTerminalState('AI_UNAVAILABLE'), true);

  // Active running states must NOT be terminal
  assert.equal(isTerminalState('PLANNING'), false);
  assert.equal(isTerminalState('EXECUTING'), false);
  assert.equal(isTerminalState('VERIFYING'), false);
  assert.equal(isTerminalState('WAITING_CONFIRMATION'), false);
  assert.equal(isTerminalState('RECOVERING'), false);
});

test('verification outcome differentiates between verified and unverified completion', () => {
  const verifiedTask = {
    id: 'task-101',
    state: 'COMPLETED',
    events: [
      { event_type: 'step_executed', payload: { action: 'click' } },
      { event_type: 'step_verified', payload: { match_score: 0.98, target: 'Search' } }
    ]
  };
  assert.equal(isVerifiedSuccessful(verifiedTask), true);

  const failedVerificationTask = {
    id: 'task-102',
    state: 'COMPLETED',
    events: [
      { event_type: 'step_executed', payload: { action: 'click' } },
      { event_type: 'task_completed', payload: { verification_passed: false, reason: 'Target text not visible' } }
    ]
  };
  assert.equal(isVerifiedSuccessful(failedVerificationTask), false);

  const failedTask = {
    id: 'task-103',
    state: 'FAILED',
    events: []
  };
  assert.equal(isVerifiedSuccessful(failedTask), false);
});

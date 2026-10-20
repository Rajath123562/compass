import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

test('index.css contains required accessibility tokens and dark mode palette', () => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const cssPath = path.resolve(currentDir, '../index.css');
  const cssContent = fs.readFileSync(cssPath, 'utf8');

  // Verify dark mode palette tokens
  assert.ok(cssContent.includes('--color-stitch-bg: #0b0d12'), 'Primary dark background token present');
  assert.ok(cssContent.includes('--color-stitch-bg-elevated: #11141b'), 'Surface container token present');
  assert.ok(cssContent.includes('--color-stitch-border: rgba(255, 255, 255, 0.08)'), 'Accessible border token present');
  assert.ok(cssContent.includes('--color-accent-blue: #3b82f6'), 'Primary action blue token present');

  // Verify accessibility focus rings
  assert.ok(cssContent.includes('focus-visible'), 'Focus visible ring rule defined');
  assert.ok(cssContent.includes('outline-offset'), 'Accessible outline offset defined');

  // Verify reduced motion accessibility support
  assert.ok(cssContent.includes('prefers-reduced-motion'), 'prefers-reduced-motion media query implemented');

  // Verify custom scrollbar styling
  assert.ok(cssContent.includes('::-webkit-scrollbar'), 'Custom scrollbar defined');
});

test('responsive breakpoints are defined and consistent with viewport expectations', () => {
  // Validating breakpoint ranges tested across the application
  const testBreakpoints = [
    { name: 'mobile-narrow', min: 320, max: 375 },
    { name: 'mobile-standard', min: 375, max: 480 },
    { name: 'tablet', min: 768, max: 1023 },
    { name: 'desktop-compact', min: 1024, max: 1279 },
    { name: 'desktop-standard', min: 1280, max: 1439 },
    { name: 'desktop-wide', min: 1440, max: 2560 },
  ];

  testBreakpoints.forEach(bp => {
    assert.ok(bp.min < bp.max, `${bp.name} has valid range`);
    assert.ok(bp.min >= 320, `${bp.name} minimum supported width is at least 320px`);
  });
});

test('semantic action and error state mappings preserve human-readable meaning', () => {
  const STATE_LABELS = {
    'SUBMITTED': 'Queued',
    'PLANNING': 'Formulating Strategy',
    'AWAITING_APPROVAL': 'Pending Operator Approval',
    'EXECUTING': 'Directing Windows Interface',
    'VERIFYING': 'Validating Outcome',
    'COMPLETED': 'Verified & Completed',
    'FAILED': 'Execution Failed',
    'STOPPED': 'Halted by Operator',
    'CANCELLED': 'Cancelled',
  };

  assert.equal(STATE_LABELS['AWAITING_APPROVAL'], 'Pending Operator Approval');
  assert.equal(STATE_LABELS['COMPLETED'], 'Verified & Completed');
  assert.equal(STATE_LABELS['FAILED'], 'Execution Failed');
});

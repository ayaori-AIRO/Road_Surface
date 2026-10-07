import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeRows, csv, fmt, statusLabel } from './telemetry.js';

test('incremental polling deduplicates and expires old records', () => {
  const rows = mergeRows([{ id: 1, received_ms: 0 }, { id: 2, received_ms: 4000000 }],
    [{ id: 2, received_ms: 4000000, pressure_hpa: 1011 }, { id: 3, received_ms: 4001000 }], 4001000);
  assert.deepEqual(rows.map(r => r.id), [2, 3]);
  assert.equal(rows[0].pressure_hpa, 1011);
});
test('missing, zero and negative measurements remain distinct', () => {
  assert.equal(fmt(null), '—');
  assert.equal(fmt(0), '0.00');
  assert.equal(fmt(-1), '-1.00');
  assert.equal(statusLabel('warming_up'), 'IMU 이력 수집 중');
});
test('CSV includes pressure and escapes untrusted text without corrupting numbers', () => {
  const text = csv([{ timestamp: '=formula', snow_height_mm: -2, pressure_hpa: 1011.2, prediction_status: 'a,"b' }]);
  assert.ok(text.includes('pressure_hpa'));
  assert.ok(text.includes('"\'=formula"'));
  assert.ok(text.includes('"-2"'));
  assert.ok(text.includes('"a,""b"'));
});

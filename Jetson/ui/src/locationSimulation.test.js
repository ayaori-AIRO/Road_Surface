import test from 'node:test';
import assert from 'node:assert/strict';
import { advanceDistance, positionAt, routeLength } from './locationSimulation.js';
test('speed is converted to metres per second and elapsed time is respected', () => {
  assert.equal(advanceDistance(0, 36, 10), 100);
  assert.equal(advanceDistance(100, 0, 60), 100);
  assert.equal(advanceDistance(0, 72, 5), 100);
});
test('route corners and loop preserve continuous position', () => {
  assert.equal(positionAt(450).x, 450);
  assert.equal(positionAt(450).y, 0);
  assert.equal(positionAt(750).y, 300);
  assert.deepEqual(positionAt(routeLength), positionAt(0));
  assert.deepEqual(positionAt(routeLength + 100), positionAt(100));
  assert.ok(Math.hypot(positionAt(1499.99).x, positionAt(1499.99).y) < .011);
});
test('coordinates and heading follow the moving marker', () => {
  assert.ok(positionAt(100).longitude > positionAt(0).longitude);
  assert.equal(positionAt(100).latitude, positionAt(0).latitude);
  assert.equal(positionAt(100).heading, 90);
  assert.ok(positionAt(550).latitude > positionAt(450).latitude);
  assert.equal(positionAt(550).heading, 0);
});

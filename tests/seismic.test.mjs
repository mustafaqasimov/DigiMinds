import test from 'node:test';
import assert from 'node:assert/strict';
import {ShakeDetector, nodePosition} from '../frontend/seismic.js';

function run(detector, seconds, amplitude, hz = 60, withGravity = false) {
  const out = [];
  for (let i = 0; i < seconds * hz; i++) {
    const wiggle = amplitude * Math.sin(i * 2.1) + (Math.random() - .5) * .02;
    out.push(detector.push({x: wiggle, y: wiggle * .6, z: (withGravity ? 9.81 : 0) + wiggle * .3}, 1 / hz, withGravity));
  }
  return out;
}

test('a phone resting on a table never triggers', () => {
  const d = new ShakeDetector();
  assert.ok(!run(d, 20, .01).some(r => r.onset));
});

test('shaking the table triggers once, then re-arms after it calms down', () => {
  const d = new ShakeDetector();
  run(d, 5, .01);
  const shake = run(d, 2, 4);
  assert.equal(shake.filter(r => r.onset).length, 1);
  assert.ok(shake.at(-1).peak > 3);
  run(d, 6, .01);
  assert.ok(!d.active);
  assert.equal(run(d, 2, 4).filter(r => r.onset).length, 1);
});

test('gravity is removed when only accelerationIncludingGravity exists', () => {
  const d = new ShakeDetector();
  assert.ok(!run(d, 10, .01, 60, true).some(r => r.onset));
  assert.ok(run(d, 2, 4, 60, true).some(r => r.onset));
});

test('no trigger during warm-up, even with motion', () => {
  const d = new ShakeDetector();
  assert.ok(!run(d, 2, 4).some(r => r.onset));
});

test('node ids map onto the training grid', () => {
  assert.deepEqual(nodePosition('n3_4'), {lat: 40.365 + 3 * .0025, lng: 49.828 + 4 * .0035});
});

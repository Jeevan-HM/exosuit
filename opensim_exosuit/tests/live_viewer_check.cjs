/* Offline logic/render-call checks; no browser, network or computer UI access. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.resolve(__dirname, '../../human_walking/live_walking.html'), 'utf8');
const data = JSON.parse(html.match(/<script id="gait-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const source = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
let frame, matrices = [], errors = [];
const drawing = new Proxy({}, {get(target, key) {
  return target[key] ?? (target[key] = () => {});
}});
const gl = new Proxy({
  createShader: () => ({}), createProgram: () => ({}), createBuffer: () => ({}),
  getShaderParameter: () => true, getProgramParameter: () => true,
  getAttribLocation: (_, name) => name === 'aPosition' ? 0 : 1,
  getUniformLocation: (_, name) => ({name}), getExtension: () => ({}),
  uniformMatrix4fv: (location, _, matrix) => {
    if (location.name === 'uModel') matrices.push(Array.from(matrix));
  }
}, {get(target, key) {
  if (key in target) return target[key];
  if (key.toUpperCase() === key) return (target[key] = Object.keys(target).length + 1);
  return (target[key] = () => {});
}});
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    id, value: '', checked: true, hidden: false, textContent: '', innerHTML: '',
    attributes: {}, listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; },
    getBoundingClientRect: () => ({width: 600, height: id === 'human' ? 540 : 211}),
    getContext: type => type === 'webgl' ? gl : drawing,
  });
  return elements.get(id);
}
element('gait-data').textContent = JSON.stringify(data);
const document = {hidden: false, getElementById: element,
  querySelector: () => element('layout'), addEventListener: () => {}};
const environment = {document, console: {error: (...items) => errors.push(items)},
  matchMedia: () => ({matches: false}), devicePixelRatio: 1,
  requestAnimationFrame: callback => { frame = callback; },
  ResizeObserver: class {observe() {}}, addEventListener: () => {}};
environment.window = environment;
vm.runInNewContext(source, environment, {timeout: 5000});
const viewer = environment.gaitViewer;
assert.ok(viewer && viewer.state().webgl_ready);
assert.equal(errors.length, 0);
assert.equal(viewer.state().playing, true);
viewer.pause();

function renderAt(seconds) {
  viewer.seek(seconds);
  matrices = [];
  frame(0);
  const result = viewer.state();
  assert.ok(matrices.length >= data.meshes.length);
  assert.ok(matrices.every(matrix => matrix.length === 16 && matrix.every(Number.isFinite)));
  return result;
}
for (const [time, angle] of [[0.12,17.04], [0.4,2.37], [0.72,58.25]]) {
  const state = renderAt(time);
  assert.ok(Math.abs(state.angle_deg - angle) < 1e-9);
  assert.ok(Math.abs(state.cycle_percent - 100*time) < 1e-9);
  assert.equal(Number(element('angle').textContent), Number(angle.toFixed(1)));
}
viewer.setKnee('l');
const left = renderAt(.22);
assert.ok(Math.abs(left.angle_deg - 58.25) < 1e-9);
assert.equal(element('knee-title').textContent, 'Left knee flexion');

viewer.setKnee('r'); viewer.setSpeed(2); viewer.reset(); viewer.play();
frame(0);
for (let index=1; index<=120; index++) frame(index*100);
const looping = viewer.state();
assert.ok(Math.abs(looping.elapsed_s - 24) < 1e-7);
assert.ok(looping.time_s >= 0 && looping.time_s < data.duration_s);
assert.ok(looping.history_count > 10 && looping.history_count <= 900);
viewer.pause();
const paused = viewer.state().elapsed_s;
frame(13000); frame(14000);
assert.equal(viewer.state().elapsed_s, paused);
viewer.setSpeed(.5); viewer.reset(); viewer.play(); frame(15000); frame(15100);
assert.ok(Math.abs(viewer.state().elapsed_s - .05) < 1e-9);
assert.throws(() => viewer.setKnee('invalid'));
assert.throws(() => viewer.setSpeed(8));
viewer.pause();
console.log('Verified continuous multi-cycle clock, source angles, pause/restart/speed, bilateral selection, bounded trace and 3D render calls.');

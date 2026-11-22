/* Logic/render-call checks using captured native solver frames; no browser UI. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
  const fixturePath = process.argv[2] || path.resolve(__dirname,
    '../../human_walking/physics_output/frontend_frames.json');
  const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
  const nativeFrames = Array.isArray(fixture) ? fixture : fixture.frames;
  assert.ok(Array.isArray(nativeFrames) && nativeFrames.length >= 3,
    'Supply at least three captured OpenSim solver frames');
  assert.ok(nativeFrames.some((frame, index) => index &&
    frame.knee_flexion_deg.r !== nativeFrames[0].knee_flexion_deg.r),
    'The captured native frames must contain changing actual angles');
  const rawScene = fixture.scene || fixture.static_scene || JSON.parse(fs.readFileSync(
    path.resolve(__dirname, '../../human_walking/live_data.json'), 'utf8'));
  const data = Object.fromEntries(['meshes', 'frame_names', 'bounds'].map(key => [key, rawScene[key]]));
  const html = fs.readFileSync(path.resolve(__dirname, '../physics_viewer.template.html'), 'utf8');
  assert.equal(html.split('__LIVE_DATA_JSON__').length - 1, 1);
  const source = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  assert.ok(!source.includes('data.poses') && !source.includes('data.times') &&
    !source.includes('data.knee_flexion_deg'), 'Only immutable anatomy may come from embedded data');

  async function runScenario(mode) {
  let usesCanvas = mode === 'fallback' || mode === 'forced-canvas';
  let animationFrame, wallTime = 1000, currentModel = null, webglRequests = 0;
  let meshDraws = [], arcs = [], failures = [], requests = [];
  let cpuPolygons = [], cpuPath = [];
  const contexts = new Map();
  function drawing(id) {
    if (!contexts.has(id)) contexts.set(id, new Proxy({
      arc: (...args) => { if (id === 'actual-plot') arcs.push(args); },
      beginPath: () => { if (id === 'human-fallback') cpuPath = []; },
      moveTo: (x, y) => { if (id === 'human-fallback') cpuPath.push([x, y]); },
      lineTo: (x, y) => { if (id === 'human-fallback') cpuPath.push([x, y]); },
      fill: () => {
        if (id === 'human-fallback' && cpuPath.length >= 3) {
          cpuPolygons.push(cpuPath.map(point => point.slice()));
        }
      },
      measureText: text => ({width: String(text).length * 7}),
      createLinearGradient: () => ({addColorStop() {}}),
    }, {get(target, key) { return target[key] ?? (target[key] = () => {}); }}));
    return contexts.get(id);
  }
  const gl = new Proxy({
    createShader: () => ({}), createProgram: () => ({}), createBuffer: () => ({}),
    getShaderParameter: () => true, getProgramParameter: () => true,
    getAttribLocation: (_, name) => name === 'aPosition' ? 0 : 1,
    getUniformLocation: (_, name) => ({name}), getExtension: () => ({}),
    uniformMatrix4fv(location, _, matrix) {
      if (location.name === 'uModel') currentModel = Array.from(matrix);
    },
    drawElements() { meshDraws.push(currentModel.slice()); },
  }, {get(target, key) {
    if (key in target) return target[key];
    if (key.toUpperCase() === key) return (target[key] = Object.keys(target).length + 1);
    return (target[key] = () => {});
  }});
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      id, value: '', checked: true, disabled: false, hidden: false,
      textContent: '', innerHTML: '', attributes: {}, listeners: {},
      addEventListener(name, callback) { this.listeners[name] = callback; },
      setAttribute(name, value) { this.attributes[name] = value; },
      getBoundingClientRect: () => ({width: 600,
        height: id === 'human' || id === 'human-fallback' ? 540 : 305}),
      getContext(type) {
        if (type === 'webgl') {
          webglRequests++;
          return mode === 'fallback' ? null : gl;
        }
        return drawing(id);
      },
    });
    return elements.get(id);
  }
  element('gait-data').textContent = JSON.stringify(data);
  const document = {hidden: false, getElementById: element,
    querySelector: () => element('layout'), addEventListener: () => {}};
  let eventSource;
  class EventSource {
    constructor(url) { assert.equal(url, '/events'); this.listeners = {}; eventSource = this; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
  }
  const environment = {
    document, EventSource, Date: {now: () => wallTime}, URLSearchParams,
    location: {search: mode === 'forced-canvas' ? '?renderer=canvas' : ''},
    console: {error: (...items) => failures.push(items), warn: () => {}},
    devicePixelRatio: 1, requestAnimationFrame: callback => { animationFrame = callback; },
    ResizeObserver: class {observe() {}}, addEventListener: () => {}, setInterval: () => 1,
    fetch: async (url, options) => {
      requests.push({url, method: options.method, body: JSON.parse(options.body)});
      return {ok: true, status: 202, json: async () => ({queued: true})};
    },
  };
  environment.window = environment;
  vm.runInNewContext(source, environment, {timeout: 5000});
  const viewer = environment.physicsViewer;
  assert.ok(viewer && viewer.state().anatomy_ready);
  assert.equal(viewer.state().renderer_mode, usesCanvas ? 'canvas' : 'webgl');
  assert.equal(viewer.state().webgl_ready, !usesCanvas);
  if (!usesCanvas) assert.equal(failures.length, 0);
  if (mode === 'forced-canvas') assert.equal(webglRequests, 0,
    'The canvas query parameter must avoid requesting a GPU context');
  assert.equal(viewer.state().time_s, null);
  assert.equal(viewer.state().history_count, 0);
  assert.equal(meshDraws.length, 0, 'No source pose may be rendered before a solver frame');
  assert.equal(cpuPolygons.length, 0,
    'The CPU renderer must not invent anatomy poses before an actual solver frame');
  assert.equal(element('connection').textContent, 'Waiting for solver');

  function send(frame) { eventSource.onmessage({data: JSON.stringify(frame)}); }
  function render() {
    meshDraws = []; cpuPolygons = []; arcs = [];
    animationFrame(); return viewer.state();
  }
  function nativeFrame(index, extras = {}) {
    return {...JSON.parse(JSON.stringify(nativeFrames[index])),
      sequence: 10 + index, run_id: 'native-capture', status: 'running', ...extras};
  }
  eventSource.onopen();
  send({status: 'starting', sequence: 0, run_id: 'starting'}); render();
  assert.equal(viewer.state().status, 'starting');
  assert.equal(viewer.state().time_s, null);
  assert.equal(viewer.state().accepted_frames, 0);
  assert.equal(element('connection').textContent, 'Starting OpenSim');
  assert.equal(element('play').disabled, true);

  let expectedHistory = [];
  function checkActual(frame) {
    const state = render();
    assert.equal(state.time_s, frame.time_s);
    assert.equal(state.angle_deg, frame.knee_flexion_deg[state.knee]);
    assert.equal(state.sequence, frame.sequence);
    assert.equal(state.rendered_sequence, frame.sequence);
    assert.equal(Number(element('angle').textContent), Number(state.angle_deg.toFixed(1)));
    assert.equal(Number(element('time').textContent), Number(frame.time_s.toFixed(2)));
    assert.equal(state.renderer_mode, usesCanvas ? 'canvas' : 'webgl');
    assert.equal(state.anatomy_ready, true);
    if (usesCanvas) {
      assert.equal(meshDraws.length, 0, 'The CPU path cannot depend on GPU draw calls');
      assert.ok(cpuPolygons.length > data.meshes.length,
        'The fallback must actually draw projected anatomy triangles');
      assert.ok(cpuPolygons.every(polygon => polygon.length >= 3 &&
        polygon.every(point => point.every(Number.isFinite))),
        'Every CPU anatomy polygon must have finite projected coordinates');
      assert.ok(cpuPolygons.some(polygon => polygon.some(([x, y]) =>
        x >= 0 && x <= 600 && y >= 0 && y <= 540)),
        'Projected anatomy must intersect the visible canvas');
    } else {
      assert.equal(meshDraws.length, data.meshes.length);
      assert.equal(cpuPolygons.length, 0);
      for (let index = 0; index < meshDraws.length; index++) {
        const matrix = meshDraws[index], offset = data.meshes[index].frame_index * 7;
        assert.ok(matrix.every(Number.isFinite));
        for (let axis = 0; axis < 3; axis++) assert.ok(
          Math.abs(matrix[12 + axis] - frame.poses[offset + axis]) < 1e-6,
          'Rendered mesh translation must equal this actual solver frame');
      }
    }
    const values = expectedHistory.map(point => point.knee_flexion_deg[state.knee]);
    const yMin = Math.min(-10, Math.floor(Math.min(0, ...values) / 20) * 20);
    const yMax = Math.max(90, Math.ceil(Math.max(0, ...values) / 20) * 20);
    const end = Math.max(10, frame.time_s), start = end - 10;
    const expectedX = 43 + (frame.time_s - start) / 10 * (600 - 43 - 17);
    const expectedY = 305 - 37 - (state.angle_deg - yMin) / (yMax - yMin) * (305 - 15 - 37);
    assert.equal(arcs.length, 1, 'The actual trace has one latest-state dot');
    assert.ok(Math.abs(arcs[0][0] - expectedX) < 1e-9);
    assert.ok(Math.abs(arcs[0][1] - expectedY) < 1e-9,
      'The plot dot must use the actual angle from the rendered pose sequence');
    return state;
  }

  const first = nativeFrame(0); expectedHistory.push(first); send(first); checkActual(first);
  let firstCpuGeometry = usesCanvas ? JSON.stringify(cpuPolygons) : null;
  if (mode === 'context-lost') {
    const beforeLoss = viewer.state();
    let prevented = false;
    element('human').listeners.webglcontextlost({preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
    usesCanvas = true;
    checkActual(first);
    assert.equal(viewer.state().time_s, beforeLoss.time_s);
    assert.equal(viewer.state().accepted_frames, beforeLoss.accepted_frames,
      'Losing the GPU must not invent a new solver frame');
    assert.equal(viewer.state().history_count, beforeLoss.history_count);
    firstCpuGeometry = JSON.stringify(cpuPolygons);
  }
  const beforeNoData = viewer.state();
  for (let index = 0; index < 240; index++) animationFrame(index * 1000 / 60);
  const afterNoData = viewer.state();
  for (const field of ['time_s', 'sequence', 'angle_deg', 'history_count', 'accepted_frames', 'render_count']) {
    assert.equal(afterNoData[field], beforeNoData[field], `No SSE frame must mean no ${field} advance`);
  }
  const second = nativeFrame(1); expectedHistory.push(second); send(second); checkActual(second);
  if (usesCanvas) assert.notEqual(JSON.stringify(cpuPolygons), firstCpuGeometry,
    'New actual native poses must change the CPU anatomy geometry');
  viewer.setKnee('l'); checkActual(second);
  assert.equal(viewer.state().angle_deg, second.knee_flexion_deg.l);
  assert.equal(element('knee-title').textContent, 'Left knee flexion');
  viewer.setKnee('r'); checkActual(second);

  const paused = {...second, status: 'paused', sequence: 20};
  send(paused); checkActual(paused);
  const pausedCount = viewer.state().history_count;
  send({...paused, sequence: 21}); checkActual({...paused, sequence: 21});
  assert.equal(viewer.state().history_count, pausedCount, 'Repeated paused time must not duplicate history');
  for (let index = 0; index < 240; index++) animationFrame(index * 1000);
  assert.equal(viewer.state().time_s, paused.time_s);

  const beforeControls = viewer.state();
  await viewer.play(); await viewer.pause(); await viewer.reset(); await viewer.disturb();
  await viewer.setSpeed(.5); await viewer.setSpeed(.25); await viewer.setSpeed(.1);
  assert.deepEqual(requests.map(request => request.body), [
    {action: 'play'}, {action: 'pause'}, {action: 'reset'},
    {action: 'disturb', value: 5}, {action: 'speed', value: .5},
    {action: 'speed', value: .25}, {action: 'speed', value: .1},
  ]);
  assert.ok(requests.every(request => request.url === '/control' && request.method === 'POST'));
  assert.equal(viewer.state().time_s, beforeControls.time_s, 'Queued commands cannot invent a solver state');
  assert.equal(viewer.state().angle_deg, beforeControls.angle_deg);
  assert.equal(viewer.state().history_count, beforeControls.history_count);
  assert.equal(viewer.state().status, 'paused', 'Play acknowledgement does not replace actual server status');

  const third = nativeFrame(2, {speed: .1}); expectedHistory.push(third); send(third); checkActual(third);
  assert.equal(viewer.state().speed, .1);
  assert.equal(element('speed').value, '0.1');
  // Reset metadata changes, but the pose and angles remain an actual captured state.
  const newRun = nativeFrame(0, {run_id: 'new-native-run', sequence: 30});
  expectedHistory = [newRun]; send(newRun); checkActual(newRun);
  assert.equal(viewer.state().history_count, 1, 'A new run_id clears the old trace');
  const beforeError = viewer.state();
  send({status: 'error', error: 'Native solver stopped', run_id: 'new-native-run', sequence: 31});
  animationFrame();
  assert.equal(viewer.state().status, 'error');
  assert.equal(viewer.state().time_s, beforeError.time_s);
  assert.equal(viewer.state().accepted_frames, beforeError.accepted_frames);
  assert.equal(element('connection').textContent, 'Solver error');
  assert.equal(element('play').disabled, true);
  assert.equal(element('notice').textContent, 'Native solver stopped');

  eventSource.onerror();
  const disconnected = viewer.state();
  wallTime += 120000;
  for (let index = 0; index < 240; index++) animationFrame(index * 1000);
  assert.equal(viewer.state().connected, false);
  assert.equal(viewer.state().time_s, disconnected.time_s);
  assert.equal(viewer.state().angle_deg, disconnected.angle_deg);
  assert.equal(viewer.state().history_count, disconnected.history_count);
  assert.equal(element('connection').textContent, 'Waiting for solver');
  assert.throws(() => viewer.setKnee('invalid'));
  assert.throws(() => viewer.setSpeed(8));
  assert.equal(failures.length, 0, 'Recovered renderer errors must not stop the page');
  if (mode === 'fallback' || mode === 'context-lost') {
    assert.equal(typeof viewer.state().graphics_error, 'string');
    assert.ok(viewer.state().graphics_error.length);
    assert.equal(element('human').hidden, true);
    assert.equal(element('human-fallback').hidden, false);
    assert.equal(element('scene-error').hidden, true,
      'A working compatibility renderer must replace the obsolete failure message');
  }
  console.log(`Verified ${mode}: actual anatomy drawing and pose/plot agreement, no client-clock advance, paused/reset/error/disconnect handling, bilateral angles and queued controls.`);
  }
  await runScenario('webgl');
  await runScenario('fallback');
  await runScenario('forced-canvas');
  await runScenario('context-lost');
}

main().catch(error => { console.error(error); process.exitCode = 1; });

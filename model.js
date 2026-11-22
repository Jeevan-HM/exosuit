/* Conceptual, one-degree-of-freedom seated knee model. SI internally, kPa inputs.
   This is a tunable reduced model, not a reconstruction or hardware controller. */
const KneeModel = (() => {
  const rad = Math.PI / 180;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const defaults = Object.freeze({ mode: 'cycle', assist: true, share: 0.65,
    supply: 120, gain: 0.12, lag: 0.25, period: 6, target: 55,
    manualFlex: 0, manualExt: 0, mass: 4, length: 0.43, damping: 0.7 });
  function reference(t, p) {
    if (p.mode !== 'cycle') return { q: p.target * rad, v: 0, a: 0 };
    const w = 2 * Math.PI / p.period;
    return { q: (47.5 - 37.5 * Math.cos(w * t)) * rad,
      v: 37.5 * rad * w * Math.sin(w * t),
      a: 37.5 * rad * w * w * Math.cos(w * t) };
  }
  function coefficients(q, p) {
    const ratio = clamp(q / (120 * rad), 0, 1);
    return { flex: p.gain * (1 - 0.75 * ratio), ext: p.gain * (0.35 + 0.65 * ratio) };
  }
  function create(p = defaults) {
    return { t: 0, q: (p.mode === 'cycle' ? 10 : p.target) * rad, v: 0,
      pf: 0, pe: 0, cf: 0, ce: 0, human: 0, robot: 0, gravity: 0,
      net: 0, power: 0, stop: 0, target: p.mode === 'manual' ? null : reference(0, p).q / rad };
  }
  function step(s, p, dt = 1 / 240) {
    if (!(dt > 0 && dt <= 0.02)) throw new Error('Use a fixed time step of 0–0.02 s.');
    const inertia = p.mass * p.length * p.length / 3;
    const r = reference(s.t, p), c = coefficients(s.q, p);
    const gravity = p.mass * 9.81 * p.length / 2 * Math.cos(s.q);
    const passive = -p.damping * s.v - 0.4 * s.q;
    const demand = inertia * r.a - gravity - passive + 22 * (r.q - s.q) + 4 * (r.v - s.v);
    let desired = 0;
    if (p.mode === 'manual') {
      s.cf = p.assist ? clamp(p.manualFlex, 0, p.supply) : 0;
      s.ce = p.assist ? clamp(p.manualExt, 0, p.supply) : 0;
      s.human = 0;
    } else {
      desired = p.assist ? clamp(p.share * demand, -p.supply * c.ext, p.supply * c.flex) : 0;
      s.cf = desired > 0 ? desired / c.flex : 0;
      s.ce = desired < 0 ? -desired / c.ext : 0;
      // The idealized wearer covers commanded assistance saturation, but not pneumatic lag.
      s.human = clamp(demand - desired, -25, 25);
    }
    const alpha = 1 - Math.exp(-dt / p.lag);
    // A supply change does not instantaneously dump stored chamber pressure.
    s.pf += (s.cf - s.pf) * alpha;
    s.pe += (s.ce - s.pe) * alpha;
    s.robot = c.flex * s.pf - c.ext * s.pe;
    s.gravity = gravity;
    s.net = s.human + s.robot + gravity + passive;
    s.v += s.net / inertia * dt;
    s.q += s.v * dt;
    s.stop = 0;
    if (s.q <= 0) { s.q = 0; if (s.v < 0) { s.v = 0; s.stop = -Math.min(0, s.net); } }
    if (s.q >= 120 * rad) { s.q = 120 * rad; if (s.v > 0) { s.v = 0; s.stop = -Math.max(0, s.net); } }
    s.power = s.robot * s.v;
    s.target = p.mode === 'manual' ? null : r.q / rad;
    s.t += dt;
    return s;
  }
  return { defaults, create, step, reference, coefficients, rad, clamp };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = KneeModel;

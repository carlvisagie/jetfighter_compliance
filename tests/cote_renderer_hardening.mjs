/**
 * COTE renderer hardening — node-run assertions (no browser).
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..');
const code = fs
  .readFileSync(path.join(root, 'ui/assets/js/cognitive-topology.js'), 'utf8')
  .replace(
    '})(typeof window !== \'undefined\' ? window : globalThis);',
    '})(global);'
  );

function makeElement() {
  const children = [];
  const el = {
    children,
    childNodes: children,
    parentNode: null,
    style: {},
    textContent: '',
    innerHTML: '',
    hidden: false,
    className: '',
    classList: {
      _c: new Set(),
      toggle(k, on) {
        if (on) this._c.add(k);
        else this._c.delete(k);
      },
      add(k) {
        this._c.add(k);
      },
      remove(k) {
        this._c.delete(k);
      },
    },
    setAttribute() {},
    getAttribute() {
      return null;
    },
    appendChild(c) {
      children.push(c);
      c.parentNode = el;
      return c;
    },
    insertBefore(n, ref) {
      const i = children.indexOf(ref);
      if (i < 0) throw new Error('NotFoundError: ref not a child');
      children.splice(i, 0, n);
      n.parentNode = el;
      return n;
    },
    removeChild(c) {
      const i = children.indexOf(c);
      if (i >= 0) children.splice(i, 1);
      return c;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    addEventListener() {},
  };
  Object.defineProperty(el, 'firstChild', {
    get() {
      return children[0] || null;
    },
  });
  return el;
}

const document = {
  createElementNS(_ns, tag) {
    const el = makeElement();
    el.tagName = tag;
    return el;
  },
  getElementById() {
    return null;
  },
};

const sandbox = { console, document, global: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const C = sandbox.global.CoteTopology;

let failed = 0;
function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL:', msg);
    failed++;
  }
}

const goodPayload = {
  ok: true,
  global_pressure: 0.2,
  system_health: 0.8,
  subsystems: {
    acquisition: { health: 0.8, pressure: 0.1, activity: 0.3, confidence: 0.7, latency: 0.05, alerts: 0 },
    knowledge: { health: 0.7, pressure: 0.2, activity: 0.2, confidence: 0.6, latency: 0.05, alerts: 0 },
    observability: { health: 0.7, pressure: 0.2, activity: 0.2, confidence: 0.6, latency: 0.05, alerts: 0 },
    upload_pipeline: {
      health: 0.75,
      pressure: 0.3,
      activity: 0.5,
      confidence: 0.7,
      latency: 0.05,
      alerts: 0,
      pending_review: 2,
      queue_depth: 2,
      urgent_count: 1,
    },
    evidence_processing: { health: 0.7, pressure: 0.2, activity: 0.2, confidence: 0.6, latency: 0.05, alerts: 0 },
    learning: { health: 0.7, pressure: 0.2, activity: 0.2, confidence: 0.6, latency: 0.05, alerts: 0, learning_status: 'healthy' },
    telemetry: { health: 0.7, pressure: 0.2, activity: 0.2, confidence: 0.6, latency: 0.05, alerts: 0, queue_depth: 55, telemetry_pulse: 'backlog' },
    alerts: { health: 0.8, pressure: 0.1, activity: 0.1, confidence: 0.7, latency: 0.05, alerts: 0 },
    system_health: { health: 0.8, pressure: 0.2, activity: 0.3, confidence: 0.7, latency: 0.05, alerts: 0 },
  },
};

// missing subsystem
const n1 = C.normalizeSubsystem(null, 'acquisition');
assert(n1._cote_uncertain === true, 'null subsystem should be uncertain');

// malformed metrics
const n2 = C.normalizeSubsystem({ health: 'broken', pressure: null }, 'knowledge');
assert(typeof n2.health === 'number', 'malformed health coerced to number');
assert(n2._cote_uncertain === true, 'malformed metrics flagged uncertain');

// partial API — missing node filled
const partial = { ok: true, subsystems: { acquisition: goodPayload.subsystems.acquisition } };
const norm = C.normalizeTopologyPayload(partial);
assert(norm.subsystems.telemetry && typeof norm.subsystems.telemetry.health === 'number', 'missing telemetry filled');

// ok_false uses last-known-good
const merged = C.mergeTopologyPayload({ ok: false }, goodPayload);
assert(merged.usedFallback === true, 'ok_false should use last-known-good');
assert(merged.data.subsystems.upload_pipeline.pending_review === 2, 'LKG preserves upload metrics');

// refresh race — stale generation ignored (smoke: merge still works)
const m1 = C.mergeTopologyPayload(goodPayload, null);
assert(m1.valid === true && !m1.usedFallback, 'valid payload accepted');

// upload pending + telemetry backlog nodes build without DOM collapse
const normFull = C.normalizeTopologyPayload(goodPayload);
const uploadCfg = C.NODES.find((x) => x.id === 'upload_pipeline');
const telCfg = C.NODES.find((x) => x.id === 'telemetry');
try {
  const g1 = C.buildRingNodeGroup(uploadCfg, normFull.subsystems.upload_pipeline);
  assert(g1.children.length >= 4, 'upload node has pulse/body/hit/label');
  const g2 = C.buildRingNodeGroup(telCfg, normFull.subsystems.telemetry);
  assert(g2.children.length >= 4, 'telemetry backlog node renders');
} catch (e) {
  assert(false, 'buildRingNodeGroup threw: ' + e.message);
}

// partial failure payload still validates after normalize
const broken = { ok: true, subsystems: null };
const normBroken = C.normalizeTopologyPayload(broken);
const check = C.validateTopologyPayload(normBroken);
assert(check.valid === true, 'normalized null subsystems container becomes valid');

if (failed) {
  console.error(failed + ' test(s) failed');
  process.exit(1);
}
console.log('cote_renderer_hardening: all tests passed');

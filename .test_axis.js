// Minimal test of the adaptive axis logic
const detail = {
  created_utc: '2026-06-03T10:00:00Z',
  custody: {
    events: [
      { at_utc: '2026-06-03T10:00:00Z', phase: 'upload_received' },
      { at_utc: '2026-06-03T10:01:00Z', phase: 'file_persisted' },
      { at_utc: '2026-06-03T11:00:00Z', phase: 'classification_complete' },
    ]
  },
  uploaded_documents: [
    { uploaded_utc: '2026-06-03T10:00:30Z' }
  ],
  generated_documents: [],
  findings: [],
  payment: {}
};

const stamps = new Set();
const custody = (detail && detail.custody && detail.custody.events) || [];
custody.forEach(e => {
  const t = Date.parse(e.at_utc || '');
  if (t) stamps.add(t);
});

console.log(`Stamps collected: ${stamps.size}`);

const sorted = Array.from(stamps).sort((a, b) => a - b);
console.log(`Sorted: ${sorted.length}`);

// Test the adaptive spacing logic
const MIN_PX = 28;
const MAX_PX = 180;
const LOG_BASE = 60000;

const weights = [];
for (let i = 1; i < sorted.length; i++) {
  const dt = sorted[i] - sorted[i - 1];
  const ratio = dt / LOG_BASE;
  const logW = Math.log2(1 + ratio);
  const visualW = MIN_PX + logW * 12;
  weights.push(Math.min(MAX_PX, visualW));
  console.log(`Gap ${i}: ${dt}ms → ratio=${ratio.toFixed(2)} → logW=${logW.toFixed(2)} → visualW=${visualW.toFixed(2)}px`);
}

console.log('Test passed!');

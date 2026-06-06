/**
 * VIO PICTOGRAPHIC ARTIFACT LIBRARY
 * ============================================================
 * Design Philosophy: MAXIMUM INFORMATION DENSITY AT A GLANCE
 * Every symbol IS the thing it represents. No abstract shapes.
 * Color + shape + texture + animation = complete story without text.
 *
 * ARTIFACT CATALOG:
 * - DocumentNode: Stack of papers (intake, filing, records)
 * - DocumentIssueNode: Paper with red torn corner + exclamation
 * - StampNode: Rubber stamp (approved/phase complete)
 * - CoinNode: Gold coin (payment received)
 * - CrackCoinNode: Cracked coin (payment issue/aging)
 * - WallNode: Brick wall (hard blocker)
 * - BrokenChainNode: Chain with broken link (dependency blocked)
 * - MagnifierNode: Magnifying glass (review/inspection)
 * - CheckmarkNode: Bold checkmark in circle (complete/delivered)
 * - ClockNode: Clock face (SLA / time pressure)
 * - AlertTriangleNode: Warning triangle with ! (attention/gap)
 * - GearNode: Spinning gear (processing/in-progress)
 * - FolderNode: Open folder (case/file collection)
 * - ScaleNode: Balance scales (compliance/legal)
 * - RocketNode: Rocket (delivery/launch)
 * - KeyNode: Key (access/approval granted)
 * - FingerNode: Pointing finger (decision/next action required)
 * - MilestoneFlag: Flag on pole (milestone reached)
 * ============================================================
 */

import React from 'react';

interface ArtifactProps {
  size?: number;
  state: 'healthy' | 'attention' | 'blocked' | 'complete' | 'processing' | 'inactive' | 'milestone';
  onClick?: () => void;
  isSelected?: boolean;
  label?: string;
}

// Color palette per state
const STATE = {
  healthy:    { primary: '#00e5a0', secondary: '#00b87a', glow: '#00e5a040', text: '#00e5a0' },
  attention:  { primary: '#ffb800', secondary: '#e09000', glow: '#ffb80050', text: '#ffb800' },
  blocked:    { primary: '#ff3d3d', secondary: '#cc1a1a', glow: '#ff3d3d50', text: '#ff3d3d' },
  complete:   { primary: '#4ade80', secondary: '#16a34a', glow: '#4ade8040', text: '#4ade80' },
  processing: { primary: '#38bdf8', secondary: '#0284c7', glow: '#38bdf840', text: '#38bdf8' },
  inactive:   { primary: '#4a5568', secondary: '#2d3748', glow: '#4a556820', text: '#4a5568' },
  milestone:  { primary: '#ffd700', secondary: '#b8860b', glow: '#ffd70060', text: '#ffd700' },
};

// Wrapper that handles glow, selection ring, and click
function ArtifactWrapper({
  size, state, onClick, isSelected, children, label
}: ArtifactProps & { children: React.ReactNode }) {
  const s = size || 36;
  const c = STATE[state];
  const pad = 12;
  const total = s + pad * 2;

  return (
    <g
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      data-hint={label}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      {/* Glow halo */}
      <circle
        cx={0} cy={0} r={s * 0.85}
        fill={c.glow}
        style={{
          filter: `blur(${s * 0.3}px)`,
        }}
      />
      {/* Selection ring */}
      {isSelected && (
        <circle
          cx={0} cy={0} r={s * 0.95}
          fill="none"
          stroke={c.primary}
          strokeWidth="2"
          strokeDasharray="4 3"
          opacity="0.9"
        />
      )}
      {children}
    </g>
  );
}

// ─────────────────────────────────────────────────────────────
// DOCUMENT — stack of papers with folded corner
// ─────────────────────────────────────────────────────────────
export function DocumentNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const w = size, h = size * 1.3;
  const fold = size * 0.28;
  return (
    <ArtifactWrapper {...props}>
      {/* Shadow paper (back) */}
      <rect x={-w/2 + 4} y={-h/2 + 4} width={w} height={h} rx="2"
        fill={c.secondary} opacity="0.5" />
      {/* Middle paper */}
      <rect x={-w/2 + 2} y={-h/2 + 2} width={w} height={h} rx="2"
        fill={c.secondary} opacity="0.7" />
      {/* Main paper body */}
      <path
        d={`M${-w/2},${-h/2 + fold} L${-w/2},${h/2} L${w/2},${h/2} L${w/2},${-h/2} L${-w/2 + fold},${-h/2} Z`}
        fill={c.primary} fillOpacity="0.15" stroke={c.primary} strokeWidth="1.5"
      />
      {/* Folded corner */}
      <path
        d={`M${-w/2 + fold},${-h/2} L${-w/2 + fold},${-h/2 + fold} L${-w/2},${-h/2 + fold}`}
        fill={c.secondary} stroke={c.primary} strokeWidth="1"
      />
      {/* Text lines */}
      <line x1={-w/2 + 6} y1={-h/2 + fold + 6} x2={w/2 - 4} y2={-h/2 + fold + 6}
        stroke={c.primary} strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
      <line x1={-w/2 + 6} y1={-h/2 + fold + 12} x2={w/2 - 4} y2={-h/2 + fold + 12}
        stroke={c.primary} strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
      <line x1={-w/2 + 6} y1={-h/2 + fold + 18} x2={w/2 - 10} y2={-h/2 + fold + 18}
        stroke={c.primary} strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// DOCUMENT WITH ISSUE — paper + red torn corner + exclamation
// ─────────────────────────────────────────────────────────────
export function DocumentIssueNode(props: ArtifactProps) {
  const { size = 28 } = props;
  const c = STATE['attention'];
  const w = size, h = size * 1.3;
  const fold = size * 0.28;
  return (
    <ArtifactWrapper {...props} state="attention">
      {/* Paper body */}
      <path
        d={`M${-w/2},${-h/2 + fold} L${-w/2},${h/2} L${w/2},${h/2} L${w/2},${-h/2} L${-w/2 + fold},${-h/2} Z`}
        fill={c.primary} fillOpacity="0.12" stroke={c.primary} strokeWidth="1.5"
      />
      {/* Torn/damaged corner — jagged red */}
      <path
        d={`M${-w/2 + fold},${-h/2} L${-w/2 + fold - 3},${-h/2 + fold/2} L${-w/2 + fold/2},${-h/2 + fold - 3} L${-w/2},${-h/2 + fold}`}
        fill="#ff3d3d" fillOpacity="0.8" stroke="#ff3d3d" strokeWidth="1"
      />
      {/* Exclamation mark */}
      <line x1={0} y1={-h/2 + fold + 4} x2={0} y2={h/2 - 10}
        stroke={c.primary} strokeWidth="3" strokeLinecap="round" />
      <circle cx={0} cy={h/2 - 5} r="2.5" fill={c.primary} />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// RUBBER STAMP — phase approval / completion
// ─────────────────────────────────────────────────────────────
export function StampNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const r = size * 0.7;
  return (
    <ArtifactWrapper {...props}>
      {/* Stamp handle */}
      <rect x={-size * 0.18} y={-r - size * 0.35} width={size * 0.36} height={size * 0.35} rx="3"
        fill={c.secondary} stroke={c.primary} strokeWidth="1.5" />
      <rect x={-size * 0.28} y={-r - size * 0.12} width={size * 0.56} height={size * 0.12} rx="2"
        fill={c.secondary} stroke={c.primary} strokeWidth="1" />
      {/* Stamp pad */}
      <ellipse cx={0} cy={r * 0.1} rx={r} ry={r * 0.45}
        fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="2" />
      {/* APPROVED text as lines */}
      <line x1={-r * 0.55} y1={r * 0.05} x2={r * 0.55} y2={r * 0.05}
        stroke={c.primary} strokeWidth="3" strokeLinecap="round" opacity="0.9" />
      <line x1={-r * 0.4} y1={r * 0.2} x2={r * 0.4} y2={r * 0.2}
        stroke={c.primary} strokeWidth="2" strokeLinecap="round" opacity="0.6" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// COIN — payment received
// ─────────────────────────────────────────────────────────────
export function CoinNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const r = size * 0.72;
  return (
    <ArtifactWrapper {...props}>
      {/* Coin edge (3D effect) */}
      <ellipse cx={size * 0.06} cy={size * 0.06} rx={r} ry={r}
        fill={c.secondary} />
      {/* Coin face */}
      <circle cx={0} cy={0} r={r}
        fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="2.5" />
      {/* Inner ring */}
      <circle cx={0} cy={0} r={r * 0.72}
        fill="none" stroke={c.primary} strokeWidth="1" opacity="0.5" />
      {/* Dollar sign */}
      <text x={0} y={size * 0.28} textAnchor="middle" fontSize={size * 0.6}
        fill={c.primary} fontWeight="bold" fontFamily="Georgia, serif">$</text>
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// CRACKED COIN — payment issue / aging
// ─────────────────────────────────────────────────────────────
export function CrackCoinNode(props: ArtifactProps) {
  const { size = 28 } = props;
  const c = STATE['attention'];
  const r = size * 0.72;
  return (
    <ArtifactWrapper {...props} state="attention">
      <circle cx={0} cy={0} r={r}
        fill={c.primary} fillOpacity="0.15" stroke={c.primary} strokeWidth="2.5" />
      <circle cx={0} cy={0} r={r * 0.72}
        fill="none" stroke={c.primary} strokeWidth="1" opacity="0.5" />
      <text x={0} y={size * 0.28} textAnchor="middle" fontSize={size * 0.6}
        fill={c.primary} fontWeight="bold" fontFamily="Georgia, serif">$</text>
      {/* Crack lines */}
      <path d={`M${-r * 0.1},${-r * 0.8} L${r * 0.15},${-r * 0.1} L${-r * 0.05},${r * 0.4} L${r * 0.2},${r * 0.8}`}
        fill="none" stroke="#ff3d3d" strokeWidth="2" strokeLinecap="round" />
      <path d={`M${r * 0.15},${-r * 0.1} L${r * 0.5},${r * 0.05}`}
        fill="none" stroke="#ff3d3d" strokeWidth="1.5" strokeLinecap="round" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// BRICK WALL — hard blocker
// ─────────────────────────────────────────────────────────────
export function WallNode(props: ArtifactProps) {
  const { size = 32 } = props;
  const c = STATE['blocked'];
  const w = size * 1.4, h = size * 1.1;
  const bw = w / 3, bh = h / 3;
  const rows = [
    [[-w/2, -h/2], [-w/2 + bw, -h/2], [-w/2 + bw*2, -h/2]],
    [[-w/2 + bw/2, -h/2 + bh], [-w/2 + bw/2 + bw, -h/2 + bh], [-w/2 + bw/2 + bw*2, -h/2 + bh]],
    [[-w/2, -h/2 + bh*2], [-w/2 + bw, -h/2 + bh*2], [-w/2 + bw*2, -h/2 + bh*2]],
  ];
  return (
    <ArtifactWrapper {...props} state="blocked">
      {rows.map((row, ri) =>
        row.map(([x, y], bi) => (
          <rect key={`${ri}-${bi}`}
            x={x} y={y} width={bw - 2} height={bh - 2} rx="1"
            fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="1.5"
          />
        ))
      )}
      {/* X mark overlay */}
      <line x1={-w * 0.3} y1={-h * 0.3} x2={w * 0.3} y2={h * 0.3}
        stroke="#ff3d3d" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
      <line x1={w * 0.3} y1={-h * 0.3} x2={-w * 0.3} y2={h * 0.3}
        stroke="#ff3d3d" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// MAGNIFYING GLASS — review / inspection
// ─────────────────────────────────────────────────────────────
export function MagnifierNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const r = size * 0.5;
  const handleLen = size * 0.55;
  const angle = Math.PI * 0.75;
  const hx = r * Math.cos(angle);
  const hy = r * Math.sin(angle);
  return (
    <ArtifactWrapper {...props}>
      {/* Lens */}
      <circle cx={0} cy={-size * 0.1} r={r}
        fill={c.primary} fillOpacity="0.12" stroke={c.primary} strokeWidth="2.5" />
      {/* Lens glint */}
      <circle cx={-r * 0.3} cy={-size * 0.1 - r * 0.3} r={r * 0.18}
        fill={c.primary} opacity="0.5" />
      {/* Handle */}
      <line
        x1={hx} y1={hy - size * 0.1}
        x2={hx + handleLen * Math.cos(angle)} y2={hy - size * 0.1 + handleLen * Math.sin(angle)}
        stroke={c.primary} strokeWidth="3.5" strokeLinecap="round"
      />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// CHECKMARK STAMP — complete / delivered
// ─────────────────────────────────────────────────────────────
export function CheckmarkNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const r = size * 0.72;
  return (
    <ArtifactWrapper {...props}>
      <circle cx={0} cy={0} r={r}
        fill={c.primary} fillOpacity="0.18" stroke={c.primary} strokeWidth="2.5" />
      <path
        d={`M${-r * 0.45},${r * 0.05} L${-r * 0.1},${r * 0.45} L${r * 0.5},${-r * 0.4}`}
        fill="none" stroke={c.primary} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"
      />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// CLOCK — SLA / time pressure
// ─────────────────────────────────────────────────────────────
export function ClockNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const r = size * 0.72;
  return (
    <ArtifactWrapper {...props}>
      {/* Clock face */}
      <circle cx={0} cy={0} r={r}
        fill={c.primary} fillOpacity="0.12" stroke={c.primary} strokeWidth="2.5" />
      {/* Hour markers */}
      {[0, 3, 6, 9].map(h => {
        const a = (h / 12) * Math.PI * 2 - Math.PI / 2;
        return (
          <line key={h}
            x1={Math.cos(a) * r * 0.72} y1={Math.sin(a) * r * 0.72}
            x2={Math.cos(a) * r * 0.88} y2={Math.sin(a) * r * 0.88}
            stroke={c.primary} strokeWidth="2" strokeLinecap="round"
          />
        );
      })}
      {/* Hour hand — pointing to ~10 o'clock */}
      <line x1={0} y1={0} x2={-r * 0.42} y2={-r * 0.42}
        stroke={c.primary} strokeWidth="2.5" strokeLinecap="round" />
      {/* Minute hand — pointing to ~2 o'clock */}
      <line x1={0} y1={0} x2={r * 0.52} y2={-r * 0.3}
        stroke={c.primary} strokeWidth="1.8" strokeLinecap="round" />
      {/* Center dot */}
      <circle cx={0} cy={0} r={2.5} fill={c.primary} />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// ALERT TRIANGLE — gap / attention needed
// ─────────────────────────────────────────────────────────────
export function AlertNode(props: ArtifactProps) {
  const { size = 28 } = props;
  const c = STATE['attention'];
  const h = size * 1.1;
  const w = size * 1.2;
  return (
    <ArtifactWrapper {...props} state="attention">
      {/* Triangle */}
      <path
        d={`M0,${-h/2} L${w/2},${h/2} L${-w/2},${h/2} Z`}
        fill={c.primary} fillOpacity="0.15" stroke={c.primary} strokeWidth="2.5" strokeLinejoin="round"
      />
      {/* Exclamation */}
      <line x1={0} y1={-h/2 + h * 0.22} x2={0} y2={h/2 - h * 0.28}
        stroke={c.primary} strokeWidth="3" strokeLinecap="round" />
      <circle cx={0} cy={h/2 - h * 0.14} r="2.8" fill={c.primary} />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// GEAR — processing / in-progress
// ─────────────────────────────────────────────────────────────
export function GearNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const r = size * 0.55;
  const teeth = 8;
  const outerR = r * 1.35;
  const innerR = r;
  const toothW = (Math.PI * 2) / teeth;

  const gearPath = Array.from({ length: teeth }).map((_, i) => {
    const a1 = (i / teeth) * Math.PI * 2 - toothW * 0.35;
    const a2 = (i / teeth) * Math.PI * 2 + toothW * 0.35;
    const a3 = ((i + 0.5) / teeth) * Math.PI * 2 - toothW * 0.2;
    const a4 = ((i + 0.5) / teeth) * Math.PI * 2 + toothW * 0.2;
    return [
      `L${Math.cos(a1) * innerR},${Math.sin(a1) * innerR}`,
      `L${Math.cos(a1) * outerR},${Math.sin(a1) * outerR}`,
      `L${Math.cos(a2) * outerR},${Math.sin(a2) * outerR}`,
      `L${Math.cos(a2) * innerR},${Math.sin(a2) * innerR}`,
      `L${Math.cos(a3) * innerR},${Math.sin(a3) * innerR}`,
      `L${Math.cos(a4) * innerR},${Math.sin(a4) * innerR}`,
    ].join(' ');
  }).join(' ');

  return (
    <ArtifactWrapper {...props}>
      <g className="vio-gear-spin">
        <path d={`M${Math.cos(0) * innerR},${Math.sin(0) * innerR} ${gearPath} Z`}
          fill={c.primary} fillOpacity="0.15" stroke={c.primary} strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx={0} cy={0} r={r * 0.42}
          fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="1.5" />
        <circle cx={0} cy={0} r={r * 0.18} fill={c.primary} />
      </g>
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// SCALE / BALANCE — compliance / legal review
// ─────────────────────────────────────────────────────────────
export function ScaleNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const armW = size * 1.1;
  const panR = size * 0.28;
  // Slightly tilted to show imbalance when attention
  const tilt = state === 'attention' ? 8 : 0;
  return (
    <ArtifactWrapper {...props}>
      {/* Pole */}
      <line x1={0} y1={-size * 0.55} x2={0} y2={size * 0.55}
        stroke={c.primary} strokeWidth="2" strokeLinecap="round" />
      {/* Base */}
      <line x1={-size * 0.3} y1={size * 0.55} x2={size * 0.3} y2={size * 0.55}
        stroke={c.primary} strokeWidth="2.5" strokeLinecap="round" />
      {/* Arm (tilted) */}
      <g transform={`rotate(${tilt})`}>
        <line x1={-armW/2} y1={-size * 0.15} x2={armW/2} y2={-size * 0.15}
          stroke={c.primary} strokeWidth="2" strokeLinecap="round" />
        {/* Left pan strings */}
        <line x1={-armW/2} y1={-size * 0.15} x2={-armW/2 - panR * 0.3} y2={size * 0.1}
          stroke={c.primary} strokeWidth="1" />
        <line x1={-armW/2} y1={-size * 0.15} x2={-armW/2 + panR * 0.3} y2={size * 0.1}
          stroke={c.primary} strokeWidth="1" />
        <path d={`M${-armW/2 - panR},${size * 0.1} Q${-armW/2},${size * 0.32} ${-armW/2 + panR},${size * 0.1}`}
          fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="1.5" />
        {/* Right pan strings */}
        <line x1={armW/2} y1={-size * 0.15} x2={armW/2 - panR * 0.3} y2={size * 0.1}
          stroke={c.primary} strokeWidth="1" />
        <line x1={armW/2} y1={-size * 0.15} x2={armW/2 + panR * 0.3} y2={size * 0.1}
          stroke={c.primary} strokeWidth="1" />
        <path d={`M${armW/2 - panR},${size * 0.1} Q${armW/2},${size * 0.32} ${armW/2 + panR},${size * 0.1}`}
          fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="1.5" />
      </g>
      {/* Pivot dot */}
      <circle cx={0} cy={-size * 0.15} r={3} fill={c.primary} />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// ROCKET — delivery / launch
// ─────────────────────────────────────────────────────────────
export function RocketNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const h = size * 1.3;
  const w = size * 0.7;
  return (
    <ArtifactWrapper {...props}>
      {/* Rocket body */}
      <path
        d={`M0,${-h/2} C${w/2},${-h/4} ${w/2},${h/6} ${w/3},${h/3} L${-w/3},${h/3} C${-w/2},${h/6} ${-w/2},${-h/4} 0,${-h/2} Z`}
        fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="2"
      />
      {/* Window */}
      <circle cx={0} cy={-h * 0.08} r={w * 0.28}
        fill={c.primary} fillOpacity="0.3" stroke={c.primary} strokeWidth="1.5" />
      {/* Left fin */}
      <path d={`M${-w/3},${h/4} L${-w * 0.7},${h/2} L${-w/3},${h/3} Z`}
        fill={c.primary} fillOpacity="0.3" stroke={c.primary} strokeWidth="1.5" />
      {/* Right fin */}
      <path d={`M${w/3},${h/4} L${w * 0.7},${h/2} L${w/3},${h/3} Z`}
        fill={c.primary} fillOpacity="0.3" stroke={c.primary} strokeWidth="1.5" />
      {/* Exhaust flame */}
      {state !== 'inactive' && (
        <>
          <path d={`M${-w/4},${h/3} Q0,${h/2 + size * 0.3} ${w/4},${h/3}`}
            fill="#ff6b35" fillOpacity="0.7" />
          <path d={`M${-w/6},${h/3} Q0,${h/2 + size * 0.15} ${w/6},${h/3}`}
            fill="#ffd700" fillOpacity="0.9" />
        </>
      )}
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// FLAG ON POLE — milestone reached
// ─────────────────────────────────────────────────────────────
export function MilestoneFlagNode(props: ArtifactProps) {
  const { size = 28 } = props;
  const c = STATE['milestone'];
  const poleH = size * 1.2;
  const flagW = size * 0.75;
  const flagH = size * 0.55;
  return (
    <ArtifactWrapper {...props} state="milestone">
      {/* Pole */}
      <line x1={-size * 0.1} y1={-poleH/2} x2={-size * 0.1} y2={poleH/2}
        stroke={c.primary} strokeWidth="2.5" strokeLinecap="round" />
      {/* Flag */}
      <path
        d={`M${-size * 0.1},${-poleH/2} L${-size * 0.1 + flagW},${-poleH/2 + flagH/2} L${-size * 0.1},${-poleH/2 + flagH} Z`}
        fill={c.primary} fillOpacity="0.85" stroke={c.primary} strokeWidth="1"
      />
      {/* Star on flag */}
      <text x={-size * 0.1 + flagW * 0.35} y={-poleH/2 + flagH * 0.65}
        textAnchor="middle" fontSize={size * 0.3} fill="#1a1a2e">★</text>
      {/* Base */}
      <line x1={-size * 0.35} y1={poleH/2} x2={size * 0.15} y2={poleH/2}
        stroke={c.primary} strokeWidth="2.5" strokeLinecap="round" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// BROKEN CHAIN — dependency blocked
// ─────────────────────────────────────────────────────────────
export function BrokenChainNode(props: ArtifactProps) {
  const { size = 28 } = props;
  const c = STATE['blocked'];
  const linkW = size * 0.45;
  const linkH = size * 0.28;
  return (
    <ArtifactWrapper {...props} state="blocked">
      {/* Top chain link */}
      <ellipse cx={0} cy={-size * 0.42} rx={linkW/2} ry={linkH/2}
        fill="none" stroke={c.primary} strokeWidth="3" />
      {/* Bottom chain link */}
      <ellipse cx={0} cy={size * 0.42} rx={linkW/2} ry={linkH/2}
        fill="none" stroke={c.primary} strokeWidth="3" />
      {/* Break gap with jagged edges */}
      <path d={`M${-size * 0.12},${-size * 0.12} L${-size * 0.05},${0} L${size * 0.05},${0} L${size * 0.12},${size * 0.12}`}
        fill="none" stroke="#ff3d3d" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="2 2" />
      {/* Spark marks */}
      <line x1={-size * 0.25} y1={-size * 0.05} x2={-size * 0.15} y2={size * 0.05}
        stroke="#ffb800" strokeWidth="1.5" strokeLinecap="round" />
      <line x1={size * 0.15} y1={-size * 0.05} x2={size * 0.25} y2={size * 0.05}
        stroke="#ffb800" strokeWidth="1.5" strokeLinecap="round" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// POINTING FINGER — decision / next action required
// ─────────────────────────────────────────────────────────────
export function DecisionNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  return (
    <ArtifactWrapper {...props}>
      {/* Hand/finger pointing right */}
      <path
        d={`
          M${-size * 0.55},${size * 0.15}
          L${-size * 0.55},${-size * 0.05}
          L${-size * 0.1},${-size * 0.05}
          L${-size * 0.1},${-size * 0.42}
          Q${-size * 0.1},${-size * 0.58} ${size * 0.05},${-size * 0.58}
          Q${size * 0.2},${-size * 0.58} ${size * 0.2},${-size * 0.42}
          L${size * 0.2},${-size * 0.05}
          L${size * 0.55},${-size * 0.05}
          Q${size * 0.72},${-size * 0.05} ${size * 0.72},${size * 0.1}
          Q${size * 0.72},${size * 0.25} ${size * 0.55},${size * 0.25}
          L${-size * 0.55},${size * 0.25}
          Z
        `}
        fill={c.primary} fillOpacity="0.2" stroke={c.primary} strokeWidth="1.8" strokeLinejoin="round"
      />
      {/* Fingernail detail */}
      <ellipse cx={size * 0.05} cy={-size * 0.48} rx={size * 0.1} ry={size * 0.06}
        fill={c.primary} fillOpacity="0.4" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// FOLDER — case / file collection
// ─────────────────────────────────────────────────────────────
export function FolderNode(props: ArtifactProps) {
  const { size = 28, state } = props;
  const c = STATE[state];
  const w = size * 1.3, h = size * 1.0;
  const tabW = w * 0.38, tabH = h * 0.2;
  return (
    <ArtifactWrapper {...props}>
      {/* Folder tab */}
      <path
        d={`M${-w/2},${-h/2 + tabH} L${-w/2},${-h/2} L${-w/2 + tabW},${-h/2} Q${-w/2 + tabW + tabH * 0.5},${-h/2} ${-w/2 + tabW + tabH},${-h/2 + tabH} Z`}
        fill={c.secondary} stroke={c.primary} strokeWidth="1.5"
      />
      {/* Folder body */}
      <rect x={-w/2} y={-h/2 + tabH} width={w} height={h - tabH} rx="2"
        fill={c.primary} fillOpacity="0.15" stroke={c.primary} strokeWidth="2"
      />
      {/* Papers sticking out */}
      <rect x={-w/2 + 6} y={-h/2 + tabH - 4} width={w * 0.3} height={8} rx="1"
        fill={c.primary} fillOpacity="0.5" />
      <rect x={-w/2 + 6 + w * 0.15} y={-h/2 + tabH - 6} width={w * 0.25} height={8} rx="1"
        fill={c.primary} fillOpacity="0.35" />
    </ArtifactWrapper>
  );
}

// ─────────────────────────────────────────────────────────────
// COMPANY ORB — identity / entity anchor
// ─────────────────────────────────────────────────────────────
export function CompanyOrb({ initials, size = 44, state, onClick, isSelected }: {
  initials: string;
  size?: number;
  state: ArtifactProps['state'];
  onClick?: () => void;
  isSelected?: boolean;
}) {
  const c = STATE[state];
  const r = size;
  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }} role="button" data-hint="Company Identity">
      {/* Outer glow ring */}
      <circle cx={0} cy={0} r={r + 8}
        fill="none" stroke={c.primary} strokeWidth="1"
        strokeDasharray={isSelected ? 'none' : '4 3'}
        opacity="0.5"
      />
      {/* Orb body */}
      <circle cx={0} cy={0} r={r}
        fill={c.primary} fillOpacity="0.12" stroke={c.primary} strokeWidth="2.5"
      />
      {/* Inner glow */}
      <circle cx={0} cy={0} r={r * 0.72}
        fill={c.primary} fillOpacity="0.08"
      />
      {/* Highlight */}
      <ellipse cx={-r * 0.28} cy={-r * 0.28} rx={r * 0.28} ry={r * 0.18}
        fill={c.primary} fillOpacity="0.25" transform="rotate(-30)"
      />
      {/* Initials */}
      <text x={0} y={size * 0.38} textAnchor="middle"
        fontSize={size * 0.55} fontWeight="800"
        fill={c.primary} fontFamily="'Space Grotesk', sans-serif"
        letterSpacing="1"
      >{initials}</text>
    </g>
  );
}

// ─────────────────────────────────────────────────────────────
// ARTIFACT REGISTRY — maps node type to component
// ─────────────────────────────────────────────────────────────
export type ArtifactType =
  | 'document' | 'document-issue' | 'stamp' | 'coin' | 'coin-crack'
  | 'wall' | 'magnifier' | 'checkmark' | 'clock' | 'alert'
  | 'gear' | 'scale' | 'rocket' | 'flag' | 'chain-broken'
  | 'decision' | 'folder';

export function renderArtifact(type: ArtifactType, props: ArtifactProps) {
  switch (type) {
    case 'document':       return <DocumentNode {...props} />;
    case 'document-issue': return <DocumentIssueNode {...props} />;
    case 'stamp':          return <StampNode {...props} />;
    case 'coin':           return <CoinNode {...props} />;
    case 'coin-crack':     return <CrackCoinNode {...props} />;
    case 'wall':           return <WallNode {...props} />;
    case 'magnifier':      return <MagnifierNode {...props} />;
    case 'checkmark':      return <CheckmarkNode {...props} />;
    case 'clock':          return <ClockNode {...props} />;
    case 'alert':          return <AlertNode {...props} />;
    case 'gear':           return <GearNode {...props} />;
    case 'scale':          return <ScaleNode {...props} />;
    case 'rocket':         return <RocketNode {...props} />;
    case 'flag':           return <MilestoneFlagNode {...props} />;
    case 'chain-broken':   return <BrokenChainNode {...props} />;
    case 'decision':       return <DecisionNode {...props} />;
    case 'folder':         return <FolderNode {...props} />;
    default:               return <DocumentNode {...props} />;
  }
}

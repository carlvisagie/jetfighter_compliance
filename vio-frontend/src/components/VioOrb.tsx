/**
 * VIO COMPANY ORB — Pure Visual Micro-Dashboard
 * ============================================================
 * ZERO TEXT on the orb face. Every pixel tells a story.
 *
 * Expanded panel renders as a React Portal (fixed position, always in viewport).
 * Three zones:
 *   LEFT  → Visual grammar legend (compact hover-chips + mini ring diagram)
 *   CENTER → The orb itself (unchanged)
 *   RIGHT → Identity panel: clickable contacts + expandable bar stories
 *
 * RING ENCODING:
 *   Ring 1 (outer) = journey completion (clockwise arc fill)
 *   Ring 2 (mid)   = payment health (green→amber→red)
 *   Ring 3 (inner) = compliance status (teal→amber→red)
 *   Fill opacity   = engagement age (darker = older)
 *   Orbit red dots = active blockers (each = 1)
 *   Orbit amber    = attention items (each = 1)
 *   Pulse speed    = urgency level
 * ============================================================
 */

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { VioOrganism } from '../vio-types';
import { STATE_COLORS } from '../vio-types';
import { renderArtifact } from './VioArtifacts';
import type { ArtifactType } from './VioArtifacts';

interface VioOrbProps {
  organism: VioOrganism;
  size?: number;
}

// Draw a partial arc path centered at 0,0
function arcPath(r: number, startDeg: number, endDeg: number): string {
  const toRad = (d: number) => (d - 90) * (Math.PI / 180);
  const x1 = r * Math.cos(toRad(startDeg));
  const y1 = r * Math.sin(toRad(startDeg));
  const x2 = r * Math.cos(toRad(endDeg));
  const y2 = r * Math.sin(toRad(endDeg));
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2}`;
}

function fractionToArc(fraction: number): [number, number] {
  const GAP = 24;
  const start = GAP / 2;
  const sweep = (360 - GAP) * Math.max(0, Math.min(1, fraction));
  return [start, start + sweep];
}

// Artifact legend items — each shows the REAL artifact SVG + hover label
const ARTIFACT_LEGEND: Array<{ type: ArtifactType; state: 'healthy'|'attention'|'blocked'|'complete'|'processing'|'inactive'|'milestone'; label: string; story: string }> = [
  { type: 'folder',         state: 'healthy',    label: 'Case / Intake',       story: 'New case or file opened' },
  { type: 'document',       state: 'complete',   label: 'Document',            story: 'Filing, record, or paper' },
  { type: 'document-issue', state: 'attention',  label: 'Document Issue',      story: 'Missing, incorrect, or flagged doc' },
  { type: 'magnifier',      state: 'processing', label: 'Review',              story: 'Under inspection or attorney review' },
  { type: 'scale',          state: 'healthy',    label: 'Compliance',          story: 'Legal or regulatory check' },
  { type: 'flag',           state: 'milestone',  label: 'Milestone',           story: 'Key stage reached' },
  { type: 'clock',          state: 'attention',  label: 'SLA / Time Pressure', story: 'Deadline approaching or overdue' },
  { type: 'coin',           state: 'complete',   label: 'Payment Received',    story: 'Funds collected' },
  { type: 'coin-crack',     state: 'attention',  label: 'Payment Issue',       story: 'Aging invoice or partial payment' },
  { type: 'wall',           state: 'blocked',    label: 'Hard Blocker',        story: 'Work cannot proceed' },
  { type: 'chain-broken',   state: 'blocked',    label: 'Dependency Break',    story: 'External dependency failed' },
  { type: 'stamp',          state: 'complete',   label: 'Approved / Closed',   story: 'Phase signed off and complete' },
  { type: 'decision',       state: 'processing', label: 'Decision Point',      story: 'Action or choice required' },
  { type: 'rocket',         state: 'complete',   label: 'Delivery / Launch',   story: 'Case delivered or product launched' },
];

// Artifact legend row — real SVG artifact + hover label
function ArtifactLegendRow({ item }: { item: typeof ARTIFACT_LEGEND[0] }) {
  const [hovered, setHovered] = React.useState(false);
  const ARTIFACT_SIZE = 11;
  const SVG_BOX = ARTIFACT_SIZE * 3.2;
  return (
    <div
      style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 4 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Real artifact SVG — same component as the spine */}
      <svg
        width={SVG_BOX} height={SVG_BOX}
        viewBox={`${-SVG_BOX/2} ${-SVG_BOX/2} ${SVG_BOX} ${SVG_BOX}`}
        style={{ flexShrink: 0, overflow: 'visible' }}
      >
        {renderArtifact(item.type, { size: ARTIFACT_SIZE, state: item.state })}
      </svg>
      {/* Label — always visible, small */}
      <span style={{
        fontSize: 8, fontFamily: "'JetBrains Mono', monospace",
        color: hovered ? '#e2e8f0' : '#64748b',
        whiteSpace: 'nowrap', lineHeight: 1, transition: 'color 0.12s',
      }}>{item.label}</span>
      {/* Tooltip — story on hover */}
      {hovered && (
        <div style={{
          position: 'fixed', zIndex: 99999,
          background: '#0a0f1e', border: '1px solid #334155',
          borderRadius: 6, padding: '5px 8px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.8)',
          pointerEvents: 'none', whiteSpace: 'nowrap',
          transform: 'translate(8px, -50%)',
          fontSize: 9, color: '#94a3b8',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {item.story}
        </div>
      )}
    </div>
  );
}

// Expandable story bar — visual bar + click to reveal full narrative
function StoryBar({
  icon, label, color, fraction, story, detail,
}: {
  icon: string; label: string; color: string;
  fraction: number; story: string; detail: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="rounded-lg overflow-hidden transition-all duration-200"
      style={{ background: open ? `${color}10` : 'transparent', border: `1px solid ${open ? color + '30' : 'transparent'}` }}
    >
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-white/5 transition-colors text-left"
      >
        <span className="text-base leading-none">{icon}</span>
        <div className="flex-1 relative h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
            style={{ width: `${Math.round(fraction * 100)}%`, background: color }}
          />
          <div
            className="absolute top-0 bottom-0 w-0.5 rounded-full"
            style={{ left: `${Math.round(fraction * 100)}%`, background: color, boxShadow: `0 0 4px ${color}` }}
          />
        </div>
        <span className="text-xs font-mono font-bold w-8 text-right" style={{ color }}>
          {Math.round(fraction * 100)}%
        </span>
        <span className="text-xs transition-transform duration-200" style={{ color, transform: open ? 'rotate(180deg)' : 'none' }}>▾</span>
      </button>
      {open && (
        <div className="px-3 pb-3">
          <div className="text-xs font-mono font-bold mb-1" style={{ color }}>{label}</div>
          <div className="text-xs text-slate-400 leading-relaxed mb-1">{story}</div>
          <div
            className="text-xs rounded px-2 py-1.5 leading-relaxed"
            style={{ background: `${color}12`, color: '#cbd5e1', borderLeft: `2px solid ${color}60` }}
          >{detail}</div>
        </div>
      )}
    </div>
  );
}

export function VioOrb({ organism, size = 52 }: VioOrbProps) {
  const [expanded, setExpanded] = useState(false);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0 });
  const orbRef = useRef<SVGGElement>(null);
  const anchorRef = useRef<SVGCircleElement>(null);

  const overallColor = STATE_COLORS[organism.overallState];

  // Derive visual data
  const invoiced  = parseFloat(organism.kpis.find(k => k.label === 'Invoiced')?.value?.replace(/[$,]/g, '') || '0');
  const collected = parseFloat(organism.kpis.find(k => k.label === 'Collected')?.value?.replace(/[$,]/g, '') || '0');
  const payFraction = invoiced > 0 ? collected / invoiced : 1;
  const payColor = payFraction >= 0.95 ? '#4ade80' : payFraction >= 0.65 ? '#ffb800' : '#ff3d3d';

  const spineNodes = organism.nodes.filter(n => !n.isBranch);
  const doneNodes  = spineNodes.filter(n => n.state === 'complete' || n.state === 'milestone');
  const completionFraction = spineNodes.length > 0 ? doneNodes.length / spineNodes.length : 0;

  const compKpi = organism.kpis.find(k =>
    k.label.toLowerCase().includes('compliance') || k.label.toLowerCase().includes('legal')
  );
  const compColor = compKpi?.valueColor || '#38bdf8';
  const compFraction = compKpi?.value?.toLowerCase().includes('hold') ? 0.25
    : compKpi?.value?.toLowerCase().includes('monitor') ? 0.65 : 0.92;

  const blockerNodes   = spineNodes.filter(n => n.state === 'blocked');
  const attentionNodes = spineNodes.filter(n => n.state === 'attention');

  const daysKpi = organism.kpis.find(k => k.label.toLowerCase().includes('days'));
  const daysActive = parseInt(daysKpi?.value || '0') || 0;
  const ageFillOpacity = Math.min(0.28, 0.05 + (daysActive / 60) * 0.23);

  const R1 = size - 3;
  const R2 = size - 11;
  const R3 = size - 19;
  const RI = size - 28;

  const [a1s, a1e] = fractionToArc(completionFraction);
  const [a2s, a2e] = fractionToArc(payFraction);
  const [a3s, a3e] = fractionToArc(compFraction);

  const urgencyWidth = organism.overallState === 'blocked' ? 5
    : organism.overallState === 'attention' ? 4 : 3;

  const pulseAnim = organism.overallState === 'blocked' ? 'vio-orb-blocked'
    : organism.overallState === 'attention' ? 'vio-orb-attention'
    : organism.overallState === 'healthy' || organism.overallState === 'processing' ? 'vio-orb-healthy'
    : '';

  const agingKpi = organism.kpis.find(k => k.label.toLowerCase().includes('aging') || k.label.toLowerCase().includes('balance'));
  const payDetail = invoiced > 0
    ? `${organism.kpis.find(k => k.label === 'Collected')?.value || '—'} collected of ${organism.kpis.find(k => k.label === 'Invoiced')?.value || '—'} invoiced${agingKpi ? ` · ${agingKpi.value} outstanding` : ''}`
    : 'No invoice data';

  const compDetail = compKpi
    ? `${compKpi.icon} ${compKpi.label}: ${compKpi.value}`
    : 'Compliance status not tracked';

  const completionDetail = `${doneNodes.length} of ${spineNodes.length} stages complete · ${spineNodes.filter(n => n.state === 'inactive').length} not started · ${blockerNodes.length} blocked`;

  // Compute panel position using SVG coordinate transform matrix
  // This is the only reliable way to get the orb's screen position from inside an SVG
  const computePos = (legendOpen: boolean) => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    // Get the SVG element that owns this element
    const svg = anchor.ownerSVGElement;
    if (!svg) return;
    // Create an SVG point at the orb center (0,0 in local coords)
    const pt = svg.createSVGPoint();
    pt.x = 0;
    pt.y = 0;
    // Transform to screen coordinates using the cumulative transform matrix
    const ctm = anchor.getScreenCTM();
    if (!ctm) return;
    const screenPt = pt.matrixTransform(ctm);
    // screenPt.x, screenPt.y is now the exact screen center of the orb
    const orbScreenX = screenPt.x;
    const orbScreenY = screenPt.y;
    const identW = 252;
    const legendW = legendOpen ? 148 + 8 : 0;
    const totalW = identW + legendW;
    const panelH = 340;
    // Open to the right of the orb by default
    let left = orbScreenX + size + 16;
    let top  = orbScreenY - 80;
    // Flip left if panel would overflow right edge
    if (left + totalW > window.innerWidth - 12) {
      left = orbScreenX - size - totalW - 16;
    }
    if (left < 8) left = 8;
    if (top + panelH > window.innerHeight - 12) top = window.innerHeight - panelH - 12;
    if (top < 8) top = 8;
    setPanelPos({ top, left });
  };

  const handleOrbClick = (e: React.MouseEvent<SVGGElement>) => {
    if (!expanded) {
      // Use the actual mouse click position — always accurate, no SVG math needed
      const identW = 252;
      const legendW = 148 + 8;
      const totalW = identW + legendW;
      const panelH = 340;
      let left = e.clientX + size + 12;
      let top  = e.clientY - 80;
      if (left + totalW > window.innerWidth - 12) left = e.clientX - size - totalW - 12;
      if (left < 8) left = 8;
      if (top + panelH > window.innerHeight - 12) top = window.innerHeight - panelH - 12;
      if (top < 8) top = 8;
      setPanelPos({ top, left });
    }
    setExpanded(e2 => !e2);
  };

  // Close on outside click
  useEffect(() => {
    if (!expanded) return;
    const handler = (e: MouseEvent) => {
      const panel = document.getElementById(`vio-panel-${organism.id}`);
      const orbEl = orbRef.current;
      if (panel && !panel.contains(e.target as Node) && orbEl && !orbEl.contains(e.target as Node)) {
        setExpanded(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [expanded, organism.id]);

  const svgSize = size * 2 + 20;

  return (
    <g ref={orbRef}>
      {/* Invisible anchor circle — used for getBoundingClientRect to get exact orb screen position */}
      <circle ref={anchorRef} cx={0} cy={0} r={size} fill="transparent" stroke="none" pointerEvents="none" />

      {/* ── ORB SVG FACE ── */}
      <g onClick={handleOrbClick} style={{ cursor: 'pointer' }} className={pulseAnim}>
        <title>{organism.name} · {organism.overallState} · {Math.round(completionFraction * 100)}% complete · {blockerNodes.length + attentionNodes.length} open items — click to expand</title>

        {/* Deep glow halo */}
        <circle cx={0} cy={0} r={R1 + 10}
          fill={overallColor} fillOpacity="0.04"
          style={{ filter: 'blur(8px)' }}
        />
        {/* Base plate */}
        <circle cx={0} cy={0} r={R1}
          fill="#060a18"
          stroke={overallColor} strokeWidth="0.5" strokeOpacity="0.2"
        />
        {/* Ring 1: Completion */}
        <circle cx={0} cy={0} r={R1} fill="none" stroke={overallColor} strokeWidth={urgencyWidth} strokeOpacity="0.1" />
        {completionFraction > 0.01 && (
          <path d={arcPath(R1, a1s, a1e)} fill="none" stroke={overallColor} strokeWidth={urgencyWidth} strokeLinecap="round" />
        )}
        {/* Ring 2: Payment */}
        <circle cx={0} cy={0} r={R2} fill="none" stroke={payColor} strokeWidth="2.5" strokeOpacity="0.1" />
        {payFraction > 0.01 && (
          <path d={arcPath(R2, a2s, a2e)} fill="none" stroke={payColor} strokeWidth="2.5" strokeLinecap="round" />
        )}
        {/* Ring 3: Compliance */}
        <circle cx={0} cy={0} r={R3} fill="none" stroke={compColor} strokeWidth="2" strokeOpacity="0.1" />
        {compFraction > 0.01 && (
          <path d={arcPath(R3, a3s, a3e)} fill="none" stroke={compColor} strokeWidth="2" strokeLinecap="round" />
        )}
        {/* Inner circle */}
        <circle cx={0} cy={0} r={RI}
          fill={overallColor} fillOpacity={ageFillOpacity}
          stroke={overallColor} strokeWidth="1" strokeOpacity="0.35"
        />
        {/* Initials */}
        <text x={0} y={size * 0.14}
          textAnchor="middle" dominantBaseline="middle"
          fontSize={size * 0.42} fontWeight="900"
          fill={overallColor}
          fontFamily="'Space Grotesk', sans-serif"
          letterSpacing="1"
        >{organism.initials}</text>
        {/* Center state dot */}
        <circle cx={0} cy={RI * 0.55} r={3} fill={overallColor} opacity="0.8" />

        {/* Blocker orbit dots */}
        {blockerNodes.map((_, i) => {
          const angle = -30 + i * 22;
          const rad = (angle - 90) * (Math.PI / 180);
          return (
            <circle key={`b${i}`}
              cx={(R1 + 5) * Math.cos(rad)} cy={(R1 + 5) * Math.sin(rad)}
              r={4} fill="#ff3d3d" opacity="0.95">
              <animate attributeName="opacity" values="0.95;0.3;0.95" dur="0.8s" repeatCount="indefinite" />
            </circle>
          );
        })}
        {/* Attention orbit dots */}
        {attentionNodes.map((_, i) => {
          const angle = -150 + i * 22;
          const rad = (angle - 90) * (Math.PI / 180);
          return (
            <circle key={`a${i}`}
              cx={(R1 + 5) * Math.cos(rad)} cy={(R1 + 5) * Math.sin(rad)}
              r={3.5} fill="#ffb800" opacity="0.85">
              <animate attributeName="opacity" values="0.85;0.35;0.85" dur="1.6s" repeatCount="indefinite" />
            </circle>
          );
        })}
        {/* Selection ring */}
        {expanded && (
          <circle cx={0} cy={0} r={R1 + 4}
            fill="none" stroke={overallColor}
            strokeWidth="1.5" strokeDasharray="5 3" opacity="0.7"
          />
        )}
      </g>

      {/* ── EXPANDED PANEL — React Portal, always in viewport ── */}
      {expanded && createPortal(
        <div
          id={`vio-panel-${organism.id}`}
          style={{
            position: 'fixed',
            top: panelPos.top,
            left: panelPos.left,
            zIndex: 9999,
            display: 'flex',
            gap: 8,
            fontFamily: "'Space Grotesk', sans-serif",
            animation: 'vio-panel-in 0.18s cubic-bezier(0.23,1,0.32,1)',
          }}
        >
          {/* ── LEFT: LEGEND PANEL — always visible when panel open ── */}
          {true && (
            <div style={{
              width: 172,
              background: '#060a18',
              border: `1px solid ${overallColor}30`,
              borderRadius: 8,
              padding: '7px 8px',
              boxShadow: `0 0 24px rgba(0,0,0,0.8), 0 0 18px ${overallColor}15`,
              flexShrink: 0,
            }}>
              <div style={{
                fontSize: 7, fontFamily: "'JetBrains Mono', monospace",
                color: '#4a5568', letterSpacing: '0.08em', textTransform: 'uppercase',
                marginBottom: 5, paddingBottom: 4,
                borderBottom: `1px solid ${overallColor}20`,
              }}>
                Visual Grammar
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {ARTIFACT_LEGEND.map((item, i) => (
                  <ArtifactLegendRow key={i} item={item} />
                ))}
              </div>
            </div>
          )}

          {/* ── RIGHT: IDENTITY + STORY PANEL ── */}
          <div style={{
            width: 252,
            background: '#060a18',
            border: `1px solid ${overallColor}35`,
            borderRadius: 10,
            overflow: 'hidden',
            boxShadow: `0 0 32px rgba(0,0,0,0.85), 0 0 24px ${overallColor}15`,
            flexShrink: 0,
          }}>
            {/* Header band */}
            <div style={{
              background: `${overallColor}12`,
              padding: '8px 12px',
              display: 'flex', alignItems: 'center', gap: 8,
              borderBottom: `1px solid ${overallColor}20`,
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: overallColor, boxShadow: `0 0 8px ${overallColor}`,
                flexShrink: 0,
              }} />
              <span style={{ fontSize: 12, fontWeight: 800, color: overallColor, flex: 1 }}>
                {organism.name}
              </span>

              {/* Close */}
              <button
                onClick={(e) => { e.stopPropagation(); setExpanded(false); }}
                style={{
                  background: 'rgba(255,255,255,0.05)', border: 'none',
                  borderRadius: 4, padding: '2px 6px', cursor: 'pointer',
                  fontSize: 10, color: '#6b7280',
                }}
              >✕</button>
            </div>

            <div style={{ padding: '10px 12px' }}>
              {/* Contact info — all clickable */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                  <span style={{ fontSize: 12 }}>👤</span>
                  {organism.linkedInUrl ? (
                    <a
                      href={organism.linkedInUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 5,
                        fontSize: 10, color: '#e2e8f0',
                        fontFamily: "'JetBrains Mono', monospace",
                        textDecoration: 'none',
                        borderBottom: '1px dotted #0a66c240',
                      }}
                      onMouseOver={e => { e.currentTarget.style.color = '#60a5fa'; e.currentTarget.style.borderBottomColor = '#0a66c2'; }}
                      onMouseOut={e => { e.currentTarget.style.color = '#e2e8f0'; e.currentTarget.style.borderBottomColor = '#0a66c240'; }}
                    >
                      {/* LinkedIn 'in' logo SVG */}
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
                        <rect width="24" height="24" rx="4" fill="#0a66c2"/>
                        <path d="M7 9h2v8H7V9zm1-1a1.25 1.25 0 110-2.5A1.25 1.25 0 018 8zm4 1h2v1.1c.3-.6 1-1.1 2-1.1 2 0 2.5 1.3 2.5 3V17h-2v-3.5c0-1-.3-1.5-1-1.5s-1.5.5-1.5 1.5V17h-2V9z" fill="white"/>
                      </svg>
                      {organism.contact}
                    </a>
                  ) : (
                    <span style={{ fontSize: 10, color: '#94a3b8', fontFamily: "'JetBrains Mono', monospace" }}>
                      {organism.contact}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                  <span style={{ fontSize: 12 }}>📧</span>
                  <a
                    href={`mailto:${organism.email}`}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      fontSize: 10, color: '#38bdf8',
                      fontFamily: "'JetBrains Mono', monospace",
                      textDecoration: 'none',
                      borderBottom: '1px dotted #38bdf840',
                    }}
                    onMouseOver={e => (e.currentTarget.style.color = '#7dd3fc')}
                    onMouseOut={e => (e.currentTarget.style.color = '#38bdf8')}
                  >{organism.email}</a>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12 }}>📞</span>
                  <a
                    href={`tel:${organism.phone.replace(/\s/g, '')}`}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      fontSize: 10, color: '#4ade80',
                      fontFamily: "'JetBrains Mono', monospace",
                      textDecoration: 'none',
                      borderBottom: '1px dotted #4ade8040',
                    }}
                    onMouseOver={e => (e.currentTarget.style.color = '#86efac')}
                    onMouseOut={e => (e.currentTarget.style.color = '#4ade80')}
                  >{organism.phone}</a>
                </div>
              </div>

              <div style={{ height: 1, background: `${overallColor}20`, marginBottom: 8 }} />

              {/* Story bars */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <StoryBar
                  icon="✅"
                  label="Journey Progress"
                  color={overallColor}
                  fraction={completionFraction}
                  story="Stages of the engagement completed vs remaining"
                  detail={completionDetail}
                />
                <StoryBar
                  icon="💰"
                  label="Payment Health"
                  color={payColor}
                  fraction={payFraction}
                  story="Amount collected as a fraction of total invoiced"
                  detail={payDetail}
                />
                <StoryBar
                  icon="⚖️"
                  label="Compliance Status"
                  color={compColor}
                  fraction={compFraction}
                  story="Legal and regulatory compliance completeness"
                  detail={compDetail}
                />
              </div>

              {/* Open items dot cluster */}
              {(blockerNodes.length + attentionNodes.length) > 0 && (
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, color: '#4a5568', fontFamily: "'JetBrains Mono', monospace" }}>open</span>
                  {blockerNodes.map((n, i) => (
                    <div key={i} title={`Blocker: ${n.label}`} style={{
                      width: 10, height: 10, borderRadius: '50%',
                      background: '#ff3d3d', boxShadow: '0 0 6px #ff3d3d80',
                      cursor: 'help',
                    }} />
                  ))}
                  {attentionNodes.map((n, i) => (
                    <div key={i} title={`Attention: ${n.label}`} style={{
                      width: 9, height: 9, borderRadius: '50%',
                      background: '#ffb800', boxShadow: '0 0 5px #ffb80060',
                      cursor: 'help',
                    }} />
                  ))}
                </div>
              )}

              {/* Days active ticks */}
              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ fontSize: 10 }}>📅</span>
                <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  {Array.from({ length: Math.min(Math.ceil(daysActive / 7), 20) }).map((_, i) => (
                    <div key={i} title={`Week ${i + 1}`} style={{
                      width: 6, height: 10, borderRadius: 2,
                      background: overallColor,
                      opacity: i < Math.floor(daysActive / 7) ? 0.7 : 0.2,
                    }} />
                  ))}
                  {daysActive > 0 && (
                    <span style={{
                      fontSize: 9, color: '#4a5568',
                      fontFamily: "'JetBrains Mono', monospace",
                      marginLeft: 4, alignSelf: 'center',
                    }}>{daysActive}d</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </g>
  );
}

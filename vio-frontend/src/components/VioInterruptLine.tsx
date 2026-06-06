/**
 * VIO INTERRUPT LINE — Vertical Deadline / Critical To-Do
 * ============================================================
 * DESIGN PHILOSOPHY:
 *   The spine is horizontal — it tells the story of time moving
 *   forward. A vertical line CUTTING ACROSS the spine is a visual
 *   STOP. It says: "Before you continue this story, deal with THIS."
 *
 *   ABOVE the spine = the ACTION required (positive, forward-looking)
 *   BELOW the spine = the CONSEQUENCE if ignored (warning)
 *
 *   The line itself IS the urgency:
 *     future  → blue, calm slow-travel dash
 *     soon    → amber, medium pulse
 *     urgent  → orange, fast pulse
 *     today   → red, rapid flicker + shake
 *     overdue → red, solid + explosion artifact replaces consequence
 *
 *   Clicking the interrupt line opens a detail panel with full story.
 * ============================================================
 */

import React, { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { VioInterrupt, InterruptUrgency } from '../vio-types';
import { INTERRUPT_COLORS } from '../vio-types';
import { renderArtifact } from './VioArtifacts';

// How far above and below the spine the line extends
const LINE_ABOVE = 90;   // px above spine
const LINE_BELOW = 90;   // px below spine
const ACTION_Y   = -LINE_ABOVE - 10;   // artifact center above spine
const CONSEQUENCE_Y = LINE_BELOW + 10; // artifact center below spine

// Animation class per urgency
function getLineClass(urgency: InterruptUrgency): string {
  switch (urgency) {
    case 'future':  return 'vio-interrupt-future';
    case 'soon':    return 'vio-interrupt-soon';
    case 'urgent':  return 'vio-interrupt-urgent';
    case 'today':   return 'vio-interrupt-today';
    case 'overdue': return 'vio-interrupt-overdue';
  }
}

// Dash pattern per urgency — the line itself communicates
function getDash(urgency: InterruptUrgency): string {
  switch (urgency) {
    case 'future':  return '6 6';
    case 'soon':    return '8 5';
    case 'urgent':  return '5 4';
    case 'today':   return '4 3';
    case 'overdue': return 'none'; // solid — it's already past
  }
}

// Days remaining badge — small number that floats on the line
function DaysBadge({ days, color }: { days: number; color: string }) {
  const label = days < 0
    ? `${Math.abs(days)}d`   // overdue: "6d" (past)
    : days === 0
    ? '!'                     // today: exclamation
    : `${days}d`;             // future: "6d" (remaining)

  const bg = days < 0 ? '#ff3d3d' : days === 0 ? '#ff3d3d' : color;

  return (
    <g transform="translate(0, 0)">
      <rect
        x={-12} y={-9}
        width={24} height={18}
        rx={4}
        fill={bg}
        opacity="0.9"
      />
      <text
        x={0} y={5}
        textAnchor="middle"
        fontSize={days === 0 ? '13' : '9'}
        fontWeight="bold"
        fill="#0d1117"
        fontFamily="'JetBrains Mono', monospace"
        style={{ pointerEvents: 'none' }}
      >{label}</text>
    </g>
  );
}

// Hover tooltip that appears above/below the artifact
function ArtifactTooltip({ label, x, y, color }: { label: string; x: number; y: number; color: string }) {
  const maxW = 160;
  return (
    <foreignObject x={x - maxW / 2} y={y} width={maxW} height={40} style={{ pointerEvents: 'none' }}>
      <div
        style={{
          background: 'rgba(13,17,23,0.95)',
          border: `1px solid ${color}40`,
          borderRadius: 4,
          padding: '3px 6px',
          fontSize: 9,
          color,
          fontFamily: "'JetBrains Mono', monospace",
          textAlign: 'center',
          lineHeight: 1.3,
          whiteSpace: 'normal',
          wordBreak: 'break-word',
        }}
      >
        {label}
      </div>
    </foreignObject>
  );
}

// The detail panel portal — appears on click
function InterruptDetailPanel({
  interrupt,
  pos,
  onClose,
}: {
  interrupt: VioInterrupt;
  pos: { x: number; y: number };
  onClose: () => void;
}) {
  const color = INTERRUPT_COLORS[interrupt.urgency];
  const urgencyLabel = {
    future: 'Upcoming',
    soon: 'Due Soon',
    urgent: 'Urgent',
    today: 'DUE TODAY',
    overdue: 'OVERDUE',
  }[interrupt.urgency];

  const panelW = 260;
  const panelH = 220;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let left = pos.x + 16;
  let top = pos.y - 40;
  if (left + panelW > vw - 12) left = pos.x - panelW - 16;
  if (top + panelH > vh - 12) top = vh - panelH - 12;
  if (top < 8) top = 8;

  return createPortal(
    <div
      style={{
        position: 'fixed',
        left,
        top,
        width: panelW,
        zIndex: 9999,
        background: 'rgba(13,17,23,0.97)',
        border: `1px solid ${color}55`,
        borderRadius: 8,
        boxShadow: `0 0 24px ${color}30, 0 4px 32px rgba(0,0,0,0.7)`,
        animation: 'vio-panel-in 180ms cubic-bezier(0.23,1,0.32,1)',
        fontFamily: "'Space Grotesk', sans-serif",
      }}
      onClick={e => e.stopPropagation()}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 12px 6px',
        borderBottom: `1px solid ${color}25`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            background: color,
            color: '#0d1117',
            fontSize: 9,
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: 3,
            letterSpacing: '0.05em',
          }}>{urgencyLabel}</span>
          <span style={{ fontSize: 11, color, fontFamily: "'JetBrains Mono', monospace" }}>
            {interrupt.dateLabel}
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none', border: 'none', color: '#4a5568',
            cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: '0 2px',
          }}
        >✕</button>
      </div>

      {/* Action + Consequence visual */}
      <div style={{
        display: 'flex', gap: 8, padding: '8px 12px',
        borderBottom: `1px solid ${color}15`,
      }}>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 8, color: '#4a5568', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Action</div>
          <svg width={32} height={32} viewBox="-16 -16 32 32">
            {renderArtifact(interrupt.actionArtifact, { size: 20, state: 'attention' })}
          </svg>
          <div style={{ fontSize: 8, color: color, marginTop: 2, lineHeight: 1.2 }}>{interrupt.actionLabel}</div>
        </div>
        <div style={{ width: 1, background: `${color}20`, alignSelf: 'stretch' }} />
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 8, color: '#4a5568', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>If Ignored</div>
          <svg width={32} height={32} viewBox="-16 -16 32 32">
            {renderArtifact(interrupt.consequenceArtifact, { size: 20, state: interrupt.urgency === 'overdue' ? 'blocked' : 'attention' })}
          </svg>
          <div style={{ fontSize: 8, color: '#ff3d3d', marginTop: 2, lineHeight: 1.2 }}>{interrupt.consequenceLabel}</div>
        </div>
      </div>

      {/* Detail fields */}
      <div style={{ padding: '6px 12px 10px' }}>
        {interrupt.details.map((field, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '3px 0',
            borderBottom: i < interrupt.details.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
          }}>
            <span style={{ fontSize: 10, color: '#4a5568', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>{field.icon}</span>
              <span>{field.label}</span>
            </span>
            <span style={{ fontSize: 10, color: field.valueColor || '#94a3b8', fontWeight: 500 }}>
              {field.value}
            </span>
          </div>
        ))}
      </div>
    </div>,
    document.body
  );
}

interface VioInterruptLineProps {
  interrupt: VioInterrupt;
  spineY: number;  // absolute SVG Y of the spine
}

export function VioInterruptLine({ interrupt, spineY }: VioInterruptLineProps) {
  const [hoverAction, setHoverAction] = useState(false);
  const [hoverConsequence, setHoverConsequence] = useState(false);
  const [selected, setSelected] = useState(false);
  const [panelPos, setPanelPos] = useState({ x: 0, y: 0 });
  const lineRef = useRef<SVGLineElement>(null);

  const color = INTERRUPT_COLORS[interrupt.urgency];
  const dash = getDash(interrupt.urgency);
  const lineClass = getLineClass(interrupt.urgency);

  // The line runs from (spineY - LINE_ABOVE) to (spineY + LINE_BELOW)
  const y1 = -LINE_ABOVE;
  const y2 = LINE_BELOW;

  const handleLineClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPanelPos({ x: e.clientX, y: e.clientY });
    setSelected(s => !s);
  };

  return (
    <g transform={`translate(${interrupt.x}, ${spineY})`}>
      {/* ── GLOW LAYER behind the line ── */}
      <line
        x1={0} y1={y1}
        x2={0} y2={y2}
        stroke={color}
        strokeWidth={8}
        opacity={0.12}
        style={{ filter: `blur(4px)` }}
      />

      {/* ── MAIN VERTICAL DASHED LINE ── */}
      <line
        ref={lineRef}
        x1={0} y1={y1}
        x2={0} y2={y2}
        stroke={color}
        strokeWidth={interrupt.urgency === 'overdue' ? 2.5 : 1.5}
        strokeDasharray={dash === 'none' ? undefined : dash}
        opacity={0.85}
        strokeLinecap="round"
        className={lineClass}
        style={{ cursor: 'pointer' }}
        onClick={handleLineClick}
      />

      {/* ── SPINE NOTCH — the line interrupts the spine ── */}
      <rect
        x={-4} y={-4}
        width={8} height={8}
        rx={1}
        fill="#0d1117"
        stroke={color}
        strokeWidth={1.5}
        opacity={0.9}
        style={{ cursor: 'pointer' }}
        onClick={handleLineClick}
      />

      {/* ── DAYS REMAINING BADGE — floats on the line ── */}
      <g transform="translate(0, -28)" style={{ cursor: 'pointer' }} onClick={handleLineClick}>
        <DaysBadge days={interrupt.daysRemaining} color={color} />
      </g>

      {/* ── ACTION ARTIFACT — above the spine ── */}
      <g
        transform={`translate(0, ${ACTION_Y})`}
        style={{ cursor: 'pointer' }}
        onMouseEnter={() => setHoverAction(true)}
        onMouseLeave={() => setHoverAction(false)}
        onClick={handleLineClick}
      >
        {renderArtifact(interrupt.actionArtifact, {
          size: 22,
          state: interrupt.urgency === 'overdue' ? 'blocked'
               : interrupt.urgency === 'today'   ? 'blocked'
               : interrupt.urgency === 'urgent'  ? 'attention'
               : interrupt.urgency === 'soon'    ? 'attention'
               : 'processing',
        })}
        {/* Hover tooltip above the artifact */}
        {hoverAction && (
          <ArtifactTooltip
            label={interrupt.actionLabel}
            x={0}
            y={-50}
            color={color}
          />
        )}
      </g>

      {/* ── CONSEQUENCE ARTIFACT — below the spine ── */}
      <g
        transform={`translate(0, ${CONSEQUENCE_Y})`}
        style={{ cursor: 'pointer' }}
        onMouseEnter={() => setHoverConsequence(true)}
        onMouseLeave={() => setHoverConsequence(false)}
        onClick={handleLineClick}
      >
        {renderArtifact(interrupt.consequenceArtifact, {
          size: 22,
          state: interrupt.urgency === 'overdue' ? 'blocked' : 'attention',
        })}
        {/* Hover tooltip below the artifact */}
        {hoverConsequence && (
          <ArtifactTooltip
            label={interrupt.consequenceLabel}
            x={0}
            y={30}
            color={'#ff3d3d'}
          />
        )}
      </g>

      {/* ── DETAIL PANEL PORTAL ── */}
      {selected && (
        <InterruptDetailPanel
          interrupt={interrupt}
          pos={panelPos}
          onClose={() => setSelected(false)}
        />
      )}
    </g>
  );
}

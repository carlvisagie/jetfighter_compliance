/**
 * VIO CANVAS — Visual Information Organism
 * ============================================================
 * Design: MAXIMUM INFORMATION DENSITY AT A GLANCE
 *
 * SPINE ENCODING:
 *   fast    → thick (5px) bright green, glowing — things are flying
 *   normal  → medium (3.5px) teal — steady
 *   slow    → thin (2px) amber — sluggish
 *   stalled → thin (1.5px) grey dashed — nothing moving
 *   broken  → red dashed with gap marker — hard stop
 *
 * NODE ENCODING:
 *   Every node IS the thing it represents — no abstract shapes.
 *   folder = case file, document = paper, magnifier = review,
 *   scale = compliance, flag = milestone, clock = time pressure,
 *   coin = payment, coin-crack = payment issue, wall = blocker,
 *   chain-broken = dependency break, rocket = delivery, etc.
 * ============================================================
 */

import React, { useRef, useState, useCallback } from 'react';
import type { VioOrganism, VioNode, SpineVelocity, VioInterrupt } from '../vio-types';
import { SPINE_STYLE, STATE_COLORS, STATE_GLOW } from '../vio-types';
import { renderArtifact } from './VioArtifacts';
import { VioOrb } from './VioOrb';
import { VioDetailPanel } from './VioDetailPanel';
import { VioInterruptLine } from './VioInterruptLine';

// Canvas dimensions
const CANVAS_W = 1060;
const SPINE_Y = 200;   // spine sits at this Y — interrupt lines extend 90px above AND below
const CANVAS_H = 440;  // enough room for interrupt lines above + branches below

interface VioCanvasProps {
  organism: VioOrganism;
  interrupts?: VioInterrupt[];
}

function getSpineNodes(organism: VioOrganism): VioNode[] {
  return organism.nodes.filter(n => !n.isBranch);
}

function getBranchNodes(organism: VioOrganism, parentId: string): VioNode[] {
  return organism.nodes.filter(n => n.isBranch && n.branchParentId === parentId);
}

// Draw a semantic spine segment between two x positions
function SpineSegment({
  x1, x2, y, velocity
}: { x1: number; x2: number; y: number; velocity: SpineVelocity }) {
  const style = SPINE_STYLE[velocity];
  const mid = (x1 + x2) / 2;

  return (
    <g>
      {/* Glow layer */}
      {style.glow !== 'none' && (
        <path
          d={`M${x1},${y} C${x1 + 30},${y} ${x2 - 30},${y} ${x2},${y}`}
          fill="none"
          stroke={style.glow}
          strokeWidth={style.width + 6}
          opacity="0.4"
          style={{ filter: `blur(4px)` }}
        />
      )}
      {/* Main spine */}
      <path
        d={`M${x1},${y} C${x1 + 30},${y} ${x2 - 30},${y} ${x2},${y}`}
        fill="none"
        stroke={style.stroke}
        strokeWidth={style.width}
        strokeDasharray={style.dash === 'none' ? undefined : style.dash}
        opacity={style.opacity}
        strokeLinecap="round"
      />
      {/* Broken spine marker — red X gap */}
      {velocity === 'broken' && (
        <g transform={`translate(${mid}, ${y})`}>
          <circle r="8" fill="#0d1117" stroke="#ff3d3d" strokeWidth="1.5" />
          <line x1="-4" y1="-4" x2="4" y2="4" stroke="#ff3d3d" strokeWidth="2" strokeLinecap="round" />
          <line x1="4" y1="-4" x2="-4" y2="4" stroke="#ff3d3d" strokeWidth="2" strokeLinecap="round" />
        </g>
      )}
      {/* Velocity arrow for fast segments */}
      {velocity === 'fast' && (
        <g transform={`translate(${mid}, ${y})`}>
          <path d="M-5,0 L0,-4 L5,0" fill="none" stroke={style.stroke} strokeWidth="1.5" opacity="0.7" />
        </g>
      )}
    </g>
  );
}

// Branch connector line from spine down to branch nodes
function BranchConnector({
  parentX, parentY, branchNodes, branchY
}: {
  parentX: number;
  parentY: number;
  branchNodes: VioNode[];
  branchY: number;
}) {
  if (branchNodes.length === 0) return null;
  const minX = Math.min(...branchNodes.map(n => n.x));
  const maxX = Math.max(...branchNodes.map(n => n.x));

  return (
    <g opacity="0.7">
      {/* Vertical drop from parent */}
      <line
        x1={parentX} y1={parentY + 18}
        x2={parentX} y2={branchY - 18}
        stroke="#4a5568" strokeWidth="1.5" strokeDasharray="3 3"
      />
      {/* Horizontal branch spine */}
      {branchNodes.length > 1 && (
        <line
          x1={minX} y1={branchY}
          x2={maxX} y2={branchY}
          stroke="#4a5568" strokeWidth="1.5" strokeDasharray="3 3"
        />
      )}
      {/* Vertical drops to each branch node */}
      {branchNodes.map(n => (
        <line
          key={n.id}
          x1={n.x} y1={branchY - 18}
          x2={n.x} y2={branchY}
          stroke="#4a5568" strokeWidth="1" strokeDasharray="2 2"
        />
      ))}
    </g>
  );
}

export function VioCanvas({ organism, interrupts = [] }: VioCanvasProps) {
  const [selectedNode, setSelectedNode] = useState<VioNode | null>(null);
  const [activeBranchParentId, setActiveBranchParentId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const spineNodes = getSpineNodes(organism);
  const branchNodes = activeBranchParentId
    ? getBranchNodes(organism, activeBranchParentId)
    : [];

  const BRANCH_Y = SPINE_Y + 130;

  const handleNodeClick = useCallback((node: VioNode) => {
    if (selectedNode?.id === node.id) {
      setSelectedNode(null);
      return;
    }
    setSelectedNode(node);
  }, [selectedNode]);

  const handleBranchExpand = useCallback((branchParentId: string) => {
    setActiveBranchParentId(prev => prev === branchParentId ? null : branchParentId);
    setSelectedNode(null);
  }, []);

  const handleClose = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Build spine segments from organism.segments (spine only)
  const spineSegments = organism.segments.filter(seg => {
    const fromNode = organism.nodes.find(n => n.id === seg.fromId);
    const toNode = organism.nodes.find(n => n.id === seg.toId);
    return fromNode && toNode && !fromNode.isBranch && !toNode.isBranch;
  });

  // Branch segments
  const branchSegments = organism.segments.filter(seg => {
    const fromNode = organism.nodes.find(n => n.id === seg.fromId);
    const toNode = organism.nodes.find(n => n.id === seg.toId);
    return fromNode?.isBranch || toNode?.isBranch;
  });

  // Find the parent node for active branch
  const branchParentNode = activeBranchParentId
    ? organism.nodes.find(n => n.id === activeBranchParentId)
    : null;

  return (
    <div
      ref={containerRef}
      className="relative w-full overflow-x-auto"
      style={{ minHeight: activeBranchParentId ? 340 : 240 }}
    >
      <svg
        width={CANVAS_W}
        height={activeBranchParentId ? CANVAS_H : SPINE_Y + 130}
        viewBox={`0 0 ${CANVAS_W} ${activeBranchParentId ? CANVAS_H : SPINE_Y + 130}`}
          style={{ minWidth: CANVAS_W, display: 'block', background: 'transparent' }}
      >
        <defs>
          {/* Glow filter for nodes */}
          {Object.entries(STATE_GLOW).map(([state, color]) => (
            <filter key={state} id={`glow-${state}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feFlood floodColor={color} result="color" />
              <feComposite in="color" in2="blur" operator="in" result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          ))}
          {/* Spine glow filter */}
          <filter id="spine-glow" x="-20%" y="-200%" width="140%" height="500%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* ── SPINE SEGMENTS ── */}
        {spineSegments.map(seg => {
          const fromNode = organism.nodes.find(n => n.id === seg.fromId);
          const toNode = organism.nodes.find(n => n.id === seg.toId);
          if (!fromNode || !toNode) return null;
          return (
            <SpineSegment
              key={`${seg.fromId}-${seg.toId}`}
              x1={fromNode.x}
              x2={toNode.x}
              y={SPINE_Y}
              velocity={seg.velocity}
            />
          );
        })}

        {/* ── BRANCH CONNECTOR ── */}
        {activeBranchParentId && branchParentNode && branchNodes.length > 0 && (
          <BranchConnector
            parentX={branchParentNode.x}
            parentY={SPINE_Y}
            branchNodes={branchNodes}
            branchY={BRANCH_Y}
          />
        )}

        {/* ── BRANCH SPINE SEGMENTS ── */}
        {activeBranchParentId && branchSegments.map(seg => {
          const fromNode = organism.nodes.find(n => n.id === seg.fromId);
          const toNode = organism.nodes.find(n => n.id === seg.toId);
          if (!fromNode || !toNode) return null;
          if (fromNode.branchParentId !== activeBranchParentId &&
              toNode.branchParentId !== activeBranchParentId) return null;
          return (
            <SpineSegment
              key={`${seg.fromId}-${seg.toId}`}
              x1={fromNode.x}
              x2={toNode.x}
              y={BRANCH_Y}
              velocity={seg.velocity}
            />
          );
        })}

        {/* ── INTERRUPT LINES — rendered BEFORE nodes so nodes sit on top ── */}
        {interrupts.map(interrupt => (
          <VioInterruptLine
            key={interrupt.id}
            interrupt={interrupt}
            spineY={SPINE_Y}
          />
        ))}

        {/* ── COMPANY ORB ── */}
        <g transform={`translate(58, ${SPINE_Y})`}>
          <VioOrb organism={organism} size={50} />
        </g>

        {/* ── SPINE NODES ── */}
        {spineNodes.map(node => (
          <g
            key={node.id}
            transform={`translate(${node.x}, ${SPINE_Y})`}
            filter={`url(#glow-${node.state})`}
          >
            <title>{node.label}</title>
            {renderArtifact(node.artifact, {
              size: 34,
              state: node.state,
              onClick: () => handleNodeClick(node),
              isSelected: selectedNode?.id === node.id,
              label: node.label,
            })}
            {/* Artifact label — always visible below node */}
            <text
              x={0} y={52}
              textAnchor="middle"
              fontSize="9"
              fill={STATE_COLORS[node.state]}
              opacity="0.75"
              fontFamily="'JetBrains Mono', monospace"
              style={{ pointerEvents: 'none' }}
            >{node.label}</text>
            {/* Branch expand indicator */}
            {node.branches && node.branches.length > 0 && (
              <g
                transform={`translate(0, 62)`}
                onClick={(e) => {
                  e.stopPropagation();
                  handleBranchExpand(node.id);
                }}
          style={{ cursor: 'pointer' }}
        >
          <circle r="9" fill="#0d1117" stroke={activeBranchParentId === node.id ? '#38bdf8' : '#4a5568'} strokeWidth="1.5" />
          <text x={0} y={4} textAnchor="middle" fontSize="9"
                  fill={activeBranchParentId === node.id ? '#38bdf8' : '#6b7280'}
                  fontFamily="monospace">⎇</text>
              </g>
            )}
          </g>
        ))}

        {/* ── BRANCH NODES ── */}
        {activeBranchParentId && branchNodes.map(node => (
          <g
            key={node.id}
            transform={`translate(${node.x}, ${BRANCH_Y})`}
            filter={`url(#glow-${node.state})`}
          >
            <title>{node.label}</title>
            {renderArtifact(node.artifact, {
              size: 28,
              state: node.state,
              onClick: () => handleNodeClick(node),
              isSelected: selectedNode?.id === node.id,
              label: node.label,
            })}
            <text
              x={0} y={44}
              textAnchor="middle"
              fontSize="8"
              fill={STATE_COLORS[node.state]}
              opacity="0.7"
              fontFamily="'JetBrains Mono', monospace"
              style={{ pointerEvents: 'none' }}
            >{node.label}</text>
          </g>
        ))}

        {/* ── SPINE LEGEND (velocity key) ── */}
        <g transform={`translate(${CANVAS_W - 10}, ${SPINE_Y + 55})`}>
          {([
            ['fast', 'Fast'],
            ['normal', 'Normal'],
            ['slow', 'Slow'],
            ['stalled', 'Stalled'],
            ['broken', 'Broken'],
          ] as [SpineVelocity, string][]).map(([vel, lbl], i) => {
            const s = SPINE_STYLE[vel];
            return (
              <g key={vel} transform={`translate(0, ${i * 14})`}>
                <line x1={-52} y1={0} x2={-32} y2={0}
                  stroke={s.stroke} strokeWidth={Math.max(s.width * 0.7, 1)}
                  strokeDasharray={s.dash === 'none' ? undefined : s.dash}
                  opacity={s.opacity} strokeLinecap="round" />
                <text x={-28} y={4} fontSize="8" fill="#4a5568"
                  fontFamily="'Space Grotesk', sans-serif">{lbl}</text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* ── DETAIL PANEL ── */}
      {selectedNode && (
        <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 100 }}>
          <VioDetailPanel
            node={selectedNode}
            onClose={handleClose}
            onBranchClick={(branchId) => {
              handleBranchExpand(branchId);
              setSelectedNode(null);
            }}
          />
        </div>
      )}
    </div>
  );
}

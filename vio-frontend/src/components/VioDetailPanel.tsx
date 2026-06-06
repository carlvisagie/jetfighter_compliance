/**
 * VIO DETAIL PANEL
 * ============================================================
 * Slides up when a node is clicked.
 * Shows all detail fields, state badge, velocity, and branch
 * expand button if the node has sub-timelines.
 * ============================================================
 */

import React from 'react';
import type { VioNode } from '../vio-types';
import { STATE_COLORS } from '../vio-types';

interface VioDetailPanelProps {
  node: VioNode;
  onClose: () => void;
  onBranchClick?: (branchId: string) => void;
}

const STATE_LABELS: Record<string, string> = {
  healthy:    'Healthy',
  attention:  'Needs Attention',
  blocked:    'Blocked',
  complete:   'Complete',
  processing: 'In Progress',
  inactive:   'Not Started',
  milestone:  'Milestone Reached',
};

const ARTIFACT_ICONS: Record<string, string> = {
  'document':       '📄',
  'document-issue': '⚠️',
  'stamp':          '🔏',
  'coin':           '💰',
  'coin-crack':     '💳',
  'wall':           '🚫',
  'magnifier':      '🔍',
  'checkmark':      '✅',
  'clock':          '⏰',
  'alert':          '⚠️',
  'gear':           '⚙️',
  'scale':          '⚖️',
  'rocket':         '🚀',
  'flag':           '🚩',
  'chain-broken':   '🔗',
  'decision':       '👆',
  'folder':         '📁',
};

export function VioDetailPanel({ node, onClose, onBranchClick }: VioDetailPanelProps) {
  const color = STATE_COLORS[node.state];
  const stateLabel = STATE_LABELS[node.state] || node.state;
  const artifactIcon = ARTIFACT_ICONS[node.artifact] || '●';

  return (
    <div
      className="vio-panel-enter absolute bottom-4 left-1/2 -translate-x-1/2 w-[400px] max-w-[92vw]"
      style={{ pointerEvents: 'all', zIndex: 200 }}
    >
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, rgba(8,12,28,0.97) 0%, rgba(12,18,40,0.97) 100%)',
          border: `1px solid ${color}30`,
          boxShadow: `0 0 32px ${color}20, 0 8px 32px rgba(0,0,0,0.6)`,
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: `1px solid ${color}20` }}
        >
          <div className="flex items-center gap-2">
            <span style={{ fontSize: 18 }}>{artifactIcon}</span>
            <div>
              <div className="text-sm font-bold text-white" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                {node.label}
              </div>
              <div
                className="text-xs px-2 py-0.5 rounded-full inline-block mt-0.5"
                style={{
                  background: `${color}20`,
                  color: color,
                  border: `1px solid ${color}40`,
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                }}
              >
                ● {stateLabel}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white transition-colors w-6 h-6 flex items-center justify-center rounded"
            style={{ fontSize: 14 }}
          >
            ✕
          </button>
        </div>

        {/* Detail fields */}
        <div className="px-4 py-3 space-y-2">
          {node.details.map((field, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span style={{ fontSize: 13 }}>{field.icon}</span>
                <span className="text-xs text-gray-400" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                  {field.label}
                </span>
              </div>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded"
                style={{
                  color: field.valueColor || color,
                  background: `${field.valueColor || color}15`,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {field.value}
              </span>
            </div>
          ))}
        </div>

        {/* Branch expand buttons */}
        {node.branches && node.branches.length > 0 && onBranchClick && (
          <div className="px-4 pb-3 space-y-1.5" style={{ borderTop: `1px solid ${color}15` }}>
            <div className="pt-2" />
            {node.branches.map(branch => (
              <button
                key={branch.id}
                onClick={() => onBranchClick(node.id)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg transition-all hover:opacity-90 active:scale-[0.98]"
                style={{
                  background: 'rgba(56,189,248,0.08)',
                  border: '1px dashed rgba(56,189,248,0.35)',
                  color: '#38bdf8',
                }}
              >
                <span className="text-xs font-semibold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                  ⎇ Branch: {branch.label} ({branch.nodeCount} nodes)
                </span>
                <span style={{ fontSize: 12 }}>›</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

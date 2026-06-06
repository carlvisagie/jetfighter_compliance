/**
 * VIO DATA MODEL — Visual Information Organism
 * ============================================================
 * PRINCIPLE: Every node IS the thing it represents.
 * Every spine segment communicates velocity + health.
 * Maximum information density at a glance.
 * ============================================================
 */

import type { ArtifactType } from '../components/VioArtifacts';

export type NodeState =
  | 'healthy'    // green — flowing well
  | 'attention'  // amber — needs eyes on it
  | 'blocked'    // red — stopped
  | 'complete'   // bright green — done
  | 'processing' // blue — actively working
  | 'inactive'   // grey — not started
  | 'milestone'; // gold — achievement

// Spine segment velocity encoding
// fast    = thick (5px) bright green — things are moving
// normal  = medium (3px) teal — steady progress
// slow    = thin (2px) amber — sluggish
// stalled = thin (1.5px) grey dashed — nothing moving
// broken  = red dashed with gap — hard stop
export type SpineVelocity = 'fast' | 'normal' | 'slow' | 'stalled' | 'broken';

export interface SpineSegment {
  fromId: string;
  toId: string;
  velocity: SpineVelocity;
}

export interface DetailField {
  icon: string;
  label: string;
  value: string;
  valueColor?: string;
}

export interface BranchRef {
  id: string;
  label: string;
  nodeCount: number;
}

export interface VioNode {
  id: string;
  artifact: ArtifactType;   // THE pictographic artifact — IS the thing
  state: NodeState;
  label: string;
  x: number;                // absolute x on 1000-unit canvas
  y: number;                // 0 = spine, positive = below, negative = above
  isBranch?: boolean;
  branchParentId?: string;
  branches?: BranchRef[];
  details: DetailField[];
}

export interface VioOrganism {
  id: string;
  name: string;
  initials: string;
  contact: string;
  email: string;
  phone: string;
  linkedInUrl?: string;   // LinkedIn profile URL for the primary contact
  overallState: NodeState;
  nodes: VioNode[];
  segments: SpineSegment[];
  activeBranchId?: string | null;
  kpis: DetailField[];
}

// Color palette per state
export const STATE_COLORS: Record<NodeState, string> = {
  healthy:    '#00e5a0',
  attention:  '#ffb800',
  blocked:    '#ff3d3d',
  complete:   '#4ade80',
  processing: '#38bdf8',
  inactive:   '#4a5568',
  milestone:  '#ffd700',
};

export const STATE_GLOW: Record<NodeState, string> = {
  healthy:    'rgba(0,229,160,0.45)',
  attention:  'rgba(255,184,0,0.45)',
  blocked:    'rgba(255,61,61,0.45)',
  complete:   'rgba(74,222,128,0.35)',
  processing: 'rgba(56,189,248,0.35)',
  inactive:   'rgba(74,85,104,0.25)',
  milestone:  'rgba(255,215,0,0.55)',
};

// Spine visual encoding
export const SPINE_STYLE: Record<SpineVelocity, {
  stroke: string; width: number; dash: string; opacity: number; glow: string;
}> = {
  fast:    { stroke: '#00e5a0', width: 5,   dash: 'none',   opacity: 1.0,  glow: 'rgba(0,229,160,0.5)' },
  normal:  { stroke: '#38bdf8', width: 3.5, dash: 'none',   opacity: 0.9,  glow: 'rgba(56,189,248,0.3)' },
  slow:    { stroke: '#ffb800', width: 2,   dash: 'none',   opacity: 0.8,  glow: 'rgba(255,184,0,0.3)' },
  stalled: { stroke: '#4a5568', width: 1.5, dash: '6 4',    opacity: 0.6,  glow: 'none' },
  broken:  { stroke: '#ff3d3d', width: 2,   dash: '4 6',    opacity: 0.85, glow: 'rgba(255,61,61,0.4)' },
};

// ─────────────────────────────────────────────────────────────
// DEMO DATA — Acme Corp: Legal Entity Formation Journey
// ─────────────────────────────────────────────────────────────
export const ACME_ORGANISM: VioOrganism = {
  id: 'acme',
  name: 'Acme Corp',
  initials: 'AC',
  contact: 'Sarah Chen',
  email: 'sarah@acme.co',
  phone: '+1 415 555 0192',
  linkedInUrl: 'https://www.linkedin.com/in/sarah-chen',
  overallState: 'attention',
  kpis: [
    { icon: '📅', label: 'Engagement Start', value: 'May 14, 2026' },
    { icon: '⏱', label: 'Days Active', value: '22 days' },
    { icon: '📋', label: 'Open Items', value: '3', valueColor: '#ffb800' },
    { icon: '💰', label: 'Invoiced', value: '$4,200' },
    { icon: '💳', label: 'Collected', value: '$2,800', valueColor: '#00e5a0' },
    { icon: '⚠️', label: 'Aging Balance', value: '$1,400', valueColor: '#ff3d3d' },
  ],
  nodes: [
    {
      id: 'ac-intake',
      artifact: 'folder',
      state: 'complete',
      label: 'Client Intake',
      x: 160, y: 0,
      details: [
        { icon: '📁', label: 'Folder', value: 'Opened & Complete' },
        { icon: '📄', label: 'Documents', value: '7 received' },
        { icon: '✅', label: 'ID Verified', value: 'Yes' },
        { icon: '📅', label: 'Date', value: 'May 14, 2026' },
      ],
    },
    {
      id: 'ac-docs',
      artifact: 'document',
      state: 'complete',
      label: 'Formation Docs',
      x: 280, y: 0,
      details: [
        { icon: '📄', label: 'Articles', value: 'Drafted & Signed' },
        { icon: '📄', label: 'Operating Agmt', value: 'Signed' },
        { icon: '📄', label: 'EIN Application', value: 'Submitted' },
        { icon: '🖊', label: 'Signatures', value: '3 / 3' },
      ],
    },
    {
      id: 'ac-gap',
      artifact: 'document-issue',
      state: 'attention',
      label: 'Missing Exhibit B',
      x: 390, y: 0,
      details: [
        { icon: '⚠️', label: 'Issue', value: 'Exhibit B missing', valueColor: '#ffb800' },
        { icon: '📋', label: 'Required By', value: 'Operating Agreement §4' },
        { icon: '📅', label: 'Flagged', value: 'May 28, 2026' },
        { icon: '⏳', label: 'Awaiting', value: 'Client response' },
      ],
    },
    {
      id: 'ac-review',
      artifact: 'magnifier',
      state: 'processing',
      label: 'Attorney Review',
      x: 500, y: 0,
      branches: [{ id: 'ac-payment-branch', label: 'Payment', nodeCount: 2 }],
      details: [
        { icon: '👁', label: 'Reviewer', value: 'J. Martinez, Esq.' },
        { icon: '📋', label: 'Items Pending', value: '3' },
        { icon: '💰', label: 'Invoice', value: '$450 received' },
        { icon: '⏱', label: 'SLA Remaining', value: '18h' },
      ],
    },
    {
      id: 'ac-compliance',
      artifact: 'scale',
      state: 'healthy',
      label: 'Compliance Check',
      x: 610, y: 0,
      details: [
        { icon: '⚖️', label: 'Status', value: 'Monitoring' },
        { icon: '🔐', label: 'Integrity', value: 'Valid' },
        { icon: '📋', label: 'Requirements', value: '12 / 12 met' },
        { icon: '🏛', label: 'Jurisdiction', value: 'Delaware' },
      ],
    },
    {
      id: 'ac-filed',
      artifact: 'flag',
      state: 'milestone',
      label: 'Delaware LLC Filed',
      x: 720, y: 0,
      details: [
        { icon: '🌟', label: 'Milestone', value: 'Delaware LLC Filed' },
        { icon: '📜', label: 'File Number', value: '#7821-DE' },
        { icon: '📅', label: 'Effective Date', value: 'Jun 2, 2026' },
        { icon: '🎉', label: 'Certificate', value: 'Issued' },
      ],
    },
    {
      id: 'ac-aging',
      artifact: 'clock',
      state: 'attention',
      label: 'Invoice Aging',
      x: 820, y: 0,
      details: [
        { icon: '💳', label: 'Balance Owed', value: '$1,400', valueColor: '#ff3d3d' },
        { icon: '📅', label: 'Due Date', value: 'May 30, 2026' },
        { icon: '⏰', label: 'Overdue', value: '6 days', valueColor: '#ffb800' },
        { icon: '📧', label: 'Reminders Sent', value: '×2' },
      ],
    },
    {
      id: 'ac-delivery',
      artifact: 'rocket',
      state: 'inactive',
      label: 'Final Delivery',
      x: 930, y: 0,
      details: [
        { icon: '🚀', label: 'Status', value: 'Pending' },
        { icon: '📦', label: 'Package', value: 'Not ready' },
        { icon: '🔒', label: 'Blocked by', value: 'Aging invoice' },
      ],
    },
    // Branch nodes — Payment sub-timeline
    {
      id: 'ac-pay-received',
      artifact: 'coin',
      state: 'complete',
      label: 'Deposit Received',
      x: 500, y: 90,
      isBranch: true,
      branchParentId: 'ac-review',
      details: [
        { icon: '💰', label: 'Amount', value: '$2,800', valueColor: '#4ade80' },
        { icon: '📅', label: 'Cleared', value: 'May 15, 2026' },
        { icon: '✅', label: 'Confirmed', value: 'Yes' },
      ],
    },
    {
      id: 'ac-pay-aging',
      artifact: 'coin-crack',
      state: 'attention',
      label: 'Balance Aging',
      x: 610, y: 90,
      isBranch: true,
      branchParentId: 'ac-review',
      details: [
        { icon: '💳', label: 'Owed', value: '$1,400', valueColor: '#ff3d3d' },
        { icon: '⏰', label: 'Age', value: '6 days overdue', valueColor: '#ffb800' },
        { icon: '📧', label: 'Notices Sent', value: '2' },
      ],
    },
  ],
  segments: [
    { fromId: 'ac-intake',       toId: 'ac-docs',       velocity: 'fast' },
    { fromId: 'ac-docs',         toId: 'ac-gap',        velocity: 'fast' },
    { fromId: 'ac-gap',          toId: 'ac-review',     velocity: 'slow' },
    { fromId: 'ac-review',       toId: 'ac-compliance', velocity: 'normal' },
    { fromId: 'ac-compliance',   toId: 'ac-filed',      velocity: 'fast' },
    { fromId: 'ac-filed',        toId: 'ac-aging',      velocity: 'slow' },
    { fromId: 'ac-aging',        toId: 'ac-delivery',   velocity: 'stalled' },
    { fromId: 'ac-pay-received', toId: 'ac-pay-aging',  velocity: 'stalled' },
  ],
};

// ─────────────────────────────────────────────────────────────
// DEMO DATA — Nexus Ventures: Investment Deal Flow
// ─────────────────────────────────────────────────────────────
export const NEXUS_ORGANISM: VioOrganism = {
  id: 'nexus',
  name: 'Nexus Ventures',
  initials: 'NV',
  contact: 'Marcus Webb',
  email: 'marcus@nexusv.io',
  phone: '+1 212 555 0847',
  linkedInUrl: 'https://www.linkedin.com/in/marcus-webb',
  overallState: 'blocked',
  kpis: [
    { icon: '📅', label: 'Deal Start', value: 'Apr 30, 2026' },
    { icon: '⏱', label: 'Days Active', value: '36 days' },
    { icon: '🔴', label: 'Blockers', value: '1 critical', valueColor: '#ff3d3d' },
    { icon: '💰', label: 'Deal Size', value: '$2.4M' },
    { icon: '📋', label: 'Diligence', value: '68% complete' },
    { icon: '⚖️', label: 'Legal Status', value: 'On hold' },
  ],
  nodes: [
    {
      id: 'nv-intake',
      artifact: 'folder',
      state: 'complete',
      label: 'Deal Intake',
      x: 160, y: 0,
      details: [
        { icon: '📁', label: 'Deal Room', value: 'Opened' },
        { icon: '📄', label: 'Pitch Deck', value: 'Received' },
        { icon: '✅', label: 'NDA', value: 'Signed' },
        { icon: '📅', label: 'Date', value: 'Apr 30, 2026' },
      ],
    },
    {
      id: 'nv-diligence',
      artifact: 'magnifier',
      state: 'complete',
      label: 'Due Diligence',
      x: 290, y: 0,
      details: [
        { icon: '🔍', label: 'Financial DD', value: 'Complete' },
        { icon: '🔍', label: 'Technical DD', value: 'Complete' },
        { icon: '🔍', label: 'Legal DD', value: 'In progress' },
        { icon: '📊', label: 'Score', value: '8.2 / 10' },
      ],
    },
    {
      id: 'nv-term',
      artifact: 'document',
      state: 'complete',
      label: 'Term Sheet',
      x: 400, y: 0,
      details: [
        { icon: '📄', label: 'Term Sheet', value: 'v3 — Agreed' },
        { icon: '💰', label: 'Valuation', value: '$12M pre-money' },
        { icon: '📊', label: 'Equity', value: '20%' },
        { icon: '🖊', label: 'Signed', value: 'Both parties' },
      ],
    },
    {
      id: 'nv-blocked',
      artifact: 'wall',
      state: 'blocked',
      label: 'IP Dispute Blocker',
      x: 510, y: 0,
      branches: [{ id: 'nv-impact-branch', label: 'Impact', nodeCount: 2 }],
      details: [
        { icon: '🚫', label: 'Blocker', value: 'IP ownership dispute', valueColor: '#ff3d3d' },
        { icon: '⚖️', label: 'Filed', value: 'Jun 1, 2026' },
        { icon: '🏛', label: 'Court', value: 'SDNY — pending' },
        { icon: '⏳', label: 'Est. Resolution', value: '30–60 days' },
      ],
    },
    {
      id: 'nv-decision',
      artifact: 'decision',
      state: 'inactive',
      label: 'IC Decision',
      x: 630, y: 0,
      details: [
        { icon: '👆', label: 'Status', value: 'Awaiting blocker resolution' },
        { icon: '👥', label: 'Committee', value: '5 members' },
        { icon: '📋', label: 'Agenda', value: 'Not scheduled' },
      ],
    },
    {
      id: 'nv-close',
      artifact: 'stamp',
      state: 'inactive',
      label: 'Deal Close',
      x: 760, y: 0,
      details: [
        { icon: '🔏', label: 'Status', value: 'Not started' },
        { icon: '📋', label: 'Closing Docs', value: 'Pending' },
        { icon: '💰', label: 'Wire Transfer', value: 'Not initiated' },
      ],
    },
    {
      id: 'nv-delivery',
      artifact: 'rocket',
      state: 'inactive',
      label: 'Portfolio Onboard',
      x: 900, y: 0,
      details: [
        { icon: '🚀', label: 'Status', value: 'Not started' },
        { icon: '🔒', label: 'Blocked by', value: 'IP dispute + close' },
      ],
    },
    // Branch — Impact sub-timeline
    {
      id: 'nv-chain',
      artifact: 'chain-broken',
      state: 'blocked',
      label: 'Dependency Break',
      x: 510, y: 90,
      isBranch: true,
      branchParentId: 'nv-blocked',
      details: [
        { icon: '🔗', label: 'Broken Link', value: 'IP → Close chain' },
        { icon: '⚡', label: 'Impact', value: 'Entire deal halted', valueColor: '#ff3d3d' },
        { icon: '📋', label: 'Resolution', value: 'Legal counsel engaged' },
      ],
    },
    {
      id: 'nv-alert',
      artifact: 'alert',
      state: 'attention',
      label: 'LP Deadline Pressure',
      x: 630, y: 90,
      isBranch: true,
      branchParentId: 'nv-blocked',
      details: [
        { icon: '⚠️', label: 'LP Deadline', value: 'Jun 30, 2026', valueColor: '#ffb800' },
        { icon: '📧', label: 'LP Notices', value: '3 received' },
        { icon: '⏰', label: 'Urgency', value: 'High' },
      ],
    },
  ],
  segments: [
    { fromId: 'nv-intake',    toId: 'nv-diligence', velocity: 'fast' },
    { fromId: 'nv-diligence', toId: 'nv-term',      velocity: 'normal' },
    { fromId: 'nv-term',      toId: 'nv-blocked',   velocity: 'slow' },
    { fromId: 'nv-blocked',   toId: 'nv-decision',  velocity: 'broken' },
    { fromId: 'nv-decision',  toId: 'nv-close',     velocity: 'stalled' },
    { fromId: 'nv-close',     toId: 'nv-delivery',  velocity: 'stalled' },
    { fromId: 'nv-chain',     toId: 'nv-alert',     velocity: 'stalled' },
  ],
};

// ─────────────────────────────────────────────────────────────
// VERTICAL INTERRUPT LINE — Deadline / Critical To-Do
// A vertical dashed line that CUTS ACROSS the spine at a date
// position. Above the spine = the ACTION required.
// Below the spine = the CONSEQUENCE if ignored.
// ─────────────────────────────────────────────────────────────

export type InterruptUrgency =
  | 'future'    // 14+ days — blue, calm glow
  | 'soon'      // 7 days — amber, slow pulse
  | 'urgent'    // 3 days — orange, fast pulse
  | 'today'     // 0 days — red, rapid flicker + shake
  | 'overdue';  // past — turns to explosion, constant red

export interface VioInterrupt {
  id: string;
  x: number;              // position on the 1000-unit canvas (maps to a date)
  urgency: InterruptUrgency;
  daysRemaining: number;  // negative = overdue
  dateLabel: string;      // e.g. 'Jun 12' — shown only on hover
  // ABOVE the spine — the action required
  actionArtifact: ArtifactType;
  actionLabel: string;    // hover tooltip
  // BELOW the spine — the consequence if ignored
  consequenceArtifact: ArtifactType;
  consequenceLabel: string; // hover tooltip
  // Click detail
  details: DetailField[];
}

// Urgency color map
export const INTERRUPT_COLORS: Record<InterruptUrgency, string> = {
  future:  '#38bdf8',  // blue
  soon:    '#ffb800',  // amber
  urgent:  '#ff8c00',  // orange
  today:   '#ff3d3d',  // red
  overdue: '#ff3d3d',  // red
};

// ─────────────────────────────────────────────────────────────
// DEMO INTERRUPT DATA — Acme Corp
// ─────────────────────────────────────────────────────────────
export const ACME_INTERRUPTS: VioInterrupt[] = [
  {
    id: 'ac-int-exhibit',
    x: 390,
    urgency: 'urgent',
    daysRemaining: 2,
    dateLabel: 'Jun 8',
    actionArtifact: 'document-issue',
    actionLabel: 'Exhibit B — must be filed by Jun 8',
    consequenceArtifact: 'wall',
    consequenceLabel: 'Operating Agreement invalid without Exhibit B',
    details: [
      { icon: '⚠️', label: 'Action', value: 'File Exhibit B', valueColor: '#ff8c00' },
      { icon: '📅', label: 'Deadline', value: 'Jun 8, 2026', valueColor: '#ff8c00' },
      { icon: '⏳', label: 'Days Left', value: '2 days', valueColor: '#ff8c00' },
      { icon: '🚫', label: 'If Missed', value: 'Operating Agreement invalid' },
      { icon: '👤', label: 'Owner', value: 'Sarah Chen' },
    ],
  },
  {
    id: 'ac-int-payment',
    x: 820,
    urgency: 'overdue',
    daysRemaining: -6,
    dateLabel: 'May 30',
    actionArtifact: 'coin',
    actionLabel: 'Collect $1,400 balance — 6 days overdue',
    consequenceArtifact: 'chain-broken',
    consequenceLabel: 'Final delivery blocked until balance cleared',
    details: [
      { icon: '💰', label: 'Action', value: 'Collect $1,400 balance', valueColor: '#ff3d3d' },
      { icon: '📅', label: 'Was Due', value: 'May 30, 2026', valueColor: '#ff3d3d' },
      { icon: '⏰', label: 'Overdue By', value: '6 days', valueColor: '#ff3d3d' },
      { icon: '🚫', label: 'If Ignored', value: 'Final delivery blocked', valueColor: '#ff3d3d' },
      { icon: '📧', label: 'Reminders', value: '2 sent' },
    ],
  },
  {
    id: 'ac-int-delivery',
    x: 930,
    urgency: 'soon',
    daysRemaining: 6,
    dateLabel: 'Jun 12',
    actionArtifact: 'rocket',
    actionLabel: 'Schedule final delivery package — due Jun 12',
    consequenceArtifact: 'alert',
    consequenceLabel: 'Client SLA breach if delivery missed',
    details: [
      { icon: '🚀', label: 'Action', value: 'Prepare delivery package', valueColor: '#ffb800' },
      { icon: '📅', label: 'Target', value: 'Jun 12, 2026', valueColor: '#ffb800' },
      { icon: '⏳', label: 'Days Left', value: '6 days', valueColor: '#ffb800' },
      { icon: '⚠️', label: 'If Missed', value: 'Client SLA breach' },
      { icon: '📋', label: 'Requires', value: 'Balance cleared first' },
    ],
  },
];

// ─────────────────────────────────────────────────────────────
// DEMO INTERRUPT DATA — Nexus Ventures
// ─────────────────────────────────────────────────────────────
export const NEXUS_INTERRUPTS: VioInterrupt[] = [
  {
    id: 'nv-int-court',
    x: 510,
    urgency: 'future',
    daysRemaining: 18,
    dateLabel: 'Jun 24',
    actionArtifact: 'scale',
    actionLabel: 'Court hearing — SDNY IP dispute — Jun 24',
    consequenceArtifact: 'wall',
    consequenceLabel: 'Deal permanently blocked if ruling adverse',
    details: [
      { icon: '⚖️', label: 'Action', value: 'Attend SDNY hearing', valueColor: '#38bdf8' },
      { icon: '📅', label: 'Date', value: 'Jun 24, 2026', valueColor: '#38bdf8' },
      { icon: '⏳', label: 'Days Left', value: '18 days', valueColor: '#38bdf8' },
      { icon: '🏛', label: 'Court', value: 'SDNY — IP Division' },
      { icon: '🚫', label: 'If Lost', value: 'Deal permanently blocked' },
    ],
  },
  {
    id: 'nv-int-lp',
    x: 760,
    urgency: 'today',
    daysRemaining: 0,
    dateLabel: 'TODAY',
    actionArtifact: 'decision',
    actionLabel: 'LP committee decision required TODAY',
    consequenceArtifact: 'chain-broken',
    consequenceLabel: 'LP capital commitment expires at midnight',
    details: [
      { icon: '👆', label: 'Action', value: 'LP committee decision', valueColor: '#ff3d3d' },
      { icon: '📅', label: 'Deadline', value: 'TODAY', valueColor: '#ff3d3d' },
      { icon: '⏰', label: 'Time Left', value: 'Hours remaining', valueColor: '#ff3d3d' },
      { icon: '💰', label: 'At Stake', value: '$2.4M commitment', valueColor: '#ff3d3d' },
      { icon: '🚫', label: 'If Missed', value: 'LP capital expires midnight' },
    ],
  },
];

export const ALL_ORGANISMS: VioOrganism[] = [ACME_ORGANISM, NEXUS_ORGANISM];
export const ALL_INTERRUPTS: Record<string, VioInterrupt[]> = {
  acme: ACME_INTERRUPTS,
  nexus: NEXUS_INTERRUPTS,
};

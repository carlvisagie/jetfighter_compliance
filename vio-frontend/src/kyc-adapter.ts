/**
 * KYC → VIO ADAPTER
 * ============================================================
 * KYC IS the organism. The VIO is its consciousness made visible.
 *
 * This adapter maps every signal the organism knows about itself
 * to the VioOrganism + VioInterrupt visual types.
 *
 * Signal sources wired here:
 *   1. vio_overview.py → company rows (intake, EI, stage, urgency)
 *   2. organism_state → health_state, checks, mismatches, residue
 *   3. evidence_intelligence → gaps, failures, confirmation_needed
 *   4. attention items → interrupt lines (action + consequence)
 *   5. custody chain → node details
 *   6. organism observability → subsystem health
 *
 * DOCTRINE:
 *   - Stillness is the default. Motion = unresolved demand.
 *   - Only waiting_client / failed / inconsistent breathe.
 *   - The organism sees itself. If it knows it, VIO shows it.
 * ============================================================
 */

import type {
  VioOrganism,
  VioNode,
  SpineSegment,
  SpineVelocity,
  VioInterrupt,
  InterruptUrgency,
  NodeState,
  DetailField,
} from './vio-types';
// ArtifactType inlined — no component dependency needed in adapter
type ArtifactType =
  | 'document' | 'document-issue' | 'stamp' | 'coin' | 'coin-crack'
  | 'wall' | 'magnifier' | 'checkmark' | 'clock' | 'alert'
  | 'gear' | 'scale' | 'rocket' | 'flag' | 'chain-broken'
  | 'decision' | 'folder';

// ── API Config ────────────────────────────────────────────────────────────────
// Configurable at runtime via window.__KYC_API_BASE or env
export function getApiBase(): string {
  if (typeof window !== 'undefined' && (window as any).__KYC_API_BASE) {
    return (window as any).__KYC_API_BASE.replace(/\/$/, '');
  }
  return '';  // same-origin by default (works when vio-demo is deployed alongside KYC)
}

// ── KYC API Types (exact shape from vio_overview.py) ─────────────────────────

export interface KycAttentionItem {
  code: string;
  severity: 'red' | 'amber' | 'info';
  message: string;
  hint?: string;
  days_remaining?: number;
  date_label?: string;
}

export interface KycQuickStats {
  files_uploaded: number;
  files_analyzed: number;
  gaps: number;
  failures: number;
  pending: number;
  confirmation_needed: number;
  entity_count: number;
}

export interface KycTimelineSegment {
  type: string;
  status: string;
  label: string;
  utc: string;
  detail?: Record<string, any>;
}

export interface KycCompany {
  intake_id: string;
  project_id?: string;
  company_name: string;
  initials: string;
  contact_email: string;
  phone?: string;
  state: string;
  stage: string;
  stage_index: number;
  stage_state: string;
  on_branch: boolean;
  branch_label?: string;
  urgency_score: number;
  days_in_stage: number;
  attention: KycAttentionItem[];
  timeline: KycTimelineSegment[];
  quick_stats: KycQuickStats;
  next_action?: string;
  ei_ok: boolean;
  priority_score?: number;
}

export interface KycOrganismHealth {
  total: number;
  error?: number;
  stuck?: number;
  gap?: number;
  waiting?: number;
  analyzing?: number;
  active?: number;
  payment_pending?: number;
  new?: number;
  complete?: number;
}

export interface KycOrganism {
  available: boolean;
  health_state: string;
  current_bottleneck?: string;
  next_recommended_action?: string;
  mismatches: Array<{ name: string; severity: string; detail: string }>;
  mismatch_count: number;
  queue_depth: number;
  intake_count_active: number;
  intake_count_total: number;
  uploaded_file_count: number;
  durable_storage_configured: boolean;
  environment: string;
  git_commit: string;
  timestamp_utc: string;
  error?: string;
}

export interface KycOverviewResponse {
  ok: boolean;
  companies: KycCompany[];
  organism_health: KycOrganismHealth;
  stage_backbone: string[];
  stage_counts: Record<string, number>;
  queue_depth: number;
  urgent_count: number;
  organism?: KycOrganism;
  error?: string;
}

// ── Stage → x-position mapping ────────────────────────────────────────────────
// 7 stages across a 1000-unit canvas. Orb at x=0, stages at fixed positions.
const STAGE_X: Record<string, number> = {
  intake:           120,
  classification:   240,
  validation:       370,
  evidence_mapping: 500,
  review:           630,
  approval:         760,
  conversion:       900,
};

const STAGE_LABELS: Record<string, string> = {
  intake:           'Intake',
  classification:   'Classified',
  validation:       'Validated',
  evidence_mapping: 'Evidence',
  review:           'Review',
  approval:         'Approved',
  conversion:       'Delivered',
};

// ── State → NodeState mapping ─────────────────────────────────────────────────
function kycStateToNodeState(state: string, stageState: string): NodeState {
  // Stage-state takes priority (doctrine §2)
  switch (stageState) {
    case 'failed':          return 'blocked';
    case 'waiting_client':  return 'attention';
    case 'inconsistent':    return 'attention';
    case 'stalled':         return 'attention';
    case 'done':            return 'complete';
    case 'healthy':         break; // fall through to state-based
  }
  switch (state) {
    case 'error':           return 'blocked';
    case 'stuck':           return 'blocked';
    case 'gap':             return 'attention';
    case 'waiting':         return 'attention';
    case 'analyzing':       return 'processing';
    case 'active':          return 'healthy';
    case 'payment_pending': return 'attention';
    case 'new':             return 'inactive';
    case 'complete':        return 'complete';
    default:                return 'inactive';
  }
}

// ── Stage → Artifact mapping ──────────────────────────────────────────────────
function stageToArtifact(stage: string, state: string, stats: KycQuickStats): ArtifactType {
  switch (stage) {
    case 'intake':
      return stats.files_uploaded > 0 ? 'folder' : 'document';
    case 'classification':
      return 'stamp';
    case 'validation':
      return stats.failures > 0 ? 'document-issue' : 'magnifier';
    case 'evidence_mapping':
      if (stats.gaps > 0)             return 'alert';
      if (stats.confirmation_needed)  return 'clock';
      if (stats.files_analyzed > 0)   return 'magnifier';
      return 'folder';
    case 'review':
      return 'scale';
    case 'approval':
      return state === 'complete' ? 'stamp' : 'decision';
    case 'conversion':
      return state === 'complete' ? 'checkmark' : 'rocket';
    default:
      return 'document';
  }
}

// ── Spine velocity between stages ─────────────────────────────────────────────
function calcVelocity(
  fromStageIdx: number,
  toStageIdx: number,
  currentStageIdx: number,
  state: string,
  daysInStage: number,
): SpineVelocity {
  // Segments after current stage = inactive
  if (fromStageIdx >= currentStageIdx) {
    if (state === 'complete') return 'fast';
    return 'stalled';
  }
  // Segments before current stage = completed
  if (toStageIdx <= currentStageIdx) {
    if (state === 'error' || state === 'stuck') return 'broken';
    return 'fast';
  }
  // Current segment
  if (state === 'error' || state === 'stuck')   return 'broken';
  if (state === 'gap' || state === 'waiting')   return 'slow';
  if (state === 'analyzing')                    return 'normal';
  if (daysInStage > 5)                          return 'slow';
  if (daysInStage > 2)                          return 'normal';
  return 'fast';
}

// ── Attention item → Interrupt line ──────────────────────────────────────────
function attentionToInterrupt(
  item: KycAttentionItem,
  idx: number,
  stageX: number,
  companyId: string,
): VioInterrupt {
  const days = item.days_remaining ?? 0;
  let urgency: InterruptUrgency;
  if (days < 0)       urgency = 'overdue';
  else if (days === 0) urgency = 'today';
  else if (days <= 3)  urgency = 'urgent';
  else if (days <= 7)  urgency = 'soon';
  else                 urgency = 'future';

  // Action artifact (above spine) — what must be done
  let actionArtifact: ArtifactType = 'alert';
  if (item.code === 'payment_link_stale' || item.code === 'payment_pending') {
    actionArtifact = 'coin';
  } else if (item.code === 'high_priority_gaps' || item.code === 'files_unindexed') {
    actionArtifact = 'document-issue';
  } else if (item.code === 'stuck_intake_no_upload') {
    actionArtifact = 'clock';
  } else if (item.code === 'extraction_failures') {
    actionArtifact = 'document-issue';
  } else if (item.code === 'confirmation_needed') {
    actionArtifact = 'decision';
  } else if (item.code === 'files_missing_on_disk') {
    actionArtifact = 'chain-broken';
  }

  // Consequence artifact (below spine) — what happens if ignored
  let consequenceArtifact: ArtifactType = 'wall';
  if (item.severity === 'red') {
    consequenceArtifact = days < 0 ? 'chain-broken' : 'wall';
  } else if (item.severity === 'amber') {
    consequenceArtifact = 'alert';
  } else {
    consequenceArtifact = 'clock';
  }

  const details: DetailField[] = [
    { icon: item.severity === 'red' ? '🔴' : item.severity === 'amber' ? '🟡' : 'ℹ️',
      label: 'Issue', value: item.message },
  ];
  if (item.hint) {
    details.push({ icon: '💡', label: 'Action', value: item.hint, valueColor: '#ffb800' });
  }
  if (days !== undefined) {
    details.push({
      icon: days < 0 ? '⏰' : '📅',
      label: days < 0 ? 'Overdue by' : 'Days remaining',
      value: days < 0 ? `${Math.abs(days)} days` : `${days} days`,
      valueColor: days <= 0 ? '#ff3d3d' : days <= 3 ? '#ff8c00' : '#ffb800',
    });
  }

  return {
    id: `${companyId}-int-${idx}`,
    x: stageX + (idx * 18),  // slight offset if multiple interrupts at same stage
    urgency,
    daysRemaining: days,
    dateLabel: item.date_label || (days < 0 ? 'OVERDUE' : days === 0 ? 'TODAY' : `${days}d`),
    actionArtifact,
    actionLabel: item.message,
    consequenceArtifact,
    consequenceLabel: item.hint || 'Action required',
    details,
  };
}

// ── Build VioNode for a stage ─────────────────────────────────────────────────
function buildStageNode(
  company: KycCompany,
  stage: string,
  stageIdx: number,
  isCurrentStage: boolean,
  isPastStage: boolean,
): VioNode {
  const stats = company.quick_stats;
  const nodeState = isPastStage
    ? 'complete'
    : isCurrentStage
    ? kycStateToNodeState(company.state, company.stage_state)
    : 'inactive';

  const artifact = isPastStage
    ? stageToArtifact(stage, 'complete', stats)
    : stageToArtifact(stage, company.state, stats);

  const details: DetailField[] = [
    { icon: '📍', label: 'Stage', value: STAGE_LABELS[stage] || stage },
    { icon: '⏱', label: 'Days in stage', value: isCurrentStage ? `${company.days_in_stage}d` : '—' },
  ];

  if (isCurrentStage) {
    if (stats.files_uploaded > 0) {
      details.push({ icon: '📄', label: 'Files', value: `${stats.files_analyzed}/${stats.files_uploaded} analyzed` });
    }
    if (stats.gaps > 0) {
      details.push({ icon: '⚠️', label: 'Gaps', value: `${stats.gaps} missing`, valueColor: '#ffb800' });
    }
    if (stats.failures > 0) {
      details.push({ icon: '❌', label: 'Failures', value: `${stats.failures} extraction failed`, valueColor: '#ff3d3d' });
    }
    if (stats.confirmation_needed > 0) {
      details.push({ icon: '❓', label: 'Confirm needed', value: `${stats.confirmation_needed} fields`, valueColor: '#ffb800' });
    }
    if (stats.entity_count > 0) {
      details.push({ icon: '🔍', label: 'Entities', value: `${stats.entity_count} extracted` });
    }
    if (company.next_action) {
      details.push({ icon: '▶️', label: 'Next action', value: company.next_action, valueColor: '#00e5a0' });
    }
  }

  return {
    id: `${company.intake_id}-${stage}`,
    artifact,
    state: nodeState,
    label: STAGE_LABELS[stage] || stage,
    x: STAGE_X[stage] || (120 + stageIdx * 130),
    y: 0,
    details,
  };
}

// ── Build branch node for client follow-up ────────────────────────────────────
function buildBranchNode(company: KycCompany): VioNode | null {
  if (!company.on_branch) return null;
  return {
    id: `${company.intake_id}-followup`,
    artifact: 'clock',
    state: 'attention',
    label: company.branch_label || 'Client Follow-up',
    x: STAGE_X['evidence_mapping'] + 60,
    y: 80,
    isBranch: true,
    branchParentId: `${company.intake_id}-evidence_mapping`,
    details: [
      { icon: '⏳', label: 'Status', value: 'Waiting for customer response' },
      { icon: '📧', label: 'Branch', value: company.branch_label || 'Client follow-up' },
    ],
  };
}

// ── Main adapter: KycCompany → VioOrganism + VioInterrupt[] ──────────────────
export function kycCompanyToOrganism(company: KycCompany): {
  organism: VioOrganism;
  interrupts: VioInterrupt[];
} {
  const STAGES = ['intake', 'classification', 'validation', 'evidence_mapping', 'review', 'approval', 'conversion'];
  const currentIdx = Math.max(0, Math.min(company.stage_index, STAGES.length - 1));

  // Build spine nodes
  const nodes: VioNode[] = [];
  for (let i = 0; i < STAGES.length; i++) {
    const stage = STAGES[i];
    const isPast = i < currentIdx;
    const isCurrent = i === currentIdx;
    nodes.push(buildStageNode(company, stage, i, isCurrent, isPast));
  }

  // Branch node if on client follow-up
  const branchNode = buildBranchNode(company);
  if (branchNode) nodes.push(branchNode);

  // Build spine segments
  const segments: SpineSegment[] = [];
  for (let i = 0; i < STAGES.length - 1; i++) {
    segments.push({
      fromId: `${company.intake_id}-${STAGES[i]}`,
      toId: `${company.intake_id}-${STAGES[i + 1]}`,
      velocity: calcVelocity(i, i + 1, currentIdx, company.state, company.days_in_stage),
    });
  }

  // Overall state
  const overallState = kycStateToNodeState(company.state, company.stage_state);

  // KPIs — the organism's vital signs for this company
  const kpis: DetailField[] = [
    { icon: '📊', label: 'Stage', value: STAGE_LABELS[company.stage] || company.stage },
    { icon: '⏱', label: 'In stage', value: `${company.days_in_stage}d` },
    { icon: '📄', label: 'Files', value: `${company.quick_stats.files_uploaded} uploaded` },
  ];
  if (company.quick_stats.gaps > 0) {
    kpis.push({ icon: '⚠️', label: 'Gaps', value: `${company.quick_stats.gaps}`, valueColor: '#ffb800' });
  }
  if (company.quick_stats.failures > 0) {
    kpis.push({ icon: '❌', label: 'Failures', value: `${company.quick_stats.failures}`, valueColor: '#ff3d3d' });
  }
  if (company.urgency_score > 0) {
    kpis.push({ icon: '🔥', label: 'Urgency', value: `${Math.round(company.urgency_score * 100)}%`, valueColor: '#ff8c00' });
  }

  const organism: VioOrganism = {
    id: company.intake_id,
    name: company.company_name,
    initials: company.initials,
    contact: company.contact_email,
    email: company.contact_email,
    phone: company.phone || '',
    overallState,
    nodes,
    segments,
    kpis,
  };

  // Build interrupt lines from attention items
  const interrupts: VioInterrupt[] = (company.attention || []).map((item, idx) => {
    const stageX = STAGE_X[company.stage] || 500;
    return attentionToInterrupt(item, idx, stageX, company.intake_id);
  });

  return { organism, interrupts };
}

// ── Organism health state → global signal ────────────────────────────────────
export function kycOrganismToHealthState(org: KycOrganism): {
  state: NodeState;
  color: string;
  label: string;
  pulse: boolean;
} {
  switch (org.health_state) {
    case 'GREEN':
      return { state: 'healthy', color: '#00e5a0', label: 'Healthy', pulse: false };
    case 'AMBER':
      return { state: 'attention', color: '#ffb800', label: 'Attention', pulse: true };
    case 'RED':
      return { state: 'blocked', color: '#ff3d3d', label: 'Critical', pulse: true };
    default:
      return { state: 'inactive', color: '#4a5568', label: 'Unknown', pulse: false };
  }
}

// ── Stage counts → pipeline health summary ────────────────────────────────────
export function buildPipelineSummary(response: KycOverviewResponse): {
  stage: string;
  label: string;
  count: number;
  x: number;
}[] {
  const STAGES = ['intake', 'classification', 'validation', 'evidence_mapping', 'review', 'approval', 'conversion'];
  return STAGES.map(stage => ({
    stage,
    label: STAGE_LABELS[stage],
    count: response.stage_counts?.[stage] || 0,
    x: STAGE_X[stage],
  }));
}

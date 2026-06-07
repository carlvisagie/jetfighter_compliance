import { describe, expect, it } from 'vitest';
import {
  isOrganismConnected,
  resolveConnectionState,
  shouldAutoOpenConfigPanel,
  shouldOpenConfigOnButtonClick,
} from './connection-state';
import type { KycOverviewResponse } from './kyc-adapter';

const sampleResponse: KycOverviewResponse = {
  ok: true,
  companies: [{ intake_id: 'I-1' } as any],
  organism_health: { total: 1 },
  stage_backbone: [],
  stage_counts: {},
  queue_depth: 1,
  urgent_count: 0,
  organism: {
    available: true,
    health_state: 'RED',
    mismatches: [],
    mismatch_count: 0,
    queue_depth: 1,
    intake_count_active: 1,
    intake_count_total: 1,
    uploaded_file_count: 3,
    durable_storage_configured: true,
    environment: 'production',
    git_commit: 'abc1234',
    timestamp_utc: '2026-06-07T00:00:00Z',
  },
};

describe('resolveConnectionState', () => {
  it('empty apiBase with successful overview shows Organism Online, not Configure API', () => {
    const state = resolveConnectionState({
      loading: false,
      error: null,
      response: sampleResponse,
    });
    expect(state.showConfigureWarning).toBe(false);
    expect(state.label).toBe('Organism Online');
    expect(state.organismConnected).toBe(true);
  });

  it('successful non-production data shows Connected', () => {
    const state = resolveConnectionState({
      loading: false,
      error: null,
      response: {
        ...sampleResponse,
        organism: { ...sampleResponse.organism!, environment: 'development' },
      },
    });
    expect(state.label).toBe('Connected');
    expect(state.showConfigureWarning).toBe(false);
  });

  it('failed API/auth still renders Configure API warning', () => {
    const state = resolveConnectionState({
      loading: false,
      error: 'HTTP 403',
      response: null,
    });
    expect(state.showConfigureWarning).toBe(true);
    expect(state.label).toBe('Configure API');
    expect(shouldOpenConfigOnButtonClick(state)).toBe(true);
  });

  it('no data and no error still warns until organism responds', () => {
    const state = resolveConnectionState({
      loading: false,
      error: null,
      response: null,
    });
    expect(state.showConfigureWarning).toBe(true);
    expect(state.label).toBe('Configure API');
  });

  it('loading without response does not warn yet', () => {
    const state = resolveConnectionState({
      loading: true,
      error: null,
      response: null,
    });
    expect(state.showConfigureWarning).toBe(false);
    expect(state.label).toBe('Connecting…');
  });
});

describe('config panel gating', () => {
  it('does not auto-open when organism data is present', () => {
    expect(
      shouldAutoOpenConfigPanel({
        loading: false,
        error: null,
        response: sampleResponse,
        configOpen: false,
      }),
    ).toBe(false);
  });

  it('auto-opens only on real connection failure', () => {
    expect(
      shouldAutoOpenConfigPanel({
        loading: false,
        error: 'HTTP 403',
        response: null,
        configOpen: false,
      }),
    ).toBe(true);
  });

  it('isOrganismConnected requires ok response', () => {
    expect(isOrganismConnected(sampleResponse)).toBe(true);
    expect(isOrganismConnected({ ...sampleResponse, ok: false })).toBe(false);
    expect(isOrganismConnected(null)).toBe(false);
  });
});

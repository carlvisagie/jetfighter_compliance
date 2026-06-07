/**
 * VIO connection state — derived from actual organism data, not apiBase alone.
 */
import type { KycOverviewResponse } from './kyc-adapter';

export type ConnectionTone = 'online' | 'warning' | 'loading';

export type ConnectionState = {
  tone: ConnectionTone;
  label: string;
  showConfigureWarning: boolean;
  organismConnected: boolean;
};

export function isOrganismConnected(
  response: KycOverviewResponse | null | undefined,
): boolean {
  return Boolean(response?.ok);
}

export function resolveConnectionState(params: {
  loading: boolean;
  error: string | null;
  response: KycOverviewResponse | null;
}): ConnectionState {
  const { loading, error, response } = params;
  const connected = isOrganismConnected(response);

  if (connected) {
    const env = response?.organism?.environment;
    const label =
      env === 'production' ? 'Organism Online' : 'Connected';
    return {
      tone: 'online',
      label,
      showConfigureWarning: false,
      organismConnected: true,
    };
  }

  if (loading && !response) {
    return {
      tone: 'loading',
      label: 'Connecting…',
      showConfigureWarning: false,
      organismConnected: false,
    };
  }

  if (error) {
    return {
      tone: 'warning',
      label: 'Configure API',
      showConfigureWarning: true,
      organismConnected: false,
    };
  }

  return {
    tone: 'warning',
    label: 'Configure API',
    showConfigureWarning: true,
    organismConnected: false,
  };
}

export function shouldOpenConfigOnButtonClick(state: ConnectionState): boolean {
  return state.showConfigureWarning;
}

export function shouldAutoOpenConfigPanel(params: {
  loading: boolean;
  error: string | null;
  response: KycOverviewResponse | null;
  configOpen: boolean;
}): boolean {
  if (params.configOpen) return false;
  if (params.loading) return false;
  if (isOrganismConnected(params.response)) return false;
  return Boolean(params.error);
}

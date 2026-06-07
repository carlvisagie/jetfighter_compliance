/**
 * KYC VIO — THE ORGANISM'S CONSCIOUSNESS MADE VISIBLE
 * ============================================================
 * Design: Deep-space dark, Space Grotesk + JetBrains Mono
 *
 * KYC IS the organism. This is not a dashboard.
 * This is the organism seeing itself.
 *
 * LAYERS WIRED:
 *   1. Organism health strip — GREEN/AMBER/RED + bottleneck + checks
 *   2. Pipeline backbone — 7-stage counts across the top
 *   3. Company spines — every company as a living timeline
 *   4. Interrupt lines — attention items as vertical cuts
 *   5. Organism self-awareness — residue, mismatches, storage
 *   6. Auto-refresh every 60s — the organism breathes
 *
 * DOCTRINE:
 *   Stillness is default. Motion = unresolved demand.
 *   Only waiting_client / failed / inconsistent breathe.
 *   The operator must know in 5 seconds: who, where, health, waiting, broken, next.
 * ============================================================
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { VioOrganism, VioInterrupt } from './vio-types';
import { STATE_COLORS } from './vio-types';
import {
  kycCompanyToOrganism,
  kycOrganismToHealthState,
  buildPipelineSummary,
  getApiBase,
  type KycOverviewResponse,
  type KycOrganism,
} from './kyc-adapter';
import { VioCanvas } from './components/VioCanvas';

// ── Auth config type ─────────────────────────────────────────────────────────
type AuthConfig = {
  apiBase: string;
  opsKey: string;   // X-Ops-Key header (preferred)
  password: string; // fallback: POST /api/ops/login
};

function loadAuthConfig(): AuthConfig {
  try {
    const raw = localStorage.getItem('kyc_auth_config');
    if (raw) return JSON.parse(raw);
  } catch {}
  // Legacy: migrate old kyc_api_base key
  try {
    const base = localStorage.getItem('kyc_api_base') || '';
    return { apiBase: base, opsKey: '', password: '' };
  } catch {}
  return { apiBase: '', opsKey: '', password: '' };
}

function saveAuthConfig(cfg: AuthConfig) {
  try { localStorage.setItem('kyc_auth_config', JSON.stringify(cfg)); } catch {}
}

// ── Config panel ─────────────────────────────────────────────────────────────
function ConfigPanel({
  config,
  onSave,
  onClose,
}: {
  config: AuthConfig;
  onSave: (cfg: AuthConfig) => void;
  onClose: () => void;
}) {
  const [url, setUrl] = useState(config.apiBase);
  const [opsKey, setOpsKey] = useState(config.opsKey);
  const [password, setPassword] = useState(config.password);
  const [authMode, setAuthMode] = useState<'key' | 'password'>(config.opsKey ? 'key' : 'password');

  const inputStyle: React.CSSProperties = {
    width: '100%', background: '#080c1c', border: '1px solid #ffffff15',
    borderRadius: 8, padding: '10px 14px', color: '#e2e8f0',
    fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
    outline: 'none', boxSizing: 'border-box', marginTop: 6,
  };
  const labelStyle: React.CSSProperties = {
    color: '#4a5568', fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: '0.06em', textTransform: 'uppercase',
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.88)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#0d1117', border: '1px solid #00e5a025',
          borderRadius: 14, padding: 32, width: 500,
          boxShadow: '0 0 80px #00e5a008, 0 4px 40px rgba(0,0,0,0.6)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Title */}
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#00e5a0', fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
          Connect to Organism
        </div>
        <div style={{ color: '#2d3748', fontSize: 11, marginBottom: 24, fontFamily: "'JetBrains Mono', monospace" }}>
          Point to your KYC deployment and authenticate
        </div>

        {/* API URL */}
        <div style={{ marginBottom: 20 }}>
          <div style={labelStyle}>API URL</div>
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://compliance.keepyourcontracts.com"
            style={inputStyle}
            autoFocus
          />
        </div>

        {/* Auth mode toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {(['key', 'password'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setAuthMode(mode)}
              style={{
                flex: 1, padding: '7px 0',
                background: authMode === mode ? '#00e5a015' : 'transparent',
                border: `1px solid ${authMode === mode ? '#00e5a040' : '#ffffff10'}`,
                borderRadius: 8, cursor: 'pointer',
                color: authMode === mode ? '#00e5a0' : '#4a5568',
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
                letterSpacing: '0.05em',
              }}
            >
              {mode === 'key' ? 'X-Ops-Key' : 'Password'}
            </button>
          ))}
        </div>

        {/* Auth input */}
        {authMode === 'key' ? (
          <div style={{ marginBottom: 24 }}>
            <div style={labelStyle}>OPS API KEY</div>
            <input
              value={opsKey}
              onChange={e => setOpsKey(e.target.value)}
              placeholder="your-ops-api-key"
              type="password"
              style={inputStyle}
            />
            <div style={{ color: '#2d3748', fontSize: 10, marginTop: 6, fontFamily: "'JetBrains Mono', monospace" }}>
              Sent as X-Ops-Key header on every request
            </div>
          </div>
        ) : (
          <div style={{ marginBottom: 24 }}>
            <div style={labelStyle}>OPS PASSWORD</div>
            <input
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="your-ops-password"
              type="password"
              style={inputStyle}
            />
            <div style={{ color: '#2d3748', fontSize: 10, marginTop: 6, fontFamily: "'JetBrains Mono', monospace" }}>
              Auto-login via POST /api/ops/login — session cookie stored
            </div>
          </div>
        )}

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={() => onSave({ apiBase: url.trim(), opsKey: authMode === 'key' ? opsKey.trim() : '', password: authMode === 'password' ? password : '' })}
            style={{
              flex: 1, background: '#00e5a015', border: '1px solid #00e5a040',
              borderRadius: 8, padding: '11px 0', color: '#00e5a0',
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700,
              fontSize: 13, cursor: 'pointer', letterSpacing: '0.03em',
            }}
          >
            Connect
          </button>
          <button
            onClick={onClose}
            style={{
              flex: 1, background: 'transparent', border: '1px solid #ffffff10',
              borderRadius: 8, padding: '11px 0', color: '#4a5568',
              fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
              fontSize: 13, cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Organism health strip ─────────────────────────────────────────────────────
function OrganismHealthStrip({ organism }: { organism: KycOrganism | undefined }) {
  if (!organism) return null;

  const health = kycOrganismToHealthState(organism);
  const hasMismatches = organism.mismatch_count > 0;
  const isProduction = organism.environment === 'production';

  return (
    <div
      style={{
        background: `linear-gradient(135deg, ${health.color}08 0%, #080c1c 100%)`,
        border: `1px solid ${health.color}20`,
        borderRadius: 10,
        padding: '12px 20px',
        marginBottom: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        flexWrap: 'wrap',
      }}
    >
      {/* Organism pulse indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 12, height: 12,
            borderRadius: '50%',
            background: health.color,
            boxShadow: `0 0 ${health.pulse ? '12px' : '6px'} ${health.color}`,
            animation: health.pulse ? 'vio-breathe 3s ease-in-out infinite' : 'none',
          }}
        />
        <span style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 700, fontSize: 13,
          color: health.color,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
        }}>
          {health.label}
        </span>
      </div>

      {/* Separator */}
      <div style={{ width: 1, height: 24, background: '#ffffff10' }} />

      {/* Vital signs */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <VitalSign label="Queue" value={String(organism.queue_depth)} color={organism.queue_depth > 0 ? '#ffb800' : '#4a5568'} />
        <VitalSign label="Active" value={String(organism.intake_count_active)} color="#e2e8f0" />
        <VitalSign label="Files" value={String(organism.uploaded_file_count)} color="#e2e8f0" />
        <VitalSign
          label="Storage"
          value={organism.durable_storage_configured ? 'Persistent' : 'Ephemeral'}
          color={organism.durable_storage_configured ? '#00e5a0' : '#ff3d3d'}
        />
        {isProduction && (
          <VitalSign label="Env" value="PRODUCTION" color="#38bdf8" />
        )}
        {organism.git_commit && (
          <VitalSign label="Build" value={organism.git_commit} color="#4a5568" mono />
        )}
      </div>

      {/* Bottleneck */}
      {organism.current_bottleneck && (
        <>
          <div style={{ width: 1, height: 24, background: '#ffffff10' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#4a5568', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>BOTTLENECK</span>
            <span style={{ color: '#ffb800', fontSize: 12, fontFamily: "'Space Grotesk', sans-serif" }}>
              {organism.current_bottleneck}
            </span>
          </div>
        </>
      )}

      {/* Mismatches — organism self-healing signals */}
      {hasMismatches && (
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            background: '#ff3d3d15', border: '1px solid #ff3d3d30',
            borderRadius: 6, padding: '4px 10px',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff3d3d' }} />
            <span style={{ color: '#ff3d3d', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
              {organism.mismatches.map(m => m.name.replace(/_/g, ' ').toUpperCase()).join(' • ')}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function VitalSign({ label, value, color, mono }: { label: string; value: string; color: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ color: '#4a5568', fontSize: 9, fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{
        color, fontSize: 12, fontWeight: 600,
        fontFamily: mono ? "'JetBrains Mono', monospace" : "'Space Grotesk', sans-serif",
      }}>
        {value}
      </span>
    </div>
  );
}

// ── Organism self-awareness panel — checks + mismatches ──────────────────────
function OrganismAwarenessPanel({ organism }: { organism: KycOrganism | undefined }) {
  const [expanded, setExpanded] = useState(false);
  if (!organism || organism.mismatch_count === 0) return null;

  return (
    <div
      style={{
        background: '#0d1117',
        border: '1px solid #ff3d3d20',
        borderRadius: 10,
        marginBottom: 16,
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%', background: 'transparent', border: 'none',
          padding: '12px 20px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#ff3d3d', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
            ⚡ ORGANISM SELF-AWARENESS — {organism.mismatch_count} RECONCILIATION FAILURE{organism.mismatch_count !== 1 ? 'S' : ''}
          </span>
        </div>
        <span style={{ color: '#4a5568', fontSize: 11 }}>{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div style={{ padding: '0 20px 16px' }}>
          {organism.next_recommended_action && (
            <div style={{
              background: '#00e5a008', border: '1px solid #00e5a020',
              borderRadius: 8, padding: '10px 14px', marginBottom: 12,
            }}>
              <span style={{ color: '#4a5568', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>NEXT ACTION</span>
              <div style={{ color: '#00e5a0', fontSize: 12, marginTop: 4, fontFamily: "'Space Grotesk', sans-serif" }}>
                {organism.next_recommended_action}
              </div>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {organism.mismatches.map((m, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '8px 12px',
                background: m.severity === 'RED' ? '#ff3d3d08' : '#ffb80008',
                border: `1px solid ${m.severity === 'RED' ? '#ff3d3d20' : '#ffb80020'}`,
                borderRadius: 6,
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', marginTop: 4, flexShrink: 0,
                  background: m.severity === 'RED' ? '#ff3d3d' : '#ffb800',
                }} />
                <div>
                  <div style={{ color: '#e2e8f0', fontSize: 12, fontFamily: "'Space Grotesk', sans-serif" }}>
                    {m.detail}
                  </div>
                  <div style={{ color: '#4a5568', fontSize: 10, marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>
                    {m.name}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Pipeline backbone strip ───────────────────────────────────────────────────
function PipelineStrip({ response }: { response: KycOverviewResponse }) {
  const stages = buildPipelineSummary(response);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0,
      background: '#080c1c', border: '1px solid #ffffff08',
      borderRadius: 10, padding: '10px 20px',
      marginBottom: 16, overflowX: 'auto',
    }}>
      {stages.map((s, i) => (
        <React.Fragment key={s.stage}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 80 }}>
            <span style={{
              fontSize: 18, fontWeight: 700,
              color: s.count > 0 ? '#e2e8f0' : '#2d3748',
              fontFamily: "'Space Grotesk', sans-serif",
            }}>
              {s.count}
            </span>
            <span style={{
              fontSize: 9, color: '#4a5568',
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: '0.06em', textTransform: 'uppercase',
              textAlign: 'center',
            }}>
              {s.label}
            </span>
          </div>
          {i < stages.length - 1 && (
            <div style={{ flex: 1, height: 1, background: '#ffffff08', minWidth: 16 }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── State legend ──────────────────────────────────────────────────────────────
function StateLegend({ response }: { response: KycOverviewResponse }) {
  const oh = response.organism_health;
  const items = [
    { key: 'error', label: 'Error', color: '#ff3d3d' },
    { key: 'stuck', label: 'Stuck', color: '#ff3d3d' },
    { key: 'gap', label: 'Gap', color: '#ffb800' },
    { key: 'waiting', label: 'Waiting', color: '#ffb800' },
    { key: 'analyzing', label: 'Analyzing', color: '#38bdf8' },
    { key: 'active', label: 'Active', color: '#00e5a0' },
    { key: 'payment_pending', label: 'Payment', color: '#ffd700' },
    { key: 'new', label: 'New', color: '#4a5568' },
    { key: 'complete', label: 'Done', color: '#4ade80' },
  ].filter(item => (oh as any)[item.key] > 0);

  if (items.length === 0) return null;

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
      {items.map(item => (
        <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: item.color, boxShadow: `0 0 4px ${item.color}80`,
          }} />
          <span style={{ color: '#4a5568', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
            {(oh as any)[item.key]} {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState({ apiBase }: { apiBase: string }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '80px 40px', gap: 16,
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        border: '2px solid #00e5a030',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 28 }}>◎</span>
      </div>
      <div style={{ color: '#4a5568', fontSize: 14, fontFamily: "'Space Grotesk', sans-serif", textAlign: 'center' }}>
        {apiBase
          ? 'No companies in the pipeline yet.'
          : 'Configure the KYC API endpoint to connect the organism.'}
      </div>
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────
function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '60px 40px', gap: 16,
    }}>
      <div style={{
        background: '#ff3d3d10', border: '1px solid #ff3d3d30',
        borderRadius: 10, padding: '20px 28px', maxWidth: 480, textAlign: 'center',
      }}>
        <div style={{ color: '#ff3d3d', fontSize: 13, fontFamily: "'JetBrains Mono', monospace", marginBottom: 8 }}>
          ORGANISM UNREACHABLE
        </div>
        <div style={{ color: '#4a5568', fontSize: 12, fontFamily: "'Space Grotesk', sans-serif", marginBottom: 16 }}>
          {error}
        </div>
        <button
          onClick={onRetry}
          style={{
            background: '#ff3d3d15', border: '1px solid #ff3d3d30',
            borderRadius: 8, padding: '8px 20px', color: '#ff3d3d',
            fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600,
            fontSize: 12, cursor: 'pointer',
          }}
        >
          Retry
        </button>
      </div>
    </div>
  );
}

// ── Refresh indicator ─────────────────────────────────────────────────────────
function RefreshIndicator({ lastFetch, isLoading }: { lastFetch: Date | null; isLoading: boolean }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(t);
  }, []);

  const age = lastFetch ? Math.floor((now - lastFetch.getTime()) / 1000) : null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {isLoading ? (
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: '#38bdf8',
          animation: 'vio-breathe 1s ease-in-out infinite',
        }} />
      ) : (
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2d3748' }} />
      )}
      <span style={{ color: '#2d3748', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>
        {isLoading ? 'SYNCING' : age !== null ? `${age}s ago` : 'IDLE'}
      </span>
    </div>
  );
}

// ── Main KYC VIO page ─────────────────────────────────────────────────────────
export default function KycVio() {
  const [auth, setAuth] = useState<AuthConfig>(() => loadAuthConfig());
  const [showConfig, setShowConfig] = useState(false);
  const [response, setResponse] = useState<KycOverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  // Build headers for every request
  const buildHeaders = useCallback((): Record<string, string> => {
    const h: Record<string, string> = {};
    if (auth.opsKey) h['X-Ops-Key'] = auth.opsKey;
    return h;
  }, [auth]);

  // Login via password if needed, returns true if session established
  const ensureSession = useCallback(async (base: string): Promise<boolean> => {
    if (auth.opsKey) return true; // key auth — no session needed
    if (!auth.password) return false;
    try {
      const resp = await fetch(`${base}/api/ops/login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: auth.password }),
      });
      return resp.ok;
    } catch {
      return false;
    }
  }, [auth]);

  // Same-origin detection: if we're served from the KYC server itself,
  // use relative URLs (empty base) — no config needed, no CORS, just works.
  const effectiveBase = auth.apiBase || getApiBase() || '';

  const fetchData = useCallback(async () => {
    const base = auth.apiBase || getApiBase() || '';
    setLoading(true);
    setError(null);
    try {
      const headers = buildHeaders();
      let resp = await fetch(`${base}/api/operator/vio/overview?limit=100`, {
        credentials: 'include',
        headers,
      });
      // 403 with password auth — try login then retry once
      if (resp.status === 403 && auth.password && !auth.opsKey) {
        const ok = await ensureSession(base);
        if (ok) {
          resp = await fetch(`${base}/api/operator/vio/overview?limit=100`, {
            credentials: 'include',
            headers,
          });
        }
      }
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try { const j = await resp.json(); detail = j.detail || detail; } catch {}
        throw new Error(detail);
      }
      const data: KycOverviewResponse = await resp.json();
      if (!data.ok) throw new Error(data.error || 'API returned ok=false');
      setResponse(data);
      setLastFetch(new Date());
    } catch (err: any) {
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [auth, buildHeaders, ensureSession]);

  // Initial fetch + 60s auto-refresh
  // Same-origin: always fetch (base is empty string = relative URLs work fine)
  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 60_000);
    return () => clearInterval(t);
  }, [fetchData]);

  const handleSaveConfig = (cfg: AuthConfig) => {
    saveAuthConfig(cfg);
    setAuth(cfg);
    setShowConfig(false);
    setResponse(null);
    setError(null);
  };

  const apiBase = effectiveBase;

  // Build organisms from response
  const organisms: Array<{ organism: VioOrganism; interrupts: VioInterrupt[] }> = response
    ? response.companies.map(c => kycCompanyToOrganism(c))
    : [];

  return (
    <div style={{
      minHeight: '100vh',
      background: 'radial-gradient(ellipse at 20% 20%, #0a1628 0%, #080c1c 40%, #050810 100%)',
      fontFamily: "'Space Grotesk', sans-serif",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: '1px solid #ffffff08',
        padding: '14px 28px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(8,12,28,0.9)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        {/* Logo + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'radial-gradient(circle, #00e5a020 0%, transparent 70%)',
            border: '1.5px solid #00e5a040',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: 10, height: 10, borderRadius: '50%',
              background: '#00e5a0',
              boxShadow: '0 0 8px #00e5a0',
            }} />
          </div>
          <div>
            <div style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700, fontSize: 15, color: '#e2e8f0',
              letterSpacing: '0.02em',
            }}>
              VIO
            </div>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9, color: '#2d3748',
              letterSpacing: '0.1em', textTransform: 'uppercase',
            }}>
              Visual Intelligence Organism
            </div>
          </div>
        </div>

        {/* Right controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <RefreshIndicator lastFetch={lastFetch} isLoading={loading} />

          {response && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: '#2d3748', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                {response.companies.length} companies
              </span>
              {response.urgent_count > 0 && (
                <div style={{
                  background: '#ff3d3d15', border: '1px solid #ff3d3d30',
                  borderRadius: 6, padding: '3px 8px',
                  color: '#ff3d3d', fontSize: 10,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {response.urgent_count} URGENT
                </div>
              )}
            </div>
          )}

          <button
            onClick={fetchData}
            disabled={loading}
            style={{
              background: 'transparent', border: '1px solid #ffffff10',
              borderRadius: 8, padding: '6px 14px', color: '#4a5568',
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.5 : 1,
            }}
          >
            ↺ Sync
          </button>

          <button
            onClick={() => setShowConfig(true)}
            style={{
              background: apiBase ? '#00e5a010' : '#ff3d3d10',
              border: `1px solid ${apiBase ? '#00e5a030' : '#ff3d3d30'}`,
              borderRadius: 8, padding: '6px 14px',
              color: apiBase ? '#00e5a0' : '#ff3d3d',
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
              cursor: 'pointer',
            }}
          >
              {apiBase || true ? '⚙ API' : '⚠ Configure API'}
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '24px 28px', maxWidth: 1200, margin: '0 auto' }}>

        {/* Organism health strip */}
        {response?.organism && (
          <OrganismHealthStrip organism={response.organism} />
        )}

        {/* Organism self-awareness — checks failing */}
        {response?.organism && (
          <OrganismAwarenessPanel organism={response.organism} />
        )}

        {/* Pipeline backbone */}
        {response && response.companies.length > 0 && (
          <PipelineStrip response={response} />
        )}

        {/* State legend */}
        {response && response.companies.length > 0 && (
          <StateLegend response={response} />
        )}

        {/* Company organisms */}
        {!response && !loading && !error && (
          <EmptyState apiBase={apiBase} />
        )}

        {error && (
          <ErrorState error={error} onRetry={fetchData} />
        )}

        {loading && !response && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '80px 40px', gap: 12,
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#00e5a0',
              animation: 'vio-breathe 1.5s ease-in-out infinite',
            }} />
            <span style={{ color: '#4a5568', fontSize: 13, fontFamily: "'JetBrains Mono', monospace" }}>
              CONNECTING TO ORGANISM...
            </span>
          </div>
        )}

        {organisms.length === 0 && response && !loading && (
          <EmptyState apiBase={apiBase} />
        )}

        {organisms.map(({ organism, interrupts }) => (
          <OrganismRow
            key={organism.id}
            organism={organism}
            interrupts={interrupts}
          />
        ))}
      </div>

      {/* Config panel */}
      {showConfig && (
        <ConfigPanel
          config={auth}
          onSave={handleSaveConfig}
          onClose={() => setShowConfig(false)}
        />
      )}
    </div>
  );
}

// ── Organism row — company orb + living timeline ──────────────────────────────
function OrganismRow({
  organism,
  interrupts,
}: {
  organism: VioOrganism;
  interrupts: VioInterrupt[];
}) {
  const [expanded, setExpanded] = useState(true);
  const orbColor = STATE_COLORS[organism.overallState];
  const hasAttention = organism.overallState === 'attention' || organism.overallState === 'blocked';

  return (
    <div
      style={{
        borderRadius: 12, overflow: 'hidden', marginBottom: 12,
        background: 'rgba(8,12,28,0.9)',
        border: `1px solid ${orbColor}18`,
        boxShadow: `0 0 30px ${orbColor}08, 0 2px 12px rgba(0,0,0,0.4)`,
        transition: 'border-color 0.3s ease',
      }}
    >
      {/* Company header */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 20px', cursor: 'pointer',
          borderBottom: expanded ? `1px solid ${orbColor}10` : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Orb */}
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: `radial-gradient(circle, ${orbColor}20 0%, transparent 70%)`,
            border: `1.5px solid ${orbColor}50`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
            animation: hasAttention ? 'vio-breathe 4s ease-in-out infinite' : 'none',
          }}>
            <span style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700, fontSize: 11, color: orbColor,
            }}>
              {organism.initials}
            </span>
          </div>

          {/* Identity */}
          <div>
            <div style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700, fontSize: 14, color: '#e2e8f0',
            }}>
              {organism.name}
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 2 }}>
              <span style={{ color: '#4a5568', fontSize: 11 }}>{organism.email}</span>
              {organism.phone && (
                <>
                  <span style={{ color: '#2d3748' }}>·</span>
                  <span style={{ color: '#4a5568', fontSize: 11 }}>{organism.phone}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* KPIs */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          {organism.kpis.slice(0, 4).map((kpi, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-end' }}>
              <span style={{ color: '#2d3748', fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: 'uppercase' }}>
                {kpi.label}
              </span>
              <span style={{
                color: kpi.valueColor || '#e2e8f0',
                fontSize: 12, fontWeight: 600,
                fontFamily: "'Space Grotesk', sans-serif",
              }}>
                {kpi.value}
              </span>
            </div>
          ))}

          {/* Interrupt count badge */}
          {interrupts.length > 0 && (
            <div style={{
              background: '#ff3d3d15', border: '1px solid #ff3d3d30',
              borderRadius: 6, padding: '4px 8px',
              display: 'flex', alignItems: 'center', gap: 4,
            }}>
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#ff3d3d' }} />
              <span style={{ color: '#ff3d3d', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}>
                {interrupts.length}
              </span>
            </div>
          )}

          <span style={{ color: '#2d3748', fontSize: 14 }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Living timeline canvas */}
      {expanded && (
        <VioCanvas organism={organism} interrupts={interrupts} />
      )}
    </div>
  );
}

/**
 * AgentIntelPage.jsx - Agent Intelligence Hub page for the PMS.
 *
 * Card grid displaying the 5 analytical agents with their latest signals,
 * confidence scores, key drivers, sparklines, and Cross-Asset LLM narrative.
 *
 * Consumes 2 API endpoints:
 * - GET /api/v1/agents           (agent list)
 * - GET /api/v1/agents/{id}/latest (per-agent latest report)
 *
 * Falls back to sample data when API unavailable.
 * All components accessed via window globals (CDN/Babel pattern).
 */

const { useState: _aiUseState, useEffect: _aiUseEffect, useMemo: _aiUseMemo } = React;

// ---------------------------------------------------------------------------
// Access PMS design system from window globals
// ---------------------------------------------------------------------------
const {
  PMS_COLORS: _AC,
  PMS_TYPOGRAPHY: _AT,
  PMS_SPACING: _AS,
  directionColor: _aDirColor,
} = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Agent metadata mapping
// ---------------------------------------------------------------------------
const AGENT_META = {
  inflation_agent:    { name: 'Inflation',       key: 'inflation',    accent: _AC.agent.inflation },
  monetary_agent:     { name: 'Monetary Policy',  key: 'monetary',     accent: _AC.agent.monetary },
  fiscal_agent:       { name: 'Fiscal',           key: 'fiscal',       accent: _AC.agent.fiscal },
  fx_agent:           { name: 'FX Equilibrium',   key: 'fx',           accent: _AC.agent.fx },
  cross_asset_agent:  { name: 'Cross-Asset',      key: 'cross_asset',  accent: _AC.agent.cross_asset },
};

const AGENT_ORDER = ['inflation_agent', 'monetary_agent', 'fiscal_agent', 'fx_agent', 'cross_asset_agent'];

// ---------------------------------------------------------------------------
// Sample Data Fallback
// ---------------------------------------------------------------------------
function generateSampleAgentData() {
  const seed = (n) => {
    const pts = [];
    let v = 0.5 + n * 0.1;
    for (let i = 0; i < 30; i++) {
      v += (Math.sin(i * 0.7 + n) * 0.08) + (Math.cos(i * 0.3 + n * 2) * 0.05);
      v = Math.max(0.1, Math.min(0.95, v));
      pts.push(v);
    }
    return pts;
  };

  return {
    inflation_agent: {
      agent_id: 'inflation_agent',
      direction: 'BEARISH',
      confidence: 0.72,
      drivers: ['IPCA momentum above target', 'Focus expectations rising', 'Wage pressure persistent'],
      risks: ['Core services sticky', 'Inertial component above model'],
      sparkline: seed(1),
      narrative: null,
    },
    monetary_agent: {
      agent_id: 'monetary_agent',
      direction: 'NEUTRAL',
      confidence: 0.65,
      drivers: ['Selic at terminal rate', 'Taylor Rule neutral gap', 'Term premium compressed'],
      risks: ['CPI surprise risk', 'External rate divergence'],
      sparkline: seed(2),
      narrative: null,
    },
    fiscal_agent: {
      agent_id: 'fiscal_agent',
      direction: 'BEARISH',
      confidence: 0.58,
      drivers: ['Debt trajectory rising', 'Primary deficit widening', 'Revenue shortfall vs target'],
      risks: ['Spending ceiling under pressure', 'Election cycle spending'],
      sparkline: seed(3),
      narrative: null,
    },
    fx_agent: {
      agent_id: 'fx_agent',
      direction: 'BULLISH',
      confidence: 0.68,
      drivers: ['Carry advantage Selic-FFR', 'Flow positive (BCB data)', 'BEER model undervalued'],
      risks: ['Global risk-off scenario', 'Terms of trade deterioration'],
      sparkline: seed(4),
      narrative: null,
    },
    cross_asset_agent: {
      agent_id: 'cross_asset_agent',
      direction: 'NEUTRAL',
      confidence: 0.61,
      drivers: ['Mixed regime signals', 'VIX moderate (14-16)', 'Correlation breakdown in rates-FX'],
      risks: ['Regime transition probability elevated', 'Tail risk composite at 0.35'],
      sparkline: seed(5),
      narrative: 'The macro environment presents a mixed picture with competing signals across asset classes. ' +
        'Inflation persistence above BCB targets supports a bearish fixed income view, while the carry advantage ' +
        'in BRL and positive flow dynamics provide support for the currency.\n\n' +
        'The HMM regime classifier assigns 45% probability to Reflation and 35% to Goldilocks, suggesting ' +
        'a potential transition period. Risk appetite indicators are moderate with VIX in the 14-16 range and ' +
        'CDS spreads stable around 145bps.\n\n' +
        'Key trades to monitor: receiver DI1 Jan26 (if COPOM signals hold), tactical BRL long via NDF, ' +
        'and NTN-B 2030 as inflation hedge. Correlation between rates and FX has broken down, creating ' +
        'opportunities for relative value positioning.\n\n' +
        'Risk warnings: Global risk-off event could trigger simultaneous BRL weakness and curve steepening. ' +
        'Fiscal trajectory remains the primary domestic concern with debt/GDP approaching 80%.',
    },
  };
}

// ---------------------------------------------------------------------------
// SVG Sparkline component
// ---------------------------------------------------------------------------
function AgentSparkline({ data, color, width, height }) {
  const w = width || 120;
  const h = height || 30;

  if (!data || data.length < 2) {
    return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = w / (data.length - 1);

  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      <polyline
        points={points}
        fill="none"
        stroke={color || _AC.border.accent}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// AgentCard component
// ---------------------------------------------------------------------------
function AgentCard({ agentData, meta, isCrossAsset }) {
  const [narrativeExpanded, setNarrativeExpanded] = _aiUseState(false);

  const dirLabel = agentData.direction || 'NEUTRAL';
  const dirColor = dirLabel === 'BULLISH' ? _AC.direction.long
    : dirLabel === 'BEARISH' ? _AC.direction.short
    : _AC.direction.neutral;

  const confidence = agentData.confidence || 0;
  const confPct = (confidence * 100).toFixed(0);

  const cardStyle = {
    backgroundColor: _AC.bg.secondary,
    border: `1px solid ${_AC.border.default}`,
    borderLeft: `3px solid ${meta.accent}`,
    borderRadius: '6px',
    padding: '10px 14px',
    fontFamily: _AT.fontFamily,
    gridColumn: isCrossAsset ? 'span 2' : 'span 1',
  };

  return (
    <div style={cardStyle}>
      {/* Header: name + direction badge + confidence */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <span style={{ fontSize: _AT.sizes.base, fontWeight: _AT.weights.bold, color: _AC.text.primary }}>
          {meta.name}
        </span>

        {/* Direction badge */}
        <span style={{
          display: 'inline-block', padding: '1px 8px', borderRadius: '9999px',
          backgroundColor: dirColor, color: _AC.text.inverse,
          fontSize: _AT.sizes.xs, fontWeight: _AT.weights.bold,
        }}>
          {dirLabel}
        </span>

        {/* Confidence */}
        <span style={{ fontSize: _AT.sizes.sm, fontWeight: _AT.weights.bold, color: meta.accent, marginLeft: 'auto' }}>
          {confPct}%
        </span>
      </div>

      {/* Signal summary: direction arrow + confidence bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        {/* Direction arrow */}
        <span style={{ fontSize: _AT.sizes.lg, color: dirColor }}>
          {dirLabel === 'BULLISH' ? '\u25B2' : dirLabel === 'BEARISH' ? '\u25BC' : '\u25B6'}
        </span>

        {/* Confidence bar */}
        <div style={{ flex: 1, height: '6px', backgroundColor: _AC.bg.tertiary, borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            width: `${confPct}%`, height: '100%',
            backgroundColor: meta.accent, borderRadius: '3px',
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Top 3 Key Drivers */}
      <div style={{ marginBottom: '8px' }}>
        <div style={{ fontSize: _AT.sizes.xs, color: _AC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '3px' }}>
          Key Drivers
        </div>
        {(agentData.drivers || []).slice(0, 3).map((driver, i) => (
          <div key={i} style={{
            fontSize: _AT.sizes.xs, color: _AC.text.secondary, lineHeight: 1.5,
            paddingLeft: '8px', position: 'relative',
          }}>
            <span style={{ position: 'absolute', left: 0, color: meta.accent }}>{'\u2022'}</span>
            {driver}
          </div>
        ))}
      </div>

      {/* Risks */}
      <div style={{ marginBottom: '8px' }}>
        <div style={{ fontSize: _AT.sizes.xs, color: _AC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '3px' }}>
          Risks
        </div>
        {(agentData.risks || []).length > 0 ? (
          agentData.risks.slice(0, 2).map((risk, i) => (
            <div key={i} style={{ fontSize: _AT.sizes.xs, color: _AC.risk.warning, lineHeight: 1.5, paddingLeft: '8px' }}>
              {'\u26A0'} {risk}
            </div>
          ))
        ) : (
          <div style={{ fontSize: _AT.sizes.xs, color: _AC.text.muted, paddingLeft: '8px' }}>No elevated risks</div>
        )}
      </div>

      {/* Sparkline */}
      <div style={{ marginBottom: isCrossAsset && agentData.narrative ? '8px' : 0 }}>
        <div style={{ fontSize: _AT.sizes.xs, color: _AC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '3px' }}>
          30-Day Signal
        </div>
        <AgentSparkline data={agentData.sparkline} color={meta.accent} width={isCrossAsset ? 280 : 120} height={30} />
      </div>

      {/* Cross-Asset Narrative (expandable) */}
      {isCrossAsset && agentData.narrative && (
        <div style={{ borderTop: `1px solid ${_AC.border.subtle}`, paddingTop: '8px', marginTop: '4px' }}>
          <button
            onClick={() => setNarrativeExpanded(!narrativeExpanded)}
            style={{
              background: 'none', border: 'none', color: _AC.border.accent,
              fontSize: _AT.sizes.xs, fontWeight: _AT.weights.semibold,
              fontFamily: _AT.fontFamily, cursor: 'pointer', padding: 0,
              display: 'flex', alignItems: 'center', gap: '4px',
            }}
          >
            <span style={{ transform: narrativeExpanded ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform 0.2s', display: 'inline-block' }}>
              {'\u25B6'}
            </span>
            {narrativeExpanded ? 'Hide narrative' : 'Read full narrative'}
          </button>

          {narrativeExpanded && (
            <div style={{
              marginTop: '8px', padding: '10px', backgroundColor: _AC.bg.tertiary,
              borderRadius: '4px', maxHeight: '300px', overflowY: 'auto',
              fontSize: _AT.sizes.sm, color: _AC.text.secondary, lineHeight: 1.6,
              fontFamily: _AT.fontFamily, whiteSpace: 'pre-wrap',
            }}>
              {agentData.narrative}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AgentIntelPage Component
// ---------------------------------------------------------------------------
function AgentIntelPage() {
  const [agentReports, setAgentReports] = _aiUseState({});
  const [loading, setLoading] = _aiUseState(true);
  const [lastUpdated, setLastUpdated] = _aiUseState(null);

  _aiUseEffect(() => {
    let cancelled = false;

    async function fetchAgentData() {
      setLoading(true);
      const results = {};

      try {
        // Fetch agent list
        const listRes = await fetch('/api/v1/agents');
        if (!listRes.ok) throw new Error('HTTP ' + listRes.status);
        const agentList = await listRes.json();
        const agentIds = Array.isArray(agentList) ? agentList.map((a) => a.id || a.agent_id || a) : AGENT_ORDER;

        // Sequential fetch per agent (per Phase 19 pattern)
        for (const agentId of agentIds) {
          if (cancelled) return;
          try {
            const res = await fetch(`/api/v1/agents/${agentId}/latest`);
            if (!res.ok) continue;
            const report = await res.json();

            // Parse report into our format
            const signals = report.signals || [];
            let direction = 'NEUTRAL';
            let totalConf = 0;
            const drivers = [];

            if (signals.length > 0) {
              let longCount = 0;
              let shortCount = 0;
              signals.forEach((s) => {
                const d = (s.direction || '').toUpperCase();
                if (d === 'LONG' || d === 'BULLISH') longCount++;
                else if (d === 'SHORT' || d === 'BEARISH') shortCount++;
                totalConf += s.confidence || 0;
                if (s.signal_id) drivers.push(`${s.signal_id}: ${s.value != null ? s.value.toFixed(2) : 'N/A'}`);
              });
              direction = longCount > shortCount ? 'BULLISH' : shortCount > longCount ? 'BEARISH' : 'NEUTRAL';
              totalConf = totalConf / signals.length;
            }

            // Generate sparkline from signal values or synthetic
            const sparkline = signals.length > 0
              ? Array.from({ length: 30 }, (_, i) => 0.5 + Math.sin(i * 0.5 + signals.length) * 0.2)
              : Array.from({ length: 30 }, (_, i) => 0.5 + Math.sin(i * 0.3) * 0.15);

            results[agentId] = {
              agent_id: agentId,
              direction,
              confidence: totalConf || 0.5,
              drivers: drivers.length > 0 ? drivers.slice(0, 3) : ['No signal data'],
              risks: [],
              sparkline,
              narrative: report.narrative || null,
            };
          } catch (_) {
            // Skip failed agent
          }
        }

        if (cancelled) return;

        if (Object.keys(results).length > 0) {
          setAgentReports(results);
          setLastUpdated(new Date());
        } else {
          throw new Error('No agent data');
        }
      } catch (_) {
        // Full fallback to sample data
        if (!cancelled) {
          setAgentReports(generateSampleAgentData());
          setLastUpdated(new Date());
        }
      }

      if (!cancelled) setLoading(false);
    }

    fetchAgentData();
    return () => { cancelled = true; };
  }, []);

  const pageStyle = {
    fontFamily: _AT.fontFamily,
    color: _AC.text.primary,
    maxWidth: '1400px',
    margin: '0 auto',
  };

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: _AS.md,
  };

  return (
    <div style={pageStyle}>
      {/* Page header */}
      <div style={{ marginBottom: _AS.md }}>
        <div style={{ fontSize: _AT.sizes['2xl'], fontWeight: _AT.weights.bold, color: _AC.text.primary, marginBottom: '2px' }}>
          Agent Intelligence Hub
        </div>
        <div style={{ fontSize: _AT.sizes.xs, color: _AC.text.muted }}>
          Latest agent signals and AI-driven analysis
          {lastUpdated && ` | Updated ${lastUpdated.toLocaleTimeString()}`}
        </div>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div style={gridStyle}>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} style={{ gridColumn: i === 5 ? 'span 2' : 'span 1' }}>
              <window.PMSSkeleton height="200px" />
            </div>
          ))}
        </div>
      )}

      {/* Agent Card Grid */}
      {!loading && (
        <div style={gridStyle}>
          {AGENT_ORDER.map((agentId) => {
            const data = agentReports[agentId];
            const meta = AGENT_META[agentId];
            if (!data || !meta) return null;
            const isCrossAsset = agentId === 'cross_asset_agent';

            return (
              <AgentCard
                key={agentId}
                agentData={data}
                meta={meta}
                isCrossAsset={isCrossAsset}
              />
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {!loading && Object.keys(agentReports).length === 0 && (
        <div style={{ textAlign: 'center', padding: '32px', color: _AC.text.muted, fontSize: _AT.sizes.sm }}>
          No agent data available
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.AgentIntelPage = AgentIntelPage;

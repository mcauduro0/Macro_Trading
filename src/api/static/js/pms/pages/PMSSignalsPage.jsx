/**
 * PMSSignalsPage.jsx - Signal Heatmap page for the PMS.
 *
 * Bloomberg PORT-dense signal visualization:
 * 1. Signal Heatmap (30 days x strategies) with direction/conviction coloring
 * 2. Signal Flip Timeline (chronological direction changes)
 * 3. Consensus Summary (agreement ratios across agents)
 *
 * Consumes: /api/v1/signals/latest (30s poll)
 * Falls back to deterministic sample data when API unavailable.
 */

const { useState, useMemo } = React;

// ---------------------------------------------------------------------------
// Access PMS design system from window globals
// ---------------------------------------------------------------------------
const {
  PMS_COLORS: _C,
  PMS_TYPOGRAPHY: _T,
  PMS_SPACING: _S,
  pnlColor: _pnlColor,
  formatNumber: _formatNumber,
  seededRng,
  dirBadgeVariant,
} = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Strategy IDs for sample data
// ---------------------------------------------------------------------------
const SAMPLE_STRATEGIES = ['INF-01', 'INF-02', 'RATES-03', 'FX-02', 'FX-04', 'SOV-01', 'CROSS-01', 'CUPOM-01'];

// ---------------------------------------------------------------------------
// Date helper: generate array of last N date strings (YYYY-MM-DD)
// ---------------------------------------------------------------------------
function getLastNDates(n) {
  const dates = [];
  const today = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    dates.push(d.toISOString().slice(0, 10));
  }
  return dates;
}

// ---------------------------------------------------------------------------
// Sample Data Fallback
// ---------------------------------------------------------------------------
function generateSampleSignals() {
  const rng = seededRng(42);
  const dates = getLastNDates(30);
  const signals = [];

  SAMPLE_STRATEGIES.forEach(sid => {
    let dir = rng() > 0.5 ? 'LONG' : 'SHORT';
    dates.forEach(d => {
      if (rng() < 0.08) dir = dir === 'LONG' ? 'SHORT' : rng() < 0.3 ? 'NEUTRAL' : 'LONG';
      signals.push({
        agent_id: sid,
        date: d,
        direction: dir,
        confidence: 0.3 + rng() * 0.6,
      });
    });
  });

  return {
    data: {
      signals,
      consensus: {
        LONG: { count: 5, agreement_ratio: 0.62, avg_confidence: 0.71 },
        SHORT: { count: 2, agreement_ratio: 0.25, avg_confidence: 0.65 },
        NEUTRAL: { count: 1, agreement_ratio: 0.13, avg_confidence: 0.45 },
      },
    },
  };
}

// ---------------------------------------------------------------------------
// Heatmap cell color: direction + conviction -> rgba
// ---------------------------------------------------------------------------
function cellColor(direction, confidence) {
  const alpha = Math.max(0.15, Math.min(0.9, confidence || 0.5));
  const dir = (direction || '').toUpperCase();
  if (dir === 'LONG') {
    // green channel from _C.pnl.positive (#3fb950)
    return 'rgba(63, 185, 80, ' + alpha.toFixed(2) + ')';
  }
  if (dir === 'SHORT') {
    // red channel from _C.pnl.negative (#f85149)
    return 'rgba(248, 81, 73, ' + alpha.toFixed(2) + ')';
  }
  // NEUTRAL - gray
  return 'rgba(139, 148, 158, ' + (alpha * 0.5).toFixed(2) + ')';
}

// ---------------------------------------------------------------------------
// Format short date for column headers (MM-DD)
// ---------------------------------------------------------------------------
function shortDate(dateStr) {
  if (!dateStr) return '';
  return dateStr.slice(5); // "MM-DD"
}

// ---------------------------------------------------------------------------
// Signal Heatmap Component
// ---------------------------------------------------------------------------
function SignalHeatmap({ signals, strategies, dates }) {
  const [tooltip, setTooltip] = useState(null);

  // Build a lookup map: strategyId -> { date -> signal }
  const signalMap = useMemo(() => {
    const map = {};
    (signals || []).forEach(s => {
      if (!map[s.agent_id]) map[s.agent_id] = {};
      map[s.agent_id][s.date] = s;
    });
    return map;
  }, [signals]);

  const containerStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '10px 12px',
    marginBottom: _S.md,
    overflowX: 'auto',
  };

  const sectionTitleStyle = {
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _T.fontFamily,
    marginBottom: '8px',
  };

  const gridContainerStyle = {
    display: 'grid',
    gridTemplateColumns: '120px ' + dates.map(() => '1fr').join(' '),
    gap: '1px',
    minWidth: dates.length * 26 + 120 + 'px',
    position: 'relative',
  };

  // Date header cell
  const dateHeaderStyle = {
    fontSize: '8px',
    fontFamily: _T.fontFamily,
    color: _C.text.muted,
    writingMode: 'vertical-rl',
    textAlign: 'center',
    padding: '4px 2px',
    whiteSpace: 'nowrap',
    transform: 'rotate(180deg)',
    minHeight: '50px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  // Strategy label cell
  const strategyLabelStyle = {
    fontSize: _T.sizes.xs,
    fontFamily: _T.fontFamily,
    fontWeight: _T.weights.semibold,
    color: _C.text.secondary,
    display: 'flex',
    alignItems: 'center',
    padding: '0 6px',
    minHeight: '24px',
    whiteSpace: 'nowrap',
    backgroundColor: _C.bg.secondary,
  };

  // Heatmap cell
  const heatmapCellStyle = (bg) => ({
    minHeight: '24px',
    backgroundColor: bg,
    borderRadius: '2px',
    cursor: 'pointer',
    transition: 'opacity 0.15s',
  });

  // Tooltip overlay
  const tooltipStyle = {
    position: 'fixed',
    zIndex: 50,
    backgroundColor: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    padding: '6px 10px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
    color: _C.text.primary,
    pointerEvents: 'none',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    maxWidth: '220px',
  };

  const handleCellEnter = (e, signal) => {
    if (!signal) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltip({
      x: rect.left + rect.width / 2,
      y: rect.top - 4,
      signal,
    });
  };

  const handleCellLeave = () => {
    setTooltip(null);
  };

  return (
    <div style={containerStyle}>
      <div style={sectionTitleStyle}>Signal Heatmap</div>

      <div style={{ overflowX: 'auto' }}>
        <div style={gridContainerStyle}>
          {/* Top-left corner (empty) */}
          <div style={{ minHeight: '50px' }} />

          {/* Date headers */}
          {dates.map(d => (
            <div key={d} style={dateHeaderStyle}>
              {shortDate(d)}
            </div>
          ))}

          {/* Strategy rows */}
          {strategies.map(sid => (
            <React.Fragment key={sid}>
              {/* Strategy label */}
              <div style={strategyLabelStyle}>{sid}</div>

              {/* Signal cells */}
              {dates.map(d => {
                const signal = signalMap[sid] && signalMap[sid][d];
                const bg = signal
                  ? cellColor(signal.direction, signal.confidence)
                  : _C.bg.tertiary;

                return (
                  <div
                    key={d}
                    style={heatmapCellStyle(bg)}
                    onMouseEnter={(e) => handleCellEnter(e, signal)}
                    onMouseLeave={handleCellLeave}
                  />
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && tooltip.signal && (
        <div style={{
          ...tooltipStyle,
          left: tooltip.x + 'px',
          top: (tooltip.y - 60) + 'px',
          transform: 'translateX(-50%)',
        }}>
          <div style={{ fontWeight: _T.weights.bold, marginBottom: '2px' }}>
            {tooltip.signal.agent_id}
          </div>
          <div style={{ color: _C.text.secondary, marginBottom: '2px' }}>
            {tooltip.signal.date}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{
              color: tooltip.signal.direction === 'LONG' ? _C.direction.long
                : tooltip.signal.direction === 'SHORT' ? _C.direction.short
                : _C.direction.neutral,
              fontWeight: _T.weights.semibold,
            }}>
              {tooltip.signal.direction}
            </span>
            <span style={{ color: _C.text.muted }}>
              {(tooltip.signal.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: '16px',
        marginTop: '10px',
        paddingTop: '8px',
        borderTop: '1px solid ' + _C.border.subtle,
      }}>
        {[
          { label: 'LONG', color: 'rgba(63, 185, 80, 0.65)' },
          { label: 'SHORT', color: 'rgba(248, 81, 73, 0.65)' },
          { label: 'NEUTRAL', color: 'rgba(139, 148, 158, 0.30)' },
        ].map(item => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '14px',
              height: '14px',
              borderRadius: '2px',
              backgroundColor: item.color,
            }} />
            <span style={{
              fontSize: _T.sizes.xs,
              fontFamily: _T.fontFamily,
              color: _C.text.secondary,
            }}>
              {item.label}
            </span>
          </div>
        ))}
        <span style={{
          fontSize: _T.sizes.xs,
          fontFamily: _T.fontFamily,
          color: _C.text.muted,
          marginLeft: 'auto',
        }}>
          Opacity = conviction strength
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal Flip Timeline Component
// ---------------------------------------------------------------------------
function SignalFlipTimeline({ signals, strategies, dates }) {
  // Extract direction changes between consecutive days
  const flips = useMemo(() => {
    if (!signals || signals.length === 0) return [];

    // Build lookup: strategy -> [signals sorted by date]
    const byStrategy = {};
    signals.forEach(s => {
      if (!byStrategy[s.agent_id]) byStrategy[s.agent_id] = {};
      byStrategy[s.agent_id][s.date] = s;
    });

    const result = [];
    strategies.forEach(sid => {
      const stratSignals = byStrategy[sid];
      if (!stratSignals) return;

      for (let i = 1; i < dates.length; i++) {
        const prev = stratSignals[dates[i - 1]];
        const curr = stratSignals[dates[i]];
        if (prev && curr && prev.direction !== curr.direction) {
          result.push({
            date: dates[i],
            strategy: sid,
            from: prev.direction,
            to: curr.direction,
            confidence: curr.confidence,
          });
        }
      }
    });

    // Sort by date descending, then strategy
    result.sort((a, b) => {
      const dateCmp = b.date.localeCompare(a.date);
      if (dateCmp !== 0) return dateCmp;
      return a.strategy.localeCompare(b.strategy);
    });

    return result.slice(0, 30);
  }, [signals, strategies, dates]);

  const containerStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '10px 12px',
    marginBottom: _S.md,
  };

  const sectionTitleStyle = {
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _T.fontFamily,
    marginBottom: '8px',
  };

  const headerRowStyle = {
    display: 'grid',
    gridTemplateColumns: '100px 90px 1fr 80px',
    gap: '8px',
    padding: '4px 8px',
    borderBottom: '1px solid ' + _C.border.default,
    marginBottom: '4px',
  };

  const headerCellStyle = {
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    fontFamily: _T.fontFamily,
    whiteSpace: 'nowrap',
  };

  const flipRowStyle = (idx) => ({
    display: 'grid',
    gridTemplateColumns: '100px 90px 1fr 80px',
    gap: '8px',
    padding: '4px 8px',
    backgroundColor: idx % 2 === 0 ? _C.bg.secondary : _C.bg.tertiary,
    alignItems: 'center',
    transition: 'background-color 0.1s',
  });

  const cellStyle = {
    fontSize: _T.sizes.sm,
    fontFamily: _T.fontFamily,
    color: _C.text.primary,
    whiteSpace: 'nowrap',
  };

  const arrowStyle = {
    fontSize: _T.sizes.sm,
    color: _C.text.muted,
    margin: '0 4px',
  };

  if (flips.length === 0) {
    return (
      <div style={containerStyle}>
        <div style={sectionTitleStyle}>Signal Flip Timeline</div>
        <div style={{
          textAlign: 'center',
          padding: '16px',
          color: _C.text.muted,
          fontSize: _T.sizes.sm,
          fontFamily: _T.fontFamily,
        }}>
          No signal direction changes detected
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={sectionTitleStyle}>Signal Flip Timeline</div>

      {/* Header */}
      <div style={headerRowStyle}>
        <div style={headerCellStyle}>Date</div>
        <div style={headerCellStyle}>Strategy</div>
        <div style={headerCellStyle}>Direction Change</div>
        <div style={{ ...headerCellStyle, textAlign: 'right' }}>Conviction</div>
      </div>

      {/* Flip rows */}
      {flips.map((flip, idx) => (
        <div
          key={flip.date + '-' + flip.strategy + '-' + idx}
          style={flipRowStyle(idx)}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = _C.bg.elevated; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = idx % 2 === 0 ? _C.bg.secondary : _C.bg.tertiary; }}
        >
          <div style={cellStyle}>{flip.date}</div>
          <div style={{ ...cellStyle, fontWeight: _T.weights.semibold }}>{flip.strategy}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <window.PMSBadge label={flip.from} variant={dirBadgeVariant(flip.from)} size="sm" />
            <span style={arrowStyle}>{'\u2192'}</span>
            <window.PMSBadge label={flip.to} variant={dirBadgeVariant(flip.to)} size="sm" />
          </div>
          <div style={{ ...cellStyle, textAlign: 'right', color: _C.text.secondary }}>
            {(flip.confidence * 100).toFixed(0)}%
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Consensus Summary Component
// ---------------------------------------------------------------------------
function ConsensusSummary({ consensus }) {
  if (!consensus) return null;

  const containerStyle = {
    display: 'flex',
    gap: _S.md,
    marginBottom: _S.md,
  };

  const directions = [
    { key: 'LONG', label: 'LONG', variant: 'positive', color: _C.direction.long },
    { key: 'SHORT', label: 'SHORT', variant: 'negative', color: _C.direction.short },
    { key: 'NEUTRAL', label: 'NEUTRAL', variant: 'neutral', color: _C.direction.neutral },
  ];

  return (
    <div>
      <div style={{
        fontSize: _T.sizes.xs,
        fontWeight: _T.weights.semibold,
        color: _C.text.muted,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        fontFamily: _T.fontFamily,
        marginBottom: '8px',
      }}>
        Consensus Summary
      </div>

      <div style={containerStyle}>
        {directions.map(dir => {
          const data = consensus[dir.key];
          if (!data) return null;

          return (
            <div key={dir.key} style={{
              flex: '1 1 0',
              backgroundColor: _C.bg.secondary,
              border: '1px solid ' + _C.border.default,
              borderLeft: '3px solid ' + dir.color,
              borderRadius: '6px',
              padding: '10px 14px',
              fontFamily: _T.fontFamily,
            }}>
              {/* Direction badge */}
              <div style={{ marginBottom: '8px' }}>
                <window.PMSBadge label={dir.label} variant={dir.variant} />
              </div>

              {/* Metrics grid */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {/* Agreement ratio */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: _T.sizes.xs, color: _C.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Agreement
                  </span>
                  <span style={{ fontSize: _T.sizes.lg, fontWeight: _T.weights.bold, color: dir.color }}>
                    {(data.agreement_ratio * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Agreement gauge bar */}
                <div style={{ width: '100%', height: '4px', backgroundColor: _C.bg.tertiary, borderRadius: '2px', overflow: 'hidden' }}>
                  <div style={{
                    width: (data.agreement_ratio * 100) + '%',
                    height: '100%',
                    backgroundColor: dir.color,
                    borderRadius: '2px',
                    transition: 'width 0.3s ease',
                  }} />
                </div>

                {/* Count */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: _T.sizes.xs, color: _C.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Count
                  </span>
                  <span style={{ fontSize: _T.sizes.base, fontWeight: _T.weights.semibold, color: _C.text.primary }}>
                    {data.count}
                  </span>
                </div>

                {/* Avg confidence */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: _T.sizes.xs, color: _C.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Avg Confidence
                  </span>
                  <span style={{ fontSize: _T.sizes.base, fontWeight: _T.weights.semibold, color: _C.text.secondary }}>
                    {(data.avg_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------
function SignalsPageSkeleton() {
  return (
    <div style={{ fontFamily: _T.fontFamily }}>
      <window.PMSSkeleton width="100%" height="280px" />
      <div style={{ marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="200px" />
      </div>
      <div style={{ display: 'flex', gap: _S.md, marginTop: _S.md }}>
        <window.PMSSkeleton width="33%" height="140px" />
        <window.PMSSkeleton width="33%" height="140px" />
        <window.PMSSkeleton width="33%" height="140px" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main PMSSignalsPage Component
// ---------------------------------------------------------------------------
function PMSSignalsPage() {
  // Fetch signals data (30s polling)
  const signalsFetch = window.useFetch('/api/v1/signals/latest', 30000);

  const isLoading = signalsFetch.loading;

  // Resolve data — empty state instead of sample fallback
  const resolved = useMemo(() => {
    const d = signalsFetch.data;
    if (d && d.data && d.data.signals) {
      return d;
    }
    if (d && d.signals) {
      return { data: d };
    }
    return { data: { signals: [], consensus: null } };
  }, [signalsFetch.data]);

  const usingSample = false;

  const signals = resolved.data.signals || [];
  const consensus = resolved.data.consensus || null;

  // Extract unique strategies and dates from signals
  const strategies = useMemo(() => {
    const set = new Set();
    signals.forEach(s => set.add(s.agent_id));
    // Maintain sample order if possible, otherwise alphabetical
    const found = [];
    SAMPLE_STRATEGIES.forEach(sid => {
      if (set.has(sid)) found.push(sid);
    });
    // Add any extra strategies not in sample list
    set.forEach(sid => {
      if (!found.includes(sid)) found.push(sid);
    });
    return found;
  }, [signals]);

  const dates = useMemo(() => {
    const set = new Set();
    signals.forEach(s => set.add(s.date));
    return Array.from(set).sort();
  }, [signals]);

  const today = new Date().toISOString().split('T')[0];

  const pageStyle = {
    fontFamily: _T.fontFamily,
    color: _C.text.primary,
    maxWidth: '1400px',
    margin: '0 auto',
  };

  const titleStyle = {
    fontSize: _T.sizes['2xl'],
    fontWeight: _T.weights.bold,
    color: _C.text.primary,
    marginBottom: '2px',
  };

  const subtitleStyle = {
    fontSize: _T.sizes.xs,
    color: _C.text.muted,
    marginBottom: _S.md,
  };

  return (
    <div style={pageStyle}>
      {usingSample && <PMSSampleDataBanner />}

      {/* Page header */}
      <div style={{ marginBottom: _S.md }}>
        <div style={titleStyle}>Signal Heatmap</div>
        <div style={subtitleStyle}>
          {today} | {strategies.length} strategies | {dates.length} days | Updated {new Date().toLocaleTimeString()}
        </div>
      </div>

      {isLoading ? (
        <SignalsPageSkeleton />
      ) : (
        <React.Fragment>
          {/* Section 1: Signal Heatmap */}
          <SignalHeatmap
            signals={signals}
            strategies={strategies}
            dates={dates}
          />

          {/* Section 2: Signal Flip Timeline */}
          <SignalFlipTimeline
            signals={signals}
            strategies={strategies}
            dates={dates}
          />

          {/* Section 3: Consensus Summary */}
          <ConsensusSummary consensus={consensus} />
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.PMSSignalsPage = PMSSignalsPage;

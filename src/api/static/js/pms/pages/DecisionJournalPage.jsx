/**
 * DecisionJournalPage.jsx - Decision Journal page for the PMS.
 *
 * Vertical timeline view of all trading decisions (OPEN, CLOSE, REJECT, NOTE)
 * with expandable detail cards, filter bar, infinite scroll, and outcome tracking.
 *
 * Consumes 3 API endpoints:
 * - GET  /api/v1/pms/journal/                      (filtered + paginated entries)
 * - GET  /api/v1/pms/journal/stats/decision-analysis (summary stats)
 * - POST /api/v1/pms/journal/{entry_id}/outcome     (record outcome)
 *
 * Falls back to sample data when API unavailable.
 * All components accessed via window globals (CDN/Babel pattern).
 */

const { useState, useEffect, useCallback, useMemo, useRef } = React;

// ---------------------------------------------------------------------------
// Access PMS design system from window globals
// ---------------------------------------------------------------------------
const {
  PMS_COLORS: _JC,
  PMS_TYPOGRAPHY: _JT,
  PMS_SPACING: _JS,
  pnlColor: _jpnl,
  formatPnL: _jfmtPnl,
  formatNumber: _jfmtNum,
} = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const PAGE_SIZE = 20;

const TYPE_COLORS = {
  OPEN: _JC.border.accent,
  CLOSE: null, // dynamic based on P&L
  REJECT: _JC.risk.warning,
  NOTE: _JC.text.muted,
};

const ASSET_CLASSES = ['All', 'FX', 'Rates', 'Inflation', 'Sovereign', 'Cross-Asset'];

// ---------------------------------------------------------------------------
// Date range preset helpers
// ---------------------------------------------------------------------------
function getDatePreset(preset) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  switch (preset) {
    case 'Today':
      return { start: today, end: today };
    case 'This Week': {
      const day = today.getDay();
      const monday = new Date(today);
      monday.setDate(today.getDate() - (day === 0 ? 6 : day - 1));
      return { start: monday, end: today };
    }
    case 'MTD':
      return { start: new Date(today.getFullYear(), today.getMonth(), 1), end: today };
    case 'QTD': {
      const qMonth = Math.floor(today.getMonth() / 3) * 3;
      return { start: new Date(today.getFullYear(), qMonth, 1), end: today };
    }
    case 'YTD':
      return { start: new Date(today.getFullYear(), 0, 1), end: today };
    default:
      return { start: null, end: null };
  }
}

function fmtIso(d) {
  if (!d) return '';
  return d.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Sample Data Fallback
// ---------------------------------------------------------------------------
function generateSampleEntries() {
  const instruments = [
    'DI1F26', 'USDBRL', 'NTN-B 2030', 'CDS BR 5Y', 'DDI Jan26',
    'IBOV FUT', 'DI1 Jan27', 'NTN-B 2035', 'USDBRL NDF 3M',
  ];
  const types = ['OPEN', 'CLOSE', 'REJECT', 'NOTE', 'OPEN', 'CLOSE', 'OPEN', 'REJECT',
    'NOTE', 'OPEN', 'CLOSE', 'OPEN', 'REJECT', 'OPEN', 'CLOSE'];
  const directions = ['LONG', 'SHORT', 'LONG', 'SHORT', 'LONG'];
  const now = Date.now();
  const DAY = 86400000;

  return types.map((t, i) => {
    const daysAgo = Math.floor(i * 2.1);
    const created = new Date(now - daysAgo * DAY);
    const pnl = t === 'CLOSE' ? (i % 3 === 0 ? 125000 : -45000) : null;
    return {
      id: i + 1,
      created_at: created.toISOString(),
      entry_type: t,
      position_id: Math.floor(i / 2) + 1,
      instrument: instruments[i % instruments.length],
      direction: directions[i % directions.length],
      notional_brl: 15000000 + i * 2000000,
      entry_price: 5800 + i * 12.5,
      manager_notes: 'Breakeven underpriced versus model fair value. Conviction supported by IPCA persistence.',
      system_notes: 'Signal from Inflation Agent with 0.82 conviction.',
      market_snapshot: { USDBRL: '4.92', DI1_Jan26: '13.75', IBOV: '127800', VIX: '14.2' },
      portfolio_snapshot: { AUM: 'BRL 500M', leverage: '1.8x', VaR_95: '1.42%', open_positions: 8 },
      content_hash: 'a1b2c3d4e5f6' + String(i).padStart(4, '0') + 'abcdef1234567890',
      realized_pnl: pnl,
      strategy: 'INF-0' + ((i % 3) + 1),
      conviction: 0.55 + (i % 5) * 0.08,
      asset_class: ['Rates', 'FX', 'Inflation', 'Sovereign', 'FX'][i % 5],
    };
  });
}

// ---------------------------------------------------------------------------
// JournalFilterBar component
// ---------------------------------------------------------------------------
function JournalFilterBar({ filters, onFilterChange }) {
  const presets = ['Today', 'This Week', 'MTD', 'QTD', 'YTD', 'Custom'];
  const types = ['OPEN', 'CLOSE', 'REJECT', 'NOTE'];
  const searchTimerRef = useRef(null);

  const handlePresetClick = (preset) => {
    if (preset === 'Custom') {
      onFilterChange({ ...filters, datePreset: 'Custom' });
    } else {
      const { start, end } = getDatePreset(preset);
      onFilterChange({
        ...filters,
        datePreset: preset,
        startDate: fmtIso(start),
        endDate: fmtIso(end),
      });
    }
  };

  const handleTypeToggle = (type) => {
    const current = filters.types || [];
    const next = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type];
    onFilterChange({ ...filters, types: next });
  };

  const handleSearchChange = (e) => {
    const val = e.target.value;
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      onFilterChange({ ...filters, instrument: val });
    }, 300);
  };

  const btnStyle = (active) => ({
    padding: '3px 10px',
    backgroundColor: active ? _JC.border.accent : _JC.bg.tertiary,
    color: active ? _JC.text.inverse : _JC.text.secondary,
    border: `1px solid ${active ? _JC.border.accent : _JC.border.default}`,
    borderRadius: '4px',
    fontSize: _JT.sizes.xs,
    fontWeight: _JT.weights.semibold,
    fontFamily: _JT.fontFamily,
    cursor: 'pointer',
  });

  const typeBtnColor = (type, active) => {
    if (!active) return _JC.bg.tertiary;
    return TYPE_COLORS[type] || _JC.border.accent;
  };

  const inputStyle = {
    padding: '3px 8px',
    backgroundColor: _JC.bg.tertiary,
    border: `1px solid ${_JC.border.default}`,
    borderRadius: '4px',
    color: _JC.text.primary,
    fontSize: _JT.sizes.xs,
    fontFamily: _JT.fontFamily,
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap',
      padding: '8px 0', marginBottom: '8px', borderBottom: `1px solid ${_JC.border.subtle}`,
    }}>
      {/* Date presets */}
      {presets.map((p) => (
        <button key={p} onClick={() => handlePresetClick(p)} style={btnStyle(filters.datePreset === p)}>
          {p}
        </button>
      ))}

      {/* Custom date inputs */}
      {filters.datePreset === 'Custom' && (
        <React.Fragment>
          <input type="date" value={filters.startDate || ''} onChange={(e) => onFilterChange({ ...filters, startDate: e.target.value })} style={inputStyle} />
          <input type="date" value={filters.endDate || ''} onChange={(e) => onFilterChange({ ...filters, endDate: e.target.value })} style={inputStyle} />
        </React.Fragment>
      )}

      <span style={{ width: '1px', height: '20px', backgroundColor: _JC.border.default, margin: '0 4px' }} />

      {/* Decision type toggles */}
      {types.map((t) => {
        const active = (filters.types || []).includes(t);
        return (
          <button key={t} onClick={() => handleTypeToggle(t)} style={{
            ...btnStyle(active),
            backgroundColor: typeBtnColor(t, active),
            borderColor: active ? typeBtnColor(t, active) : _JC.border.default,
          }}>
            {t}
          </button>
        );
      })}

      <span style={{ width: '1px', height: '20px', backgroundColor: _JC.border.default, margin: '0 4px' }} />

      {/* Asset class dropdown */}
      <select
        value={filters.assetClass || 'All'}
        onChange={(e) => onFilterChange({ ...filters, assetClass: e.target.value })}
        style={inputStyle}
      >
        {ASSET_CLASSES.map((ac) => (
          <option key={ac} value={ac}>{ac}</option>
        ))}
      </select>

      {/* Instrument search */}
      <input
        type="text"
        placeholder="Search instrument..."
        defaultValue={filters.instrument || ''}
        onChange={handleSearchChange}
        style={{ ...inputStyle, width: '140px' }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// DecisionCard component (collapsed + expandable)
// ---------------------------------------------------------------------------
function DecisionCard({ entry, onRecordOutcome }) {
  const [expanded, setExpanded] = useState(false);
  const [outcomeMode, setOutcomeMode] = useState(false);
  const [outcomeNotes, setOutcomeNotes] = useState('');
  const [pnlAssessment, setPnlAssessment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const typeColor = entry.entry_type === 'CLOSE'
    ? _jpnl(entry.realized_pnl)
    : (TYPE_COLORS[entry.entry_type] || _JC.text.muted);

  const dt = entry.created_at ? new Date(entry.created_at) : null;
  const timeStr = dt
    ? dt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    : '--';

  const handleSubmitOutcome = async () => {
    setSubmitting(true);
    try {
      const res = await fetch(`/api/v1/pms/journal/${entry.id}/outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          outcome_notes: outcomeNotes,
          realized_pnl_assessment: pnlAssessment || null,
        }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
    } catch (_) {
      // Sample data fallback
    }
    setOutcomeMode(false);
    setOutcomeNotes('');
    setPnlAssessment('');
    setSubmitting(false);
    if (onRecordOutcome) onRecordOutcome(entry.id);
  };

  const cardStyle = {
    backgroundColor: _JC.bg.secondary,
    border: `1px solid ${_JC.border.default}`,
    borderRadius: '6px',
    padding: '6px 12px',
    fontFamily: _JT.fontFamily,
    marginBottom: '4px',
    cursor: 'pointer',
  };

  const inputStyle = {
    width: '100%',
    padding: '5px 8px',
    backgroundColor: _JC.bg.tertiary,
    border: `1px solid ${_JC.border.default}`,
    borderRadius: '4px',
    color: _JC.text.primary,
    fontSize: _JT.sizes.sm,
    fontFamily: _JT.fontFamily,
    boxSizing: 'border-box',
  };

  return (
    <div style={cardStyle}>
      {/* Collapsed header row */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{ display: 'flex', alignItems: 'center', gap: '10px', minHeight: '28px' }}
      >
        {/* Type badge */}
        <span style={{
          display: 'inline-block', padding: '1px 8px', borderRadius: '9999px',
          backgroundColor: typeColor, color: _JC.text.inverse,
          fontSize: _JT.sizes.xs, fontWeight: _JT.weights.bold, minWidth: '48px', textAlign: 'center',
        }}>
          {entry.entry_type}
        </span>

        {/* Instrument */}
        <span style={{ fontSize: _JT.sizes.sm, fontWeight: _JT.weights.bold, color: _JC.text.primary, fontFamily: _JT.fontFamily }}>
          {entry.instrument || '--'}
        </span>

        {/* Direction */}
        {entry.direction && (
          <span style={{
            fontSize: _JT.sizes.xs, fontWeight: _JT.weights.semibold,
            color: entry.direction === 'LONG' ? _JC.direction.long : _JC.direction.short,
          }}>
            {entry.direction}
          </span>
        )}

        {/* Time */}
        <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted }}>{timeStr}</span>

        {/* P&L outcome */}
        <span style={{
          fontSize: _JT.sizes.sm, fontWeight: _JT.weights.bold,
          color: entry.entry_type === 'CLOSE' && entry.realized_pnl != null ? _jpnl(entry.realized_pnl) : _JC.text.muted,
          marginLeft: 'auto',
        }}>
          {entry.entry_type === 'CLOSE' && entry.realized_pnl != null ? _jfmtPnl(entry.realized_pnl) : '--'}
        </span>

        {/* Chevron */}
        <span style={{ fontSize: _JT.sizes.sm, color: _JC.text.muted, transition: 'transform 0.2s', transform: expanded ? 'rotate(90deg)' : 'rotate(0)' }}>
          {'\u25B6'}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: `1px solid ${_JC.border.subtle}` }}>
          {/* Rationale */}
          <div style={{ marginBottom: '8px' }}>
            <div style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>Rationale</div>
            {entry.manager_notes && <div style={{ fontSize: _JT.sizes.sm, color: _JC.text.secondary, lineHeight: 1.4 }}>{entry.manager_notes}</div>}
            {entry.system_notes && <div style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, marginTop: '2px' }}>{entry.system_notes}</div>}
          </div>

          {/* Macro Snapshot */}
          {entry.market_snapshot && Object.keys(entry.market_snapshot).length > 0 && (
            <div style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>Macro Snapshot</div>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {Object.entries(entry.market_snapshot).map(([k, v]) => (
                  <span key={k} style={{ fontSize: _JT.sizes.xs, color: _JC.text.secondary }}>
                    <span style={{ color: _JC.text.muted }}>{k}:</span> {String(v)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Portfolio State */}
          {entry.portfolio_snapshot && Object.keys(entry.portfolio_snapshot).length > 0 && (
            <div style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>Portfolio State</div>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {Object.entries(entry.portfolio_snapshot).map(([k, v]) => (
                  <span key={k} style={{ fontSize: _JT.sizes.xs, color: _JC.text.secondary }}>
                    <span style={{ color: _JC.text.muted }}>{k.replace(/_/g, ' ')}:</span> {String(v)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Details */}
          <div style={{ marginBottom: '8px' }}>
            <div style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '2px' }}>Details</div>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: _JT.sizes.xs, color: _JC.text.secondary }}>
              {entry.strategy && <span>Strategy: {entry.strategy}</span>}
              {entry.conviction != null && <span>Conviction: {entry.conviction.toFixed(2)}</span>}
              {entry.notional_brl != null && <span>Notional: BRL {(entry.notional_brl / 1e6).toFixed(1)}M</span>}
              {entry.entry_price != null && <span>Price: {entry.entry_price}</span>}
              {entry.content_hash && <span>Hash: {entry.content_hash.slice(0, 12)}...</span>}
            </div>
          </div>

          {/* Record Outcome button / form */}
          {!outcomeMode ? (
            <button
              onClick={(e) => { e.stopPropagation(); setOutcomeMode(true); }}
              style={{
                padding: '4px 12px', backgroundColor: _JC.bg.tertiary, color: _JC.text.secondary,
                border: `1px solid ${_JC.border.default}`, borderRadius: '4px',
                fontSize: _JT.sizes.xs, fontFamily: _JT.fontFamily, cursor: 'pointer',
              }}
            >
              Record Outcome
            </button>
          ) : (
            <div onClick={(e) => e.stopPropagation()} style={{ padding: '8px', backgroundColor: _JC.bg.tertiary, borderRadius: '4px', marginTop: '4px' }}>
              <div style={{ marginBottom: '6px' }}>
                <label style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, display: 'block', marginBottom: '2px' }}>Outcome Notes</label>
                <textarea value={outcomeNotes} onChange={(e) => setOutcomeNotes(e.target.value)} rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="Describe the outcome..." />
              </div>
              <div style={{ marginBottom: '6px' }}>
                <label style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, display: 'block', marginBottom: '2px' }}>Realized P&L Assessment</label>
                <input type="text" value={pnlAssessment} onChange={(e) => setPnlAssessment(e.target.value)} style={inputStyle} placeholder="e.g., +125K as expected" />
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={handleSubmitOutcome}
                  disabled={submitting || !outcomeNotes.trim()}
                  style={{
                    padding: '4px 12px', backgroundColor: _JC.pnl.positive, color: _JC.text.inverse,
                    border: 'none', borderRadius: '4px', fontSize: _JT.sizes.xs, fontWeight: _JT.weights.semibold,
                    fontFamily: _JT.fontFamily, cursor: outcomeNotes.trim() ? 'pointer' : 'not-allowed',
                    opacity: outcomeNotes.trim() ? 1 : 0.5,
                  }}
                >
                  {submitting ? 'Submitting...' : 'Submit'}
                </button>
                <button
                  onClick={() => { setOutcomeMode(false); setOutcomeNotes(''); setPnlAssessment(''); }}
                  style={{
                    padding: '4px 12px', backgroundColor: 'transparent', color: _JC.text.muted,
                    border: `1px solid ${_JC.border.default}`, borderRadius: '4px',
                    fontSize: _JT.sizes.xs, fontFamily: _JT.fontFamily, cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main DecisionJournalPage Component
// ---------------------------------------------------------------------------
function DecisionJournalPage() {
  const [entries, setEntries] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [filters, setFilters] = useState({
    datePreset: 'YTD',
    startDate: fmtIso(new Date(new Date().getFullYear(), 0, 1)),
    endDate: fmtIso(new Date()),
    types: [],
    assetClass: 'All',
    instrument: '',
  });
  const sentinelRef = useRef(null);

  // Fetch stats
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/v1/pms/journal/stats/decision-analysis');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        setStats(data);
      } catch (_) {
        setStats({
          total_entries: 42, approval_rate: 0.72, avg_holding_days: 8.3,
          total_positions_opened: 18, total_positions_closed: 12, total_rejections: 7,
          by_type: { OPEN: 18, CLOSE: 12, REJECT: 7, NOTE: 5 },
        });
      }
    })();
  }, []);

  // Fetch entries
  const fetchEntries = useCallback(async (newOffset, append) => {
    if (newOffset === 0) setLoading(true);
    else setLoadingMore(true);

    try {
      const params = new URLSearchParams();
      params.set('limit', String(PAGE_SIZE));
      params.set('offset', String(newOffset));
      if (filters.startDate) params.set('start_date', filters.startDate);
      if (filters.endDate) params.set('end_date', filters.endDate);
      if (filters.types && filters.types.length === 1) params.set('entry_type', filters.types[0]);
      if (filters.instrument) params.set('instrument', filters.instrument);

      const res = await fetch('/api/v1/pms/journal/?' + params.toString());
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();

      let filtered = data;
      if (filters.types && filters.types.length > 1) {
        filtered = data.filter((e) => filters.types.includes(e.entry_type));
      }
      if (filters.assetClass && filters.assetClass !== 'All') {
        filtered = filtered.filter((e) => (e.asset_class || '').toLowerCase() === filters.assetClass.toLowerCase());
      }

      if (append) {
        setEntries((prev) => [...prev, ...filtered]);
      } else {
        setEntries(filtered);
      }
      setHasMore(data.length >= PAGE_SIZE);
    } catch (_) {
      // Sample data fallback
      let sample = generateSampleEntries();
      if (filters.types && filters.types.length > 0) {
        sample = sample.filter((e) => filters.types.includes(e.entry_type));
      }
      if (filters.assetClass && filters.assetClass !== 'All') {
        sample = sample.filter((e) => (e.asset_class || '').toLowerCase() === filters.assetClass.toLowerCase());
      }
      if (filters.instrument) {
        const q = filters.instrument.toLowerCase();
        sample = sample.filter((e) => (e.instrument || '').toLowerCase().includes(q));
      }
      if (append) {
        setEntries((prev) => [...prev, ...sample]);
      } else {
        setEntries(sample);
      }
      setHasMore(false);
    }

    setLoading(false);
    setLoadingMore(false);
  }, [filters]);

  // Re-fetch when filters change
  useEffect(() => {
    setOffset(0);
    fetchEntries(0, false);
  }, [filters.datePreset, filters.startDate, filters.endDate, filters.types.length, filters.assetClass, filters.instrument]);

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(
      (ents) => {
        if (ents[0].isIntersecting && hasMore && !loadingMore && !loading) {
          const nextOffset = offset + PAGE_SIZE;
          setOffset(nextOffset);
          fetchEntries(nextOffset, true);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, loading, offset, fetchEntries]);

  // Group entries by date
  const dateGroups = useMemo(() => {
    const groups = [];
    const map = {};
    entries.forEach((e) => {
      const d = e.created_at ? new Date(e.created_at) : new Date();
      const key = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      if (!map[key]) {
        map[key] = { label: key, entries: [] };
        groups.push(map[key]);
      }
      map[key].entries.push(e);
    });
    return groups;
  }, [entries]);

  const pageStyle = {
    fontFamily: _JT.fontFamily,
    color: _JC.text.primary,
    maxWidth: '1200px',
    margin: '0 auto',
  };

  return (
    <div style={pageStyle}>
      {/* Page header */}
      <div style={{ marginBottom: _JS.md }}>
        <div style={{ fontSize: _JT.sizes['2xl'], fontWeight: _JT.weights.bold, color: _JC.text.primary, marginBottom: '2px' }}>
          Decision Journal
        </div>
        <div style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted }}>
          Trading decision audit trail | Timeline view
        </div>
      </div>

      {/* Summary Stats Bar */}
      {stats && (
        <div style={{
          display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: _JS.md,
          padding: '8px 12px', backgroundColor: _JC.bg.secondary, border: `1px solid ${_JC.border.default}`, borderRadius: '6px',
        }}>
          <div style={{ display: 'inline-flex', flexDirection: 'column' }}>
            <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase' }}>Total</span>
            <span style={{ fontSize: _JT.sizes.lg, fontWeight: _JT.weights.bold, color: _JC.text.primary }}>{stats.total_entries}</span>
          </div>
          <div style={{ display: 'inline-flex', flexDirection: 'column' }}>
            <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase' }}>Approval Rate</span>
            <span style={{ fontSize: _JT.sizes.lg, fontWeight: _JT.weights.bold, color: _JC.pnl.positive }}>{(stats.approval_rate * 100).toFixed(0)}%</span>
          </div>
          <div style={{ display: 'inline-flex', flexDirection: 'column' }}>
            <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase' }}>Avg Hold Days</span>
            <span style={{ fontSize: _JT.sizes.lg, fontWeight: _JT.weights.bold, color: _JC.text.primary }}>{stats.avg_holding_days}</span>
          </div>
          <div style={{ display: 'inline-flex', flexDirection: 'column' }}>
            <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase' }}>Opened</span>
            <span style={{ fontSize: _JT.sizes.lg, fontWeight: _JT.weights.bold, color: _JC.border.accent }}>{stats.total_positions_opened}</span>
          </div>
          <div style={{ display: 'inline-flex', flexDirection: 'column' }}>
            <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase' }}>Closed</span>
            <span style={{ fontSize: _JT.sizes.lg, fontWeight: _JT.weights.bold, color: _JC.pnl.positive }}>{stats.total_positions_closed}</span>
          </div>
          <div style={{ display: 'inline-flex', flexDirection: 'column' }}>
            <span style={{ fontSize: _JT.sizes.xs, color: _JC.text.muted, textTransform: 'uppercase' }}>Rejected</span>
            <span style={{ fontSize: _JT.sizes.lg, fontWeight: _JT.weights.bold, color: _JC.risk.warning }}>{stats.total_rejections}</span>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <JournalFilterBar filters={filters} onFilterChange={setFilters} />

      {/* Loading skeleton */}
      {loading && (
        <div style={{ padding: '16px 0' }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} style={{ marginBottom: '6px' }}>
              <window.PMSSkeleton height="36px" />
            </div>
          ))}
        </div>
      )}

      {/* Vertical Timeline */}
      {!loading && (
        <div style={{ display: 'flex', gap: '0' }}>
          {/* Timeline content */}
          <div style={{ flex: 1 }}>
            {dateGroups.map((group, gi) => (
              <div key={group.label} style={{ display: 'flex', marginBottom: '8px' }}>
                {/* Date column */}
                <div style={{
                  width: '72px', flexShrink: 0, position: 'relative',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: '6px',
                }}>
                  <span style={{
                    fontSize: _JT.sizes.xs, fontWeight: _JT.weights.semibold, color: _JC.text.secondary,
                    backgroundColor: _JC.bg.primary, padding: '0 4px', position: 'relative', zIndex: 1,
                  }}>
                    {group.label}
                  </span>
                  {/* Dot */}
                  <div style={{
                    width: '8px', height: '8px', borderRadius: '50%', backgroundColor: _JC.border.accent,
                    marginTop: '4px', position: 'relative', zIndex: 1,
                  }} />
                  {/* Connecting line */}
                  {gi < dateGroups.length - 1 && (
                    <div style={{
                      width: '2px', flex: 1, backgroundColor: _JC.border.default, marginTop: '4px',
                    }} />
                  )}
                </div>

                {/* Cards column */}
                <div style={{ flex: 1, paddingLeft: '8px' }}>
                  {group.entries.map((entry) => (
                    <DecisionCard key={entry.id} entry={entry} />
                  ))}
                </div>
              </div>
            ))}

            {/* Empty state */}
            {dateGroups.length === 0 && !loading && (
              <div style={{ textAlign: 'center', padding: '32px', color: _JC.text.muted, fontSize: _JT.sizes.sm }}>
                No journal entries match the selected filters
              </div>
            )}

            {/* Loading more indicator */}
            {loadingMore && (
              <div style={{ textAlign: 'center', padding: '12px' }}>
                <window.PMSSkeleton height="32px" width="200px" />
              </div>
            )}

            {/* Sentinel for infinite scroll */}
            <div ref={sentinelRef} style={{ height: '1px' }} />
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.DecisionJournalPage = DecisionJournalPage;

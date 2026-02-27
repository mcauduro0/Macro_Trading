/**
 * PositionBookPage.jsx - Position Book page for the PMS.
 *
 * Bloomberg PORT-style position viewer with:
 * 1. P&L Summary Cards (horizontal strip)
 * 2. Equity Curve Chart with CDI benchmark and time range buttons
 * 3. Positions Table with collapsible asset class groups and expandable detail rows
 * 4. Close Position Dialog (modal overlay)
 *
 * Consumes 2 API endpoints:
 * - /api/v1/pms/book        (positions + summary + by_asset_class)
 * - /api/v1/pms/pnl/equity-curve (timeseries for equity chart)
 *
 * Falls back to sample data when API unavailable.
 * All components accessed via window globals (CDN/Babel pattern).
 */

const { useState, useEffect, useCallback, useMemo } = React;
const { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } = Recharts;

// ---------------------------------------------------------------------------
// Access PMS design system from window globals
// ---------------------------------------------------------------------------
const {
  PMS_COLORS: _C,
  PMS_TYPOGRAPHY: _T,
  PMS_SPACING: _S,
  pnlColor: _pnlColor,
  formatPnL: _formatPnL,
  formatPercent: _formatPercent,
  formatNumber: _formatNumber,
} = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Seeded PRNG (same approach as PortfolioPage / MorningPackPage)
// ---------------------------------------------------------------------------
function seededRng(seed) {
  let s = seed;
  return function () {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ---------------------------------------------------------------------------
// Formatting Helpers
// ---------------------------------------------------------------------------

/**
 * Format notional value with abbreviated notation.
 * e.g., 15000000 -> "15.0M", 500000 -> "500K"
 */
function formatSize(value) {
  if (value == null || isNaN(value)) return '--';
  const abs = Math.abs(value);
  if (abs >= 1e9) return (value / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return (value / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (value / 1e3).toFixed(0) + 'K';
  return value.toFixed(0);
}

/**
 * Format P&L in BRL with abbreviated notation and sign.
 * e.g., 245000 -> "+245K", -1820000 -> "-1.8M"
 */
function formatPnLShort(value) {
  if (value == null || isNaN(value)) return '--';
  const sign = value >= 0 ? '+' : '-';
  const abs = Math.abs(value);
  let formatted;
  if (abs >= 1e9) formatted = (abs / 1e9).toFixed(1) + 'B';
  else if (abs >= 1e6) formatted = (abs / 1e6).toFixed(1) + 'M';
  else if (abs >= 1e3) formatted = (abs / 1e3).toFixed(0) + 'K';
  else formatted = abs.toFixed(0);
  return sign + 'R$ ' + formatted;
}

/**
 * Get badge variant for direction.
 */
function dirBadgeVariant(dir) {
  if (!dir) return 'neutral';
  const d = dir.toUpperCase();
  if (d === 'LONG') return 'positive';
  if (d === 'SHORT') return 'negative';
  return 'neutral';
}

// ---------------------------------------------------------------------------
// Sample Data Constants
// ---------------------------------------------------------------------------

const SAMPLE_BOOK = {
  summary: {
    aum: 150000000,
    total_notional_brl: 180000000,
    leverage: 1.2,
    open_positions: 12,
    pnl_today_brl: 245000,
    pnl_mtd_brl: 1820000,
    pnl_ytd_brl: 8450000,
    total_unrealized_pnl_brl: 3200000,
    total_realized_pnl_brl: 5250000,
  },
  positions: [
    { id: 1, instrument: 'USDBRL NDF 3M', asset_class: 'FX', direction: 'SHORT', notional_brl: 25000000, entry_price: 5.15, current_price: 4.92, unrealized_pnl_brl: 562000, daily_pnl_brl: 18500, entry_dv01: null, entry_delta: 0.98, entry_var_contribution: 0.018, entry_date: '2025-12-10', strategy_ids: ['FX-02', 'FX-03'], notes: 'target:4.80|stop:5.30', business_days: 52 },
    { id: 2, instrument: 'USDBRL NDF 6M', asset_class: 'FX', direction: 'SHORT', notional_brl: 15000000, entry_price: 5.22, current_price: 5.01, unrealized_pnl_brl: 315000, daily_pnl_brl: 7200, entry_dv01: null, entry_delta: 0.95, entry_var_contribution: 0.012, entry_date: '2025-11-20', strategy_ids: ['FX-04'], notes: 'target:4.85|stop:5.40', business_days: 66 },
    { id: 3, instrument: 'DI1 Jan26', asset_class: 'RATES', direction: 'LONG', notional_brl: 20000000, entry_price: 14.50, current_price: 14.25, unrealized_pnl_brl: 180000, daily_pnl_brl: -12000, entry_dv01: 4500, entry_delta: null, entry_var_contribution: 0.022, entry_date: '2026-01-08', strategy_ids: ['RATES-03'], notes: 'target:13.80|stop:14.90', business_days: 34 },
    { id: 4, instrument: 'DI1 Jan27', asset_class: 'RATES', direction: 'LONG', notional_brl: 18000000, entry_price: 13.95, current_price: 13.80, unrealized_pnl_brl: 125000, daily_pnl_brl: 8500, entry_dv01: 8200, entry_delta: null, entry_var_contribution: 0.028, entry_date: '2026-01-15', strategy_ids: ['RATES-05'], notes: 'target:13.20|stop:14.30', business_days: 29 },
    { id: 5, instrument: 'NTN-B 2030', asset_class: 'INFLATION', direction: 'LONG', notional_brl: 22000000, entry_price: 6.25, current_price: 6.10, unrealized_pnl_brl: 420000, daily_pnl_brl: 22000, entry_dv01: 3800, entry_delta: null, entry_var_contribution: 0.015, entry_date: '2025-10-15', strategy_ids: ['INF-02'], notes: 'target:5.80|stop:6.50', business_days: 92 },
    { id: 6, instrument: 'NTN-B 2035', asset_class: 'INFLATION', direction: 'LONG', notional_brl: 18000000, entry_price: 6.45, current_price: 6.30, unrealized_pnl_brl: 310000, daily_pnl_brl: 15000, entry_dv01: 5200, entry_delta: null, entry_var_contribution: 0.020, entry_date: '2025-11-05', strategy_ids: ['INF-03'], notes: 'target:6.00|stop:6.70', business_days: 77 },
    { id: 7, instrument: 'DDI Jan26', asset_class: 'CUPOM_CAMBIAL', direction: 'SHORT', notional_brl: 12000000, entry_price: 11.80, current_price: 11.50, unrealized_pnl_brl: 95000, daily_pnl_brl: 3200, entry_dv01: 2800, entry_delta: null, entry_var_contribution: 0.009, entry_date: '2026-01-20', strategy_ids: ['CUPOM-02'], notes: 'target:11.00|stop:12.20', business_days: 26 },
    { id: 8, instrument: 'CDS BR 5Y', asset_class: 'SOVEREIGN', direction: 'SHORT', notional_brl: 10000000, entry_price: 158, current_price: 145, unrealized_pnl_brl: 210000, daily_pnl_brl: -5500, entry_dv01: null, entry_delta: 0.45, entry_var_contribution: 0.011, entry_date: '2025-12-01', strategy_ids: ['SOV-02'], notes: 'target:130|stop:175', business_days: 59 },
    { id: 9, instrument: 'LTN 2025', asset_class: 'SOVEREIGN', direction: 'LONG', notional_brl: 8000000, entry_price: 850, current_price: 862, unrealized_pnl_brl: 112000, daily_pnl_brl: 4800, entry_dv01: 1200, entry_delta: null, entry_var_contribution: 0.006, entry_date: '2026-01-28', strategy_ids: ['RATES-06'], notes: 'target:880|stop:835', business_days: 20 },
    { id: 10, instrument: 'IBOV FUT', asset_class: 'CROSS_ASSET', direction: 'LONG', notional_brl: 15000000, entry_price: 125800, current_price: 128450, unrealized_pnl_brl: 316000, daily_pnl_brl: 42000, entry_dv01: null, entry_delta: 1.0, entry_var_contribution: 0.025, entry_date: '2026-01-10', strategy_ids: ['CROSS-01'], notes: 'target:132000|stop:122000', business_days: 32 },
    { id: 11, instrument: 'DOL WDO', asset_class: 'FX', direction: 'SHORT', notional_brl: 10000000, entry_price: 5.10, current_price: 4.95, unrealized_pnl_brl: 294000, daily_pnl_brl: 9800, entry_dv01: null, entry_delta: 0.99, entry_var_contribution: 0.014, entry_date: '2025-12-18', strategy_ids: ['FX-05'], notes: 'target:4.75|stop:5.25', business_days: 47 },
    { id: 12, instrument: 'UST 10Y', asset_class: 'CROSS_ASSET', direction: 'SHORT', notional_brl: 7000000, entry_price: 4.45, current_price: 4.35, unrealized_pnl_brl: -39000, daily_pnl_brl: -8200, entry_dv01: 6500, entry_delta: null, entry_var_contribution: 0.019, entry_date: '2026-02-05', strategy_ids: ['CROSS-02'], notes: 'target:4.15|stop:4.65', business_days: 14 },
  ],
  by_asset_class: {
    FX: { count: 3, total_notional: 50000000, unrealized_pnl: 1171000 },
    RATES: { count: 2, total_notional: 38000000, unrealized_pnl: 305000 },
    INFLATION: { count: 2, total_notional: 40000000, unrealized_pnl: 730000 },
    CUPOM_CAMBIAL: { count: 1, total_notional: 12000000, unrealized_pnl: 95000 },
    SOVEREIGN: { count: 2, total_notional: 18000000, unrealized_pnl: 322000 },
    CROSS_ASSET: { count: 2, total_notional: 22000000, unrealized_pnl: 277000 },
  },
};

/**
 * Generate 252 daily equity curve points with seeded PRNG.
 * Includes cumulative P&L, daily P&L, drawdown, and CDI benchmark.
 */
function generateSampleEquityCurve() {
  const rand = seededRng(42);
  const data = [];
  let cumulativePnl = 0;
  let peak = 0;
  let cdiCumulative = 0;
  const dailyCdiRate = Math.pow(1.1375, 1 / 252) - 1; // ~13.75% annual CDI

  for (let i = 0; i < 252; i++) {
    const dailyPnl = (rand() - 0.46) * 120000; // slight positive drift
    cumulativePnl += dailyPnl;
    peak = Math.max(peak, cumulativePnl);
    const drawdown = peak > 0 ? ((cumulativePnl - peak) / 150000000) * 100 : 0;
    cdiCumulative += dailyCdiRate * 150000000;

    const d = new Date(2025, 2, 3); // start 2025-03-03
    d.setDate(d.getDate() + Math.floor(i * 365 / 252));

    data.push({
      snapshot_date: d.toISOString().slice(0, 10),
      daily_pnl_brl: Math.round(dailyPnl),
      cumulative_pnl_brl: Math.round(cumulativePnl),
      drawdown_pct: Math.round(drawdown * 100) / 100,
      cdi_cumulative: Math.round(cdiCumulative),
    });
  }
  return data;
}

const SAMPLE_EQUITY_CURVE = generateSampleEquityCurve();

// ---------------------------------------------------------------------------
// Asset Class ordering and labels
// ---------------------------------------------------------------------------
const ASSET_CLASS_ORDER = ['FX', 'RATES', 'INFLATION', 'CUPOM_CAMBIAL', 'SOVEREIGN', 'CROSS_ASSET'];
const ASSET_CLASS_LABELS = {
  FX: 'Foreign Exchange',
  RATES: 'Interest Rates',
  INFLATION: 'Inflation-Linked',
  CUPOM_CAMBIAL: 'Cupom Cambial',
  SOVEREIGN: 'Sovereign Credit',
  CROSS_ASSET: 'Cross-Asset',
};

// ---------------------------------------------------------------------------
// Section 1: P&L Summary Cards
// ---------------------------------------------------------------------------
function PnLSummaryCards({ summary }) {
  const cards = [
    { label: 'Today P&L', value: summary.pnl_today_brl, isPnl: true },
    { label: 'MTD P&L', value: summary.pnl_mtd_brl, isPnl: true },
    { label: 'YTD P&L', value: summary.pnl_ytd_brl, isPnl: true },
    { label: 'Unrealized P&L', value: summary.total_unrealized_pnl_brl, isPnl: true },
    { label: 'AUM / Leverage', value: null, isPnl: false },
  ];

  const containerStyle = {
    display: 'flex',
    flexDirection: 'row',
    gap: '8px',
    marginBottom: _S.md,
    overflowX: 'auto',
  };

  const cardStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    padding: '8px 14px',
    minWidth: '140px',
    flex: '1 1 0',
    fontFamily: _T.fontFamily,
  };

  const labelStyle = {
    fontSize: _T.sizes.xs,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '2px',
  };

  const valueStyle = (val, isPnl) => ({
    fontSize: _T.sizes.xl,
    fontWeight: _T.weights.bold,
    color: isPnl ? _pnlColor(val) : _C.text.primary,
    lineHeight: 1.3,
  });

  return (
    <div style={containerStyle}>
      {cards.map((card, idx) => (
        <div key={idx} style={cardStyle}>
          <div style={labelStyle}>{card.label}</div>
          {card.isPnl ? (
            <div style={valueStyle(card.value, true)}>
              {formatPnLShort(card.value)}
            </div>
          ) : (
            <div>
              <div style={{ fontSize: _T.sizes.lg, fontWeight: _T.weights.bold, color: _C.text.primary, lineHeight: 1.3 }}>
                {formatSize(summary.aum)}
              </div>
              <div style={{ fontSize: _T.sizes.xs, color: _C.text.secondary }}>
                Leverage: {summary.leverage != null ? summary.leverage.toFixed(2) + 'x' : '--'}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 2: Equity Curve Chart
// ---------------------------------------------------------------------------
function EquityCurveSection({ equityCurve }) {
  const [range, setRange] = useState('YTD');

  const ranges = ['1M', '3M', '6M', 'YTD', '1Y', 'All'];

  const filteredData = useMemo(() => {
    if (!equityCurve || equityCurve.length === 0) return [];
    if (range === 'All') return equityCurve;

    const lastDate = new Date(equityCurve[equityCurve.length - 1].snapshot_date);
    let startDate;

    if (range === '1M') {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 1);
    } else if (range === '3M') {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 3);
    } else if (range === '6M') {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 6);
    } else if (range === 'YTD') {
      startDate = new Date(lastDate.getFullYear(), 0, 1);
    } else if (range === '1Y') {
      startDate = new Date(lastDate);
      startDate.setFullYear(startDate.getFullYear() - 1);
    }

    const startStr = startDate.toISOString().slice(0, 10);
    return equityCurve.filter(d => d.snapshot_date >= startStr);
  }, [equityCurve, range]);

  const containerStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '12px',
    marginBottom: _S.md,
  };

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '8px',
  };

  const titleStyle = {
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _T.fontFamily,
  };

  const buttonContainerStyle = {
    display: 'flex',
    gap: '4px',
  };

  const rangeButtonStyle = (isActive) => ({
    background: isActive ? _C.border.accent : 'transparent',
    color: isActive ? _C.text.primary : _C.text.secondary,
    border: '1px solid ' + (isActive ? _C.border.accent : _C.border.default),
    borderRadius: '3px',
    padding: '2px 8px',
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.medium,
    fontFamily: _T.fontFamily,
    cursor: 'pointer',
    lineHeight: 1.4,
  });

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

  const tooltipLabelStyle = { color: _C.text.secondary };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={titleStyle}>Equity Curve & Drawdown</div>
        <div style={buttonContainerStyle}>
          {ranges.map(r => (
            <button
              key={r}
              style={rangeButtonStyle(r === range)}
              onClick={() => setRange(r)}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={filteredData}>
          <CartesianGrid strokeDasharray="3 3" stroke={_C.border.subtle} />
          <XAxis
            dataKey="snapshot_date"
            stroke={_C.text.muted}
            tick={{ fontSize: 8, fontFamily: _T.fontFamily }}
            interval={Math.max(1, Math.floor(filteredData.length / 8))}
          />
          <YAxis
            yAxisId="pnl"
            orientation="left"
            stroke={_C.text.muted}
            tick={{ fontSize: 9, fontFamily: _T.fontFamily }}
            tickFormatter={(v) => formatSize(v)}
          />
          <YAxis
            yAxisId="dd"
            orientation="right"
            stroke={_C.text.muted}
            tick={{ fontSize: 9, fontFamily: _T.fontFamily }}
            tickFormatter={(v) => v.toFixed(1) + '%'}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={tooltipLabelStyle}
            formatter={(value, name) => {
              if (name === 'Drawdown %') return [value.toFixed(2) + '%', name];
              return [formatPnLShort(value), name];
            }}
          />
          <Line
            yAxisId="pnl"
            type="monotone"
            dataKey="cumulative_pnl_brl"
            stroke="#58a6ff"
            strokeWidth={1.5}
            dot={false}
            name="Cumulative P&L"
          />
          <Line
            yAxisId="pnl"
            type="monotone"
            dataKey="cdi_cumulative"
            stroke="#8b949e"
            strokeWidth={1}
            strokeDasharray="5 3"
            dot={false}
            name="CDI Benchmark"
          />
          <Area
            yAxisId="dd"
            type="monotone"
            dataKey="drawdown_pct"
            fill="rgba(248, 81, 73, 0.15)"
            stroke="#f85149"
            strokeWidth={1}
            dot={false}
            name="Drawdown %"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 3: Positions Table with Collapsible Asset Class Groups
// ---------------------------------------------------------------------------
function PositionsTable({ positions, onExpandRow, expandedRowId, onCloseClick }) {
  const [expandedGroups, setExpandedGroups] = useState(() => new Set(ASSET_CLASS_ORDER));

  const toggleGroup = (group) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  };

  // Group positions by asset_class
  const grouped = useMemo(() => {
    const groups = {};
    (positions || []).forEach(pos => {
      const ac = pos.asset_class || 'OTHER';
      if (!groups[ac]) groups[ac] = [];
      groups[ac].push(pos);
    });
    return groups;
  }, [positions]);

  // Column header styles
  const thStyle = {
    padding: '4px 8px',
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    borderBottom: '1px solid ' + _C.border.default,
    fontFamily: _T.fontFamily,
    whiteSpace: 'nowrap',
  };

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.sm,
  };

  const groupHeaderStyle = (isExpanded) => ({
    backgroundColor: _C.bg.tertiary,
    cursor: 'pointer',
    userSelect: 'none',
  });

  const groupHeaderCellStyle = {
    padding: '6px 8px',
    fontWeight: _T.weights.semibold,
    color: _C.text.primary,
    fontSize: _T.sizes.sm,
    fontFamily: _T.fontFamily,
    borderBottom: '1px solid ' + _C.border.default,
  };

  const cellStyle = (align) => ({
    padding: '4px 8px',
    color: _C.text.primary,
    textAlign: align || 'left',
    borderBottom: '1px solid ' + _C.border.subtle,
    whiteSpace: 'nowrap',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.sm,
  });

  // Compute group subtotals
  const groupSubtotal = (groupPositions) => {
    return groupPositions.reduce((sum, p) => sum + (p.unrealized_pnl_brl || 0), 0);
  };

  const columns = [
    { key: 'instrument', label: 'Instrument', align: 'left' },
    { key: 'direction', label: 'Dir', align: 'center' },
    { key: 'notional_brl', label: 'Size', align: 'right' },
    { key: 'entry_price', label: 'Entry', align: 'right' },
    { key: 'current_price', label: 'Current', align: 'right' },
    { key: 'unrealized_pnl', label: 'Unreal P&L', align: 'right' },
    { key: 'dv01_delta', label: 'DV01/Delta', align: 'right' },
    { key: 'var_contrib', label: 'VaR Contrib', align: 'right' },
    { key: 'daily_pnl', label: 'Daily P&L', align: 'right' },
    { key: 'holding_days', label: 'Days', align: 'right' },
    { key: 'actions', label: '', align: 'center' },
  ];

  const closeButtonStyle = {
    background: 'transparent',
    color: _C.pnl.negative,
    border: '1px solid ' + _C.pnl.negative,
    borderRadius: '3px',
    padding: '1px 8px',
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.medium,
    fontFamily: _T.fontFamily,
    cursor: 'pointer',
    lineHeight: 1.4,
  };

  return (
    <div style={{ backgroundColor: _C.bg.secondary, border: '1px solid ' + _C.border.default, borderRadius: '6px', padding: '8px', marginBottom: _S.md }}>
      <div style={{ fontSize: _T.sizes.xs, fontWeight: _T.weights.semibold, color: _C.text.muted, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: _T.fontFamily, marginBottom: '6px', padding: '0 4px' }}>
        Position Book
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key} style={{ ...thStyle, textAlign: col.align }}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ASSET_CLASS_ORDER.map(ac => {
              const groupPositions = grouped[ac];
              if (!groupPositions || groupPositions.length === 0) return null;
              const isExpanded = expandedGroups.has(ac);
              const subtotal = groupSubtotal(groupPositions);
              const arrow = isExpanded ? '\u25BC' : '\u25B6';

              return (
                <React.Fragment key={ac}>
                  {/* Group header row */}
                  <tr style={groupHeaderStyle(isExpanded)} onClick={() => toggleGroup(ac)}>
                    <td style={groupHeaderCellStyle} colSpan={6}>
                      <span style={{ marginRight: '6px', fontSize: _T.sizes.xs }}>{arrow}</span>
                      {ASSET_CLASS_LABELS[ac] || ac}
                      <span style={{ marginLeft: '8px', fontSize: _T.sizes.xs, color: _C.text.secondary }}>
                        ({groupPositions.length})
                      </span>
                    </td>
                    <td style={{ ...groupHeaderCellStyle, textAlign: 'right' }} colSpan={5}>
                      <span style={{ color: _pnlColor(subtotal), fontWeight: _T.weights.bold }}>
                        {formatPnLShort(subtotal)}
                      </span>
                    </td>
                  </tr>
                  {/* Position rows */}
                  {isExpanded && groupPositions.map((pos) => {
                    const isRowExpanded = expandedRowId === pos.id;
                    const rowBg = isRowExpanded ? _C.bg.elevated : _C.bg.secondary;

                    return (
                      <React.Fragment key={pos.id}>
                        <tr
                          style={{ backgroundColor: rowBg, cursor: 'pointer', transition: 'background-color 0.1s' }}
                          onClick={() => onExpandRow(pos.id)}
                          onMouseEnter={(e) => { if (!isRowExpanded) e.currentTarget.style.backgroundColor = _C.bg.tertiary; }}
                          onMouseLeave={(e) => { if (!isRowExpanded) e.currentTarget.style.backgroundColor = _C.bg.secondary; }}
                        >
                          <td style={cellStyle('left')}>{pos.instrument}</td>
                          <td style={cellStyle('center')}>
                            <window.PMSBadge label={pos.direction} variant={dirBadgeVariant(pos.direction)} size="sm" />
                          </td>
                          <td style={cellStyle('right')}>{formatSize(pos.notional_brl)}</td>
                          <td style={cellStyle('right')}>{pos.entry_price != null ? _formatNumber(pos.entry_price, pos.entry_price >= 100 ? 0 : 2) : '--'}</td>
                          <td style={cellStyle('right')}>{pos.current_price != null ? _formatNumber(pos.current_price, pos.current_price >= 100 ? 0 : 2) : '--'}</td>
                          <td style={{ ...cellStyle('right'), color: _pnlColor(pos.unrealized_pnl_brl) }}>
                            {formatPnLShort(pos.unrealized_pnl_brl)}
                          </td>
                          <td style={cellStyle('right')}>
                            {pos.entry_dv01 != null ? _formatNumber(pos.entry_dv01, 0) : (pos.entry_delta != null ? pos.entry_delta.toFixed(2) : '--')}
                          </td>
                          <td style={cellStyle('right')}>
                            {pos.entry_var_contribution != null ? (pos.entry_var_contribution * 100).toFixed(1) + '%' : '--'}
                          </td>
                          <td style={{ ...cellStyle('right'), color: _pnlColor(pos.daily_pnl_brl) }}>
                            {pos.daily_pnl_brl != null ? formatPnLShort(pos.daily_pnl_brl) : '--'}
                          </td>
                          <td style={cellStyle('right')}>{pos.business_days != null ? pos.business_days : '--'}</td>
                          <td style={cellStyle('center')}>
                            <button
                              style={closeButtonStyle}
                              onClick={(e) => { e.stopPropagation(); onCloseClick(pos); }}
                              title="Close position"
                            >
                              Close
                            </button>
                          </td>
                        </tr>
                        {/* Expanded detail row */}
                        {isRowExpanded && (
                          <tr>
                            <td colSpan={11} style={{ backgroundColor: _C.bg.tertiary, padding: '8px 16px 8px 32px', borderBottom: '1px solid ' + _C.border.default }}>
                              <PositionDetailRow position={pos} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 3b: Expandable Row Detail
// ---------------------------------------------------------------------------
function PositionDetailRow({ position }) {
  const detailStyle = {
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
    color: _C.text.secondary,
    display: 'flex',
    gap: '24px',
    alignItems: 'flex-start',
  };

  const fieldStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  };

  const fieldLabelStyle = {
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    fontSize: _T.sizes.xs,
  };

  const fieldValueStyle = {
    color: _C.text.primary,
    fontWeight: _T.weights.medium,
  };

  // Parse target/stop from notes
  let target = '--';
  let stop = '--';
  if (position.notes) {
    const parts = position.notes.split('|');
    parts.forEach(part => {
      const [key, val] = part.split(':');
      if (key === 'target') target = val;
      if (key === 'stop') stop = val;
    });
  }

  // Generate spark chart data using seeded PRNG per position ID
  const sparkData = useMemo(() => {
    const rand = seededRng(position.id * 137 + 7);
    const points = [];
    let value = 0;
    for (let i = 0; i < 10; i++) {
      value += (rand() - 0.45) * 30000;
      points.push(value);
    }
    return points;
  }, [position.id]);

  // Render SVG spark line
  const sparkWidth = 100;
  const sparkHeight = 24;
  const minVal = Math.min(...sparkData);
  const maxVal = Math.max(...sparkData);
  const sparkRange = maxVal - minVal || 1;

  const sparkPoints = sparkData.map((val, idx) => {
    const x = (idx / (sparkData.length - 1)) * sparkWidth;
    const y = sparkHeight - ((val - minVal) / sparkRange) * sparkHeight;
    return x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');

  const lastVal = sparkData[sparkData.length - 1];
  const sparkColor = lastVal >= 0 ? _C.pnl.positive : _C.pnl.negative;

  return (
    <div style={detailStyle}>
      <div style={fieldStyle}>
        <span style={fieldLabelStyle}>Strategies</span>
        <span style={fieldValueStyle}>{(position.strategy_ids || []).join(', ') || '--'}</span>
      </div>
      <div style={fieldStyle}>
        <span style={fieldLabelStyle}>Entry Date</span>
        <span style={fieldValueStyle}>{position.entry_date || '--'}</span>
      </div>
      <div style={fieldStyle}>
        <span style={fieldLabelStyle}>Target</span>
        <span style={{ ...fieldValueStyle, color: _C.pnl.positive }}>{target}</span>
      </div>
      <div style={fieldStyle}>
        <span style={fieldLabelStyle}>Stop Loss</span>
        <span style={{ ...fieldValueStyle, color: _C.pnl.negative }}>{stop}</span>
      </div>
      <div style={fieldStyle}>
        <span style={fieldLabelStyle}>P&L Trend</span>
        <svg width={sparkWidth} height={sparkHeight} style={{ display: 'block' }}>
          <polyline
            points={sparkPoints}
            fill="none"
            stroke={sparkColor}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 4: Close Position Dialog
// ---------------------------------------------------------------------------
function ClosePositionDialog({ position, onConfirm, onCancel }) {
  const [closePrice, setClosePrice] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (!position) return null;

  const handleConfirm = async () => {
    if (!closePrice || isNaN(parseFloat(closePrice)) || parseFloat(closePrice) <= 0) {
      setError('Close price is required and must be positive');
      return;
    }
    setError(null);
    setSubmitting(true);

    try {
      const res = await fetch('/api/v1/pms/book/positions/' + position.id + '/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          close_price: parseFloat(closePrice),
          manager_notes: notes || null,
        }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      onConfirm(position.id);
    } catch (err) {
      // For sample data fallback, still close in UI
      onConfirm(position.id);
    } finally {
      setSubmitting(false);
    }
  };

  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    fontFamily: _T.fontFamily,
  };

  const dialogStyle = {
    backgroundColor: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '8px',
    padding: '20px',
    minWidth: '380px',
    maxWidth: '440px',
  };

  const dialogTitleStyle = {
    fontSize: _T.sizes.lg,
    fontWeight: _T.weights.bold,
    color: _C.text.primary,
    marginBottom: '4px',
  };

  const dialogSubtitleStyle = {
    fontSize: _T.sizes.sm,
    color: _C.text.secondary,
    marginBottom: '16px',
  };

  const labelStyle = {
    display: 'block',
    fontSize: _T.sizes.xs,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    marginBottom: '4px',
    fontFamily: _T.fontFamily,
  };

  const inputStyle = {
    width: '100%',
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    padding: '6px 10px',
    color: _C.text.primary,
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.sm,
    outline: 'none',
    boxSizing: 'border-box',
  };

  const textareaStyle = {
    ...inputStyle,
    minHeight: '60px',
    resize: 'vertical',
  };

  const buttonRowStyle = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '8px',
    marginTop: '16px',
  };

  const cancelButtonStyle = {
    background: 'transparent',
    color: _C.text.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    padding: '6px 16px',
    fontSize: _T.sizes.sm,
    fontWeight: _T.weights.medium,
    fontFamily: _T.fontFamily,
    cursor: 'pointer',
  };

  const confirmButtonStyle = {
    backgroundColor: _C.pnl.negative,
    color: '#ffffff',
    border: 'none',
    borderRadius: '4px',
    padding: '6px 16px',
    fontSize: _T.sizes.sm,
    fontWeight: _T.weights.semibold,
    fontFamily: _T.fontFamily,
    cursor: submitting ? 'wait' : 'pointer',
    opacity: submitting ? 0.7 : 1,
  };

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div style={dialogStyle}>
        <div style={dialogTitleStyle}>Close Position</div>
        <div style={dialogSubtitleStyle}>
          {position.instrument} | {position.direction} | {formatSize(position.notional_brl)}
        </div>

        <div style={{ marginBottom: '12px' }}>
          <label style={labelStyle}>Close Price *</label>
          <input
            type="number"
            step="any"
            value={closePrice}
            onChange={(e) => setClosePrice(e.target.value)}
            style={inputStyle}
            placeholder={position.current_price != null ? String(position.current_price) : '0.00'}
            autoFocus
          />
        </div>

        <div style={{ marginBottom: '4px' }}>
          <label style={labelStyle}>Manager Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            style={textareaStyle}
            placeholder="Reason for closing..."
          />
        </div>

        {error && (
          <div style={{ fontSize: _T.sizes.xs, color: _C.pnl.negative, marginTop: '4px' }}>
            {error}
          </div>
        )}

        <div style={buttonRowStyle}>
          <button style={cancelButtonStyle} onClick={onCancel}>Cancel</button>
          <button style={confirmButtonStyle} onClick={handleConfirm} disabled={submitting}>
            {submitting ? 'Closing...' : 'Confirm Close'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------
function PositionBookSkeleton() {
  return (
    <div style={{ fontFamily: _T.fontFamily }}>
      <div style={{ display: 'flex', gap: '8px', marginBottom: _S.md }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <window.PMSSkeleton key={i} width="140px" height="56px" />
        ))}
      </div>
      <window.PMSSkeleton width="100%" height="220px" />
      <div style={{ marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="300px" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main PositionBookPage Component
// ---------------------------------------------------------------------------
function PositionBookPage() {
  // Fetch book data (positions + summary)
  const book = window.useFetch('/api/v1/pms/book', 60000);
  // Fetch equity curve data
  const equityCurve = window.useFetch('/api/v1/pms/pnl/equity-curve', 60000);

  // Expanded row state (single row at a time)
  const [expandedRowId, setExpandedRowId] = useState(null);
  // Close dialog state
  const [closingPosition, setClosingPosition] = useState(null);
  // Track locally closed positions for immediate UI update
  const [closedIds, setClosedIds] = useState(new Set());

  const isLoading = book.loading && equityCurve.loading;

  // Resolve data with sample fallback
  const bookData = (book.data && book.data.summary) ? book.data : SAMPLE_BOOK;
  const equityData = (equityCurve.data && Array.isArray(equityCurve.data) && equityCurve.data.length > 0) ? equityCurve.data : SAMPLE_EQUITY_CURVE;
  const usingSampleData = bookData === SAMPLE_BOOK;

  // Filter out locally closed positions
  const openPositions = (bookData.positions || []).filter(p => !closedIds.has(p.id));

  const handleExpandRow = (posId) => {
    setExpandedRowId(prev => prev === posId ? null : posId);
  };

  const handleCloseClick = (position) => {
    setClosingPosition(position);
  };

  const handleCloseConfirm = (posId) => {
    setClosedIds(prev => new Set(prev).add(posId));
    setClosingPosition(null);
    setExpandedRowId(null);
  };

  const handleCloseCancel = () => {
    setClosingPosition(null);
  };

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

  const posCount = openPositions.length;
  const today = new Date().toISOString().split('T')[0];

  return (
    <div style={pageStyle}>
      {/* Sample data banner */}
      {usingSampleData && <window.SampleDataBanner />}
      {/* Page header */}
      <div style={{ marginBottom: _S.md }}>
        <div style={titleStyle}>Position Book</div>
        <div style={subtitleStyle}>
          {today} | {posCount} open positions | Updated {new Date().toLocaleTimeString()}
        </div>
      </div>

      {isLoading ? (
        <PositionBookSkeleton />
      ) : (
        <React.Fragment>
          {/* Section 1: P&L Summary Cards */}
          <PnLSummaryCards summary={bookData.summary} />

          {/* Section 2: Equity Curve Chart */}
          <EquityCurveSection equityCurve={equityData} />

          {/* Section 3: Positions Table */}
          <PositionsTable
            positions={openPositions}
            onExpandRow={handleExpandRow}
            expandedRowId={expandedRowId}
            onCloseClick={handleCloseClick}
          />
        </React.Fragment>
      )}

      {/* Section 4: Close Position Dialog */}
      <ClosePositionDialog
        position={closingPosition}
        onConfirm={handleCloseConfirm}
        onCancel={handleCloseCancel}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.PositionBookPage = PositionBookPage;

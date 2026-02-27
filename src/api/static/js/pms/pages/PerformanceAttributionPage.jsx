/**
 * PerformanceAttributionPage.jsx - Performance Attribution page for the PMS.
 *
 * Bloomberg PORT-style multi-dimensional P&L decomposition with:
 * 1. PeriodSelector (Daily, MTD, QTD, YTD, Custom) -- updates all charts simultaneously
 * 2. DimensionSwitcher (By Strategy, By Asset Class, By Instrument) -- tabbed
 * 3. WaterfallChart -- floating-bar P&L contribution chart
 * 4. AttributionTable -- dense data table with inline magnitude bars
 * 5. TimeSeriesDecomposition -- daily P&L bars + cumulative P&L line (ComposedChart)
 *
 * Consumes 2 API endpoints:
 * - /api/v1/pms/attribution?period=...           (60s poll -- multi-dim attribution)
 * - /api/v1/pms/attribution/equity-curve          (60s poll -- daily equity curve)
 *
 * Falls back to comprehensive sample data when API unavailable.
 * All components accessed via window globals (CDN/Babel pattern).
 */

const { useState, useEffect, useCallback, useMemo } = React;
const {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, ComposedChart, Line,
} = Recharts;

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
// Seeded PRNG (same approach as PositionBookPage / RiskMonitorPage)
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
 * Format P&L in BRL with abbreviated notation and sign.
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
 * Format notional with abbreviated notation.
 */
function formatSize(value) {
  if (value == null || isNaN(value)) return '--';
  const abs = Math.abs(value);
  if (abs >= 1e9) return (value / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return (value / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (value / 1e3).toFixed(0) + 'K';
  return value.toFixed(0);
}

// ---------------------------------------------------------------------------
// Sample Data Constants
// ---------------------------------------------------------------------------

const SAMPLE_ATTRIBUTION = {
  period: { label: 'MTD', start: '2026-02-01', end: '2026-02-25' },
  total_pnl_brl: 1820000,
  total_return_pct: 0.0121,
  by_strategy: [
    { strategy_id: 'FX-02', pnl_brl: 420000, return_contribution_pct: 0.0028, trades_count: 12, win_rate_pct: 66.7 },
    { strategy_id: 'FX-03', pnl_brl: -85000, return_contribution_pct: -0.0006, trades_count: 8, win_rate_pct: 37.5 },
    { strategy_id: 'FX-04', pnl_brl: 195000, return_contribution_pct: 0.0013, trades_count: 5, win_rate_pct: 60.0 },
    { strategy_id: 'RATES-03', pnl_brl: 380000, return_contribution_pct: 0.0025, trades_count: 9, win_rate_pct: 55.6 },
    { strategy_id: 'RATES-05', pnl_brl: -120000, return_contribution_pct: -0.0008, trades_count: 6, win_rate_pct: 33.3 },
    { strategy_id: 'INF-02', pnl_brl: 510000, return_contribution_pct: 0.0034, trades_count: 4, win_rate_pct: 75.0 },
    { strategy_id: 'SOV-02', pnl_brl: 285000, return_contribution_pct: 0.0019, trades_count: 7, win_rate_pct: 57.1 },
    { strategy_id: 'CROSS-01', pnl_brl: 235000, return_contribution_pct: 0.0016, trades_count: 3, win_rate_pct: 66.7 },
  ],
  by_asset_class: [
    { asset_class: 'FX', pnl_brl: 530000, return_contribution_pct: 0.0035, avg_notional_brl: 16700000 },
    { asset_class: 'RATES', pnl_brl: 260000, return_contribution_pct: 0.0017, avg_notional_brl: 19000000 },
    { asset_class: 'INFLATION', pnl_brl: 510000, return_contribution_pct: 0.0034, avg_notional_brl: 20000000 },
    { asset_class: 'CUPOM_CAMBIAL', pnl_brl: 95000, return_contribution_pct: 0.0006, avg_notional_brl: 12000000 },
    { asset_class: 'SOVEREIGN', pnl_brl: 190000, return_contribution_pct: 0.0013, avg_notional_brl: 9000000 },
    { asset_class: 'CROSS_ASSET', pnl_brl: 235000, return_contribution_pct: 0.0016, avg_notional_brl: 11000000 },
  ],
  by_instrument: [
    { instrument: 'USDBRL NDF 3M', pnl_brl: 340000, return_contribution_pct: 0.0023, trades_count: 8 },
    { instrument: 'USDBRL NDF 6M', pnl_brl: 105000, return_contribution_pct: 0.0007, trades_count: 4 },
    { instrument: 'DOL WDO', pnl_brl: 85000, return_contribution_pct: 0.0006, trades_count: 5 },
    { instrument: 'DI1 Jan26', pnl_brl: 180000, return_contribution_pct: 0.0012, trades_count: 6 },
    { instrument: 'DI1 Jan27', pnl_brl: 80000, return_contribution_pct: 0.0005, trades_count: 3 },
    { instrument: 'NTN-B 2030', pnl_brl: 320000, return_contribution_pct: 0.0021, trades_count: 2 },
    { instrument: 'NTN-B 2035', pnl_brl: 190000, return_contribution_pct: 0.0013, trades_count: 2 },
    { instrument: 'DDI Jan26', pnl_brl: 95000, return_contribution_pct: 0.0006, trades_count: 3 },
    { instrument: 'CDS BR 5Y', pnl_brl: -45000, return_contribution_pct: -0.0003, trades_count: 4 },
    { instrument: 'LTN 2025', pnl_brl: 235000, return_contribution_pct: 0.0016, trades_count: 3 },
    { instrument: 'IBOV FUT', pnl_brl: 195000, return_contribution_pct: 0.0013, trades_count: 2 },
    { instrument: 'UST 10Y', pnl_brl: 40000, return_contribution_pct: 0.0003, trades_count: 1 },
  ],
  by_time_period: [
    { period_start: '2026-02-03', pnl_brl: 95000 },
    { period_start: '2026-02-04', pnl_brl: -42000 },
    { period_start: '2026-02-05', pnl_brl: 128000 },
    { period_start: '2026-02-06', pnl_brl: 67000 },
    { period_start: '2026-02-07', pnl_brl: -18000 },
    { period_start: '2026-02-10', pnl_brl: 145000 },
    { period_start: '2026-02-11', pnl_brl: 82000 },
    { period_start: '2026-02-12', pnl_brl: -65000 },
    { period_start: '2026-02-13', pnl_brl: 112000 },
    { period_start: '2026-02-14', pnl_brl: 198000 },
    { period_start: '2026-02-17', pnl_brl: -93000 },
    { period_start: '2026-02-18', pnl_brl: 156000 },
    { period_start: '2026-02-19', pnl_brl: 74000 },
    { period_start: '2026-02-20', pnl_brl: 245000 },
    { period_start: '2026-02-21', pnl_brl: -38000 },
    { period_start: '2026-02-24', pnl_brl: 310000 },
    { period_start: '2026-02-25', pnl_brl: 164000 },
    { period_start: '2026-02-26', pnl_brl: 0 },
  ],
  by_factor: [],
  by_trade_type: {},
  performance_stats: {},
};

/**
 * Generate 60 daily equity curve points with seeded PRNG (MTD scope).
 */
function generateSampleEquityCurve() {
  const rand = seededRng(77);
  const data = [];
  let equity = 150000000;
  let peak = equity;

  for (let i = 0; i < 60; i++) {
    const dailyReturn = (rand() - 0.46) * 0.008;
    equity *= (1 + dailyReturn);
    peak = Math.max(peak, equity);
    const drawdown = ((equity - peak) / peak) * 100;

    const d = new Date(2025, 11, 15); // start 2025-12-15
    d.setDate(d.getDate() + i);

    const cumulativeReturn = (equity - 150000000) / 150000000;

    data.push({
      date: d.toISOString().slice(0, 10),
      equity_brl: Math.round(equity),
      return_pct_daily: Math.round(dailyReturn * 10000) / 10000,
      return_pct_cumulative: Math.round(cumulativeReturn * 10000) / 10000,
      drawdown_pct: Math.round(drawdown * 100) / 100,
    });
  }
  return data;
}

const SAMPLE_EQUITY_CURVE = generateSampleEquityCurve();

// ---------------------------------------------------------------------------
// Period Selector
// ---------------------------------------------------------------------------
function PeriodSelector({ period, onPeriodChange, customStart, customEnd, onCustomStartChange, onCustomEndChange }) {
  const periods = ['Daily', 'MTD', 'QTD', 'YTD', 'Custom'];

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    flexWrap: 'wrap',
  };

  const buttonStyle = (isActive) => ({
    background: isActive ? _C.border.accent : 'transparent',
    color: isActive ? _C.text.primary : _C.text.secondary,
    border: '1px solid ' + (isActive ? _C.border.accent : _C.border.default),
    borderRadius: '3px',
    padding: '4px 12px',
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.medium,
    fontFamily: _T.fontFamily,
    cursor: 'pointer',
    lineHeight: 1.4,
  });

  const dateInputStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '3px',
    padding: '3px 8px',
    color: _C.text.primary,
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
    outline: 'none',
  };

  return (
    <div style={containerStyle}>
      {periods.map(p => (
        <button
          key={p}
          style={buttonStyle(period === p)}
          onClick={() => onPeriodChange(p)}
        >
          {p}
        </button>
      ))}
      {period === 'Custom' && (
        <React.Fragment>
          <input
            type="date"
            value={customStart}
            onChange={(e) => onCustomStartChange(e.target.value)}
            style={dateInputStyle}
          />
          <span style={{ color: _C.text.muted, fontSize: _T.sizes.xs, fontFamily: _T.fontFamily }}>to</span>
          <input
            type="date"
            value={customEnd}
            onChange={(e) => onCustomEndChange(e.target.value)}
            style={dateInputStyle}
          />
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dimension Switcher (Tabs)
// ---------------------------------------------------------------------------
function DimensionSwitcher({ dimension, onDimensionChange }) {
  const tabs = [
    { key: 'strategy', label: 'By Strategy' },
    { key: 'asset_class', label: 'By Asset Class' },
    { key: 'instrument', label: 'By Instrument' },
  ];

  const containerStyle = {
    display: 'flex',
    borderBottom: '1px solid ' + _C.border.default,
    marginBottom: _S.md,
  };

  const tabStyle = (isActive) => ({
    padding: '6px 16px',
    fontSize: _T.sizes.sm,
    fontWeight: isActive ? _T.weights.semibold : _T.weights.medium,
    fontFamily: _T.fontFamily,
    color: isActive ? _C.text.primary : _C.text.secondary,
    cursor: 'pointer',
    borderBottom: isActive ? '2px solid ' + _C.border.accent : '2px solid transparent',
    background: 'transparent',
    border: 'none',
    borderBottomWidth: '2px',
    borderBottomStyle: 'solid',
    borderBottomColor: isActive ? _C.border.accent : 'transparent',
    marginBottom: '-1px',
  });

  return (
    <div style={containerStyle}>
      {tabs.map(tab => (
        <button
          key={tab.key}
          style={tabStyle(dimension === tab.key)}
          onClick={() => onDimensionChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Waterfall Chart
// ---------------------------------------------------------------------------
function WaterfallChart({ data, dimension, totalPnl }) {
  const waterfallData = useMemo(() => {
    if (!data || data.length === 0) return [];

    // Sort by pnl_brl descending (positive first, then negative)
    const sorted = [...data].sort((a, b) => (b.pnl_brl || 0) - (a.pnl_brl || 0));

    let runningSum = 0;
    const items = sorted.map(item => {
      const value = item.pnl_brl || 0;
      const base = value >= 0 ? runningSum : runningSum + value;
      const barValue = Math.abs(value);
      runningSum += value;

      let name;
      if (dimension === 'strategy') name = item.strategy_id;
      else if (dimension === 'asset_class') name = item.asset_class;
      else name = item.instrument;

      return {
        name: name || '--',
        invisible: Math.max(0, base),
        value: barValue,
        rawValue: value,
        isTotal: false,
      };
    });

    // Add total bar
    items.push({
      name: 'Total',
      invisible: 0,
      value: Math.abs(totalPnl || runningSum),
      rawValue: totalPnl || runningSum,
      isTotal: true,
    });

    return items;
  }, [data, dimension, totalPnl]);

  if (waterfallData.length === 0) {
    return (
      <div style={{ color: _C.text.muted, fontSize: _T.sizes.sm, textAlign: 'center', padding: '32px 0', fontFamily: _T.fontFamily }}>
        No attribution data available
      </div>
    );
  }

  const getBarColor = (entry) => {
    if (entry.isTotal) return _C.border.accent;
    return entry.rawValue >= 0 ? _C.pnl.positive : _C.pnl.negative;
  };

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;
    const entry = waterfallData.find(d => d.name === label);
    if (!entry) return null;

    const total = totalPnl || 1;
    const pctOfTotal = total !== 0 ? ((entry.rawValue / total) * 100).toFixed(1) : '0.0';

    return (
      <div style={tooltipStyle}>
        <div style={{ padding: '6px 8px' }}>
          <div style={{ color: _C.text.primary, marginBottom: '2px', fontWeight: _T.weights.semibold }}>{entry.name}</div>
          <div style={{ color: _pnlColor(entry.rawValue) }}>{formatPnLShort(entry.rawValue)}</div>
          {!entry.isTotal && (
            <div style={{ color: _C.text.secondary, marginTop: '2px' }}>{pctOfTotal}% of total</div>
          )}
        </div>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={waterfallData} margin={{ left: 10, right: 10, top: 10, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={_C.border.subtle} />
        <XAxis
          dataKey="name"
          stroke={_C.text.muted}
          tick={{ fontSize: 8, fontFamily: _T.fontFamily, fill: _C.text.secondary }}
          interval={0}
          angle={waterfallData.length > 8 ? -30 : 0}
          textAnchor={waterfallData.length > 8 ? 'end' : 'middle'}
          height={waterfallData.length > 8 ? 50 : 30}
        />
        <YAxis
          stroke={_C.text.muted}
          tick={{ fontSize: 9, fontFamily: _T.fontFamily }}
          tickFormatter={(v) => formatPnLShort(v)}
        />
        <Tooltip content={<CustomTooltip />} />
        {/* Invisible base bar */}
        <Bar dataKey="invisible" stackId="waterfall" fill="transparent" />
        {/* Visible value bar */}
        <Bar dataKey="value" stackId="waterfall" radius={[2, 2, 0, 0]}>
          {waterfallData.map((entry, index) => (
            <Cell key={index} fill={getBarColor(entry)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Attribution Table
// ---------------------------------------------------------------------------
function AttributionTable({ data, dimension, totalPnl }) {
  // Sort by absolute P&L descending
  const sortedData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return [...data].sort((a, b) => Math.abs(b.pnl_brl || 0) - Math.abs(a.pnl_brl || 0));
  }, [data]);

  const maxAbsPnl = useMemo(() => {
    if (sortedData.length === 0) return 1;
    return Math.max(...sortedData.map(d => Math.abs(d.pnl_brl || 0)));
  }, [sortedData]);

  // Define columns per dimension
  const getColumns = () => {
    if (dimension === 'strategy') {
      return [
        { key: 'strategy_id', label: 'Strategy ID', align: 'left', format: (v) => v || '--' },
        { key: 'pnl_brl', label: 'P&L (BRL)', align: 'right', format: (v) => formatPnLShort(v) },
        { key: 'return_contribution_pct', label: 'Return Contr.', align: 'right', format: (v) => _formatPercent(v) },
        { key: 'trades_count', label: 'Trades', align: 'right', format: (v) => v != null ? String(v) : '--' },
        { key: 'win_rate_pct', label: 'Win Rate', align: 'right', format: (v) => v != null ? v.toFixed(1) + '%' : '--' },
        { key: '_bar', label: '', align: 'left' },
      ];
    }
    if (dimension === 'asset_class') {
      return [
        { key: 'asset_class', label: 'Asset Class', align: 'left', format: (v) => v || '--' },
        { key: 'pnl_brl', label: 'P&L (BRL)', align: 'right', format: (v) => formatPnLShort(v) },
        { key: 'return_contribution_pct', label: 'Return Contr.', align: 'right', format: (v) => _formatPercent(v) },
        { key: 'avg_notional_brl', label: 'Avg Notional', align: 'right', format: (v) => formatSize(v) },
        { key: '_bar', label: 'Magnitude', align: 'left' },
      ];
    }
    // instrument
    return [
      { key: 'instrument', label: 'Instrument', align: 'left', format: (v) => v || '--' },
      { key: 'pnl_brl', label: 'P&L (BRL)', align: 'right', format: (v) => formatPnLShort(v) },
      { key: 'return_contribution_pct', label: 'Return Contr.', align: 'right', format: (v) => _formatPercent(v) },
      { key: 'trades_count', label: 'Trades', align: 'right', format: (v) => v != null ? String(v) : '--' },
      { key: '_bar', label: 'Magnitude', align: 'left' },
    ];
  };

  const columns = getColumns();

  const cellPadding = '5px 10px';

  const headerCellStyle = {
    padding: cellPadding,
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

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} style={{ ...headerCellStyle, textAlign: col.align }}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row, rowIdx) => {
            const rowBg = rowIdx % 2 === 0 ? _C.bg.secondary : _C.bg.tertiary;
            const pnl = row.pnl_brl || 0;
            const barWidth = maxAbsPnl > 0 ? (Math.abs(pnl) / maxAbsPnl) * 100 : 0;
            const barColor = _pnlColor(pnl);

            return (
              <tr
                key={rowIdx}
                style={{
                  backgroundColor: rowBg,
                  transition: 'background-color 0.1s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = _C.bg.elevated; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = rowBg; }}
              >
                {columns.map(col => {
                  if (col.key === '_bar') {
                    return (
                      <td key={col.key} style={{ padding: cellPadding, borderBottom: '1px solid ' + _C.border.subtle, minWidth: '80px' }}>
                        <div style={{
                          width: barWidth + '%',
                          height: '6px',
                          backgroundColor: barColor,
                          borderRadius: '3px',
                          minWidth: barWidth > 0 ? '4px' : '0px',
                          transition: 'width 0.3s ease',
                        }} />
                      </td>
                    );
                  }

                  const rawValue = row[col.key];
                  const displayValue = col.format ? col.format(rawValue, row) : (rawValue != null ? String(rawValue) : '--');
                  const isPnlCol = col.key === 'pnl_brl';

                  return (
                    <td
                      key={col.key}
                      style={{
                        padding: cellPadding,
                        color: isPnlCol ? _pnlColor(rawValue) : _C.text.primary,
                        textAlign: col.align || 'left',
                        borderBottom: '1px solid ' + _C.border.subtle,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {displayValue}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      {sortedData.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '16px',
          color: _C.text.muted,
          fontSize: _T.sizes.sm,
          fontFamily: _T.fontFamily,
        }}>
          No data available
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Time-Series Decomposition (Daily P&L bars + Cumulative P&L line)
// ---------------------------------------------------------------------------
function TimeSeriesDecomposition({ timePeriodData, equityCurve, periodLabel }) {
  // Build chart data from by_time_period, computing cumulative P&L
  const chartData = useMemo(() => {
    if (!timePeriodData || timePeriodData.length === 0) return [];
    let cumulative = 0;
    return timePeriodData.map(entry => {
      const pnl = entry.pnl_brl || 0;
      cumulative += pnl;
      return {
        date: entry.period_start || entry.date || '--',
        daily_pnl: pnl,
        cumulative_pnl: cumulative,
      };
    });
  }, [timePeriodData]);

  if (chartData.length === 0) {
    return (
      <div style={{ color: _C.text.muted, fontSize: _T.sizes.sm, textAlign: 'center', padding: '32px 0', fontFamily: _T.fontFamily }}>
        No time-series data available
      </div>
    );
  }

  const containerStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '12px',
    marginTop: _S.md,
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

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={titleStyle}>P&L Time Series</div>
        {periodLabel && (
          <div style={{ fontSize: _T.sizes.xs, color: _C.text.muted, fontFamily: _T.fontFamily }}>
            {periodLabel}
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={chartData} margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={_C.border.subtle} />
          <XAxis
            dataKey="date"
            stroke={_C.text.muted}
            tick={{ fontSize: 8, fontFamily: _T.fontFamily }}
            interval={Math.max(1, Math.floor(chartData.length / 8))}
          />
          <YAxis
            yAxisId="daily"
            orientation="left"
            stroke={_C.text.muted}
            tick={{ fontSize: 9, fontFamily: _T.fontFamily }}
            tickFormatter={(v) => formatPnLShort(v)}
          />
          <YAxis
            yAxisId="cumulative"
            orientation="right"
            stroke={_C.text.muted}
            tick={{ fontSize: 9, fontFamily: _T.fontFamily }}
            tickFormatter={(v) => formatPnLShort(v)}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelStyle={{ color: _C.text.secondary }}
            formatter={(value, name) => [formatPnLShort(value), name]}
          />
          {/* Daily P&L bars */}
          <Bar yAxisId="daily" dataKey="daily_pnl" name="Daily P&L" barSize={12}>
            {chartData.map((entry, index) => (
              <Cell key={index} fill={entry.daily_pnl >= 0 ? _C.pnl.positive : _C.pnl.negative} />
            ))}
          </Bar>
          {/* Cumulative P&L line */}
          <Line
            yAxisId="cumulative"
            type="monotone"
            dataKey="cumulative_pnl"
            stroke={_C.border.accent}
            strokeWidth={2}
            dot={false}
            name="Cumulative P&L"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Attribution Skeleton (loading state)
// ---------------------------------------------------------------------------
function AttributionSkeleton() {
  return (
    <div style={{ fontFamily: _T.fontFamily }}>
      {/* Period selector skeleton */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: _S.md }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <window.PMSSkeleton key={i} width="60px" height="28px" />
        ))}
      </div>
      {/* Tabs skeleton */}
      <window.PMSSkeleton width="300px" height="32px" />
      {/* Waterfall chart skeleton */}
      <div style={{ marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="280px" />
      </div>
      {/* Table skeleton */}
      <div style={{ marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="200px" />
      </div>
      {/* Time series skeleton */}
      <div style={{ marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="220px" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Backtest Detail Section (migrated from Dashboard StrategiesPage)
// ---------------------------------------------------------------------------
function BacktestDetailSection() {
  const { useState: _bUseState, useMemo: _bUseMemo, useCallback: _bUseCallback } = React;
  const strategies = window.useFetch('/api/v1/strategies', 60000);
  const [expandedId, setExpandedId] = _bUseState(null);

  const stratList = _bUseMemo(() => {
    const d = strategies.data;
    return d && d.data ? d.data : [];
  }, [strategies.data]);

  const cardStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '12px',
    marginTop: _S.md,
  };

  const sectionTitleSt = {
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _T.fontFamily,
    marginBottom: '8px',
  };

  if (strategies.loading && stratList.length === 0) {
    return (
      <div style={cardStyle}>
        <div style={sectionTitleSt}>Strategy Backtest Metrics</div>
        <div style={{ height: '60px', backgroundColor: _C.bg.tertiary, borderRadius: '4px' }} />
      </div>
    );
  }

  if (stratList.length === 0) return null;

  const thStyle = {
    fontSize: _T.sizes.xs, color: _C.text.muted, textTransform: 'uppercase',
    letterSpacing: '0.04em', fontFamily: _T.fontFamily, padding: '6px 8px',
    borderBottom: '1px solid ' + _C.border.default, textAlign: 'left',
  };
  const tdStyle = {
    fontSize: _T.sizes.sm, color: _C.text.primary, fontFamily: _T.fontFamily,
    padding: '6px 8px', borderBottom: '1px solid ' + _C.border.subtle,
  };

  return (
    <div style={cardStyle}>
      <div style={sectionTitleSt}>Strategy Backtest Metrics</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>Strategy</th>
              <th style={thStyle}>Asset Class</th>
              <th style={{ ...thStyle, textAlign: 'center' }}>Signal</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Sharpe</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Max DD</th>
            </tr>
          </thead>
          <tbody>
            {stratList.map((s) => {
              const sid = s.strategy_id;
              const isExpanded = expandedId === sid;
              const dir = (s.signal_direction || '').toUpperCase();
              const dirColor = dir === 'LONG' ? _C.pnl.positive : dir === 'SHORT' ? _C.pnl.negative : _C.text.muted;
              const dirLabel = dir === 'LONG' ? '\u2191 LONG' : dir === 'SHORT' ? '\u2193 SHORT' : '\u2014 NEUTRAL';
              return (
                <React.Fragment key={sid}>
                  <tr
                    style={{ cursor: 'pointer', backgroundColor: isExpanded ? _C.bg.tertiary : 'transparent' }}
                    onClick={() => setExpandedId(isExpanded ? null : sid)}
                    onMouseEnter={(e) => { if (!isExpanded) e.currentTarget.style.backgroundColor = _C.bg.tertiary; }}
                    onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <td style={{ ...tdStyle, fontWeight: _T.weights.medium }}>{sid}</td>
                    <td style={tdStyle}>{s.asset_class || '--'}</td>
                    <td style={{ ...tdStyle, textAlign: 'center', color: dirColor, fontWeight: _T.weights.semibold }}>{dirLabel}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{s.sharpe_ratio != null ? s.sharpe_ratio.toFixed(2) : '--'}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{s.max_drawdown != null ? (s.max_drawdown * 100).toFixed(1) + '%' : '--'}</td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={5} style={{ padding: '8px', backgroundColor: _C.bg.primary }}>
                        <BacktestMetricsPanel strategyId={sid} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BacktestMetricsPanel({ strategyId }) {
  const bt = window.useFetch('/api/v1/backtest/results?strategy_id=' + encodeURIComponent(strategyId), 60000);

  if (bt.loading) {
    return <div style={{ height: '60px', backgroundColor: _C.bg.tertiary, borderRadius: '4px' }} />;
  }

  const d = bt.data && bt.data.data ? bt.data.data : {};
  const metrics = [
    { label: 'Ann. Ret', value: d.annual_return != null ? (d.annual_return * 100).toFixed(1) + '%' : '--' },
    { label: 'Sharpe', value: d.sharpe_ratio != null ? d.sharpe_ratio.toFixed(2) : '--' },
    { label: 'Sortino', value: d.sortino_ratio != null ? d.sortino_ratio.toFixed(2) : '--' },
    { label: 'Max DD', value: d.max_drawdown != null ? (d.max_drawdown * 100).toFixed(1) + '%' : '--' },
    { label: 'Win Rate', value: d.win_rate != null ? (d.win_rate * 100).toFixed(0) + '%' : '--' },
    { label: 'Trades', value: d.total_trades != null ? d.total_trades : '--' },
    { label: 'P. Factor', value: d.profit_factor != null ? d.profit_factor.toFixed(2) : '--' },
  ];

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
    gap: '6px',
  };

  const metricCardStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.subtle,
    borderRadius: '4px',
    padding: '6px 8px',
    textAlign: 'center',
  };

  return (
    <div style={gridStyle}>
      {metrics.map((m, i) => (
        <div key={i} style={metricCardStyle}>
          <div style={{ fontSize: _T.sizes.xs, color: _C.text.muted, textTransform: 'uppercase', marginBottom: '2px', fontFamily: _T.fontFamily }}>{m.label}</div>
          <div style={{ fontSize: _T.sizes.sm, fontWeight: _T.weights.bold, color: _C.text.primary, fontFamily: _T.fontFamily }}>{m.value}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main PerformanceAttributionPage Component
// ---------------------------------------------------------------------------
function PerformanceAttributionPage() {
  // State
  const [period, setPeriod] = useState('MTD');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [dimension, setDimension] = useState('strategy');

  // Build attribution URL based on period
  const attributionUrl = useMemo(() => {
    let url = '/api/v1/pms/attribution?period=' + encodeURIComponent(period);
    if (period === 'Custom' && customStart && customEnd) {
      url = '/api/v1/pms/attribution?period=custom&start_date=' + encodeURIComponent(customStart) + '&end_date=' + encodeURIComponent(customEnd);
    }
    return url;
  }, [period, customStart, customEnd]);

  // Fetch attribution data
  const attribution = window.useFetch(attributionUrl, 60000);
  // Fetch equity curve data
  const equityCurve = window.useFetch('/api/v1/pms/attribution/equity-curve', 60000);

  const isLoading = attribution.loading && equityCurve.loading;

  // Resolve data with sample fallback
  const attrData = useMemo(() => {
    const d = attribution.data;
    if (d && d.total_pnl_brl != null) return d;
    return SAMPLE_ATTRIBUTION;
  }, [attribution.data]);

  const equityData = useMemo(() => {
    const d = equityCurve.data;
    if (d && Array.isArray(d) && d.length > 0) return d;
    return SAMPLE_EQUITY_CURVE;
  }, [equityCurve.data]);

  // Get active dimension data
  const dimensionData = useMemo(() => {
    if (dimension === 'strategy') return attrData.by_strategy || [];
    if (dimension === 'asset_class') return attrData.by_asset_class || [];
    return attrData.by_instrument || [];
  }, [dimension, attrData]);

  // Period label
  const periodLabel = useMemo(() => {
    const p = attrData.period || {};
    if (p.start && p.end) return p.start + ' to ' + p.end;
    if (p.label) return p.label;
    return period;
  }, [attrData, period]);

  const usingSampleData = attrData === SAMPLE_ATTRIBUTION;
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

  // Summary metrics row
  const totalPnl = attrData.total_pnl_brl || 0;
  const totalReturn = attrData.total_return_pct || 0;

  const metricRowStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: _S.md,
    padding: '8px 12px',
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
  };

  const metricLabelStyle = {
    fontSize: _T.sizes.xs,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    fontFamily: _T.fontFamily,
  };

  const metricValueStyle = (val) => ({
    fontSize: _T.sizes.lg,
    fontWeight: _T.weights.bold,
    color: _pnlColor(val),
    fontFamily: _T.fontFamily,
  });

  // Waterfall + table container
  const sectionCardStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '12px',
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

  return (
    <div style={pageStyle}>
      {/* Sample data banner */}
      {usingSampleData && <window.SampleDataBanner />}
      {/* Page header */}
      <div style={{ marginBottom: _S.sm }}>
        <div style={titleStyle}>Performance Attribution</div>
        <div style={subtitleStyle}>
          {periodLabel} | Updated {new Date().toLocaleTimeString()}
        </div>
      </div>

      {isLoading ? (
        <AttributionSkeleton />
      ) : (
        <React.Fragment>
          {/* Period Selector */}
          <div style={{ marginBottom: _S.md }}>
            <PeriodSelector
              period={period}
              onPeriodChange={setPeriod}
              customStart={customStart}
              customEnd={customEnd}
              onCustomStartChange={setCustomStart}
              onCustomEndChange={setCustomEnd}
            />
          </div>

          {/* Total P&L Summary */}
          <div style={metricRowStyle}>
            <div>
              <div style={metricLabelStyle}>Total P&L</div>
              <div style={metricValueStyle(totalPnl)}>{formatPnLShort(totalPnl)}</div>
            </div>
            <div style={{ width: '1px', height: '32px', backgroundColor: _C.border.default }} />
            <div>
              <div style={metricLabelStyle}>Total Return</div>
              <div style={metricValueStyle(totalReturn)}>{_formatPercent(totalReturn)}</div>
            </div>
            <div style={{ width: '1px', height: '32px', backgroundColor: _C.border.default }} />
            <div>
              <div style={metricLabelStyle}>Period</div>
              <div style={{ fontSize: _T.sizes.sm, color: _C.text.primary, fontFamily: _T.fontFamily, fontWeight: _T.weights.medium }}>
                {(attrData.period && attrData.period.label) || period}
              </div>
            </div>
          </div>

          {/* Dimension Switcher */}
          <DimensionSwitcher dimension={dimension} onDimensionChange={setDimension} />

          {/* Waterfall Chart */}
          <div style={sectionCardStyle}>
            <div style={sectionTitleStyle}>P&L Contribution Waterfall</div>
            <WaterfallChart
              data={dimensionData}
              dimension={dimension}
              totalPnl={totalPnl}
            />
          </div>

          {/* Attribution Table */}
          <div style={sectionCardStyle}>
            <div style={sectionTitleStyle}>Attribution Detail</div>
            <AttributionTable
              data={dimensionData}
              dimension={dimension}
              totalPnl={totalPnl}
            />
          </div>

          {/* Time-Series P&L Decomposition */}
          <TimeSeriesDecomposition
            timePeriodData={attrData.by_time_period}
            equityCurve={equityData}
            periodLabel={periodLabel}
          />

          {/* Strategy Backtest Detail (migrated from Dashboard) */}
          <BacktestDetailSection />
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.PerformanceAttributionPage = PerformanceAttributionPage;

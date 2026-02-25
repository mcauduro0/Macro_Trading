/**
 * RiskMonitorPage.jsx - Risk Monitor page for the PMS.
 *
 * Bloomberg PORT-dense 4-quadrant dashboard providing real-time risk oversight:
 * 1. Alert Summary Bar (breach/warning counts)
 * 2. Four-Quadrant Grid:
 *    - Top-Left:  VaR Gauges (Parametric 95/99%, MC 95/99%) as semi-circular SVG arcs
 *    - Top-Right: Stress Test Horizontal Bar Chart (6 scenarios, severity-sorted)
 *    - Bot-Left:  Limit Utilization Bars (click-to-expand, 2-tier WARNING/BREACH alerting)
 *    - Bot-Right: Concentration Pie Chart (asset class allocation donut)
 * 3. Historical VaR Chart (time-series with trailing window selector)
 *
 * Consumes 3 API endpoints:
 * - /api/v1/pms/risk/live    (30s poll -- live risk snapshot)
 * - /api/v1/pms/risk/trend   (60s poll -- historical VaR time-series)
 * - /api/v1/pms/risk/limits  (60s poll -- limits config + summary)
 *
 * Falls back to comprehensive sample data when API unavailable.
 * All components accessed via window globals (CDN/Babel pattern).
 */

const { useState, useEffect, useCallback, useMemo, useRef } = React;
const {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie, Legend, ComposedChart, Line, ReferenceLine,
} = Recharts;

// ---------------------------------------------------------------------------
// Access PMS design system from window globals
// ---------------------------------------------------------------------------
const {
  PMS_COLORS: _C,
  PMS_TYPOGRAPHY: _T,
  PMS_SPACING: _S,
  pnlColor: _pnlColor,
  riskColor: _riskColor,
  formatPnL: _formatPnL,
  formatPercent: _formatPercent,
  formatNumber: _formatNumber,
} = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Seeded PRNG (same approach as PositionBookPage / MorningPackPage)
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

// ---------------------------------------------------------------------------
// Pie chart colors
// ---------------------------------------------------------------------------
const PIE_COLORS = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7', '#f0883e'];

// ---------------------------------------------------------------------------
// Sample Data Constants
// ---------------------------------------------------------------------------

const SAMPLE_RISK_LIVE = {
  as_of_date: new Date().toISOString().slice(0, 10),
  var: {
    parametric_95: 1.42,
    parametric_99: 2.15,
    monte_carlo_95: 1.38,
    monte_carlo_99: 2.08,
    limit_95_pct: 2.0,
    limit_99_pct: 3.0,
    utilization_95_pct: 71.0,
    utilization_99_pct: 71.7,
  },
  leverage: { gross: 1.20, net: 0.85, limit: 2.0 },
  drawdown: { current_pct: -1.8, max_pct: -3.2, limit_pct: -5.0 },
  concentration: {
    FX: 27.8,
    RATES: 21.1,
    INFLATION: 22.2,
    CUPOM_CAMBIAL: 6.7,
    SOVEREIGN: 10.0,
    CROSS_ASSET: 12.2,
  },
  stress_tests: [
    { scenario: 'Taper Tantrum', impact_brl: -4250000, impact_pct: -2.83 },
    { scenario: 'BR Crisis 2015', impact_brl: -6100000, impact_pct: -4.07 },
    { scenario: 'COVID 2020', impact_brl: -7800000, impact_pct: -5.20 },
    { scenario: 'Rate Shock 2022', impact_brl: -3900000, impact_pct: -2.60 },
    { scenario: 'BR Fiscal Crisis', impact_brl: -5500000, impact_pct: -3.67 },
    { scenario: 'Global Risk-Off', impact_brl: -8200000, impact_pct: -5.47 },
  ],
  limits_summary: {
    items: [
      { name: 'VaR 95%', current: 1.42, limit: 2.0, utilization: 71.0, severity: 'OK' },
      { name: 'VaR 99%', current: 2.15, limit: 3.0, utilization: 71.7, severity: 'OK' },
      { name: 'Gross Leverage', current: 1.20, limit: 2.0, utilization: 60.0, severity: 'OK' },
      { name: 'Max Drawdown', current: 3.2, limit: 5.0, utilization: 64.0, severity: 'OK' },
      { name: 'Daily Loss', current: 0.45, limit: 0.50, utilization: 90.0, severity: 'WARNING' },
      { name: 'Weekly Loss', current: 1.1, limit: 1.5, utilization: 73.3, severity: 'OK' },
      { name: 'Single Name Conc', current: 18.5, limit: 20.0, utilization: 92.5, severity: 'WARNING' },
      { name: 'Sector Conc', current: 32.0, limit: 30.0, utilization: 106.7, severity: 'BREACH' },
      { name: 'Duration Limit', current: 4.8, limit: 7.0, utilization: 68.6, severity: 'OK' },
    ],
  },
  alerts: [
    { type: 'limit', severity: 'WARNING', message: 'Daily Loss limit at 90% utilization', value: 0.45, limit: 0.50 },
    { type: 'limit', severity: 'WARNING', message: 'Single Name Concentration at 92.5%', value: 18.5, limit: 20.0 },
    { type: 'limit', severity: 'BREACH', message: 'Sector Concentration breached (106.7%)', value: 32.0, limit: 30.0 },
  ],
};

/**
 * Generate 90 daily trend data points with seeded PRNG.
 */
function generateSampleTrend() {
  const rand = seededRng(42);
  const data = [];
  let var95 = 1.35;
  let leverage = 1.15;
  let dd = -1.0;

  for (let i = 0; i < 90; i++) {
    var95 += (rand() - 0.48) * 0.08;
    var95 = Math.max(0.5, Math.min(2.8, var95));
    leverage += (rand() - 0.50) * 0.03;
    leverage = Math.max(0.8, Math.min(1.8, leverage));
    dd += (rand() - 0.52) * 0.15;
    dd = Math.min(0, Math.max(-5.0, dd));

    const d = new Date();
    d.setDate(d.getDate() - (90 - i));

    data.push({
      date: d.toISOString().slice(0, 10),
      var_95: Math.round(var95 * 100) / 100,
      var_99: Math.round((var95 * 1.52) * 100) / 100,
      leverage_gross: Math.round(leverage * 100) / 100,
      drawdown_pct: Math.round(dd * 100) / 100,
      alert_count: var95 > 1.8 ? 1 : 0,
    });
  }
  return data;
}

const SAMPLE_RISK_TREND = generateSampleTrend();

const SAMPLE_LIMITS = {
  config: {
    var_95_limit: 2.0,
    var_99_limit: 3.0,
    max_leverage_gross: 2.0,
    max_drawdown_pct: 5.0,
    max_daily_loss_pct: 0.5,
    max_weekly_loss_pct: 1.5,
    max_single_name_pct: 20.0,
    max_sector_pct: 30.0,
    max_duration: 7.0,
  },
  limits_summary: SAMPLE_RISK_LIVE.limits_summary,
};

// ---------------------------------------------------------------------------
// Inject pulse-breach keyframes
// ---------------------------------------------------------------------------
(function injectBreachAnimation() {
  if (typeof document === 'undefined') return;
  var id = 'pms-risk-breach-anim';
  if (document.getElementById(id)) return;
  var style = document.createElement('style');
  style.id = id;
  style.textContent = '@keyframes pulse-breach { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }';
  document.head.appendChild(style);
})();

// ---------------------------------------------------------------------------
// AlertSummaryBar
// ---------------------------------------------------------------------------
function AlertSummaryBar({ alerts }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div style={{
        backgroundColor: 'rgba(63, 185, 80, 0.12)',
        border: '1px solid ' + _C.risk.ok,
        borderRadius: '4px',
        padding: '6px 12px',
        marginBottom: _S.md,
        fontFamily: _T.fontFamily,
        fontSize: _T.sizes.sm,
        color: _C.risk.ok,
        fontWeight: _T.weights.semibold,
      }}>
        All clear -- no active risk alerts
      </div>
    );
  }

  const warnings = alerts.filter(a => a.severity === 'WARNING').length;
  const breaches = alerts.filter(a => a.severity === 'BREACH').length;
  const hasBreach = breaches > 0;

  const bgColor = hasBreach
    ? 'rgba(248, 81, 73, 0.15)'
    : 'rgba(210, 153, 34, 0.15)';
  const borderColor = hasBreach ? _C.risk.breach : _C.risk.warning;
  const textColor = hasBreach ? _C.risk.breach : _C.risk.warning;

  const parts = [];
  if (warnings > 0) parts.push(warnings + ' warning' + (warnings > 1 ? 's' : ''));
  if (breaches > 0) parts.push(breaches + ' breach' + (breaches > 1 ? 'es' : ''));

  return (
    <div style={{
      backgroundColor: bgColor,
      border: '1px solid ' + borderColor,
      borderRadius: '4px',
      padding: '6px 12px',
      marginBottom: _S.md,
      fontFamily: _T.fontFamily,
      fontSize: _T.sizes.sm,
      color: textColor,
      fontWeight: _T.weights.semibold,
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    }}>
      <span style={{ fontSize: _T.sizes.base }}>
        {hasBreach ? '\u26A0' : '\u26A0'}
      </span>
      <span>{parts.join(', ')}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VaRGauge -- single SVG semi-circular gauge
// ---------------------------------------------------------------------------
function VaRGauge({ label, value, limitValue }) {
  const utilization = limitValue > 0 ? Math.min(1.0, Math.abs(value || 0) / limitValue) : 0;

  // Color by severity: green (<50%), amber (50-80%), red (>=80%)
  let color = _C.risk.ok;
  if (utilization >= 0.5) color = _C.risk.warning;
  if (utilization >= 0.8) color = _C.risk.breach;

  // SVG arc math (same approach as RiskPage.jsx GaugeChart)
  const cx = 65, cy = 55, r = 40;
  const startAngle = Math.PI;
  const endAngle = Math.PI + Math.PI * utilization;

  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy + r * Math.sin(endAngle);
  const largeArc = utilization > 0.5 ? 1 : 0;

  // Background arc (full semi-circle)
  const bgX2 = cx + r * Math.cos(Math.PI * 2);
  const bgY2 = cy + r * Math.sin(Math.PI * 2);

  // Needle line
  const needleAngle = Math.PI + Math.PI * utilization;
  const needleX = cx + (r - 5) * Math.cos(needleAngle);
  const needleY = cy + (r - 5) * Math.sin(needleAngle);

  const displayValue = (Math.abs(value || 0)).toFixed(2) + '%';

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      minWidth: '130px',
      flex: '1 1 0',
    }}>
      <svg width="130" height="80" viewBox="0 0 130 80">
        {/* Background arc */}
        <path
          d={'M ' + x1 + ' ' + y1 + ' A ' + r + ' ' + r + ' 0 1 1 ' + bgX2 + ' ' + bgY2}
          fill="none"
          stroke={_C.bg.tertiary}
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Value arc */}
        {utilization > 0 && (
          <path
            d={'M ' + x1 + ' ' + y1 + ' A ' + r + ' ' + r + ' 0 ' + largeArc + ' 1 ' + x2 + ' ' + y2}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
          />
        )}
        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke={_C.text.primary}
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="3" fill={_C.text.primary} />
        {/* Center text */}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fill={color}
          fontSize="13"
          fontWeight="bold"
          fontFamily={_T.fontFamily}
        >
          {displayValue}
        </text>
      </svg>
      <div style={{
        fontSize: _T.sizes.xs,
        fontWeight: _T.weights.semibold,
        color: _C.text.secondary,
        fontFamily: _T.fontFamily,
        textAlign: 'center',
        marginTop: '-4px',
      }}>
        {label}
      </div>
      <div style={{
        fontSize: _T.sizes.xs,
        color: _C.text.muted,
        fontFamily: _T.fontFamily,
        textAlign: 'center',
      }}>
        Limit: {limitValue}%
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VaRGaugeRow -- 4 gauges in a horizontal row
// ---------------------------------------------------------------------------
function VaRGaugeRow({ varData }) {
  const v = varData || {};
  const gauges = [
    { label: 'Parametric 95%', value: v.parametric_95, limit: v.limit_95_pct || 2.0 },
    { label: 'Parametric 99%', value: v.parametric_99, limit: v.limit_99_pct || 3.0 },
    { label: 'MC 95%', value: v.monte_carlo_95 || v.mc_95, limit: v.limit_95_pct || 2.0 },
    { label: 'MC 99%', value: v.monte_carlo_99 || v.mc_99, limit: v.limit_99_pct || 3.0 },
  ];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'row',
      gap: _S.sm,
      justifyContent: 'space-around',
      alignItems: 'flex-start',
      flexWrap: 'wrap',
    }}>
      {gauges.map((g, idx) => (
        <VaRGauge key={idx} label={g.label} value={g.value} limitValue={g.limit} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StressTestBars -- Recharts horizontal BarChart
// ---------------------------------------------------------------------------
function StressTestBars({ stressTests }) {
  const sortedData = useMemo(() => {
    if (!stressTests || stressTests.length === 0) return [];
    return [...stressTests]
      .sort((a, b) => (a.impact_brl || a.pnl || 0) - (b.impact_brl || b.pnl || 0));
  }, [stressTests]);

  if (sortedData.length === 0) {
    return (
      <div style={{ color: _C.text.muted, fontSize: _T.sizes.sm, textAlign: 'center', padding: '32px 0', fontFamily: _T.fontFamily }}>
        No stress test data available
      </div>
    );
  }

  const getBarColor = (value) => {
    const pct = value != null ? value : 0;
    if (pct > 0) return _C.pnl.positive;
    if (pct > -5) return _C.risk.warning;
    return _C.risk.breach;
  };

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart
        data={sortedData}
        layout="vertical"
        margin={{ left: 10, right: 10, top: 5, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={_C.border.subtle} horizontal={false} />
        <XAxis
          type="number"
          stroke={_C.text.muted}
          tick={{ fontSize: 9, fontFamily: _T.fontFamily, fill: _C.text.muted }}
          tickFormatter={(v) => formatPnLShort(v)}
        />
        <YAxis
          type="category"
          dataKey="scenario"
          stroke={_C.text.muted}
          tick={{ fontSize: 8, fontFamily: _T.fontFamily, fill: _C.text.secondary }}
          width={95}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          labelStyle={{ color: _C.text.secondary }}
          formatter={(val) => [formatPnLShort(val), 'Impact']}
        />
        <Bar dataKey="impact_brl" name="Impact BRL">
          {sortedData.map((entry, index) => (
            <Cell key={index} fill={getBarColor(entry.impact_pct)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// LimitUtilizationBars -- custom div-based bars with click-to-expand
// ---------------------------------------------------------------------------
function LimitUtilizationBars({ limitsData, limitConfig }) {
  const [expandedIdx, setExpandedIdx] = useState(null);

  const items = useMemo(() => {
    if (limitsData && limitsData.items && limitsData.items.length > 0) {
      return limitsData.items;
    }
    return [];
  }, [limitsData]);

  if (items.length === 0) {
    return (
      <div style={{ color: _C.text.muted, fontSize: _T.sizes.sm, textAlign: 'center', padding: '32px 0', fontFamily: _T.fontFamily }}>
        No limit data available
      </div>
    );
  }

  const getSeverityColor = (severity, utilization) => {
    if (severity === 'BREACH' || utilization >= 100) return _C.risk.breach;
    if (severity === 'WARNING' || utilization >= 80) return _C.risk.warning;
    return _C.risk.ok;
  };

  const handleClick = (idx) => {
    setExpandedIdx(prev => prev === idx ? null : idx);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {items.map((item, idx) => {
        const utilization = item.utilization || 0;
        const severity = item.severity || 'OK';
        const barColor = getSeverityColor(severity, utilization);
        const isExpanded = expandedIdx === idx;
        const isBreach = severity === 'BREACH' || utilization >= 100;
        const barWidth = Math.min(100, utilization);

        return (
          <div key={idx}>
            <div
              style={{
                cursor: 'pointer',
                padding: '4px 0',
                userSelect: 'none',
              }}
              onClick={() => handleClick(idx)}
            >
              {/* Label row */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '3px',
              }}>
                <span style={{
                  fontSize: _T.sizes.xs,
                  color: _C.text.secondary,
                  fontFamily: _T.fontFamily,
                  fontWeight: _T.weights.medium,
                }}>
                  {item.name}
                </span>
                <span style={{
                  fontSize: _T.sizes.xs,
                  color: barColor,
                  fontFamily: _T.fontFamily,
                  fontWeight: _T.weights.semibold,
                }}>
                  {utilization.toFixed(1)}%
                </span>
              </div>
              {/* Bar track */}
              <div style={{
                width: '100%',
                height: '6px',
                backgroundColor: _C.bg.tertiary,
                borderRadius: '3px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: barWidth + '%',
                  height: '100%',
                  backgroundColor: barColor,
                  borderRadius: '3px',
                  transition: 'width 0.3s ease',
                  animation: isBreach ? 'pulse-breach 1.5s ease-in-out 3' : 'none',
                }} />
              </div>
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div style={{
                backgroundColor: _C.bg.tertiary,
                borderRadius: '4px',
                padding: '8px 10px',
                marginTop: '4px',
                fontFamily: _T.fontFamily,
                fontSize: _T.sizes.xs,
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
                  <div>
                    <span style={{ color: _C.text.muted }}>Limit Name: </span>
                    <span style={{ color: _C.text.primary }}>{item.name}</span>
                  </div>
                  <div>
                    <span style={{ color: _C.text.muted }}>Current Value: </span>
                    <span style={{ color: _C.text.primary }}>{_formatNumber(item.current, 2)}</span>
                  </div>
                  <div>
                    <span style={{ color: _C.text.muted }}>Threshold: </span>
                    <span style={{ color: _C.text.primary }}>{_formatNumber(item.limit, 2)}</span>
                  </div>
                  <div>
                    <span style={{ color: _C.text.muted }}>Utilization: </span>
                    <span style={{ color: barColor, fontWeight: _T.weights.semibold }}>{utilization.toFixed(1)}%</span>
                  </div>
                  <div>
                    <span style={{ color: _C.text.muted }}>Last OK: </span>
                    <span style={{ color: _C.text.secondary }}>{item.last_ok || '--'}</span>
                  </div>
                  <div>
                    <span style={{ color: _C.text.muted }}>Trend: </span>
                    <span style={{
                      color: (item.previous != null && item.current > item.previous) ? _C.risk.breach : _C.risk.ok,
                    }}>
                      {item.previous != null
                        ? (item.current > item.previous ? 'Worsening' : 'Improving')
                        : '--'}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ConcentrationPie -- Recharts PieChart (donut)
// ---------------------------------------------------------------------------
function ConcentrationPie({ concentration }) {
  const data = useMemo(() => {
    if (!concentration) return [];
    return Object.entries(concentration).map(([name, value]) => ({
      name,
      value: typeof value === 'number' ? Math.round(value * 10) / 10 : 0,
    }));
  }, [concentration]);

  if (data.length === 0) {
    return (
      <div style={{ color: _C.text.muted, fontSize: _T.sizes.sm, textAlign: 'center', padding: '32px 0', fontFamily: _T.fontFamily }}>
        No concentration data available
      </div>
    );
  }

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="45%"
          innerRadius={45}
          outerRadius={75}
          paddingAngle={2}
          dataKey="value"
          nameKey="name"
          label={({ name, value }) => name + ' ' + value + '%'}
          labelLine={{ stroke: _C.text.muted }}
        >
          {data.map((entry, index) => (
            <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(val) => [val + '%', 'Allocation']}
        />
        <Legend
          wrapperStyle={{
            color: _C.text.secondary,
            fontSize: _T.sizes.xs,
            fontFamily: _T.fontFamily,
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// HistoricalVaRChart -- full-width time-series below 4-quadrant grid
// ---------------------------------------------------------------------------
function HistoricalVaRChart({ trendData, limitsConfig }) {
  const [window_, setWindow] = useState(90);

  const windowOptions = [
    { label: '30d', value: 30 },
    { label: '60d', value: 60 },
    { label: '90d', value: 90 },
    { label: '1Y', value: 365 },
  ];

  const filteredData = useMemo(() => {
    if (!trendData || trendData.length === 0) return [];
    const cutoff = trendData.length - window_;
    return cutoff > 0 ? trendData.slice(cutoff) : trendData;
  }, [trendData, window_]);

  const limit95 = (limitsConfig && limitsConfig.var_95_limit) || 2.0;
  const limit99 = (limitsConfig && limitsConfig.var_99_limit) || 3.0;

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

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

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={titleStyle}>Historical VaR Trend</div>
        <div style={buttonContainerStyle}>
          {windowOptions.map(opt => (
            <button
              key={opt.value}
              style={rangeButtonStyle(opt.value === window_)}
              onClick={() => setWindow(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      {filteredData.length > 0 ? (
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={filteredData}>
            <CartesianGrid strokeDasharray="3 3" stroke={_C.border.subtle} />
            <XAxis
              dataKey="date"
              stroke={_C.text.muted}
              tick={{ fontSize: 8, fontFamily: _T.fontFamily }}
              interval={Math.max(1, Math.floor(filteredData.length / 8))}
            />
            <YAxis
              stroke={_C.text.muted}
              tick={{ fontSize: 9, fontFamily: _T.fontFamily }}
              tickFormatter={(v) => v.toFixed(1) + '%'}
              domain={[0, 'auto']}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: _C.text.secondary }}
              formatter={(value, name) => [value.toFixed(2) + '%', name]}
            />
            <Line
              type="monotone"
              dataKey="var_95"
              stroke="#58a6ff"
              strokeWidth={1.5}
              dot={false}
              name="VaR 95%"
            />
            <Line
              type="monotone"
              dataKey="var_99"
              stroke="#a371f7"
              strokeWidth={1.5}
              dot={false}
              name="VaR 99%"
            />
            <ReferenceLine
              y={limit95}
              stroke="#58a6ff"
              strokeDasharray="5 3"
              strokeWidth={1}
              label={{ value: 'Limit 95%', position: 'right', fill: _C.text.muted, fontSize: 9 }}
            />
            <ReferenceLine
              y={limit99}
              stroke="#a371f7"
              strokeDasharray="5 3"
              strokeWidth={1}
              label={{ value: 'Limit 99%', position: 'right', fill: _C.text.muted, fontSize: 9 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <div style={{ color: _C.text.muted, fontSize: _T.sizes.sm, textAlign: 'center', padding: '32px 0', fontFamily: _T.fontFamily }}>
          No trend data available
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RiskMonitorSkeleton -- loading state
// ---------------------------------------------------------------------------
function RiskMonitorSkeleton() {
  return (
    <div style={{ fontFamily: _T.fontFamily }}>
      {/* Alert bar skeleton */}
      <window.PMSSkeleton width="100%" height="32px" />
      {/* 4-quadrant skeleton */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: _S.md, marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="240px" />
        <window.PMSSkeleton width="100%" height="240px" />
        <window.PMSSkeleton width="100%" height="260px" />
        <window.PMSSkeleton width="100%" height="260px" />
      </div>
      {/* Historical chart skeleton */}
      <div style={{ marginTop: _S.md }}>
        <window.PMSSkeleton width="100%" height="200px" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main RiskMonitorPage Component
// ---------------------------------------------------------------------------
function RiskMonitorPage() {
  // Fetch live risk snapshot (30s polling)
  const riskLive = window.useFetch('/api/v1/pms/risk/live', 30000);
  // Fetch trend data (60s polling)
  const riskTrend = window.useFetch('/api/v1/pms/risk/trend?days=90', 60000);
  // Fetch limits config (60s polling)
  const riskLimits = window.useFetch('/api/v1/pms/risk/limits', 60000);

  const isLoading = riskLive.loading && riskTrend.loading && riskLimits.loading;

  // Resolve data with sample fallback
  const risk = useMemo(() => {
    const d = riskLive.data;
    if (d && d.var) return d;
    return SAMPLE_RISK_LIVE;
  }, [riskLive.data]);

  const trend = useMemo(() => {
    const d = riskTrend.data;
    if (d && Array.isArray(d) && d.length > 0) return d;
    return SAMPLE_RISK_TREND;
  }, [riskTrend.data]);

  const limits = useMemo(() => {
    const d = riskLimits.data;
    if (d && d.config) return d;
    return SAMPLE_LIMITS;
  }, [riskLimits.data]);

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

  // Card wrapper style for quadrants
  const quadrantCardStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '10px 12px',
  };

  const quadrantTitleStyle = {
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
      {/* Page header */}
      <div style={{ marginBottom: _S.md }}>
        <div style={titleStyle}>Risk Monitor</div>
        <div style={subtitleStyle}>
          {risk.as_of_date || today} | Updated {new Date().toLocaleTimeString()}
        </div>
      </div>

      {isLoading ? (
        <RiskMonitorSkeleton />
      ) : (
        <React.Fragment>
          {/* Alert Summary Bar */}
          <AlertSummaryBar alerts={risk.alerts} />

          {/* 4-Quadrant Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: _S.md,
          }}>
            {/* Top-Left: VaR Gauges */}
            <div style={quadrantCardStyle}>
              <div style={quadrantTitleStyle}>Value at Risk</div>
              <VaRGaugeRow varData={risk.var} />
            </div>

            {/* Top-Right: Stress Test Bars */}
            <div style={quadrantCardStyle}>
              <div style={quadrantTitleStyle}>Stress Test Scenarios</div>
              <StressTestBars stressTests={risk.stress_tests} />
            </div>

            {/* Bottom-Left: Limit Utilization */}
            <div style={quadrantCardStyle}>
              <div style={quadrantTitleStyle}>Risk Limit Utilization</div>
              <LimitUtilizationBars
                limitsData={risk.limits_summary}
                limitConfig={limits.config}
              />
            </div>

            {/* Bottom-Right: Concentration Pie Chart */}
            <div style={quadrantCardStyle}>
              <div style={quadrantTitleStyle}>Asset Class Concentration</div>
              <ConcentrationPie concentration={risk.concentration} />
            </div>
          </div>

          {/* Historical VaR Chart */}
          <HistoricalVaRChart
            trendData={trend}
            limitsConfig={limits.config}
          />
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.RiskMonitorPage = RiskMonitorPage;

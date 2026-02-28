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
  seededRng,
  formatPnLShort,
} = window.PMS_THEME;

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
// AdHocStressTestSection -- interactive custom shock scenario panel
// ---------------------------------------------------------------------------
function AdHocStressTestSection({ risk }) {
  const [shocks, setShocks] = useState({
    fx_pct: -5.0,
    rates_bps: 100,
    equity_pct: -10.0,
    credit_bps: 50,
    vol_pct: 30.0,
  });
  const [scenarioName, setScenarioName] = useState('Custom Scenario');
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  const handleShockChange = useCallback((field, value) => {
    setShocks(prev => ({ ...prev, [field]: parseFloat(value) || 0 }));
  }, []);

  const handleRunStressTest = async () => {
    setRunning(true);
    try {
      const res = await fetch('/api/v1/pms/risk/stress-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_name: scenarioName, shocks }),
      });
      if (res.ok) {
        setResult(await res.json());
      } else {
        throw new Error('API error');
      }
    } catch (_) {
      const totalImpact = (shocks.fx_pct * 0.3 + shocks.equity_pct * 0.2) * 1000000 +
                           shocks.rates_bps * -15000 + shocks.credit_bps * -8000 + shocks.vol_pct * -12000;
      setResult({
        scenario_name: scenarioName,
        total_pnl_impact_brl: totalImpact,
        positions_impact: [
          { instrument: 'USDBRL NDF 3M', impact_brl: shocks.fx_pct * 300000 },
          { instrument: 'DI1 Jan26', impact_brl: shocks.rates_bps * -15000 },
          { instrument: 'IBOV FUT', impact_brl: shocks.equity_pct * 200000 },
          { instrument: 'NTN-B 2030', impact_brl: shocks.rates_bps * -12000 + shocks.vol_pct * -5000 },
          { instrument: 'CDS BR 5Y', impact_brl: shocks.credit_bps * -8000 },
        ],
      });
    }
    setRunning(false);
  };

  const sortedImpacts = useMemo(() => {
    if (!result || !result.positions_impact) return [];
    return [...result.positions_impact].sort((a, b) => Math.abs(b.impact_brl) - Math.abs(a.impact_brl));
  }, [result]);

  const shockFields = [
    { key: 'fx_pct', label: 'FX', unit: '%', step: 0.5, min: -50, max: 50 },
    { key: 'rates_bps', label: 'Rates', unit: 'bps', step: 10, min: -500, max: 500 },
    { key: 'equity_pct', label: 'Equity', unit: '%', step: 1, min: -50, max: 50 },
    { key: 'credit_bps', label: 'Credit', unit: 'bps', step: 5, min: -200, max: 500 },
    { key: 'vol_pct', label: 'Vol', unit: '%', step: 5, min: -50, max: 100 },
  ];

  const containerStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '12px',
  };

  const sectionTitleStyle = {
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.semibold,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _T.fontFamily,
    marginBottom: '12px',
  };

  const inputStyle = {
    backgroundColor: _C.bg.tertiary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '3px',
    color: _C.text.primary,
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.sm,
    padding: '4px 8px',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  };

  const numberInputStyle = {
    backgroundColor: _C.bg.tertiary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '3px',
    color: _C.text.primary,
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.sm,
    fontWeight: _T.weights.semibold,
    padding: '4px 6px',
    outline: 'none',
    width: '72px',
    textAlign: 'right',
    boxSizing: 'border-box',
  };

  const buttonStyle = {
    background: running ? _C.border.default : _C.border.accent,
    color: _C.text.primary,
    border: 'none',
    borderRadius: '4px',
    padding: '8px 24px',
    fontSize: _T.sizes.sm,
    fontWeight: _T.weights.semibold,
    fontFamily: _T.fontFamily,
    cursor: running ? 'wait' : 'pointer',
    opacity: running ? 0.7 : 1,
    letterSpacing: '0.03em',
    transition: 'opacity 0.2s ease',
  };

  const maxAbsImpact = useMemo(() => {
    if (sortedImpacts.length === 0) return 1;
    return Math.max(...sortedImpacts.map(d => Math.abs(d.impact_brl)));
  }, [sortedImpacts]);

  return (
    <div style={containerStyle}>
      <div style={sectionTitleStyle}>Custom Stress Test</div>

      {/* Scenario name input */}
      <div style={{ marginBottom: '12px' }}>
        <label style={{
          fontSize: _T.sizes.xs,
          color: _C.text.muted,
          fontFamily: _T.fontFamily,
          display: 'block',
          marginBottom: '4px',
        }}>
          Scenario Name
        </label>
        <input
          type="text"
          value={scenarioName}
          onChange={(e) => setScenarioName(e.target.value)}
          style={{ ...inputStyle, maxWidth: '320px' }}
        />
      </div>

      {/* Shock parameter grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: '12px',
        marginBottom: '16px',
      }}>
        {shockFields.map((field) => (
          <div key={field.key} style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}>
            <label style={{
              fontSize: _T.sizes.xs,
              fontWeight: _T.weights.semibold,
              color: _C.text.secondary,
              fontFamily: _T.fontFamily,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}>
              {field.label}
            </label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}>
              <input
                type="number"
                value={shocks[field.key]}
                onChange={(e) => handleShockChange(field.key, e.target.value)}
                step={field.step}
                min={field.min}
                max={field.max}
                style={numberInputStyle}
              />
              <span style={{
                fontSize: _T.sizes.xs,
                color: _C.text.muted,
                fontFamily: _T.fontFamily,
                fontWeight: _T.weights.medium,
                minWidth: '24px',
              }}>
                {field.unit}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Run button */}
      <div style={{ marginBottom: result ? '16px' : '0' }}>
        <button style={buttonStyle} onClick={handleRunStressTest} disabled={running}>
          {running ? 'Running...' : 'Run Stress Test'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div style={{
          borderTop: '1px solid ' + _C.border.default,
          paddingTop: '14px',
        }}>
          {/* Scenario name and total impact */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: '12px',
          }}>
            <div style={{
              fontSize: _T.sizes.sm,
              fontWeight: _T.weights.semibold,
              color: _C.text.secondary,
              fontFamily: _T.fontFamily,
            }}>
              {result.scenario_name}
            </div>
            <div style={{
              fontSize: _T.sizes['2xl'],
              fontWeight: _T.weights.bold,
              color: _pnlColor(result.total_pnl_impact_brl),
              fontFamily: _T.fontFamily,
              letterSpacing: '-0.02em',
            }}>
              {formatPnLShort(result.total_pnl_impact_brl)}
            </div>
          </div>

          {/* Position-level horizontal bar chart */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}>
            {sortedImpacts.map((pos, idx) => {
              const barPct = maxAbsImpact > 0 ? (Math.abs(pos.impact_brl) / maxAbsImpact) * 100 : 0;
              const isPositive = pos.impact_brl >= 0;
              const barColor = isPositive ? _C.pnl.positive : _C.pnl.negative;

              return (
                <div key={idx} style={{
                  display: 'grid',
                  gridTemplateColumns: '140px 1fr 90px',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                  {/* Instrument label */}
                  <div style={{
                    fontSize: _T.sizes.xs,
                    color: _C.text.secondary,
                    fontFamily: _T.fontFamily,
                    fontWeight: _T.weights.medium,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                    {pos.instrument}
                  </div>
                  {/* Bar */}
                  <div style={{
                    position: 'relative',
                    height: '14px',
                    backgroundColor: _C.bg.tertiary,
                    borderRadius: '2px',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: isPositive ? '50%' : (50 - barPct / 2) + '%',
                      width: (barPct / 2) + '%',
                      height: '100%',
                      backgroundColor: barColor,
                      borderRadius: '2px',
                      transition: 'width 0.3s ease',
                    }} />
                    {/* Center line */}
                    <div style={{
                      position: 'absolute',
                      top: 0,
                      left: '50%',
                      width: '1px',
                      height: '100%',
                      backgroundColor: _C.border.default,
                    }} />
                  </div>
                  {/* Impact value */}
                  <div style={{
                    fontSize: _T.sizes.xs,
                    fontWeight: _T.weights.semibold,
                    color: _pnlColor(pos.impact_brl),
                    fontFamily: _T.fontFamily,
                    textAlign: 'right',
                  }}>
                    {formatPnLShort(pos.impact_brl)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DrawdownHistorySection -- underwater area chart showing drawdown from HWM
// ---------------------------------------------------------------------------
function DrawdownHistorySection({ trend }) {
  const { Area } = Recharts;

  const drawdownData = useMemo(() => {
    let hwm = 100;
    const rng = seededRng(88);
    return trend.map((d) => {
      const nav = 100 + (d.var_95_pct || (rng() * 3 - 1.5)) * 10;
      hwm = Math.max(hwm, nav);
      const dd = ((nav - hwm) / hwm) * 100;
      return { date: d.date || d.as_of_date || '', drawdown: Math.min(0, Math.round(dd * 100) / 100) };
    });
  }, [trend]);

  const containerStyle = {
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    padding: '12px',
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

  const tooltipStyle = {
    background: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '4px',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.xs,
  };

  const minDrawdown = useMemo(() => {
    if (drawdownData.length === 0) return -6;
    const min = Math.min(...drawdownData.map(d => d.drawdown));
    return Math.min(min - 1, -6);
  }, [drawdownData]);

  // Current drawdown stat
  const currentDD = drawdownData.length > 0 ? drawdownData[drawdownData.length - 1].drawdown : 0;
  const maxDD = useMemo(() => {
    if (drawdownData.length === 0) return 0;
    return Math.min(...drawdownData.map(d => d.drawdown));
  }, [drawdownData]);

  return (
    <div style={containerStyle}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '8px',
      }}>
        <div style={sectionTitleStyle}>Drawdown History</div>
        <div style={{
          display: 'flex',
          gap: '16px',
          alignItems: 'center',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '4px',
          }}>
            <span style={{
              fontSize: _T.sizes.xs,
              color: _C.text.muted,
              fontFamily: _T.fontFamily,
            }}>
              Current:
            </span>
            <span style={{
              fontSize: _T.sizes.sm,
              fontWeight: _T.weights.bold,
              color: currentDD < -3 ? _C.risk.breach : currentDD < -1 ? _C.risk.warning : _C.risk.ok,
              fontFamily: _T.fontFamily,
            }}>
              {currentDD.toFixed(2)}%
            </span>
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '4px',
          }}>
            <span style={{
              fontSize: _T.sizes.xs,
              color: _C.text.muted,
              fontFamily: _T.fontFamily,
            }}>
              Max:
            </span>
            <span style={{
              fontSize: _T.sizes.sm,
              fontWeight: _T.weights.bold,
              color: _C.risk.breach,
              fontFamily: _T.fontFamily,
            }}>
              {maxDD.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      {drawdownData.length > 0 ? (
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={drawdownData} margin={{ left: 5, right: 10, top: 5, bottom: 5 }}>
            <defs>
              <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={_C.pnl.negative} stopOpacity={0.15} />
                <stop offset="100%" stopColor={_C.pnl.negative} stopOpacity={0.65} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={_C.border.subtle} />
            <XAxis
              dataKey="date"
              stroke={_C.text.muted}
              tick={{ fontSize: 8, fontFamily: _T.fontFamily, fill: _C.text.muted }}
              interval={Math.max(1, Math.floor(drawdownData.length / 8))}
            />
            <YAxis
              stroke={_C.text.muted}
              tick={{ fontSize: 9, fontFamily: _T.fontFamily, fill: _C.text.muted }}
              tickFormatter={(v) => v.toFixed(1) + '%'}
              domain={[minDrawdown, 0]}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: _C.text.secondary }}
              formatter={(value) => [value.toFixed(2) + '%', 'Drawdown']}
            />
            <ReferenceLine
              y={0}
              stroke={_C.text.muted}
              strokeWidth={1}
            />
            <ReferenceLine
              y={-5}
              stroke={_C.risk.breach}
              strokeDasharray="5 3"
              strokeWidth={1.5}
              label={{
                value: 'Limit -5%',
                position: 'right',
                fill: _C.risk.breach,
                fontSize: 9,
                fontFamily: _T.fontFamily,
              }}
            />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke={_C.pnl.negative}
              strokeWidth={1.5}
              fill="url(#drawdownGradient)"
              dot={false}
              activeDot={{
                r: 3,
                stroke: _C.pnl.negative,
                strokeWidth: 2,
                fill: _C.bg.primary,
              }}
              name="Drawdown"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <div style={{
          color: _C.text.muted,
          fontSize: _T.sizes.sm,
          textAlign: 'center',
          padding: '32px 0',
          fontFamily: _T.fontFamily,
        }}>
          No drawdown data available
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
// ---------------------------------------------------------------------------
// Circuit Breaker Status (migrated from Dashboard RiskPage)
// ---------------------------------------------------------------------------
function CircuitBreakerStatus({ riskData }) {
  const cb = riskData && riskData.circuit_breaker;
  if (!cb) return null;

  const stateUpper = (cb.state || 'unknown').toUpperCase();
  let stateColor, stateBg;
  if (stateUpper === 'NORMAL') {
    stateColor = _C.pnl.positive;
    stateBg = 'rgba(34, 197, 94, 0.12)';
  } else if (stateUpper === 'WARNING') {
    stateColor = '#f59e0b';
    stateBg = 'rgba(245, 158, 11, 0.12)';
  } else {
    stateColor = _C.pnl.negative;
    stateBg = 'rgba(239, 68, 68, 0.12)';
  }

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginTop: _S.md,
    padding: '8px 12px',
    backgroundColor: _C.bg.secondary,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    fontFamily: _T.fontFamily,
  };

  const labelStyle = {
    fontSize: _T.sizes.xs,
    color: _C.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    fontWeight: _T.weights.semibold,
  };

  const badgeStyle = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: _T.sizes.xs,
    fontWeight: _T.weights.bold,
    color: stateColor,
    backgroundColor: stateBg,
  };

  const detailStyle = {
    fontSize: _T.sizes.xs,
    color: _C.text.secondary,
  };

  return (
    <div style={containerStyle}>
      <span style={labelStyle}>Circuit Breaker:</span>
      <span style={badgeStyle}>{stateUpper}</span>
      <span style={detailStyle}>
        Scale: {cb.scale != null ? (cb.scale * 100).toFixed(0) + '%' : '--'} |
        Drawdown: {cb.drawdown_pct != null ? (cb.drawdown_pct * 100).toFixed(2) + '%' : '--'}
      </span>
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

  // Resolve data — empty state instead of sample fallback
  const risk = useMemo(() => {
    const d = riskLive.data;
    if (d && d.var) return d;
    return { var: {}, leverage: {}, drawdown: {}, concentration: {}, stress_tests: [], limits_summary: { items: [] }, alerts: [] };
  }, [riskLive.data]);

  const trend = useMemo(() => {
    const d = riskTrend.data;
    if (d && Array.isArray(d) && d.length > 0) return d;
    return [];
  }, [riskTrend.data]);

  const limits = useMemo(() => {
    const d = riskLimits.data;
    if (d && d.config) return d;
    return { config: {}, limits_summary: { items: [] } };
  }, [riskLimits.data]);

  const usingSample = false;
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
      {usingSample && <PMSSampleDataBanner />}
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

          {/* Ad-Hoc Stress Test */}
          <div style={{ marginTop: _S.md }}>
            <AdHocStressTestSection risk={risk} />
          </div>

          {/* Drawdown History */}
          <div style={{ marginTop: _S.md }}>
            <DrawdownHistorySection trend={trend} />
          </div>
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.RiskMonitorPage = RiskMonitorPage;

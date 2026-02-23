/**
 * RiskPage.jsx - Dense single-view risk dashboard.
 *
 * Features:
 * - SVG gauge widgets for VaR 95%, VaR 99%, CVaR
 * - Stress test horizontal bar chart (Recharts BarChart)
 * - Limits status panel with utilization percentages
 * - Concentration pie chart (Recharts PieChart)
 * - All data from /api/v1/risk/dashboard, /api/v1/risk/stress, /api/v1/risk/limits
 */

const { useState, useMemo } = React;
const { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
        PieChart, Pie, Cell, Legend } = Recharts;

// Color constants
const PIE_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316"];

// ---------------------------------------------------------------------------
// GaugeChart — Semi-circular SVG arc with value in center
// ---------------------------------------------------------------------------
function GaugeChart({ label, value, maxValue, format }) {
  const pct = Math.min(1.0, Math.max(0, Math.abs(value || 0) / (maxValue || 0.1)));

  // Color by severity
  let color = "#22c55e"; // green
  if (pct >= 0.5) color = "#f59e0b"; // amber
  if (pct >= 0.8) color = "#ef4444"; // red

  // SVG arc math
  const cx = 60, cy = 55, r = 40;
  const startAngle = Math.PI;
  const endAngle = Math.PI + Math.PI * pct;

  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy + r * Math.sin(endAngle);
  const largeArc = pct > 0.5 ? 1 : 0;

  // Background arc (full semi-circle)
  const bgX2 = cx + r * Math.cos(Math.PI * 2);
  const bgY2 = cy + r * Math.sin(Math.PI * 2);

  const displayValue = format === "pct"
    ? (Math.abs(value || 0) * 100).toFixed(2) + "%"
    : (value || 0).toFixed(4);

  return (
    <div className="bg-gray-800 rounded-lg p-4 text-center">
      <div className="text-gray-500 text-xs uppercase mb-1">{label}</div>
      <svg width="120" height="75" viewBox="0 0 120 75" className="mx-auto">
        {/* Background arc */}
        <path
          d={"M " + x1 + " " + y1 + " A " + r + " " + r + " 0 1 1 " + bgX2 + " " + bgY2}
          fill="none"
          stroke="#2a2a3a"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Value arc */}
        {pct > 0 && (
          <path
            d={"M " + x1 + " " + y1 + " A " + r + " " + r + " 0 " + largeArc + " 1 " + x2 + " " + y2}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
          />
        )}
        {/* Value text */}
        <text x={cx} y={cy - 2} textAnchor="middle" fill={color} fontSize="12" fontWeight="bold" fontFamily="monospace">
          {displayValue}
        </text>
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge for limits
// ---------------------------------------------------------------------------
function StatusBadge({ breached, utilization }) {
  if (breached) {
    return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-500/20 text-red-400">BREACH</span>;
  }
  if (utilization > 80) {
    return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-400">WARN</span>;
  }
  return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-green-500/20 text-green-400">OK</span>;
}

function RiskPage() {
  const { data: dashData, loading: dashLoading, error: dashError } = useFetch("/api/v1/risk/dashboard", 30000);
  const { data: stressData, loading: stressLoading, error: stressError } = useFetch("/api/v1/risk/stress", 30000);
  const { data: limitsData, loading: limitsLoading, error: limitsError } = useFetch("/api/v1/risk/limits", 30000);

  // Parse dashboard data
  const dashboard = dashData && dashData.data ? dashData.data : {};
  const varResults = dashboard.var || {};

  // Pick the first available method for gauges (prefer historical)
  const primaryVar = varResults.historical || varResults.parametric || Object.values(varResults)[0] || {};

  // Parse stress data
  const stressScenarios = useMemo(() => {
    const raw = stressData && stressData.data && stressData.data.scenarios ? stressData.data.scenarios : [];
    return raw.map((s) => ({
      name: s.scenario_name || "Unknown",
      pnl: s.portfolio_pnl || 0,
      pnl_pct: s.portfolio_pnl_pct || 0,
    })).sort((a, b) => a.pnl - b.pnl);
  }, [stressData]);

  // Parse limits data
  const limits = useMemo(() => {
    const raw = limitsData && limitsData.data ? limitsData.data : {};
    return {
      items: raw.limits || [],
      overall: raw.overall_status || "UNKNOWN",
      lossStatus: raw.loss_status || null,
      riskBudget: raw.risk_budget || null,
    };
  }, [limitsData]);

  // Concentration data from dashboard positions
  const concentrationData = useMemo(() => {
    // Build from stress test positions if available, or use defaults
    const positions = dashboard.positions || {
      FX: 0.20,
      Rates: 0.30,
      Inflation: 0.15,
      Equity: 0.25,
      "Cross-Asset": 0.10,
    };
    return Object.entries(positions).map(([name, value]) => ({
      name,
      value: Math.round(Math.abs(value) * 100),
    }));
  }, [dashboard]);

  const hasError = dashError || stressError || limitsError;
  const isLoading = dashLoading && stressLoading && limitsLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Risk Dashboard</h1>
        {dashboard.overall_risk_level && (
          <span className={`px-3 py-1 rounded-lg text-sm font-semibold ${
            dashboard.overall_risk_level === "LOW" ? "bg-green-500/20 text-green-400" :
            dashboard.overall_risk_level === "MEDIUM" ? "bg-amber-500/20 text-amber-400" :
            "bg-red-500/20 text-red-400"
          }`}>
            Risk Level: {dashboard.overall_risk_level}
          </span>
        )}
      </div>

      {/* Error banner */}
      {hasError && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 text-red-300 text-sm">
          Error loading risk data: {dashError || stressError || limitsError}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-3 gap-4 mb-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton bg-gray-800 h-24 rounded-lg"></div>
          ))}
        </div>
      )}

      {/* Top row: VaR gauges */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <GaugeChart label="VaR 95%" value={primaryVar.var_95} maxValue={0.05} format="pct" />
        <GaugeChart label="VaR 99%" value={primaryVar.var_99} maxValue={0.05} format="pct" />
        <GaugeChart label="CVaR 95%" value={primaryVar.cvar_95} maxValue={0.08} format="pct" />
      </div>

      {/* Main 2-column grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Left column: Stress test bar chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Stress Test Scenarios</h2>
          {stressScenarios.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={stressScenarios} layout="vertical" margin={{ left: 20, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" horizontal={false} />
                <XAxis type="number" stroke="#6b7280" tick={{ fontSize: 10 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke="#6b7280"
                  tick={{ fontSize: 9 }}
                  width={100}
                />
                <Tooltip
                  contentStyle={{ background: "#1e1e2a", border: "1px solid #3a3a4a", borderRadius: "8px" }}
                  labelStyle={{ color: "#9ca3af" }}
                  formatter={(val) => ["$" + val.toLocaleString(), "P&L"]}
                />
                <Bar dataKey="pnl" name="P&L Impact">
                  {stressScenarios.map((entry, index) => (
                    <Cell key={index} fill={entry.pnl < 0 ? "#ef4444" : "#22c55e"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-gray-500 text-sm py-8 text-center">
              {stressLoading ? "Loading..." : "No stress test data available"}
            </div>
          )}
        </div>

        {/* Right column: Limits status panel */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-gray-300 text-sm font-semibold uppercase">Limit Status</h2>
            <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
              limits.overall === "OK" ? "bg-green-500/20 text-green-400" :
              limits.overall === "WARNING" ? "bg-amber-500/20 text-amber-400" :
              limits.overall === "BREACHED" ? "bg-red-500/20 text-red-400" :
              "bg-gray-600/30 text-gray-400"
            }`}>
              {limits.overall}
            </span>
          </div>
          {limits.items.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                  <th className="py-2 text-left">Limit</th>
                  <th className="py-2 text-right">Current</th>
                  <th className="py-2 text-right">Limit</th>
                  <th className="py-2 text-right">Util %</th>
                  <th className="py-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {limits.items.map((lim, idx) => (
                  <tr key={idx} className="border-b border-gray-800/50">
                    <td className="py-2 text-gray-300 text-xs">{lim.limit_name}</td>
                    <td className="py-2 text-right text-gray-300 font-mono text-xs">
                      {typeof lim.current_value === "number" ? lim.current_value.toFixed(4) : lim.current_value}
                    </td>
                    <td className="py-2 text-right text-gray-400 font-mono text-xs">
                      {typeof lim.limit_value === "number" ? lim.limit_value.toFixed(4) : lim.limit_value}
                    </td>
                    <td className="py-2 text-right font-mono text-xs">
                      <span className={
                        lim.utilization_pct >= 100 ? "text-red-400" :
                        lim.utilization_pct >= 80 ? "text-amber-400" :
                        "text-green-400"
                      }>
                        {lim.utilization_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 text-center">
                      <StatusBadge breached={lim.breached} utilization={lim.utilization_pct} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-gray-500 text-sm py-8 text-center">
              {limitsLoading ? "Loading..." : "No limit data available"}
            </div>
          )}

          {/* Risk budget summary */}
          {limits.riskBudget && (
            <div className="mt-3 pt-3 border-t border-gray-800">
              <div className="text-gray-500 text-xs uppercase mb-1">Risk Budget</div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Allocated: {(limits.riskBudget.allocated * 100).toFixed(1)}%</span>
                <span className="text-gray-400">Available: {(limits.riskBudget.available * 100).toFixed(1)}%</span>
                <span className={limits.riskBudget.utilization_pct > 80 ? "text-amber-400" : "text-green-400"}>
                  Util: {limits.riskBudget.utilization_pct.toFixed(1)}%
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom: Concentration pie chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Asset Class Concentration</h2>
        <div className="flex items-center justify-center">
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={concentrationData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                paddingAngle={2}
                dataKey="value"
                nameKey="name"
                label={({ name, value }) => name + " " + value + "%"}
              >
                {concentrationData.map((entry, index) => (
                  <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#1e1e2a", border: "1px solid #3a3a4a", borderRadius: "8px" }}
                formatter={(val) => [val + "%", "Allocation"]}
              />
              <Legend
                wrapperStyle={{ color: "#9ca3af", fontSize: "12px" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Circuit breaker status */}
      {dashboard.circuit_breaker && (
        <div className="mt-4 bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-4">
          <span className="text-gray-500 text-xs uppercase">Circuit Breaker:</span>
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
            dashboard.circuit_breaker.state === "normal" ? "bg-green-500/20 text-green-400" :
            dashboard.circuit_breaker.state === "warning" ? "bg-amber-500/20 text-amber-400" :
            "bg-red-500/20 text-red-400"
          }`}>
            {dashboard.circuit_breaker.state.toUpperCase()}
          </span>
          <span className="text-gray-400 text-xs">
            Scale: {(dashboard.circuit_breaker.scale * 100).toFixed(0)}% |
            Drawdown: {(dashboard.circuit_breaker.drawdown_pct * 100).toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.RiskPage = RiskPage;

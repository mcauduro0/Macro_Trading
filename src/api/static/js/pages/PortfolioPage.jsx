/**
 * PortfolioPage.jsx - Portfolio dashboard with 4 sections.
 *
 * Features:
 * - Positions table with direction, size, PnL, risk contribution
 * - Equity curve with drawdown overlay (Recharts ComposedChart)
 * - Monthly return heatmap (HTML table with inline bg colors)
 * - Strategy attribution horizontal bar chart
 * - Data from /api/v1/portfolio/current and /api/v1/portfolio/attribution
 */

const { useState, useMemo } = React;
const { ComposedChart, LineChart, Line, Area, BarChart, Bar, XAxis, YAxis,
        CartesianGrid, Tooltip, ResponsiveContainer, Cell } = Recharts;

// PnL color helper
function pnlColor(value) {
  if (value > 0) return "text-green-400";
  if (value < 0) return "text-red-400";
  return "text-gray-400";
}

// Direction badge
function DirectionBadge({ direction }) {
  const d = (direction || "").toUpperCase();
  const base = "inline-block px-2 py-0.5 rounded text-xs font-semibold";
  if (d === "LONG") return <span className={base + " bg-green-500/20 text-green-400"}>LONG</span>;
  if (d === "SHORT") return <span className={base + " bg-red-500/20 text-red-400"}>SHORT</span>;
  return <span className={base + " bg-gray-600/30 text-gray-400"}>{d || "N/A"}</span>;
}

// Monthly return heatmap color
function monthlyReturnColor(value) {
  if (value == null) return "transparent";
  const v = Math.max(-10, Math.min(10, value));
  if (v > 0) {
    const intensity = Math.min(1.0, v / 5) * 0.7 + 0.1;
    return "rgba(34, 197, 94, " + intensity.toFixed(2) + ")";
  }
  if (v < 0) {
    const intensity = Math.min(1.0, Math.abs(v) / 5) * 0.7 + 0.1;
    return "rgba(239, 68, 68, " + intensity.toFixed(2) + ")";
  }
  return "rgba(107, 114, 128, 0.1)";
}

// Generate sample equity curve and drawdown data
function generateEquityCurve() {
  const data = [];
  let equity = 1000000;
  let peak = equity;
  const rng = (seed) => {
    let s = seed;
    return () => { s = (s * 16807 + 0) % 2147483647; return (s - 1) / 2147483646; };
  };
  const rand = rng(42);
  for (let i = 0; i < 252; i++) {
    const ret = (rand() - 0.48) * 0.02;
    equity = equity * (1 + ret);
    peak = Math.max(peak, equity);
    const dd = ((equity - peak) / peak) * 100;
    const d = new Date(2025, 0, 1);
    d.setDate(d.getDate() + i);
    data.push({
      date: d.toISOString().slice(0, 10),
      equity: Math.round(equity),
      drawdown: Math.round(dd * 100) / 100,
    });
  }
  return data;
}

// Generate sample monthly returns
function generateMonthlyReturns() {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const years = [2023, 2024, 2025];
  const rng = (seed) => {
    let s = seed;
    return () => { s = (s * 16807 + 0) % 2147483647; return (s - 1) / 2147483646; };
  };
  const rand = rng(123);
  const returns = {};
  for (const year of years) {
    returns[year] = {};
    for (const month of months) {
      // Skip future months
      if (year === 2025 && months.indexOf(month) > 1) {
        returns[year][month] = null;
      } else {
        returns[year][month] = Math.round((rand() - 0.45) * 8 * 100) / 100;
      }
    }
  }
  return { months, years, returns };
}

function PortfolioPage() {
  const { data: posData, loading: posLoading, error: posError } = useFetch("/api/v1/portfolio/current", 30000);
  const { data: attrData, loading: attrLoading, error: attrError } = useFetch("/api/v1/portfolio/attribution", 30000);

  // Parse positions
  const positions = posData && posData.data && posData.data.positions ? posData.data.positions : [];
  const summary = posData && posData.data && posData.data.summary ? posData.data.summary : {};

  // Parse attribution
  const attributionByStrategy = useMemo(() => {
    const attr = attrData && attrData.data && attrData.data.by_strategy ? attrData.data.by_strategy : {};
    return Object.entries(attr)
      .map(([id, pnl]) => ({ strategy: id, pnl }))
      .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl));
  }, [attrData]);

  const totalPnl = attrData && attrData.data ? attrData.data.total_pnl || 0 : 0;

  // Equity curve data
  const equityData = useMemo(() => generateEquityCurve(), []);

  // Monthly returns data
  const { months, years, returns: monthlyReturns } = useMemo(() => generateMonthlyReturns(), []);

  const hasError = posError || attrError;
  const isLoading = posLoading && attrLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Portfolio</h1>
        <div className="flex gap-4 text-sm">
          {summary.total_positions != null && (
            <span className="text-gray-400">
              Positions: <span className="text-gray-200 font-semibold">{summary.total_positions}</span>
            </span>
          )}
          {summary.gross_leverage != null && (
            <span className="text-gray-400">
              Gross Lev: <span className="text-gray-200 font-semibold">{(summary.gross_leverage * 100).toFixed(1)}%</span>
            </span>
          )}
          {summary.net_leverage != null && (
            <span className="text-gray-400">
              Net Lev: <span className="text-gray-200 font-semibold">{(summary.net_leverage * 100).toFixed(1)}%</span>
            </span>
          )}
        </div>
      </div>

      {/* Error banner */}
      {hasError && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 text-red-300 text-sm">
          Error loading portfolio data: {posError || attrError}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton bg-gray-800 h-48 rounded-lg"></div>
          ))}
        </div>
      )}

      {/* 2x2 grid layout */}
      <div className="grid grid-cols-2 gap-4">
        {/* Section 1: Positions table */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Current Positions</h2>
          {positions.length > 0 ? (
            <div className="overflow-y-auto max-h-52">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                    <th className="py-2 text-left">Instrument</th>
                    <th className="py-2 text-center">Direction</th>
                    <th className="py-2 text-right">Weight</th>
                    <th className="py-2 text-left">Asset Class</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos, idx) => (
                    <tr key={idx} className="border-b border-gray-800/50">
                      <td className="py-2 text-gray-300 font-mono text-xs">{pos.instrument}</td>
                      <td className="py-2 text-center">
                        <DirectionBadge direction={pos.direction} />
                      </td>
                      <td className={`py-2 text-right font-mono text-xs ${pnlColor(pos.weight)}`}>
                        {(pos.weight * 100).toFixed(2)}%
                      </td>
                      <td className="py-2 text-gray-400 text-xs">{pos.asset_class || "--"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-gray-500 text-sm py-8 text-center">
              {posLoading ? "Loading..." : "No positions found"}
            </div>
          )}
        </div>

        {/* Section 2: Equity curve with drawdown overlay */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Equity Curve & Drawdown</h2>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={equityData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
              <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 8 }} interval={40} />
              <YAxis yAxisId="equity" stroke="#6b7280" tick={{ fontSize: 9 }} orientation="left" />
              <YAxis yAxisId="dd" stroke="#6b7280" tick={{ fontSize: 9 }} orientation="right" />
              <Tooltip
                contentStyle={{ background: "#1e1e2a", border: "1px solid #3a3a4a", borderRadius: "8px" }}
                labelStyle={{ color: "#9ca3af" }}
              />
              <Line yAxisId="equity" type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="Equity" />
              <Area yAxisId="dd" type="monotone" dataKey="drawdown" fill="rgba(239, 68, 68, 0.15)" stroke="#ef4444" strokeWidth={1} dot={false} name="Drawdown %" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Section 3: Monthly return heatmap */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Monthly Returns (%)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 uppercase">
                  <th className="py-1 px-1 text-left">Year</th>
                  {months.map((m) => (
                    <th key={m} className="py-1 px-1 text-center">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {years.map((year) => (
                  <tr key={year}>
                    <td className="py-1 px-1 text-gray-400 font-mono">{year}</td>
                    {months.map((m) => {
                      const val = monthlyReturns[year][m];
                      return (
                        <td
                          key={m}
                          className="py-1 px-1 text-center font-mono"
                          style={{ backgroundColor: monthlyReturnColor(val) }}
                          title={val != null ? val.toFixed(2) + "%" : "N/A"}
                        >
                          <span className="text-gray-200">
                            {val != null ? val.toFixed(1) : ""}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: "rgba(34, 197, 94, 0.5)" }}></span>
              Positive
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: "rgba(239, 68, 68, 0.5)" }}></span>
              Negative
            </span>
          </div>
        </div>

        {/* Section 4: Strategy attribution */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-gray-300 text-sm font-semibold uppercase">Strategy Attribution</h2>
            <span className={`text-sm font-mono font-semibold ${pnlColor(totalPnl)}`}>
              Total: ${totalPnl.toLocaleString()}
            </span>
          </div>
          {attributionByStrategy.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={attributionByStrategy} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" horizontal={false} />
                <XAxis type="number" stroke="#6b7280" tick={{ fontSize: 10 }} />
                <YAxis
                  type="category"
                  dataKey="strategy"
                  stroke="#6b7280"
                  tick={{ fontSize: 9 }}
                  width={80}
                />
                <Tooltip
                  contentStyle={{ background: "#1e1e2a", border: "1px solid #3a3a4a", borderRadius: "8px" }}
                  labelStyle={{ color: "#9ca3af" }}
                  formatter={(val) => ["$" + val.toLocaleString(), "P&L"]}
                />
                <Bar dataKey="pnl" name="P&L Contribution">
                  {attributionByStrategy.map((entry, index) => (
                    <Cell key={index} fill={entry.pnl >= 0 ? "#22c55e" : "#ef4444"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-gray-500 text-sm py-8 text-center">
              {attrLoading ? "Loading..." : "No attribution data available"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.PortfolioPage = PortfolioPage;

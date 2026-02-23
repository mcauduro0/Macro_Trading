/**
 * StrategiesPage.jsx - Strategy table with expandable backtest rows and asset class filters.
 *
 * Features:
 * - Fetches strategy list from /api/v1/strategies
 * - Asset class filter tabs: All, FX, Rates, Inflation, Cupom, Sovereign, Cross-Asset
 * - Table columns: Strategy ID, Asset Class, Current Signal, Sharpe, MaxDD
 * - Expandable rows with backtest metrics grid and equity curve (Recharts LineChart)
 * - Color-coded signals: green LONG, red SHORT, gray NEUTRAL
 * - Loading skeleton and error banner states
 */

const { useState, useEffect } = React;
const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } = Recharts;

// Asset class filter options
const ASSET_CLASS_FILTERS = ["All", "FX", "Rates", "Inflation", "Cupom", "Sovereign", "Cross-Asset"];

// Map asset class values from API to filter labels
function normalizeAssetClass(raw) {
  if (!raw) return "UNKNOWN";
  const upper = raw.toUpperCase();
  if (upper.includes("FX") || upper.includes("CURRENCY")) return "FX";
  if (upper.includes("RATE") || upper.includes("INTEREST")) return "Rates";
  if (upper.includes("INFLATION") || upper.includes("INF")) return "Inflation";
  if (upper.includes("CUPOM") || upper.includes("CIP")) return "Cupom";
  if (upper.includes("SOVEREIGN") || upper.includes("SOV")) return "Sovereign";
  if (upper.includes("CROSS")) return "Cross-Asset";
  return raw;
}

// Signal color helper
function signalColor(direction) {
  if (!direction) return "text-gray-400";
  const d = direction.toUpperCase();
  if (d === "LONG") return "text-green-500";
  if (d === "SHORT") return "text-red-500";
  return "text-gray-400";
}

function signalArrow(direction) {
  if (!direction) return "--";
  const d = direction.toUpperCase();
  if (d === "LONG") return "\u2191 LONG";
  if (d === "SHORT") return "\u2193 SHORT";
  return "\u2014 NEUTRAL";
}

// Skeleton loader row
function SkeletonRow() {
  return (
    <tr className="border-b border-gray-800">
      {[...Array(5)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="skeleton bg-gray-700 h-4 rounded w-3/4"></div>
        </td>
      ))}
    </tr>
  );
}

// Expanded backtest detail panel
function BacktestDetail({ strategyId }) {
  const { data, loading, error } = useFetch(
    "/api/v1/backtest/results?strategy_id=" + encodeURIComponent(strategyId),
    60000
  );

  if (loading) {
    return (
      <div className="p-4">
        <div className="skeleton bg-gray-700 h-32 rounded w-full"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-400 text-sm">
        Failed to load backtest data: {error}
      </div>
    );
  }

  const bt = data && data.data ? data.data : {};
  const equityCurve = (bt.equity_curve || []).map((val, idx) => ({
    day: idx,
    equity: val,
  }));

  return (
    <div className="p-4 space-y-4">
      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {[
          { label: "Ann. Ret", value: bt.annual_return != null ? (bt.annual_return * 100).toFixed(1) + "%" : "--" },
          { label: "Sharpe", value: bt.sharpe_ratio != null ? bt.sharpe_ratio.toFixed(2) : "--" },
          { label: "Sortino", value: bt.sortino_ratio != null ? bt.sortino_ratio.toFixed(2) : "--" },
          { label: "Max DD", value: bt.max_drawdown != null ? (bt.max_drawdown * 100).toFixed(1) + "%" : "--" },
          { label: "Win Rate", value: bt.win_rate != null ? (bt.win_rate * 100).toFixed(0) + "%" : "--" },
          { label: "Trades", value: bt.total_trades != null ? bt.total_trades : "--" },
          { label: "P. Factor", value: bt.profit_factor != null ? bt.profit_factor.toFixed(2) : "--" },
        ].map((m, i) => (
          <div key={i} className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-gray-500 text-xs uppercase mb-1">{m.label}</div>
            <div className="text-gray-100 text-sm font-mono font-semibold">{m.value}</div>
          </div>
        ))}
      </div>

      {/* Equity curve */}
      {equityCurve.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs uppercase mb-2">Equity Curve</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={equityCurve}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
              <XAxis dataKey="day" stroke="#6b7280" tick={{ fontSize: 10 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#1e1e2a", border: "1px solid #3a3a4a", borderRadius: "8px" }}
                labelStyle={{ color: "#9ca3af" }}
                itemStyle={{ color: "#22c55e" }}
              />
              <Line type="monotone" dataKey="equity" stroke="#22c55e" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {bt.note && (
        <div className="text-gray-500 text-xs italic">{bt.note}</div>
      )}
    </div>
  );
}

function StrategiesPage() {
  const { data, loading, error } = useFetch("/api/v1/strategies", 30000);
  const [expandedId, setExpandedId] = useState(null);
  const [filter, setFilter] = useState("All");

  const strategies = data && data.data ? data.data : [];

  // Filter strategies by asset class
  const filtered = filter === "All"
    ? strategies
    : strategies.filter((s) => normalizeAssetClass(s.asset_class) === filter);

  // Toggle row expansion
  const handleRowClick = (strategyId) => {
    setExpandedId(expandedId === strategyId ? null : strategyId);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-100 mb-6">Strategies</h1>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 text-red-300 text-sm">
          Error loading strategies: {error}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-2 mb-4">
        {ASSET_CLASS_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => { setFilter(f); setExpandedId(null); }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Strategy table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase">
              <th className="px-4 py-3 text-left">Strategy ID</th>
              <th className="px-4 py-3 text-left">Asset Class</th>
              <th className="px-4 py-3 text-left">Signal</th>
              <th className="px-4 py-3 text-right">Sharpe</th>
              <th className="px-4 py-3 text-right">Max DD</th>
            </tr>
          </thead>
          <tbody>
            {loading && strategies.length === 0 ? (
              // Skeleton rows while loading
              [...Array(6)].map((_, i) => <SkeletonRow key={i} />)
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  {strategies.length === 0 ? "No strategies found" : "No strategies match this filter"}
                </td>
              </tr>
            ) : (
              filtered.map((s) => (
                <React.Fragment key={s.strategy_id}>
                  <tr
                    onClick={() => handleRowClick(s.strategy_id)}
                    className={`border-b border-gray-800 cursor-pointer transition-colors ${
                      expandedId === s.strategy_id
                        ? "bg-gray-800"
                        : "hover:bg-gray-800/50"
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-gray-200">{s.strategy_id}</td>
                    <td className="px-4 py-3">
                      <span className="bg-gray-700 text-gray-300 text-xs px-2 py-0.5 rounded">
                        {normalizeAssetClass(s.asset_class)}
                      </span>
                    </td>
                    <td className={`px-4 py-3 font-semibold ${signalColor(s.signal_direction)}`}>
                      {signalArrow(s.signal_direction)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {s.sharpe_ratio != null ? s.sharpe_ratio.toFixed(2) : "--"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {s.max_drawdown != null ? (s.max_drawdown * 100).toFixed(1) + "%" : "--"}
                    </td>
                  </tr>
                  {expandedId === s.strategy_id && (
                    <tr className="bg-gray-850">
                      <td colSpan={5} className="bg-gray-900/50">
                        <BacktestDetail strategyId={s.strategy_id} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Strategy count */}
      {!loading && (
        <div className="mt-3 text-gray-500 text-xs">
          Showing {filtered.length} of {strategies.length} strategies
          {filter !== "All" && " (" + filter + " filter)"}
        </div>
      )}
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.StrategiesPage = StrategiesPage;

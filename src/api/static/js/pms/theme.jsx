/**
 * theme.jsx - PMS Design Tokens for the Macro Trading Portfolio Management System.
 *
 * Provides:
 * - PMS_COLORS: Semantic color palette (P&L, risk, direction, conviction, agent accents)
 * - PMS_TYPOGRAPHY: Font family, sizes, weights (Bloomberg-dense monospace)
 * - PMS_SPACING: Compact spacing scale
 * - Helper functions: pnlColor, riskColor, directionColor, convictionColor,
 *   formatPnL, formatPercent, formatNumber
 *
 * All exposed on window.PMS_THEME for CDN/Babel compatibility.
 */

// ---------------------------------------------------------------------------
// Color Palette — semantic tokens for financial UI
// ---------------------------------------------------------------------------
const PMS_COLORS = {
  // Background layers (dark theme, Bloomberg-dense)
  bg: {
    primary: '#0d1117',
    secondary: '#161b22',
    tertiary: '#21262d',
    elevated: '#30363d',
  },
  // Text hierarchy
  text: {
    primary: '#e6edf3',
    secondary: '#8b949e',
    muted: '#484f58',
    inverse: '#0d1117',
  },
  // P&L semantic (locked: classic red/green)
  pnl: {
    positive: '#3fb950',
    negative: '#f85149',
    neutral: '#8b949e',
  },
  // Risk levels (locked: traffic light)
  risk: {
    ok: '#3fb950',
    warning: '#d29922',
    breach: '#f85149',
  },
  // Signal directions
  direction: {
    long: '#3fb950',
    short: '#f85149',
    neutral: '#8b949e',
    hold: '#d29922',
  },
  // Conviction color scale (0.0 to 1.0)
  conviction: {
    low: '#8b949e',
    medium: '#d29922',
    high: '#3fb950',
    veryHigh: '#58a6ff',
  },
  // Borders and accents
  border: {
    default: '#30363d',
    subtle: '#21262d',
    accent: '#58a6ff',
  },
  // Agent card accent colors (one per agent)
  agent: {
    inflation: '#f0883e',
    monetary: '#a371f7',
    fiscal: '#3fb950',
    fx: '#58a6ff',
    cross_asset: '#d29922',
  },
};

// ---------------------------------------------------------------------------
// Typography — Bloomberg-dense monospace
// ---------------------------------------------------------------------------
const PMS_TYPOGRAPHY = {
  fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace",
  sizes: {
    xs: '0.625rem',
    sm: '0.75rem',
    base: '0.8125rem',
    lg: '0.9375rem',
    xl: '1.125rem',
    '2xl': '1.5rem',
  },
  weights: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
};

// ---------------------------------------------------------------------------
// Spacing — compact scale for dense layouts
// ---------------------------------------------------------------------------
const PMS_SPACING = {
  xs: '0.25rem',
  sm: '0.5rem',
  md: '0.75rem',
  lg: '1rem',
  xl: '1.5rem',
};

// ---------------------------------------------------------------------------
// Helper Functions — semantic color mappers and formatters
// ---------------------------------------------------------------------------

/**
 * Returns the appropriate P&L color based on numeric value sign.
 * Positive -> green, negative -> red, zero/null -> neutral gray.
 */
function pnlColor(value) {
  if (value == null || value === 0) return PMS_COLORS.pnl.neutral;
  return value > 0 ? PMS_COLORS.pnl.positive : PMS_COLORS.pnl.negative;
}

/**
 * Returns the appropriate risk color from a string level.
 * Accepts: 'ok', 'warning', 'breach' (case-insensitive).
 */
function riskColor(level) {
  if (!level) return PMS_COLORS.risk.ok;
  const normalized = String(level).toLowerCase();
  if (normalized === 'breach' || normalized === 'breached' || normalized === 'critical') {
    return PMS_COLORS.risk.breach;
  }
  if (normalized === 'warning' || normalized === 'warn') {
    return PMS_COLORS.risk.warning;
  }
  return PMS_COLORS.risk.ok;
}

/**
 * Returns the appropriate direction color from a string direction.
 * Accepts: 'long', 'short', 'neutral', 'hold' (case-insensitive).
 */
function directionColor(dir) {
  if (!dir) return PMS_COLORS.direction.neutral;
  const normalized = String(dir).toLowerCase();
  if (normalized === 'long' || normalized === 'buy') return PMS_COLORS.direction.long;
  if (normalized === 'short' || normalized === 'sell') return PMS_COLORS.direction.short;
  if (normalized === 'hold') return PMS_COLORS.direction.hold;
  return PMS_COLORS.direction.neutral;
}

/**
 * Returns the appropriate conviction color based on numeric score (0.0 to 1.0).
 * < 0.4 -> low (gray), < 0.6 -> medium (yellow), < 0.8 -> high (green), >= 0.8 -> veryHigh (blue).
 */
function convictionColor(score) {
  if (score == null) return PMS_COLORS.conviction.low;
  if (score < 0.4) return PMS_COLORS.conviction.low;
  if (score < 0.6) return PMS_COLORS.conviction.medium;
  if (score < 0.8) return PMS_COLORS.conviction.high;
  return PMS_COLORS.conviction.veryHigh;
}

/**
 * Formats a numeric P&L value with +/- sign and 2 decimal places.
 * Example: 1234.5 -> "+1,234.50", -500 -> "-500.00"
 */
function formatPnL(value) {
  if (value == null || isNaN(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return sign + value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Formats a numeric value as a percentage string with sign.
 * Example: 0.0532 -> "+5.32%", -0.12 -> "-12.00%"
 */
function formatPercent(value) {
  if (value == null || isNaN(value)) return '--';
  const pct = value * 100;
  const sign = pct > 0 ? '+' : '';
  return sign + pct.toFixed(2) + '%';
}

/**
 * Generic number formatter with configurable decimal places.
 * Example: formatNumber(1234.567, 1) -> "1,234.6"
 */
function formatNumber(value, decimals) {
  if (value == null || isNaN(value)) return '--';
  const d = decimals != null ? decimals : 2;
  return value.toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

// ---------------------------------------------------------------------------
// Export on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.PMS_THEME = {
  PMS_COLORS,
  PMS_TYPOGRAPHY,
  PMS_SPACING,
  pnlColor,
  riskColor,
  directionColor,
  convictionColor,
  formatPnL,
  formatPercent,
  formatNumber,
};

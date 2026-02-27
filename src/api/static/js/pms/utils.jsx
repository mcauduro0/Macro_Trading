/**
 * utils.jsx - Shared PMS Utility Functions and Components.
 *
 * Provides:
 * - seededRng:        Deterministic PRNG for reproducible sample data
 * - formatPnLShort:   Abbreviated P&L formatting (e.g., +R$ 45K)
 * - SampleDataBanner: Prominent banner indicating sample/mock data is displayed
 *
 * Eliminates duplication across PositionBookPage, RiskMonitorPage,
 * and PerformanceAttributionPage.
 *
 * All exposed on window for CDN/Babel compatibility.
 */

const { PMS_COLORS: _UC, PMS_TYPOGRAPHY: _UT } = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Seeded PRNG — deterministic random number generator
// ---------------------------------------------------------------------------
/**
 * Creates a seeded pseudo-random number generator.
 * Returns a function that produces values in [0, 1) on each call.
 * Same seed always produces the same sequence.
 */
function seededRng(seed) {
  let s = seed;
  return function () {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ---------------------------------------------------------------------------
// formatPnLShort — abbreviated P&L formatting in BRL
// ---------------------------------------------------------------------------
/**
 * Format P&L in BRL with abbreviated notation and sign.
 * e.g., 45000 -> "+R$ 45K", -12000 -> "-R$ 12K", 1500000 -> "+R$ 1.5M"
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
// SampleDataBanner — visible indicator for sample/mock data
// ---------------------------------------------------------------------------
/**
 * Renders a prominent banner at the top of a page section indicating that
 * the displayed data is sample/mock data, not live production data.
 *
 * Props:
 * - message (string): Optional custom message. Defaults to standard text.
 * - compact (bool):   If true, renders a smaller inline badge instead of full banner.
 */
function SampleDataBanner({ message, compact }) {
  const defaultMessage = 'DADOS DE AMOSTRA — Os dados exibidos são ilustrativos. Conecte os endpoints da API para dados reais.';
  const displayMessage = message || defaultMessage;

  if (compact) {
    const badgeStyle = {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '2px 8px',
      backgroundColor: 'rgba(210, 153, 34, 0.15)',
      border: '1px solid rgba(210, 153, 34, 0.4)',
      borderRadius: '4px',
      fontSize: _UT.sizes.xs,
      fontWeight: _UT.weights.semibold,
      color: '#d29922',
      fontFamily: _UT.fontFamily,
      letterSpacing: '0.04em',
    };

    return (
      <span style={badgeStyle}>
        <span style={{ fontSize: '10px' }}>&#9888;</span>
        AMOSTRA
      </span>
    );
  }

  const bannerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 14px',
    marginBottom: '12px',
    backgroundColor: 'rgba(210, 153, 34, 0.1)',
    border: '1px solid rgba(210, 153, 34, 0.35)',
    borderRadius: '6px',
    fontSize: _UT.sizes.sm,
    fontWeight: _UT.weights.medium,
    color: '#d29922',
    fontFamily: _UT.fontFamily,
    lineHeight: 1.4,
  };

  const iconStyle = {
    fontSize: '16px',
    flexShrink: 0,
  };

  return (
    <div style={bannerStyle}>
      <span style={iconStyle}>&#9888;</span>
      <span>{displayMessage}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Export on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.PMS_UTILS = {
  seededRng,
  formatPnLShort,
};
window.SampleDataBanner = SampleDataBanner;

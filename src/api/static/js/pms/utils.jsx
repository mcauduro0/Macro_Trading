/**
 * utils.jsx - Shared PMS Utility Components.
 *
 * Provides:
 * - SampleDataBanner: Prominent banner indicating sample/mock data is displayed
 *
 * Note: seededRng and formatPnLShort are defined in theme.jsx and exported
 * via window.PMS_THEME. They were removed here to eliminate duplication.
 *
 * All exposed on window for CDN/Babel compatibility.
 */

const { PMS_COLORS: _UC, PMS_TYPOGRAPHY: _UT } = window.PMS_THEME;

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
window.SampleDataBanner = SampleDataBanner;

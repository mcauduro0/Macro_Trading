/**
 * App.jsx - Main application component for ARC Macro PMS.
 *
 * Features:
 * - HashRouter with PMS routes (8 pages) + default redirect
 * - PMS-only interface (Dashboard mode removed per review)
 * - Sidebar + content area layout with PMS dark theme
 * - WebSocket alert connection with toast notifications
 * - Alert badge count passed to Sidebar
 * - Legacy Dashboard routes redirect to PMS equivalents
 */

const { useState, useEffect } = React;
const { HashRouter, Routes, Route, Navigate, useNavigate, useLocation } = window.ReactRouterDOM;

// ---------------------------------------------------------------------------
// Toast notification card
// ---------------------------------------------------------------------------
function ToastCard({ toast, onClose }) {
  const { PMS_COLORS: _C, PMS_TYPOGRAPHY: _T } = window.PMS_THEME;

  const cardStyle = {
    backgroundColor: _C.bg.elevated,
    border: '1px solid ' + _C.border.default,
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    padding: '10px 12px',
    marginBottom: '6px',
    maxWidth: '320px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    fontFamily: _T.fontFamily,
    animation: 'slideIn 0.3s ease-out',
  };

  const msgStyle = {
    flex: 1,
    fontSize: _T.sizes.sm,
    color: _C.text.primary,
    lineHeight: 1.4,
  };

  const timeStyle = {
    fontSize: _T.sizes.xs,
    color: _C.text.muted,
    marginTop: '2px',
  };

  const closeBtnStyle = {
    background: 'none',
    border: 'none',
    color: _C.text.muted,
    fontSize: '14px',
    cursor: 'pointer',
    padding: 0,
    lineHeight: 1,
    flexShrink: 0,
  };

  return (
    <div style={cardStyle}>
      <div style={{ flex: 1 }}>
        <div style={msgStyle}>{toast.message}</div>
        <div style={timeStyle}>
          {new Date(toast.timestamp).toLocaleTimeString()}
        </div>
      </div>
      <button
        onClick={() => onClose(toast.id)}
        style={closeBtnStyle}
        title="Dismiss"
      >
        &#x2715;
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toast container (fixed bottom-right)
// ---------------------------------------------------------------------------
function ToastContainer({ toasts, onClose }) {
  if (toasts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: '16px',
      right: '16px',
      zIndex: 50,
      display: 'flex',
      flexDirection: 'column-reverse',
    }}>
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onClose={onClose} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout wrapper — sidebar + content with PMS theme
// ---------------------------------------------------------------------------
function Layout({ children, alertCount, toasts, onCloseToast }) {
  const { PMS_COLORS: _C } = window.PMS_THEME;

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      backgroundColor: _C.bg.primary,
      color: _C.text.primary,
    }}>
      <Sidebar alertCount={alertCount} />
      {/* Content area — offset by sidebar width */}
      <main style={{
        flex: 1,
        marginLeft: '224px',
        overflowY: 'auto',
        backgroundColor: _C.bg.primary,
      }}>
        <div style={{
          padding: '16px',
          maxWidth: '1600px',
          margin: '0 auto',
        }}>
          {children}
        </div>
      </main>
      <ToastContainer toasts={toasts} onClose={onCloseToast} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inner app content (needs to be inside HashRouter for useNavigate)
// ---------------------------------------------------------------------------
function AppContent() {
  const [toasts, setToasts] = useState([]);

  // Connect to alerts WebSocket
  const { connected, lastMessage } = useWebSocket("/ws/alerts");

  // Push new alerts into toast stack
  useEffect(() => {
    if (lastMessage) {
      const id = Date.now() + Math.random();
      const message =
        typeof lastMessage === "string"
          ? lastMessage
          : lastMessage.message || lastMessage.alert || JSON.stringify(lastMessage);
      const newToast = { id, message, timestamp: Date.now() };

      setToasts((prev) => [...prev, newToast]);

      // Auto-dismiss after 10 seconds
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 10000);
    }
  }, [lastMessage]);

  // Manual close handler
  const handleCloseToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const alertCount = toasts.length;

  // PMS page components — resolved from window globals
  const MorningPackPage = window.MorningPackPage;
  const PositionBookPage = window.PositionBookPage;
  const TradeBlotterPage = window.TradeBlotterPage;
  const RiskMonitorPage = window.RiskMonitorPage;
  const PerformanceAttributionPage = window.PerformanceAttributionPage;
  const DecisionJournalPage = window.DecisionJournalPage;
  const AgentIntelPage = window.AgentIntelPage;
  const ComplianceAuditPage = window.ComplianceAuditPage;

  return (
    <Layout
      alertCount={alertCount}
      toasts={toasts}
      onCloseToast={handleCloseToast}
    >
      <Routes>
        {/* Default route — redirect to Morning Pack */}
        <Route path="/" element={<Navigate to="/pms/morning-pack" replace />} />

        {/* PMS routes */}
        <Route path="/pms/morning-pack" element={<MorningPackPage />} />
        <Route path="/pms/portfolio" element={<PositionBookPage />} />
        <Route path="/pms/risk" element={<RiskMonitorPage />} />
        <Route path="/pms/blotter" element={<TradeBlotterPage />} />
        <Route path="/pms/attribution" element={<PerformanceAttributionPage />} />
        <Route path="/pms/journal" element={<DecisionJournalPage />} />
        <Route path="/pms/agents" element={<AgentIntelPage />} />
        <Route path="/pms/compliance" element={<ComplianceAuditPage />} />

        {/* Legacy Dashboard routes — redirect to PMS equivalents */}
        <Route path="/strategies" element={<Navigate to="/pms/attribution" replace />} />
        <Route path="/signals" element={<Navigate to="/pms/morning-pack" replace />} />
        <Route path="/risk" element={<Navigate to="/pms/risk" replace />} />
        <Route path="/portfolio" element={<Navigate to="/pms/portfolio" replace />} />
        <Route path="/agents" element={<Navigate to="/pms/agents" replace />} />

        {/* Catch-all — redirect to Morning Pack */}
        <Route path="*" element={<Navigate to="/pms/morning-pack" replace />} />
      </Routes>
    </Layout>
  );
}

// ---------------------------------------------------------------------------
// Main App component
// ---------------------------------------------------------------------------
function App() {
  return (
    <HashRouter>
      <AppContent />
    </HashRouter>
  );
}

// Expose on window for CDN/Babel compatibility
window.App = App;

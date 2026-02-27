/**
 * App.jsx - Main application component for the Macro Trading PMS.
 *
 * Features:
 * - HashRouter with PMS routes (9 pages) + legacy redirects
 * - Bloomberg-dense dark theme (#0d1117) for all pages
 * - WebSocket alert connection with toast notifications
 * - Alert badge count passed to Sidebar
 */

const { useState, useEffect } = React;
const { HashRouter, Routes, Route, Navigate, useLocation } = window.ReactRouterDOM;

// ---------------------------------------------------------------------------
// Toast notification card
// ---------------------------------------------------------------------------
function ToastCard({ toast, onClose }) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg shadow-lg p-3 mb-2 max-w-sm animate-slide-in flex items-start gap-2">
      <div className="flex-1">
        <div className="text-gray-200 text-sm">{toast.message}</div>
        <div className="text-gray-500 text-xs mt-1">
          {new Date(toast.timestamp).toLocaleTimeString()}
        </div>
      </div>
      <button
        onClick={() => onClose(toast.id)}
        className="text-gray-500 hover:text-gray-300 text-lg leading-none flex-shrink-0"
        title="Dismiss"
      >
        x
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
    <div className="fixed bottom-4 right-4 z-50 flex flex-col-reverse">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onClose={onClose} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout wrapper — sidebar + content with PMS styling
// ---------------------------------------------------------------------------
function Layout({ children, alertCount, toasts, onCloseToast }) {
  return (
    <div className="flex h-screen text-gray-100" style={{ backgroundColor: '#0d1117' }}>
      <Sidebar alertCount={alertCount} />
      {/* Content area — offset by sidebar width */}
      <main className="flex-1 ml-56 overflow-y-auto" style={{ backgroundColor: '#0d1117' }}>
        <div className="p-4 max-w-screen-2xl mx-auto">
          {children}
        </div>
      </main>
      <ToastContainer toasts={toasts} onClose={onCloseToast} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inner app content (needs to be inside HashRouter for hooks)
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

  // PMS page components from window globals
  const MorningPackPage = window.MorningPackPage;
  const PositionBookPage = window.PositionBookPage;
  const TradeBlotterPage = window.TradeBlotterPage;
  const RiskMonitorPage = window.RiskMonitorPage;
  const PerformanceAttributionPage = window.PerformanceAttributionPage;
  const DecisionJournalPage = window.DecisionJournalPage;
  const AgentIntelPage = window.AgentIntelPage;
  const ComplianceAuditPage = window.ComplianceAuditPage;
  const PMSSignalsPage = window.PMSSignalsPage;

  return (
    <Layout
      alertCount={alertCount}
      toasts={toasts}
      onCloseToast={handleCloseToast}
    >
      <Routes>
        {/* PMS routes */}
        <Route path="/pms/morning-pack" element={<MorningPackPage />} />
        <Route path="/pms/portfolio" element={<PositionBookPage />} />
        <Route path="/pms/risk" element={<RiskMonitorPage />} />
        <Route path="/pms/blotter" element={<TradeBlotterPage />} />
        <Route path="/pms/signals" element={<PMSSignalsPage />} />
        <Route path="/pms/attribution" element={<PerformanceAttributionPage />} />
        <Route path="/pms/journal" element={<DecisionJournalPage />} />
        <Route path="/pms/agents" element={<AgentIntelPage />} />
        <Route path="/pms/compliance" element={<ComplianceAuditPage />} />

        {/* Default + legacy redirects */}
        <Route path="/" element={<Navigate to="/pms/morning-pack" replace />} />
        <Route path="/strategies" element={<Navigate to="/pms/morning-pack" replace />} />
        <Route path="/signals" element={<Navigate to="/pms/signals" replace />} />
        <Route path="/risk" element={<Navigate to="/pms/risk" replace />} />
        <Route path="/portfolio" element={<Navigate to="/pms/portfolio" replace />} />
        <Route path="/agents" element={<Navigate to="/pms/agents" replace />} />
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

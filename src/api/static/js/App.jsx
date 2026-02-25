/**
 * App.jsx - Main application component for the Macro Trading Dashboard.
 *
 * Features:
 * - HashRouter with Dashboard (5 routes) + PMS (7 routes) + default redirect
 * - Mode switch: Dashboard vs PMS mode with separate navigation
 * - Sidebar + content area layout with mode-aware styling
 * - WebSocket alert connection with toast notifications
 * - Alert badge count passed to Sidebar
 */

const { useState, useEffect } = React;
const { HashRouter, Routes, Route, Navigate, useNavigate, useLocation } = window.ReactRouterDOM;

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
// PMS Placeholder page for future pages
// ---------------------------------------------------------------------------
function PMSPlaceholder({ title }) {
  return (
    <div style={{
      color: '#e6edf3',
      padding: '2rem',
      fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace",
    }}>
      <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>{title}</h1>
      <p style={{ color: '#8b949e' }}>Coming soon...</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout wrapper — sidebar + content with mode-aware styling
// ---------------------------------------------------------------------------
function Layout({ children, alertCount, pmsMode, onModeChange, toasts, onCloseToast }) {
  const mainBg = pmsMode
    ? { backgroundColor: '#0d1117' }
    : {};

  return (
    <div className="flex h-screen text-gray-100" style={pmsMode ? { backgroundColor: '#0d1117' } : {}}>
      <Sidebar alertCount={alertCount} pmsMode={pmsMode} onModeChange={onModeChange} />
      {/* Content area — offset by sidebar width */}
      <main className={`flex-1 ml-56 overflow-y-auto ${!pmsMode ? 'bg-gray-950' : ''}`} style={mainBg}>
        <div className={pmsMode ? "p-4 max-w-screen-2xl mx-auto" : "p-6 max-w-screen-2xl mx-auto"}>
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
  const [pmsMode, setPmsMode] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Detect PMS mode from URL on initial load and hash changes
  useEffect(() => {
    const isPmsRoute = location.pathname.startsWith('/pms/');
    if (isPmsRoute && !pmsMode) {
      setPmsMode(true);
    }
  }, [location.pathname]);

  // Mode change handler — navigates to default page for each mode
  const handleModeChange = (isPms) => {
    setPmsMode(isPms);
    if (isPms) {
      navigate('/pms/morning-pack');
    } else {
      navigate('/strategies');
    }
  };

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

  // MorningPackPage — resolved from window global (loaded from pms/pages/MorningPackPage.jsx)
  const MorningPackPage = window.MorningPackPage;
  // PositionBookPage — resolved from window global (loaded from pms/pages/PositionBookPage.jsx)
  const PositionBookPage = window.PositionBookPage;
  // TradeBlotterPage — resolved from window global (loaded from pms/pages/TradeBlotterPage.jsx)
  const TradeBlotterPage = window.TradeBlotterPage;

  return (
    <Layout
      alertCount={alertCount}
      pmsMode={pmsMode}
      onModeChange={handleModeChange}
      toasts={toasts}
      onCloseToast={handleCloseToast}
    >
      <Routes>
        {/* Dashboard routes */}
        <Route path="/" element={<Navigate to="/strategies" replace />} />
        <Route path="/strategies" element={<StrategiesPage />} />
        <Route path="/signals" element={<SignalsPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/agents" element={<AgentsPage />} />

        {/* PMS routes */}
        <Route path="/pms/morning-pack" element={<MorningPackPage />} />
        <Route path="/pms/portfolio" element={<PositionBookPage />} />
        <Route path="/pms/risk" element={<PMSPlaceholder title="Risk Monitor" />} />
        <Route path="/pms/blotter" element={<TradeBlotterPage />} />
        <Route path="/pms/attribution" element={<PMSPlaceholder title="Performance Attribution" />} />
        <Route path="/pms/strategies" element={<PMSPlaceholder title="PMS Strategies" />} />
        <Route path="/pms/settings" element={<PMSPlaceholder title="PMS Settings" />} />
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

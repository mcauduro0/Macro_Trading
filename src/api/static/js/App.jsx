/**
 * App.jsx - Main application component for the Macro Trading Dashboard.
 *
 * Features:
 * - HashRouter with 5 page routes + default redirect
 * - Sidebar + content area layout
 * - WebSocket alert connection with toast notifications
 * - Alert badge count passed to Sidebar
 */

const { useState, useEffect } = React;
const { HashRouter, Routes, Route, Navigate } = window.ReactRouterDOM;

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
// Layout wrapper — sidebar + content
// ---------------------------------------------------------------------------
function Layout({ children, alertCount, toasts, onCloseToast }) {
  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <Sidebar alertCount={alertCount} />
      {/* Content area — offset by sidebar width */}
      <main className="flex-1 ml-56 overflow-y-auto">
        <div className="p-6 max-w-screen-2xl mx-auto">
          {children}
        </div>
      </main>
      <ToastContainer toasts={toasts} onClose={onCloseToast} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main App component
// ---------------------------------------------------------------------------
function App() {
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

  return (
    <HashRouter>
      <Layout alertCount={alertCount} toasts={toasts} onCloseToast={handleCloseToast}>
        <Routes>
          <Route path="/" element={<Navigate to="/strategies" replace />} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="/signals" element={<SignalsPage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/agents" element={<AgentsPage />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
}

// Expose on window for CDN/Babel compatibility
window.App = App;

import { Navigate, Route, Routes, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { PatientDashboard } from "./pages/PatientDashboard";
import { ProviderDashboard } from "./pages/ProviderDashboard";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Secure RPM Platform — Research Prototype</span>
        {user && (
          <span className="user-info">
            {user.display_name} ({user.role}){" "}
            <button onClick={() => logout()}>Sign out</button>
          </span>
        )}
      </header>
      <main>{children}</main>
      <footer className="footer">
        AI-generated information is for monitoring/research purposes and is not a medical diagnosis.
      </footer>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="loading">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Home() {
  const { user } = useAuth();
  if (user?.role === "provider") return <ProviderDashboard />;
  if (user?.role === "patient") return <PatientDashboard />;
  return (
    <div className="card">
      <p>
        Administrator accounts have no default health-data access in this prototype. There is
        no admin dashboard here by design (Section 5.3).
      </p>
      <p>
        <Link to="/login">Sign in</Link> as a patient or provider to continue.
      </p>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Shell>
              <Home />
            </Shell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

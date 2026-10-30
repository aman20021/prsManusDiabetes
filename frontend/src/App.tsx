import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import BatchPage from "./pages/BatchPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import ModelsPage from "./pages/ModelsPage";
import PredictPage from "./pages/PredictPage";
import UploadDetailPage from "./pages/UploadDetailPage";
import UploadsPage from "./pages/UploadsPage";
import UsersPage from "./pages/UsersPage";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="layout">
      <header>
        <strong>MANAS Inference</strong>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/predict">Single</NavLink>
          <NavLink to="/batch">Batch</NavLink>
          <NavLink to="/uploads">Uploads</NavLink>
          {user?.role === "mlops" && <NavLink to="/models">Models</NavLink>}
          {user?.role === "mlops" && <NavLink to="/people">People</NavLink>}
        </nav>
        <span className="user">
          {user?.username} ({user?.role}){" "}
          <button type="button" onClick={logout}>
            Logout
          </button>
        </span>
      </header>
      <main>{children}</main>
    </div>
  );
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <DashboardPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/predict"
        element={
          <PrivateRoute>
            <PredictPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/batch"
        element={
          <PrivateRoute>
            <BatchPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/uploads"
        element={
          <PrivateRoute>
            <UploadsPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/uploads/:id"
        element={
          <PrivateRoute>
            <UploadDetailPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/models"
        element={
          <PrivateRoute>
            <ModelsPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/people"
        element={
          <PrivateRoute>
            <UsersPage />
          </PrivateRoute>
        }
      />
    </Routes>
  );
}

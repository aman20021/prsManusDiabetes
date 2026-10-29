import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import ErrorBox from "../components/ErrorBox";

export default function LoginPage() {
  const { user, login, loading } = useAuth();
  const [username, setUsername] = useState("clinician");
  const [password, setPassword] = useState("clinician123");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (!loading && user) return <Navigate to="/" replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page card">
      <h1>Sign in</h1>
      <p className="muted">Demo: clinician / clinician123 or mlops / mlops123</p>
      <form onSubmit={onSubmit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Login"}
        </button>
      </form>
      {error ? <ErrorBox error={error} /> : null}
    </div>
  );
}

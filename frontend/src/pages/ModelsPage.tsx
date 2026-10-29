import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";

type Model = {
  version: string;
  status: string;
  framework: string;
  offline_metrics: Record<string, unknown> | null;
};

export default function ModelsPage() {
  const { user } = useAuth();
  const [models, setModels] = useState<Model[]>([]);
  const [reason, setReason] = useState("Approved after offline eval");
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  const load = () =>
    api<{ models: Model[] }>("/api/v1/models")
      .then((r) => setModels(r.models))
      .catch(setError);

  useEffect(() => {
    load();
  }, []);

  if (user?.role !== "mlops") return <Navigate to="/" replace />;

  const promote = async (version: string) => {
    setError(null);
    setMessage("");
    try {
      await api(`/api/v1/models/${version}/promote`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setMessage(`Promoted ${version}`);
      await load();
    } catch (err) {
      setError(err);
    }
  };

  const rollback = async () => {
    setError(null);
    setMessage("");
    try {
      const res = await api<{ version: string }>("/api/v1/models/rollback", {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setMessage(`Rolled back to ${res.version}`);
      await load();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div>
      <h1>Model versions</h1>
      <div className="card">
        <label>
          Promotion / rollback reason
          <input value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <button type="button" onClick={rollback}>
          Rollback production
        </button>
      </div>
      {message ? <p>{message}</p> : null}
      {error ? <ErrorBox error={error} /> : null}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Status</th>
              <th>Framework</th>
              <th>Metrics</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.version}>
                <td>{m.version}</td>
                <td>{m.status}</td>
                <td>{m.framework}</td>
                <td>
                  <code>{JSON.stringify(m.offline_metrics ?? {})}</code>
                </td>
                <td>
                  {m.status === "candidate" ? (
                    <button type="button" onClick={() => promote(m.version)}>
                      Promote
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";

type Summary = {
  active_model_version: string | null;
  request_count: number;
  error_rate: number;
  latency_ms_p50: number | null;
  positive_prediction_rate: number | null;
};

type Prediction = {
  request_id: string;
  model_version: string;
  label: number;
  probability_positive: number;
  created_at: string;
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    Promise.all([
      api<Summary>("/api/v1/monitoring/summary"),
      api<{ predictions: Prediction[] }>("/api/v1/predictions?limit=10"),
    ])
      .then(([s, p]) => {
        setSummary(s);
        setPredictions(p.predictions);
      })
      .catch(setError);
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      {error ? <ErrorBox error={error} /> : null}
      {summary ? (
        <div className="card">
          <p>
            <strong>Active model:</strong> {summary.active_model_version ?? "—"}
          </p>
          <p>Requests (24h): {summary.request_count}</p>
          <p>Error rate: {(summary.error_rate * 100).toFixed(1)}%</p>
          <p>Latency p50: {summary.latency_ms_p50 ?? "—"} ms</p>
          <p>
            Positive prediction rate:{" "}
            {summary.positive_prediction_rate != null
              ? (summary.positive_prediction_rate * 100).toFixed(1) + "%"
              : "—"}
          </p>
        </div>
      ) : (
        <p className="muted">Loading metrics…</p>
      )}
      <div className="card">
        <h2>Recent predictions</h2>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Model</th>
              <th>Label</th>
              <th>P(+)</th>
            </tr>
          </thead>
          <tbody>
            {predictions.map((p) => (
              <tr key={p.request_id}>
                <td>{p.created_at?.slice(0, 19)}</td>
                <td>{p.model_version}</td>
                <td>{p.label}</td>
                <td>{p.probability_positive?.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          <Link to="/uploads">View all uploads →</Link>
        </p>
      </div>
    </div>
  );
}

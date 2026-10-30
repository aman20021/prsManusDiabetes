import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Histogram, OutcomeChart, ProbabilityChart, type ScreeningPoint } from "../components/Charts";
import ErrorBox from "../components/ErrorBox";

type Summary = {
  window_hours: number;
  active_model_version: string | null;
  request_count: number;
  error_count: number;
  error_rate: number;
  latency_ms_p50: number | null;
  latency_ms_p95: number | null;
  positive_prediction_rate: number | null;
};

type Prediction = {
  request_id: string;
  upload_id: number | null;
  model_version: string | null;
  label: number | null;
  probability_positive: number | null;
  created_at: string;
};

function formatMs(ms: number): string {
  return Number.isInteger(ms) ? `${ms} ms` : `${ms.toFixed(1)} ms`;
}

function lede(summary: Summary): string {
  const noun = summary.request_count === 1 ? "request" : "requests";
  const failed =
    summary.error_count === 0
      ? "none failed"
      : summary.error_count === 1
        ? "1 failed"
        : `${summary.error_count} failed`;
  const latency =
    summary.latency_ms_p50 != null
      ? ` Median response ${formatMs(summary.latency_ms_p50)}.`
      : "";
  const model = summary.active_model_version
    ? ` Model ${summary.active_model_version} is active.`
    : "";
  return `${summary.request_count} ${noun} in the last ${summary.window_hours} hours, ${failed}.${latency}${model}`;
}

function callName(label: number): string {
  return label === 1 ? "Diabetes or prediabetes" : "No diabetes";
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16);
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(d);
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    Promise.all([
      api<Summary>("/api/v1/monitoring/summary"),
      api<{ predictions: Prediction[] }>("/api/v1/predictions?limit=200"),
    ])
      .then(([s, p]) => {
        setSummary(s);
        setPredictions(p.predictions);
      })
      .catch(setError);
  }, []);

  const points: ScreeningPoint[] = predictions
    .filter((p) => p.label != null && p.probability_positive != null && p.created_at)
    .map((p) => ({
      id: p.request_id,
      at: p.created_at,
      label: p.label as number,
      probability: p.probability_positive as number,
    }))
    .sort((a, b) => a.at.localeCompare(b.at));

  const plotted = points.slice(-24);
  const positive = points.filter((p) => p.label === 1).length;
  const negative = points.length - positive;

  return (
    <article className="dash">
      <h1>Dashboard</h1>
      {error ? <ErrorBox error={error} /> : null}
      {summary ? <p className="dash-lede">{lede(summary)}</p> : <p className="muted">Loading…</p>}

      {summary && points.length === 0 ? (
        <p className="dash-empty">
          No screenings yet. A single or batch run will show up in these charts.
        </p>
      ) : null}

      {points.length > 0 ? (
        <>
          <section className="dash-panel">
            <h2>Chance of diabetes or prediabetes</h2>
            <p className="dash-note">
              Each bar is one screening. The dashed line is 50%.
              {points.length > plotted.length
                ? ` Showing the latest ${plotted.length}.`
                : ""}
            </p>
            <ProbabilityChart points={plotted} />
            <p className="dash-legend">
              <span className="swatch pos" /> Diabetes or prediabetes
              <span className="swatch neg" /> No diabetes
            </p>
          </section>

          <div className="dash-split">
            <section className="dash-panel">
              <h2>Calls</h2>
              <p className="dash-note">How the recent screenings were called.</p>
              <OutcomeChart positive={positive} negative={negative} />
            </section>
            <section className="dash-panel">
              <h2>Where the chances sit</h2>
              <p className="dash-note">Count of screenings in each band of percent positive.</p>
              <Histogram values={points.map((p) => p.probability)} />
            </section>
          </div>

          <section className="dash-panel">
            <h2>Recent screenings</h2>
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Call</th>
                    <th>Positive</th>
                    <th>Model</th>
                  </tr>
                </thead>
                <tbody>
                  {[...points].reverse().slice(0, 8).map((p) => {
                    const source = predictions.find((row) => row.request_id === p.id);
                    const time = formatWhen(p.at);
                    return (
                      <tr key={p.id} className={p.label === 1 ? "positive" : undefined}>
                        <td>
                          {source?.upload_id ? (
                            <Link to={`/uploads/${source.upload_id}`}>{time}</Link>
                          ) : (
                            time
                          )}
                        </td>
                        <td className={p.label === 1 ? "call-pos" : "call-neg"}>{callName(p.label)}</td>
                        <td>{(p.probability * 100).toFixed(1)}%</td>
                        <td>{source?.model_version ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="dash-foot">
              <Link to="/uploads">Uploads</Link>
            </p>
          </section>
        </>
      ) : null}
    </article>
  );
}

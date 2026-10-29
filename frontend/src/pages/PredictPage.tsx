import { FormEvent, useState } from "react";
import { FEATURES, api, defaultSample } from "../api";
import ErrorBox from "../components/ErrorBox";

export default function PredictPage() {
  const [form, setForm] = useState<Record<string, number>>(defaultSample());
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const payload = Object.fromEntries(
        FEATURES.map((f) => [f, Number(form[f])]),
      );
      const res = await api<Record<string, unknown>>("/api/v1/predict", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(res);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const onCsv = async (file: File) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const text = await file.text();
      const [header, row] = text.trim().split("\n");
      const cols = header.split(",");
      const vals = row.split(",");
      const payload: Record<string, number> = {};
      cols.forEach((c, i) => {
        payload[c.trim()] = Number(vals[i].trim());
      });
      const res = await api<Record<string, unknown>>("/api/v1/predict", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(res);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Single prediction</h1>
      <div className="card">
        <label>
          Upload single-row CSV
          <input
            type="file"
            accept=".csv"
            onChange={(e) => e.target.files?.[0] && onCsv(e.target.files[0])}
          />
        </label>
      </div>
      <form className="card" onSubmit={onSubmit}>
        <div className="grid">
          {FEATURES.map((f) => (
            <label key={f}>
              {f}
              <input
                type="number"
                value={form[f]}
                onChange={(e) => setForm({ ...form, [f]: Number(e.target.value) })}
              />
            </label>
          ))}
        </div>
        <button type="submit" disabled={busy}>
          {busy ? "Running…" : "Predict"}
        </button>
      </form>
      {error ? <ErrorBox error={error} /> : null}
      {result ? (
        <div className="card">
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      ) : null}
    </div>
  );
}

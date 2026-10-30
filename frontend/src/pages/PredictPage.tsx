import { FormEvent, useCallback, useState } from "react";
import { FEATURES, api, defaultSample } from "../api";
import ErrorBox from "../components/ErrorBox";
import ModelSelect, { modelQuery } from "../components/ModelSelect";
import ResultSheet from "../components/ResultSheet";

type SingleResult = {
  model_version: string;
  upload_id: number;
  prediction: {
    label: number;
    probability_positive: number;
    input_echo: Record<string, number>;
  };
};

export default function PredictPage() {
  const [form, setForm] = useState<Record<string, number>>(defaultSample());
  const [modelVersion, setModelVersion] = useState("");
  const [result, setResult] = useState<SingleResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const chooseModel = useCallback((version: string) => {
    setModelVersion(version);
    setResult(null);
  }, []);

  const predict = async (payload: Record<string, number>) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await api<SingleResult>(`/api/v1/predict${modelQuery(modelVersion)}`, {
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

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const payload = Object.fromEntries(FEATURES.map((f) => [f, Number(form[f])]));
    await predict(payload);
  };

  const onCsv = async (file: File) => {
    const text = await file.text();
    const [header, row] = text.trim().split("\n");
    const cols = header.split(",");
    const vals = row.split(",");
    const payload: Record<string, number> = {};
    cols.forEach((c, i) => {
      payload[c.trim()] = Number(vals[i].trim());
    });
    await predict(payload);
  };

  return (
    <div>
      <h1>Single prediction</h1>
      <div className="card">
        <ModelSelect version={modelVersion} onChange={chooseModel} />
      </div>
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
        <ResultSheet
          title="This screening"
          kind="single"
          modelVersion={result.model_version}
          rows={[
            {
              rowIndex: 0,
              label: result.prediction.label,
              probability: result.prediction.probability_positive,
              values: result.prediction.input_echo,
            },
          ]}
        />
      ) : null}
    </div>
  );
}

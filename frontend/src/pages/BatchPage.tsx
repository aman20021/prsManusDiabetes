import { FormEvent, useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { getToken } from "../api";
import ErrorBox from "../components/ErrorBox";
import ModelSelect, { modelQuery } from "../components/ModelSelect";
import ResultSheet from "../components/ResultSheet";

type BatchPrediction = {
  row_index: number;
  label: number;
  probability_positive: number;
  input_echo: Record<string, number>;
};

type BatchResult = {
  upload_id: number;
  model_version?: string;
  predictions: BatchPrediction[];
};

export default function BatchPage() {
  const [result, setResult] = useState<BatchResult | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [modelVersion, setModelVersion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const chooseModel = useCallback((version: string) => {
    setModelVersion(version);
    setResult(null);
  }, []);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fileInput = (e.target as HTMLFormElement).elements.namedItem(
      "file",
    ) as HTMLInputElement;
    const file = fileInput.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setFilename(file.name);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/v1/predict/batch${modelQuery(modelVersion)}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw Object.assign(new Error(data.message), { api: data });
      setResult(data);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Batch inference</h1>
      <div className="card">
        <ModelSelect version={modelVersion} onChange={chooseModel} />
      </div>
      <form className="card" onSubmit={onSubmit}>
        <input name="file" type="file" accept=".csv" required />
        <button type="submit" disabled={busy}>
          {busy ? "Processing…" : "Run batch"}
        </button>
      </form>
      {error ? <ErrorBox error={error} /> : null}
      {result ? (
        <>
          <p className="sheet-back">
            Saved as{" "}
            <Link to={`/uploads/${result.upload_id}`}>
              {filename ?? `upload ${result.upload_id}`}
            </Link>
          </p>
          <ResultSheet
            title={filename ?? "Batch file"}
            kind="batch"
            modelVersion={result.model_version ?? null}
            rows={result.predictions.map((p) => ({
              rowIndex: p.row_index,
              label: p.label,
              probability: p.probability_positive,
              values: p.input_echo,
            }))}
          />
        </>
      ) : null}
    </div>
  );
}

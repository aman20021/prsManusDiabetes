import { FormEvent, useState } from "react";
import { getToken } from "../api";
import ErrorBox from "../components/ErrorBox";

export default function BatchPage() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

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
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/v1/predict/batch", {
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
      <form className="card" onSubmit={onSubmit}>
        <input name="file" type="file" accept=".csv" required />
        <button type="submit" disabled={busy}>
          {busy ? "Processing…" : "Run batch"}
        </button>
      </form>
      {error ? <ErrorBox error={error} /> : null}
      {result ? (
        <div className="card">
          <p>Upload ID: {String(result.upload_id)}</p>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      ) : null}
    </div>
  );
}

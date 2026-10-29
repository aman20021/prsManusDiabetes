import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";

export default function UploadDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!id) return;
    api<Record<string, unknown>>(`/api/v1/uploads/${id}`)
      .then(setData)
      .catch(setError);
  }, [id]);

  return (
    <div>
      <h1>Upload #{id}</h1>
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <div className="card">
          <pre>{JSON.stringify(data, null, 2)}</pre>
        </div>
      ) : (
        <p className="muted">Loading…</p>
      )}
    </div>
  );
}

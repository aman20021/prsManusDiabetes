import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";
import ResultSheet from "../components/ResultSheet";

type Prediction = {
  row_index: number | null;
  label: number | null;
  probability_positive: number | null;
  input_echo: Record<string, number> | null;
  model_version: string | null;
};

type UploadDetail = {
  id: number;
  filename: string | null;
  upload_type: string;
  created_at: string | null;
  predictions: Prediction[];
};

export default function UploadDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<UploadDetail | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!id) return;
    setData(null);
    setError(null);
    api<UploadDetail>(`/api/v1/uploads/${id}`)
      .then(setData)
      .catch(setError);
  }, [id]);

  const rows =
    data?.predictions
      .filter((p) => p.input_echo && p.label != null)
      .map((p) => ({
        rowIndex: p.row_index ?? 0,
        label: p.label as number,
        probability: p.probability_positive ?? 0,
        values: p.input_echo ?? {},
      })) ?? [];

  const title =
    data?.filename ??
    (data?.upload_type === "single" ? "Single screening" : data ? `Upload ${data.id}` : "");

  return (
    <div>
      <p className="sheet-back">
        <Link to="/uploads">Uploads</Link>
      </p>
      {error ? <ErrorBox error={error} /> : null}
      {!data && !error ? <p className="muted">Loading…</p> : null}
      {data ? (
        <ResultSheet
          title={title}
          when={data.created_at}
          kind={data.upload_type}
          modelVersion={data.predictions.find((p) => p.model_version)?.model_version ?? null}
          rows={rows}
        />
      ) : null}
    </div>
  );
}

import { ApiError } from "../api";

export default function ErrorBox({ error }: { error: unknown }) {
  const api = (error as { api?: ApiError })?.api;
  const message = api?.message || (error as Error)?.message || "Request failed";
  return (
    <div className="error">
      <strong>{message}</strong>
      {api?.details?.length ? (
        <ul>
          {api.details.map((d, i) => (
            <li key={i}>
              {d.row_index != null ? `Row ${d.row_index}: ` : ""}
              {d.field ? `${d.field}: ` : ""}
              {d.message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

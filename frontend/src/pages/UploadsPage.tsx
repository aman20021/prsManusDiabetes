import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";

type Upload = {
  id: number;
  filename: string | null;
  upload_type: string;
  row_count: number;
  status: string;
  created_at: string;
};

export default function UploadsPage() {
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<{ uploads: Upload[] }>("/api/v1/uploads")
      .then((r) => setUploads(r.uploads))
      .catch(setError);
  }, []);

  return (
    <div>
      <h1>Your uploads</h1>
      {error ? <ErrorBox error={error} /> : null}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>File</th>
              <th>Rows</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {uploads.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link to={`/uploads/${u.id}`}>{u.id}</Link>
                </td>
                <td>{u.upload_type}</td>
                <td>
                  {u.filename ? (
                    <Link to={`/uploads/${u.id}`}>{u.filename}</Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{u.row_count}</td>
                <td>{u.created_at?.slice(0, 19)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

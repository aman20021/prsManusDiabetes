import { useEffect, useState } from "react";
import { api } from "../api";

export type ModelOption = {
  version: string;
  status: string;
  framework: string;
};

export function modelQuery(version: string): string {
  if (!version) return "";
  return `?model_version=${encodeURIComponent(version)}`;
}

export default function ModelSelect({
  version,
  onChange,
}: {
  version: string;
  onChange: (version: string) => void;
}) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ models: ModelOption[] }>("/api/v1/models")
      .then((r) => {
        const list = r.models;
        setModels(list);
        const production = list.find((m) => m.status === "production");
        onChange(production?.version ?? list[0]?.version ?? "");
      })
      .catch((err: Error) => setError(err.message || "Could not load models"));
  }, [onChange]);

  const selected = models.find((m) => m.version === version);

  return (
    <div className="model-select">
      <label>
        Model
        <select
          value={version}
          onChange={(e) => onChange(e.target.value)}
          disabled={models.length === 0}
        >
          {models.length === 0 ? <option value="">Loading models…</option> : null}
          {models.map((m) => (
            <option key={m.version} value={m.version}>
              {m.version} ({m.status})
            </option>
          ))}
        </select>
      </label>
      {selected ? (
        <p className="model-select-note">
          Scores will use {selected.version}, the {selected.status} {selected.framework} model.
        </p>
      ) : null}
      {error ? <p className="model-select-note">{error}</p> : null}
    </div>
  );
}

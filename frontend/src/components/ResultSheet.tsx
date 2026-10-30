import { FEATURES } from "../api";

export type SheetRow = {
  rowIndex: number;
  label: number;
  probability: number;
  values: Record<string, number | string | null | undefined>;
};

type Props = {
  title: string;
  when?: string | null;
  kind?: string | null;
  modelVersion?: string | null;
  rows: SheetRow[];
};

function screeningCall(label: number): string {
  return label === 1 ? "Diabetes or prediabetes" : "No diabetes";
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16);
  const formatted = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "UTC",
  }).format(d);
  return `${formatted} UTC`;
}

function contextSentence(
  kind: string | null | undefined,
  when: string | null | undefined,
  modelVersion: string | null | undefined,
): string | null {
  let sentence = "";
  if (kind === "batch") sentence = "Batch file";
  else if (kind === "single") sentence = "Single screening";
  if (when) {
    const stamp = formatWhen(when);
    sentence = sentence ? `${sentence} from ${stamp}` : stamp;
  }
  if (modelVersion) {
    sentence = sentence
      ? `${sentence}, using model ${modelVersion}`
      : `Model ${modelVersion}`;
  }
  return sentence ? `${sentence}.` : null;
}

function columnsFor(rows: SheetRow[]): string[] {
  const seen = new Set<string>(FEATURES);
  const extra: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row.values)) {
      if (!seen.has(key)) {
        seen.add(key);
        extra.push(key);
      }
    }
  }
  return [...FEATURES, ...extra];
}

export default function ResultSheet({
  title,
  when,
  kind,
  modelVersion,
  rows,
}: Props) {
  const flagged = rows.filter((r) => r.label === 1).length;
  const noun = rows.length === 1 ? "row" : "rows";
  const recorded = contextSentence(kind, when, modelVersion);

  const columns = columnsFor(rows);

  return (
    <article className="result-sheet">
      <h1>{title}</h1>
      {rows.length > 0 ? (
        <p className="sheet-lede">
          {flagged} of {rows.length} {noun} screened as diabetes or prediabetes.
        </p>
      ) : (
        <p className="sheet-lede">No saved rows for this upload.</p>
      )}
      {recorded ? <p className="sheet-meta">{recorded}</p> : null}
      <p className="sheet-note">Assistive screening only. This is not a diagnosis.</p>

      {rows.length === 0 ? (
        <p className="sheet-empty">
          The original file rows were not stored with this upload, so the table
          cannot be rebuilt. Run the CSV again from Batch to keep the rows and
          results together.
        </p>
      ) : (
        <div className="sheet-scroll" tabIndex={0}>
          <table className="sheet-table" aria-label="Uploaded rows and screening results">
            <thead>
              <tr>
                <th className="sticky-row" scope="col">
                  Row
                </th>
                <th className="sticky-result" scope="col">
                  Result
                </th>
                {columns.map((col) => (
                  <th key={col} scope="col">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const positive = row.label === 1;
                const pct = Math.round(row.probability * 1000) / 10;
                return (
                  <tr key={row.rowIndex} className={positive ? "positive" : "negative"}>
                    <td className="sticky-row">{row.rowIndex + 1}</td>
                    <td className="sticky-result">
                      <div className="call">
                        <span className={positive ? "call-name pos" : "call-name neg"}>
                          {screeningCall(row.label)}
                        </span>
                        <span className="call-pct">{pct.toFixed(1)}% positive</span>
                        <span className="meter" aria-hidden="true">
                          <span style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
                        </span>
                      </div>
                    </td>
                    {columns.map((col) => (
                      <td key={col}>{row.values[col] ?? ""}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

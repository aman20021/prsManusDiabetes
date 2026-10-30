export type ScreeningPoint = {
  id: string;
  at: string;
  label: number;
  probability: number;
};

const POS = "#8e2f2f";
const NEG = "#1b5e45";
const INK = "#3d5166";
const GRID = "#e4ebf0";
const AXIS = "#8aa0b2";

function callName(label: number): string {
  return label === 1 ? "Diabetes or prediabetes" : "No diabetes";
}

function formatTick(iso: string, withDay: boolean): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    ...(withDay ? { day: "numeric", month: "short" } : {}),
  }).format(d);
}

export function ProbabilityChart({ points }: { points: ScreeningPoint[] }) {
  const w = 680;
  const h = 240;
  const pad = { l: 40, r: 16, t: 16, b: 42 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const n = points.length;
  const gap = n > 12 ? 4 : 10;
  const barW = n === 0 ? 0 : Math.min(42, (innerW - gap * (n - 1)) / n);
  const groupW = n === 0 ? 0 : n * barW + (n - 1) * gap;
  const start = pad.l + (innerW - groupW) / 2;
  const y = (p: number) => pad.t + innerH - p * innerH;
  const days = new Set(points.map((p) => p.at.slice(0, 10)));
  const withDay = days.size > 1;
  const desc = points
    .map(
      (p) =>
        `${formatTick(p.at, withDay)} ${callName(p.label)} ${(p.probability * 100).toFixed(1)}%`,
    )
    .join(", ");

  return (
    <svg
      className="dash-chart"
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="Chance of diabetes or prediabetes for each recent screening"
    >
      <title>Chance of diabetes or prediabetes</title>
      <desc>{desc || "No screenings to plot."}</desc>
      {[0, 0.5, 1].map((tick) => (
        <g key={tick}>
          <line
            x1={pad.l}
            x2={w - pad.r}
            y1={y(tick)}
            y2={y(tick)}
            stroke={tick === 0.5 ? POS : GRID}
            strokeDasharray={tick === 0.5 ? "4 4" : undefined}
          />
          <text x={pad.l - 8} y={y(tick) + 4} textAnchor="end" fill={INK} fontSize="11">
            {Math.round(tick * 100)}
          </text>
        </g>
      ))}
      {points.map((p, i) => {
        const barH = Math.max(2, p.probability * innerH);
        const x = start + i * (barW + gap);
        const positive = p.label === 1;
        return (
          <g key={p.id}>
            <rect
              x={x}
              y={y(p.probability)}
              width={barW}
              height={barH}
              fill={positive ? POS : NEG}
            >
              <title>
                {formatTick(p.at, withDay)}: {callName(p.label)},{" "}
                {(p.probability * 100).toFixed(1)}% positive
              </title>
            </rect>
            <text
              x={x + barW / 2}
              y={h - 16}
              textAnchor="middle"
              fill={INK}
              fontSize="11"
            >
              {formatTick(p.at, false)}
            </text>
          </g>
        );
      })}
      <line x1={pad.l} x2={pad.l} y1={pad.t} y2={pad.t + innerH} stroke={AXIS} />
    </svg>
  );
}

export function OutcomeChart({
  positive,
  negative,
}: {
  positive: number;
  negative: number;
}) {
  const rows = [
    { name: "Diabetes or prediabetes", count: positive, color: POS },
    { name: "No diabetes", count: negative, color: NEG },
  ];
  const max = Math.max(positive, negative, 1);
  const w = 420;
  const h = 150;
  const barMax = w - 36;
  const desc = rows.map((r) => `${r.name} ${r.count}`).join(", ");

  return (
    <svg
      className="dash-chart"
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="How many screenings were called diabetes or prediabetes, and how many were not"
    >
      <title>Screening calls</title>
      <desc>{desc}</desc>
      {rows.map((row, i) => {
        const y = i * 74;
        const width = (row.count / max) * barMax;
        const drawn = Math.max(width, row.count > 0 ? 6 : 0);
        return (
          <g key={row.name}>
            <text x="0" y={y + 16} fill={INK} fontSize="13">
              {row.name}
            </text>
            <rect x="0" y={y + 26} width={drawn} height="20" fill={row.color}>
              <title>
                {row.name}: {row.count}
              </title>
            </rect>
            <text x={drawn + 8} y={y + 41} fill={INK} fontSize="13">
              {row.count}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const BIN_LABELS = ["0–20", "20–40", "40–60", "60–80", "80–100"];

export function Histogram({ values }: { values: number[] }) {
  const counts = [0, 0, 0, 0, 0];
  for (const value of values) {
    const index = value >= 1 ? 4 : Math.max(0, Math.min(4, Math.floor(value / 0.2)));
    counts[index] += 1;
  }
  const max = Math.max(...counts, 1);
  const w = 420;
  const h = 180;
  const pad = { l: 28, r: 8, t: 12, b: 32 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const gap = 10;
  const barW = (innerW - gap * 4) / 5;
  const desc = BIN_LABELS.map((label, i) => `${label}% ${counts[i]}`).join(", ");

  return (
    <svg
      className="dash-chart"
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="How screening chances cluster, in bands of 20 percentage points"
    >
      <title>Distribution of positive chance</title>
      <desc>{desc}</desc>
      {counts.map((count, i) => {
        const barH = (count / max) * innerH;
        const x = pad.l + i * (barW + gap);
        const y = pad.t + innerH - barH;
        return (
          <g key={BIN_LABELS[i]}>
            <rect x={x} y={y} width={barW} height={Math.max(barH, count > 0 ? 3 : 0)} fill="#1f4e6e">
              <title>
                {BIN_LABELS[i]}%: {count}
              </title>
            </rect>
            {count > 0 ? (
              <text x={x + barW / 2} y={y - 4} textAnchor="middle" fill={INK} fontSize="11">
                {count}
              </text>
            ) : null}
            <text x={x + barW / 2} y={h - 10} textAnchor="middle" fill={INK} fontSize="11">
              {BIN_LABELS[i]}
            </text>
          </g>
        );
      })}
      <line
        x1={pad.l}
        x2={w - pad.r}
        y1={pad.t + innerH}
        y2={pad.t + innerH}
        stroke={AXIS}
      />
    </svg>
  );
}

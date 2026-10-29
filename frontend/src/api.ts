export type ApiError = {
  code: string;
  message: string;
  details?: Array<{ field?: string; message: string; row_index?: number }>;
};

const tokenKey = "manas_token";

export function getToken(): string | null {
  return localStorage.getItem(tokenKey);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(tokenKey, token);
  else localStorage.removeItem(tokenKey);
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = data as ApiError;
    throw Object.assign(new Error(err.message || res.statusText), {
      status: res.status,
      api: err,
    });
  }
  return data as T;
}

export const FEATURES = [
  "HighBP",
  "HighChol",
  "CholCheck",
  "BMI",
  "Smoker",
  "Stroke",
  "HeartDiseaseorAttack",
  "PhysActivity",
  "Fruits",
  "Veggies",
  "HvyAlcoholConsump",
  "AnyHealthcare",
  "NoDocbcCost",
  "GenHlth",
  "MentHlth",
  "PhysHlth",
  "DiffWalk",
  "Sex",
  "Age",
  "Education",
  "Income",
] as const;

export function defaultSample(): Record<string, number> {
  return {
    HighBP: 1,
    HighChol: 1,
    CholCheck: 1,
    BMI: 30,
    Smoker: 0,
    Stroke: 0,
    HeartDiseaseorAttack: 0,
    PhysActivity: 1,
    Fruits: 1,
    Veggies: 1,
    HvyAlcoholConsump: 0,
    AnyHealthcare: 1,
    NoDocbcCost: 0,
    GenHlth: 3,
    MentHlth: 0,
    PhysHlth: 0,
    DiffWalk: 0,
    Sex: 0,
    Age: 5,
    Education: 4,
    Income: 5,
  };
}

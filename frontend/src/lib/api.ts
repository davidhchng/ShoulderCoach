const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface FieldSchema {
  key: string;
  label: string;
  type: "button_group" | "toggle" | "slider";
  options?: string[];
  default: string | boolean | number;
}

export interface InputSchema {
  fields: FieldSchema[];
}

export interface DecisionMeta {
  decision_type: string;
  display_name: string;
  description: string;
  input_schema: InputSchema;
}

export interface DecisionResponse {
  decision_type: string;
  recommended_action: string;
  confidence: "high" | "moderate" | "low" | "insufficient";
  primary_stat: number;
  primary_stat_label: string;
  primary_sample_size: number;
  comparison_stat: number | null;
  comparison_stat_label: string | null;
  comparison_sample_size: number | null;
  edge_pct: number | null;
  details: Record<string, unknown>;
  low_sample_warning: boolean;
  insufficient_data: boolean;
  narrative: string;
  narrative_available: boolean;
}

export async function fetchDecisions(): Promise<DecisionMeta[]> {
  const res = await fetch(`${API_BASE}/api/decisions`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch decisions");
  const data = await res.json();
  return data.decisions;
}

export async function parseDecisionInputs(
  type: string,
  description: string
): Promise<{ inputs: Record<string, unknown>; confidence: string }> {
  const res = await fetch(`${API_BASE}/api/decisions/${type}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Parse failed");
  }
  return res.json();
}

export interface AskResponse {
  answer: string;
  available: boolean;
  engine_used: string | null;
  decision_result: DecisionResponse | null;
}

export async function askCoach(
  question: string,
  opts?: { teamName?: string; opponentName?: string; gameContext?: string }
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/api/coach/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      team_name: opts?.teamName || null,
      opponent_name: opts?.opponentName || null,
      game_context: opts?.gameContext || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export interface FormMetric {
  name: string;
  key: string;
  value: number | null;
  unit: string;
  ideal_range: string;
  in_range: boolean | null;
  note: string;
}

export interface FormCheckResponse {
  metrics: FormMetric[];
  passing: number;
  total: number;
  frames_analyzed: number;
  phase_detected: boolean;
  narrative: string;
  video_id: string | null;
}

export async function analyzeShootingForm(file: File): Promise<FormCheckResponse> {
  const form = new FormData();
  form.append("video", file);
  const res = await fetch(`${API_BASE}/api/form-check`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Analysis failed");
  }
  return res.json();
}

export async function postDecision(
  type: string,
  inputs: Record<string, unknown>
): Promise<DecisionResponse> {
  const res = await fetch(`${API_BASE}/api/decisions/${type}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

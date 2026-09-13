export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface Dashboard {
  projects: number | null;
  candidates: number | null;
  auto_score: number | null;
  avg_duration: number | null;
  fallback_rate: number | null;
  adoption_rate: number | null;
  estimated_cost_usd: number;
  estimated_cost_month_usd: number;
  image_success_rate: number | null;
  budget?: { monthly_limit_usd: number; monthly_remaining_usd: number | null };
}

export interface ProjectSummary {
  id: number;
  name: string;
  status: string;
  candidate_count: number;
  best_score: number | null;
  updated_at: string;
}

export interface CandidateResult {
  positive_prompt: string;
  negative_prompt: string;
  analysis: string;
  generation_mode: string;
  rag_citations: Array<{ index: number; source: string; excerpt: string; distance: number | null }>;
  quality: {
    overall: number;
    requirement_coverage: number;
    intent_alignment: number;
    deliverable_completeness: number;
    prompt_quality: number;
    notes: string[];
  };
  visual_quality?: {
    status: string;
    overall: number | null;
    requirement_match?: number;
    spatial_coherence?: number;
    material_fidelity?: number;
    lighting_quality?: number;
    issues?: string[];
    reason?: string;
  };
  decision_score?: number;
  locked_fields?: string[];
  costs?: { image_estimated_usd: number; is_estimate: boolean };
  image: { image_path?: string; success?: boolean; provider?: string; error?: string } | null;
  timings: { total?: number };
  observability?: { active: boolean; warning?: string };
  llm_backend?: string;
}

export interface GenerationJob {
  id: string;
  kind?: "generation" | "iteration";
  status: "queued" | "running" | "cancel_requested" | "canceled" | "completed" | "failed";
  progress: number;
  project_id: number | null;
  error: string;
  attempts?: number;
  max_attempts?: number;
  estimated_cost_usd?: number;
}

export interface ProjectDetail extends ProjectSummary {
  requirement: string;
  structured_requirement: {
    style_name?: string;
    room?: string;
    area_sqm?: number | null;
    completeness?: number;
    locked_fields?: string[];
  };
  candidates: Array<{
    id: number;
    version: number;
    variant: string;
    auto_score: number | null;
    image_path: string | null;
    parent_candidate_id?: number | null;
    iteration_instruction?: string;
    selected?: number;
    result: CandidateResult;
  }>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "服务请求失败" }));
    throw new Error(payload.detail ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{
    status: string;
    llm_backend: string;
    llm_model: string;
    image_estimated_cost_usd: number;
    task_queue: { backend: string; connected: boolean; warning: string };
    budgets: { per_job_usd: number; monthly_usd: number };
    observability: { active: boolean; warning?: string };
  }>("/api/v1/health"),
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),
  projects: () => request<ProjectSummary[]>("/api/v1/projects"),
  project: (id: number) => request<ProjectDetail>(`/api/v1/projects/${id}`),
  generate: (payload: Record<string, unknown>) => request<ProjectDetail>("/api/v1/projects/generate", { method: "POST", body: JSON.stringify(payload) }),
  startJob: (payload: Record<string, unknown>, idempotencyKey: string) => request<GenerationJob>("/api/v1/generation-jobs", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(payload) }),
  job: (id: string) => request<GenerationJob>(`/api/v1/generation-jobs/${id}`),
  cancelJob: (id: string) => request<GenerationJob>(`/api/v1/generation-jobs/${id}/cancel`, { method: "POST" }),
  iterate: (candidateId: number, payload: Record<string, unknown>, idempotencyKey: string) => request<GenerationJob>(`/api/v1/candidates/${candidateId}/iterations`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(payload) }),
  reportUrl: (projectId: number) => `${API_BASE}/api/v1/projects/${projectId}/report`,
  feedback: (payload: Record<string, unknown>) => request<{ id: number; status: string }>("/api/v1/feedback", { method: "POST", body: JSON.stringify(payload) }),
};

export type Material = 'fabric' | 'pmma';
export type Outcome = 'burned' | 'went_out' | 'cool_flame' | 'flame' | 'measured';

export interface Preset { key: string; label: string; g: number; o2: number; psi: number; u: number; env: string; note: string | null }

export interface Investigation {
  slug: string; name: string; full_name: string | null; purposes: string[]; fuels: string[]; envs: string[];
  hardware: string | null; summary: string | null; psi_url: string | null; members: { id: string; name: string }[]; origin: string;
}

export interface Credibility {
  score: number | null; label: 'High' | 'Medium' | 'Low' | 'Unverified'; level: number;
  factors: { publisher: number; review: number; trace: number } | null; explanation: string;
}

export interface Resource {
  id: string; type: string; title: string; publisher: string | null; year: number | null; format: string | null;
  url: string | null; description: string | null; status: string; investigation: string | null; investigations: string[];
  investigation_detail: string | null; origin: string; doi: string | null; psi_id: string | null; dataset: string | null;
  envs: string[]; points_count: number; sim_point: string | null; credibility: Credibility; placeholder: boolean;
  fit?: number; near?: number | null;
}

export interface TestPoint {
  code: string; investigation: string | null; investigation_detail: string | null; source_resource_id: string | null;
  material: string; sample_desc: string | null; geometry: string | null; gravity_g: number | null; o2_pct: number | null;
  pressure_kpa: number | null; flow_cm_s: number | null; flow_direction: string | null; diluent: string | null;
  outcome: Outcome; outcome_text: string; spread_mm_s: number | null; notes: string | null;
  source_file: string | null; source_page: string | null; source_quote: string | null;
  extraction: string; verified: boolean; verified_by: string | null; unverified_reason: string | null;
  origin: string; dataset: string | null; extra: Record<string, unknown>; simulatable: boolean; placeholder: boolean;
}

export interface ResourceDetail extends Resource {
  test_points: TestPoint[]; points_total: number; investigation_names: string[]; credibility_formula: string;
}

export interface ResourceList {
  items: Resource[]; total: number; page: number; page_size: number;
  facets: { types: Record<string, number> }; counts: { high: number; unverified: number }; preset: string | null;
}

export interface ModelParams { xmin: number; ustar: number; kl: number; kh: number; c: number; pexp: number }
export interface ModelParamsResponse {
  params: Record<Material, ModelParams>;
  meta: Record<Material, { n_points: number; rmse: number | null; fitted_at: string | null; source: string }>;
}

export interface Filters {
  q: string; types: string[]; inv: string[]; purpose: string[]; fuel: string[]; env: string[];
  credMin: 'any' | 'verified' | 'medium' | 'high'; sort: string;
}

export interface Summary { text: string; citations: string[]; source: 'template' | 'ai'; model?: string | null; note?: string }

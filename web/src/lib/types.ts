// Mirrors api/openapi.yaml (contract v0.3). Field names are the contract's;
// do not add a field here that the API does not return.

export type Region = "nord-ovest" | "nord-est" | "centro" | "sud" | "isole";
export type Band = "low" | "medium" | "high" | "critical";
export type Source = "inbound" | "outbound" | "referral" | "partner" | "event";
export type LeadStatus =
  | "new"
  | "contacted"
  | "qualified"
  | "proposal"
  | "won"
  | "lost";
export type ActionKind =
  | "call"
  | "exec_sponsor_meeting"
  | "discovery_meeting"
  | "discount_review";

export interface Driver {
  feature: string;
  label: string;
  contribution: number;
  value: string;
  direction: "increases" | "decreases";
}

export interface Lead {
  id: string;
  status: LeadStatus;
  source: Source;
  created_at: string;
  closed_at: string | null;
  amount_arr: number | null;
  discount_pct: number;
  lost_reason: string | null;
}

export interface PipelineItem {
  lead_id: string;
  company_name: string;
  region: Region;
  source: Source;
  status: string;
  amount_arr: number;
  probability: number;
  band: Band;
  expected_value: number;
  days_open: number;
  // Contract v0.3 addition: largest achievable probability delta across the
  // supported counterfactual levers. Nullable for closed leads; optional
  // because the field was added to PipelineItem without being made required.
  max_leverage?: number | null;
  top_driver: Driver;
}

export interface PipelineResponse {
  total: number;
  total_expected_value: number;
  items: PipelineItem[];
}

export interface CompanySummary {
  id: string;
  name: string;
  region: Region;
  industry: string;
  employees: number;
  lifetime_won_arr: number;
  dormant: boolean;
}

export interface Score {
  probability: number;
  band: Band;
  model_version: string;
  scored_at: string;
  expected_value: number;
}

export interface Action {
  id: string;
  kind: string;
  status: "open" | "done" | "cancelled";
  created_at: string;
  created_by: string;
  note?: string;
}

export interface LeadDetail {
  lead: Lead;
  company: CompanySummary;
  score: Score;
  drivers: Driver[];
  prior_initiatives: Lead[];
  open_actions: Action[];
  // Contract v0.3: null for closed leads, optional in the schema.
  max_leverage?: number | null;
}

export interface CounterfactualRequest {
  exec_sponsor_meeting?: boolean;
  discovery_meeting?: boolean;
  discount_pct?: number;
}

export interface CounterfactualResponse {
  current_probability: number;
  hypothetical_probability: number;
  delta: number;
  explanation: string;
}

export interface ActionRequest {
  kind: ActionKind;
  note?: string;
}

export interface ActionResponse {
  action: Action;
  probability_after: number;
  delta: number;
}

export interface RegionPortfolio {
  region: Region;
  open_leads: number;
  win_rate: number;
  expected_value: number;
}

export interface CalibrationPoint {
  predicted: number;
  actual: number;
}

export interface Portfolio {
  total_expected_value: number;
  by_region: RegionPortfolio[];
  calibration: CalibrationPoint[];
  drift: {
    psi: number;
    status: "stable" | "watch" | "alert";
    // Optional: omitted when the labelled population cannot be split into
    // train and holdout. The UI must show "not measurable", never a fallback.
    train_mean?: number;
    holdout_mean?: number;
    train_win_rate?: number;
    holdout_win_rate?: number;
  };
}

export interface Health {
  status: "ok" | "degraded";
  model_version: string;
  scored_at: string;
}

export interface ApiError {
  error: string;
  detail: string;
}
